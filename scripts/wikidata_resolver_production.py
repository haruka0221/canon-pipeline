#!/usr/bin/env python3
"""Production-oriented Wikidata literary-work resolver."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd
import requests

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "derived/benchmark/full_eval_130items_worklevel_v2.tsv"
DEFAULT_OUTDIR = ROOT / "derived/benchmark/wikidata_production_v1"
DEFAULT_PROMPT = ROOT / "prompts/wikidata_judge_v1.txt"
WD_API = "https://www.wikidata.org/w/api.php"
WDQS = "https://query.wikidata.org/sparql"
USER_AGENT = "canon-pipeline-wikidata-production/1.0"
SOURCE_ORDER = {"author_exact": 0, "author_fuzzy": 1, "title_search": 2}
ALLOWED_DECISIONS = {"MATCH", "NO_MATCH", "AMBIGUOUS"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_ISSUES = {
    "duplicate_work_items", "edition_or_translation", "edition_without_work_item",
    "adaptation", "author_ambiguity", "missing_metadata", "title_variant", "wrong_work",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def load_json(path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def append_jsonl(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)


def normalize_author(raw):
    if raw is None or pd.isna(raw):
        return ""
    s = str(raw).strip()
    if "," in s:
        last, first = s.split(",", 1)
        last, first = last.strip(), first.strip()
        if first.lower().endswith(last.lower()):
            return first
        return f"{first} {last}"
    return s


def normalize_title(raw):
    s = str(raw or "").strip()
    s = re.sub(r"^textplus\s*[-:]\s*", "", s, flags=re.I)
    s = unicodedata.normalize("NFKD", s).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def title_similarity(a, b):
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def compound_title_suspected(title):
    parts = [x.strip() for x in str(title).split(";") if x.strip()]
    return len(parts) >= 2


def title_search_variants(title):
    values = [str(title).strip()]
    cleaned = re.sub(r"^textplus\s*[-:]\s*", "", str(title), flags=re.I).strip()
    if cleaned and cleaned not in values:
        values.append(cleaned)
    # Do not split semicolon-separated compound records into one component.
    if ";" not in cleaned and ":" in cleaned:
        short = cleaned.split(":", 1)[0].strip()
        if short and short not in values:
            values.append(short)
    return list(dict.fromkeys(x for x in values if x))


def load_targets(path):
    if path.suffix.lower() in {".tsv", ".txt"}:
        df = pd.read_csv(path, sep="\t", dtype=str).fillna("")
    else:
        df = pd.read_csv(path, dtype=str).fillna("")
    id_col = next((c for c in ["target_id", "wk", "work_id", "id"] if c in df.columns), None)
    if id_col is None:
        raise ValueError("Need target_id/wk/work_id/id column")
    for c in ["title", "author"]:
        if c not in df.columns:
            raise ValueError(f"Missing required column: {c}")
    year_col = next((c for c in ["year", "first_publication_year", "publication_year"] if c in df.columns), None)
    rows, seen = [], set()
    for _, r in df.iterrows():
        tid = str(r[id_col]).strip()
        if not tid:
            continue
        if tid in seen:
            raise ValueError(f"Duplicate target_id: {tid}")
        seen.add(tid)
        rows.append({
            "target_id": tid,
            "title": str(r["title"]).strip(),
            "author": str(r["author"]).strip(),
            "year": str(r[year_col]).strip() if year_col else "",
        })
    return rows


class Resolver:
    def __init__(self, outdir, model, prompt, fuzzy_limit=20, title_search_limit=10,
                 wdqs_sleep=1.0, api_sleep=0.5):
        self.outdir = outdir
        self.outdir.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.prompt = prompt
        self.fuzzy_limit = fuzzy_limit
        self.title_search_limit = title_search_limit
        self.wdqs_sleep = wdqs_sleep
        self.api_sleep = api_sleep
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.author_resolution_cache_path = outdir / "author_resolution_cache.json"
        self.author_items_cache_path = outdir / "author_items_cache.json"
        self.search_cache_path = outdir / "search_cache.json"
        self.entity_cache_path = outdir / "entity_cache.json"
        self.author_resolution_cache = load_json(self.author_resolution_cache_path, {})
        self.author_items_cache = load_json(self.author_items_cache_path, {})
        self.search_cache = load_json(self.search_cache_path, {})
        self.entity_cache = load_json(self.entity_cache_path, {})
        self._client = None

    def client(self):
        if self._client is not None:
            return self._client
        if OpenAI is None:
            raise RuntimeError("openai package missing: pip install -U openai")
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set")
        self._client = OpenAI()
        return self._client

    def call_model(self, instructions, user_input, max_output_tokens=900):
        last = None
        for attempt in range(6):
            try:
                r = self.client().responses.create(
                    model=self.model,
                    instructions=instructions,
                    input=user_input,
                    max_output_tokens=max_output_tokens,
                )
                text = (r.output_text or "").strip()
                if not text:
                    raise RuntimeError("Empty model response")
                return text
            except Exception as e:
                last = e
                if attempt == 5:
                    raise
                wait = min(60, 5 * (2 ** attempt))
                print(f"      model retry {attempt+1}/6: {type(e).__name__}: {e}; waiting {wait}s")
                time.sleep(wait)
        raise RuntimeError(last)

    def wd_api(self, params, attempts=8):
        params = dict(params)
        params.setdefault("format", "json")
        params.setdefault("maxlag", 5)
        last = None
        for attempt in range(attempts):
            try:
                r = self.session.get(WD_API, params=params, timeout=60)
                if r.status_code in (429, 502, 503, 504):
                    wait = min(120, 10 * (attempt + 1))
                    print(f"      Wikidata HTTP {r.status_code}; waiting {wait}s")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                data = r.json()
                if "error" in data:
                    wait = min(120, 10 * (attempt + 1))
                    print(f"      Wikidata API error {data['error'].get('code')}; waiting {wait}s")
                    time.sleep(wait)
                    continue
                if self.api_sleep:
                    time.sleep(self.api_sleep)
                return data
            except Exception as e:
                last = e
                if attempt == attempts - 1:
                    raise
                wait = min(120, 5 * (attempt + 1))
                print(f"      Wikidata retry {attempt+1}/{attempts}: {type(e).__name__}: {e}; waiting {wait}s")
                time.sleep(wait)
        raise RuntimeError(last)

    def search_entities(self, query, limit=10):
        key = f"wbsearchentities|en|{limit}|{query}"
        if key in self.search_cache:
            return self.search_cache[key]
        data = self.wd_api({
            "action": "wbsearchentities", "search": query, "language": "en",
            "uselang": "en", "type": "item", "limit": limit,
        })
        hits = data.get("search", [])
        self.search_cache[key] = hits
        atomic_write_json(self.search_cache_path, self.search_cache)
        return hits

    @staticmethod
    def writer_like(desc):
        d = str(desc or "").lower()
        return any(w in d for w in ["writer", "novelist", "author", "poet", "playwright", "journalist"])

    def choose_author(self, author, title, hits):
        candidates = [f'{h.get("id","")} | {h.get("label","")} | {h.get("description","")}' for h in hits[:10]]
        instructions = """
You are resolving the identity of a literary author in Wikidata.
Choose the candidate that represents the PERSON who wrote the target work.
Historical married names, pen names, initials, and catalog forms may differ.
Do not choose a work, organization, place, fictional character, or unrelated namesake.
Never invent a QID. Return ONLY one supplied QID, or NO_MATCH.
""".strip()
        user = f"TARGET AUTHOR\n{author}\n\nTARGET WORK TITLE\n{title}\n\nCANDIDATES\n" + "\n".join(candidates)
        try:
            text = self.call_model(instructions, user, 300)
        except Exception as e:
            print(
                f"      author LLM failed: {type(e).__name__}: {e}; "
                "continuing without author match"
            )
            return None

        if text.strip().upper() == "NO_MATCH":
            return None
        allowed = {h.get("id") for h in hits}
        qids = re.findall(r"\bQ\d+\b", text)
        return qids[0] if len(qids) == 1 and qids[0] in allowed else None

    def resolve_author(self, author_raw, title, year=""):
        author = normalize_author(author_raw)
        if not author:
            return None, "EMPTY_AUTHOR"
        name_key = f"name::{author.casefold()}"
        context_key = f"context::{author.casefold()}::{normalize_title(title)}::{year}"
        if name_key in self.author_resolution_cache:
            x = self.author_resolution_cache[name_key]
            return x.get("qid"), x.get("strategy", "CACHE")
        if context_key in self.author_resolution_cache:
            x = self.author_resolution_cache[context_key]
            return x.get("qid"), x.get("strategy", "CACHE")

        hits = self.search_entities(author, 10)
        exact = [h for h in hits if h.get("label", "").casefold() == author.casefold() and self.writer_like(h.get("description", ""))]
        if len(exact) == 1:
            result = {"qid": exact[0]["id"], "strategy": "API_exact", "author": author, "saved_at": utc_now()}
            self.author_resolution_cache[name_key] = result
            atomic_write_json(self.author_resolution_cache_path, self.author_resolution_cache)
            return result["qid"], result["strategy"]

        if hits:
            qid = self.choose_author(author, title, hits)
            if qid:
                result = {"qid": qid, "strategy": "API_search_llm", "author": author,
                          "title_context": title, "saved_at": utc_now()}
                self.author_resolution_cache[context_key] = result
                atomic_write_json(self.author_resolution_cache_path, self.author_resolution_cache)
                return qid, result["strategy"]

        instructions = """
Given a literary author name, propose likely English name variants used as Wikidata labels:
fuller names, catalog variants, married names, birth names, initials, or pen names.
Return ONLY a JSON array of strings.
""".strip()
        try:
            text = self.call_model(
                instructions,
                f"Author: {author}\nKnown work title: {title}",
                500,
            )
        except Exception as e:
            print(
                f"      author alias LLM failed: {type(e).__name__}: {e}; "
                "continuing with title-search fallback"
            )
            text = ""

        try:
            aliases = json.loads(
                text.replace("```json", "")
                    .replace("```", "")
                    .strip()
            )
        except Exception:
            aliases = []
        if isinstance(aliases, list):
            for alias in aliases[:8]:
                hits2 = self.search_entities(str(alias).strip(), 10)
                if hits2:
                    qid = self.choose_author(author, title, hits2)
                    if qid:
                        result = {"qid": qid, "strategy": f"API_alias:{alias}", "author": author,
                                  "title_context": title, "saved_at": utc_now()}
                        self.author_resolution_cache[context_key] = result
                        atomic_write_json(self.author_resolution_cache_path, self.author_resolution_cache)
                        return qid, result["strategy"]
        result = {"qid": None, "strategy": "FAILED", "author": author,
                  "title_context": title, "saved_at": utc_now()}
        self.author_resolution_cache[context_key] = result
        atomic_write_json(self.author_resolution_cache_path, self.author_resolution_cache)
        return None, "FAILED"

    def get_author_items(self, author_qid):
        if author_qid in self.author_items_cache:
            return self.author_items_cache[author_qid]
        query = f"""
SELECT ?item ?label ?statedTitle ?parent WHERE {{
  ?item wdt:P50 wd:{author_qid}.
  OPTIONAL {{ ?item rdfs:label ?label. FILTER(LANG(?label) = "en") }}
  OPTIONAL {{ ?item wdt:P1476 ?statedTitle. FILTER(LANG(?statedTitle) = "en" || LANG(?statedTitle) = "") }}
  OPTIONAL {{ ?item wdt:P629 ?parent. }}
}}
""".strip()
        rows = None
        for attempt in range(7):
            try:
                r = self.session.get(WDQS, params={"query": query, "format": "json"}, timeout=180)
                if r.status_code in (429, 502, 503, 504):
                    wait = min(180, 15 * (attempt + 1))
                    print(f"      WDQS HTTP {r.status_code}; waiting {wait}s")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                rows = r.json()["results"]["bindings"]
                break
            except Exception as e:
                if attempt == 6:
                    raise
                wait = min(180, 10 * (attempt + 1))
                print(f"      WDQS retry {attempt+1}/7: {type(e).__name__}: {e}; waiting {wait}s")
                time.sleep(wait)
        merged = {}
        for x in rows or []:
            qid = x["item"]["value"].split("/")[-1]
            merged.setdefault(qid, {"qid": qid, "texts": [], "parents": []})
            if "label" in x and x["label"]["value"] not in merged[qid]["texts"]:
                merged[qid]["texts"].append(x["label"]["value"])
            if "statedTitle" in x and x["statedTitle"]["value"] not in merged[qid]["texts"]:
                merged[qid]["texts"].append(x["statedTitle"]["value"])
            if "parent" in x:
                p = x["parent"]["value"].split("/")[-1]
                if p not in merged[qid]["parents"]:
                    merged[qid]["parents"].append(p)
        items = list(merged.values())
        self.author_items_cache[author_qid] = items
        atomic_write_json(self.author_items_cache_path, self.author_items_cache)
        if self.wdqs_sleep:
            time.sleep(self.wdqs_sleep)
        return items

    @staticmethod
    def canonical_qid(item):
        return item["parents"][0] if len(item.get("parents", [])) == 1 else item["qid"]

    @staticmethod
    def best_item_score(title, item):
        return max((title_similarity(title, x) for x in item.get("texts", [])), default=0.0)

    @staticmethod
    def item_is_exact(title, item):
        target = normalize_title(title)
        return any(normalize_title(x) == target for x in item.get("texts", []))

    def add_candidate(self, store, qid, source, collapsed_from=None, title_score=None):
        if not qid or not qid.startswith("Q"):
            return
        store.setdefault(qid, {"qid": qid, "sources": [], "collapsed_from": [], "title_score": None})
        x = store[qid]
        if source not in x["sources"]:
            x["sources"].append(source)
            x["sources"].sort(key=lambda s: SOURCE_ORDER.get(s, 999))
        if collapsed_from and collapsed_from != qid and collapsed_from not in x["collapsed_from"]:
            x["collapsed_from"].append(collapsed_from)
        if title_score is not None and (x["title_score"] is None or title_score > x["title_score"]):
            x["title_score"] = round(float(title_score), 6)

    def title_search_qids(self, title):
        out = []
        for variant in title_search_variants(title):
            for h in self.search_entities(variant, self.title_search_limit):
                q = h.get("id")
                if q and q not in out:
                    out.append(q)
        return out

    def build_stage1_packet(self, target):
        tid, title, author_raw, year = target["target_id"], target["title"], target["author"], target.get("year", "")
        author = normalize_author(author_raw)
        author_qid, strategy = self.resolve_author(author_raw, title, year)
        store, exact_qids = {}, []
        author_item_count = 0
        if author_qid:
            items = self.get_author_items(author_qid)
            author_item_count = len(items)
            exact_items = [x for x in items if self.item_is_exact(title, x)]
            for item in exact_items:
                q = self.canonical_qid(item)
                self.add_candidate(store, q, "author_exact",
                                   item["qid"] if q != item["qid"] else None,
                                   self.best_item_score(title, item))
                if q not in exact_qids:
                    exact_qids.append(q)
            ranked = sorted(items, key=lambda x: self.best_item_score(title, x), reverse=True)
            fuzzy_seen = set()
            for item in ranked:
                q = self.canonical_qid(item)
                if q in fuzzy_seen:
                    continue
                fuzzy_seen.add(q)
                self.add_candidate(store, q, "author_fuzzy",
                                   item["qid"] if q != item["qid"] else None,
                                   self.best_item_score(title, item))
                if len(fuzzy_seen) >= self.fuzzy_limit:
                    break
        title_search_added = []
        if not exact_qids:
            for q in self.title_search_qids(title):
                already = q in store
                self.add_candidate(store, q, "title_search")
                if not already:
                    title_search_added.append(q)
        candidates = list(store.values())
        sources = [s for s in ["author_exact", "author_fuzzy", "title_search"]
                   if any(s in c["sources"] for c in candidates)]
        route = "+".join((["author_resolved"] if author_qid else ["author_unresolved"]) + sources)
        return {
            "target_id": tid, "title": title, "author": author_raw, "normalized_author": author,
            "year": year, "author_qid": author_qid, "author_resolution_strategy": strategy,
            "route": route, "compound_title_suspected": compound_title_suspected(title),
            "author_item_count": author_item_count, "exact_count": len(exact_qids),
            "candidate_count": len(candidates), "title_search_added": title_search_added,
            "candidates": candidates, "generated_at": utc_now(),
        }

    def run_stage1(self, targets):
        out = self.outdir / "stage1_candidates.jsonl"
        done = {x["target_id"]: x for x in read_jsonl(out)}
        if done:
            print(f"Stage 1 resume: {len(done)} already saved")
        for i, target in enumerate(targets, 1):
            if target["target_id"] in done:
                print(f"[stage1 {i:>4}/{len(targets)}] SKIP {target['title']}")
                continue
            print(f"[stage1 {i:>4}/{len(targets)}] {target['title']} / {target['author']}")
            p = self.build_stage1_packet(target)
            print(f"      author={p['author_qid']} ({p['author_resolution_strategy']}) | P50={p['author_item_count']} | exact={p['exact_count']} | candidates={p['candidate_count']}")
            append_jsonl(out, p)
            done[target["target_id"]] = p
        print(f"Stage 1 saved: {out}")
        return out

    def fetch_entities(self, qids):
        qids = list(dict.fromkeys(q for q in qids if q and q.startswith("Q")))
        missing = [q for q in qids if q not in self.entity_cache]
        print(f"Entity request: {len(qids)} | missing: {len(missing)}")
        for i in range(0, len(missing), 40):
            batch = missing[i:i+40]
            print(f"      fetching {i+1}-{min(i+40, len(missing))}/{len(missing)}")
            data = self.wd_api({
                "action": "wbgetentities", "ids": "|".join(batch),
                "props": "labels|descriptions|aliases|claims|sitelinks",
                "languages": "en", "languagefallback": 1, "sitefilter": "enwiki",
            })
            self.entity_cache.update(data.get("entities", {}))
            atomic_write_json(self.entity_cache_path, self.entity_cache)

    @staticmethod
    def claim_item_ids(ent, prop):
        out = []
        for claim in ent.get("claims", {}).get(prop, []):
            try:
                v = claim["mainsnak"]["datavalue"]["value"]
                if isinstance(v, dict) and "id" in v:
                    out.append(v["id"])
            except Exception:
                pass
        return list(dict.fromkeys(out))

    @staticmethod
    def claim_dates(ent):
        out = []
        for claim in ent.get("claims", {}).get("P577", []):
            try:
                out.append(claim["mainsnak"]["datavalue"]["value"]["time"].lstrip("+"))
            except Exception:
                pass
        return list(dict.fromkeys(out))

    @staticmethod
    def monolingual_texts(ent, prop):
        out = []
        for claim in ent.get("claims", {}).get(prop, []):
            try:
                v = claim["mainsnak"]["datavalue"]["value"]
                if isinstance(v, dict) and v.get("text"):
                    out.append({"text": v["text"], "language": v.get("language", "")})
            except Exception:
                pass
        return out

    @staticmethod
    def first_lang_value(mapping):
        if "en" in mapping:
            return mapping["en"].get("value", "")
        for x in mapping.values():
            if isinstance(x, dict) and x.get("value"):
                return x["value"]
        return ""

    def label(self, qid):
        return self.first_lang_value(self.entity_cache.get(qid, {}).get("labels", {}))

    def description(self, qid):
        return self.first_lang_value(self.entity_cache.get(qid, {}).get("descriptions", {}))

    def aliases(self, qid):
        a = self.entity_cache.get(qid, {}).get("aliases", {}).get("en", [])
        return [x.get("value", "") for x in a if x.get("value")]

    def run_stage2(self):
        src = self.outdir / "stage1_candidates.jsonl"
        if not src.exists():
            raise FileNotFoundError(src)
        rows = read_jsonl(src)
        candidate_qids = list(dict.fromkeys(c["qid"] for row in rows for c in row.get("candidates", [])))
        print(f"Stage 2 unique candidate QIDs: {len(candidate_qids)}")
        self.fetch_entities(candidate_qids)
        related = set()
        for q in candidate_qids:
            ent = self.entity_cache.get(q, {})
            for prop in ("P31", "P50", "P629"):
                related.update(self.claim_item_ids(ent, prop))
        print(f"Stage 2 related QIDs: {len(related)}")
        self.fetch_entities(sorted(related))
        packets = []
        for row in rows:
            enriched = []
            for pos, c0 in enumerate(row.get("candidates", []), 1):
                q = c0["qid"]
                ent = self.entity_cache.get(q, {})
                p31, p50, p629 = (self.claim_item_ids(ent, p) for p in ("P31", "P50", "P629"))
                enriched.append({
                    "qid": q, "sources": c0.get("sources", []),
                    "collapsed_from": c0.get("collapsed_from", []),
                    "title_score": c0.get("title_score"), "combined_position": pos,
                    "label": self.label(q), "description": self.description(q),
                    "aliases": self.aliases(q), "stated_titles": self.monolingual_texts(ent, "P1476"),
                    "publication_dates": self.claim_dates(ent),
                    "instance_of": [{"qid": x, "label": self.label(x)} for x in p31],
                    "authors": [{"qid": x, "label": self.label(x)} for x in p50],
                    "edition_or_translation_of": [{"qid": x, "label": self.label(x)} for x in p629],
                    "has_enwiki": "enwiki" in ent.get("sitelinks", {}),
                })
            packets.append({
                "target_id": row["target_id"], "title": row["title"], "author": row["author"],
                "year": row.get("year", ""), "author_qid": row.get("author_qid"),
                "author_resolution_strategy": row.get("author_resolution_strategy"),
                "route": row.get("route"), "compound_title_suspected": row.get("compound_title_suspected", False),
                "author_item_count": row.get("author_item_count", 0), "exact_count": row.get("exact_count", 0),
                "candidate_count": len(enriched), "candidates": enriched,
            })
        out = self.outdir / "stage2_packets.jsonl"
        write_jsonl(out, packets)
        print(f"Stage 2 complete: targets={len(packets)} | candidate_qids={len(candidate_qids)} | cache_entities={len(self.entity_cache)}")
        print(f"Stage 2 saved: {out}")
        return out

    @staticmethod
    def compact_candidate(c):
        return {
            "qid": c["qid"], "sources": c.get("sources", []),
            "collapsed_from": c.get("collapsed_from", []), "label": c.get("label", ""),
            "description": c.get("description", ""), "aliases": c.get("aliases", [])[:10],
            "stated_titles": c.get("stated_titles", []), "publication_dates": c.get("publication_dates", []),
            "instance_of": c.get("instance_of", []), "authors": c.get("authors", []),
            "edition_or_translation_of": c.get("edition_or_translation_of", []),
            "has_enwiki": c.get("has_enwiki", False),
        }

    @staticmethod
    def extract_json_object(text):
        cleaned = str(text).replace("```json", "").replace("```", "").strip()
        try:
            obj = json.loads(cleaned)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        a, b = cleaned.find("{"), cleaned.rfind("}")
        if a >= 0 and b > a:
            obj = json.loads(cleaned[a:b+1])
            if isinstance(obj, dict):
                return obj
        raise ValueError("Could not parse one JSON object")

    def validate_judgment(self, obj, candidate_qids):
        decision = str(obj.get("decision", "")).upper().strip()
        if decision not in ALLOWED_DECISIONS:
            raise ValueError(f"invalid decision: {decision}")
        selected = obj.get("selected_qid")
        if selected in ("", "null", "None"):
            selected = None
        alts = obj.get("alternative_qids", []) or []
        if not isinstance(alts, list):
            raise ValueError("alternative_qids must be a list")
        alts = [str(x) for x in alts if str(x).strip()]
        confidence = str(obj.get("confidence", "")).lower().strip()
        if confidence not in ALLOWED_CONFIDENCE:
            raise ValueError(f"invalid confidence: {confidence}")
        issues = obj.get("issue_codes", []) or []
        if not isinstance(issues, list):
            raise ValueError("issue_codes must be a list")
        issues = [str(x).strip() for x in issues if str(x).strip()]
        unknown = [x for x in issues if x not in ALLOWED_ISSUES]
        if unknown:
            raise ValueError(f"unknown issue_codes: {unknown}")
        if decision == "NO_MATCH" and selected is not None:
            raise ValueError("NO_MATCH must have selected_qid=null")
        if decision == "MATCH" and not selected:
            raise ValueError("MATCH requires selected_qid")
        if selected and selected not in candidate_qids:
            raise ValueError(f"selected_qid not supplied: {selected}")
        bad = [q for q in alts if q not in candidate_qids]
        if bad:
            raise ValueError(f"alternative_qids not supplied: {bad}")
        return {
            "decision": decision, "selected_qid": selected, "alternative_qids": alts,
            "confidence": confidence, "issue_codes": issues,
            "reason": str(obj.get("reason", "")).strip(),
        }

    def judge_one(self, packet, system_prompt):
        candidates = [self.compact_candidate(c) for c in packet.get("candidates", [])]
        payload = {
            "target": {
                "target_id": packet["target_id"], "title": packet["title"], "author": packet["author"],
                "year": packet.get("year", ""), "author_qid": packet.get("author_qid"),
                "author_resolution_strategy": packet.get("author_resolution_strategy"),
                "compound_title_suspected": packet.get("compound_title_suspected", False),
            },
            "candidates": candidates,
        }
        user = json.dumps(payload, ensure_ascii=False, indent=2)
        allowed = {c["qid"] for c in candidates}
        text = self.call_model(system_prompt, user, 900)
        try:
            return self.validate_judgment(self.extract_json_object(text), allowed), text
        except Exception as e:
            retry = user + "\n\nReturn exactly one valid JSON object using only supplied candidate QIDs. Validation error: " + str(e)
            text2 = self.call_model(system_prompt, retry, 900)
            return self.validate_judgment(self.extract_json_object(text2), allowed), text2

    def build_results_tsv(self, judgments):
        rows = []
        for x in judgments:
            rows.append({
                "target_id": x["target_id"], "title": x["title"], "author": x["author"],
                "author_qid": x.get("author_qid") or "", "route": x.get("route") or "",
                "candidate_count": x.get("candidate_count", 0), "decision": x["decision"],
                "selected_qid": x.get("selected_qid") or "",
                "alternative_qids": ";".join(x.get("alternative_qids", [])),
                "confidence": x.get("confidence", ""), "issue_codes": ";".join(x.get("issue_codes", [])),
                "reason": x.get("reason", ""), "model": x.get("model", ""),
                "prompt_sha256": x.get("prompt_sha256", ""),
            })
        out = self.outdir / "results.tsv"
        pd.DataFrame(rows).to_csv(out, sep="\t", index=False)
        return out

    def run_judge(self):
        src = self.outdir / "stage2_packets.jsonl"
        if not src.exists():
            raise FileNotFoundError(src)
        if not self.prompt.exists():
            raise FileNotFoundError(self.prompt)
        system_prompt = self.prompt.read_text(encoding="utf-8").strip()
        prompt_sha = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()
        packets = read_jsonl(src)
        out = self.outdir / "judgments.jsonl"
        done = {x["target_id"]: x for x in read_jsonl(out)}
        if done:
            print(f"Judge resume: {len(done)} already saved")
        for i, packet in enumerate(packets, 1):
            tid = packet["target_id"]
            if tid in done:
                print(f"[judge {i:>4}/{len(packets)}] SKIP {packet['title']}")
                continue
            print(f"[judge {i:>4}/{len(packets)}] {packet['title']} / {packet['author']} | candidates={packet['candidate_count']}")
            judgment, raw = self.judge_one(packet, system_prompt)
            row = {
                "target_id": tid, "title": packet["title"], "author": packet["author"],
                "year": packet.get("year", ""), "author_qid": packet.get("author_qid"),
                "route": packet.get("route"), "candidate_count": packet.get("candidate_count", 0),
                **judgment, "model": self.model, "prompt_path": str(self.prompt),
                "prompt_sha256": prompt_sha, "judged_at": utc_now(), "raw_response": raw,
            }
            append_jsonl(out, row)
            done[tid] = row
            print(f"      -> {row['decision']} {row.get('selected_qid') or ''} ({row['confidence']})")
        final_rows = [done[p["target_id"]] for p in packets if p["target_id"] in done]
        results = self.build_results_tsv(final_rows)
        print(f"Judgments saved: {out}")
        print(f"Results saved: {results}")
        return results


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["stage1", "stage2", "judge", "all"])
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    p.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    p.add_argument("--model", default=os.environ.get("WIKIDATA_JUDGE_MODEL", "gpt-5.6-luna"))
    p.add_argument("--fuzzy-limit", type=int, default=20)
    p.add_argument("--title-search-limit", type=int, default=10)
    p.add_argument("--wdqs-sleep", type=float, default=1.0)
    p.add_argument("--api-sleep", type=float, default=0.5)
    return p.parse_args()


def main():
    args = parse_args()
    r = Resolver(args.outdir, args.model, args.prompt, args.fuzzy_limit,
                 args.title_search_limit, args.wdqs_sleep, args.api_sleep)
    if args.command in {"stage1", "all"}:
        targets = load_targets(args.input)
        print(f"Targets loaded: {len(targets)}")
        r.run_stage1(targets)
    if args.command in {"stage2", "all"}:
        r.run_stage2()
    if args.command in {"judge", "all"}:
        r.run_judge()


if __name__ == "__main__":
    main()
