#!/usr/bin/env python3
"""Fill derived/bl_calibration/calibration_v2/first_edition_targets_v1.tsv in place.

Values were drafted on 2026-10-21 from general bibliographic knowledge and
Wikipedia-level references, WITHOUT consulting the British Library
catalogue. Each row records its confidence and whether a human verified
it (verified=no unless changed by hand). Rows that could not be
established are frozen as NO_EVIDENCE and are excluded from the coverage
denominator; they are not replaced. Run once; refuses to run if any row
is no longer PENDING.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "derived" / "bl_calibration" / "calibration_v2" / "first_edition_targets_v1.tsv"

# fe_id: (year, publisher, place, earlier_non_uk, sources, confidence, notes, status)
V = {
 "FE2_01": ("", "", "", "", "Wikipedia: Alice Campbell (novelist) — not checked", "low",
            "UK publisher likely Collins c.1930; not established", "NO_EVIDENCE"),
 "FE2_02": ("", "", "", "", "", "low", "Picture book by Richard André, 1880s; publisher not established", "NO_EVIDENCE"),
 "FE2_03": ("1944", "Jonathan Cape", "London", "", "Wikipedia: Julian Maclaren-Ross (unverified)", "high", "", "ESTABLISHED"),
 "FE2_04": ("", "", "", "US edition, year not established", "", "low", "Not fiction; UK edition unknown", "NO_EVIDENCE"),
 "FE2_05": ("", "", "", "Harper, New York 1914 (unverified)", "", "low", "US author; UK edition not known", "NO_UK_EDITION_KNOWN"),
 "FE2_06": ("", "", "", "Random House, New York 1946 (unverified)", "", "medium", "US author; UK edition not known", "NO_UK_EDITION_KNOWN"),
 "FE2_07": ("", "", "", "", "", "none", "Author obscure; nothing established", "NO_EVIDENCE"),
 "FE2_08": ("", "", "", "Lee & Shepard, Boston 1867 (unverified)", "", "medium", "US juvenile; UK edition not known", "NO_UK_EDITION_KNOWN"),
 "FE2_09": ("1902", "Early English Text Society / Kegan Paul, Trench, Trübner", "London",
            "", "EETS Original Series 121 (1902) and 122 (1903) — unverified", "high",
            "Scholarly edition in two parts; second part 1903", "ESTABLISHED"),
 "FE2_10": ("", "", "", "Julian Messner, New York 1945 (unverified)", "", "medium", "US juvenile; UK edition not known", "NO_UK_EDITION_KNOWN"),
 "FE2_11": ("1947", "Victor Gollancz", "London", "", "Wikipedia: Negley Farson (unverified)", "medium", "", "ESTABLISHED"),
 "FE2_12": ("", "", "", "E. P. Dutton, New York 1929 (unverified)", "", "medium",
            "UK edition possibly Ward Lock 1929/30; not established", "NO_EVIDENCE"),
 "FE2_13": ("", "", "", "C. M. Clark, Boston 1901 (unverified)", "", "medium", "US author; UK edition not known", "NO_UK_EDITION_KNOWN"),
 "FE2_14": ("", "", "", "US Catholic publisher, c.1881 (unverified)", "", "low", "US author; UK edition not known", "NO_UK_EDITION_KNOWN"),
 "FE2_15": ("", "", "", "Self-published, Louisville 1906 (unverified)", "Wikipedia: George Marion McClellan", "medium",
            "US author; UK edition not known", "NO_UK_EDITION_KNOWN"),
 "FE2_16": ("1937", "Victor Gollancz", "London", "", "Wikipedia: John Leslie Palmer (David Pilgrim = Palmer & Saunders) — unverified", "medium", "", "ESTABLISHED"),
 "FE2_17": ("", "", "", "US edition, 1900s (unverified)", "", "low", "Title ambiguous (several Baldwin 'Hero Tales' volumes); not established", "NO_EVIDENCE"),
 "FE2_18": ("1905", "Alston Rivers", "London", "", "Wikipedia: Arnold Bennett bibliography (unverified)", "high", "", "ESTABLISHED"),
 "FE2_19": ("1925", "Jonathan Cape", "London", "", "Wikipedia: Naomi Mitchison (unverified)", "high", "", "ESTABLISHED"),
 "FE2_20": ("1950", "Victor Gollancz", "London", "Farrar, Straus, New York 1949", "Wikipedia: The Lottery and Other Stories (unverified)", "medium", "", "ESTABLISHED"),
 "FE2_21": ("1965", "Peter Owen", "London", "Gyldendal, Oslo 1939 (Norwegian original)",
            "Wikipedia: Cora Sandel (unverified)", "medium",
            "UK edition is the English translation 'Alberte Alone'; OL title is Norwegian", "ESTABLISHED"),
 "FE2_22": ("", "", "", "Dodd, Mead, New York 1899 (unverified)", "", "low", "UK edition (Constable?) not established", "NO_EVIDENCE"),
 "FE2_23": ("", "", "", "Grosset & Dunlap, New York 1947 (unverified)", "", "low", "UK Nancy Drew editions (Sampson Low) not established for this title", "NO_EVIDENCE"),
 "FE2_24": ("1872", "George Routledge and Sons", "London", "American Publishing Co., Hartford 1872 (UK issue preceded it)",
            "Wikipedia: Roughing It; BAL (unverified)", "high", "OL title is a volume title ('in two volumes. 2/2')", "ESTABLISHED"),
 "FE2_25": ("1929", "Collins", "London", "", "Wikipedia: The Poisoned Chocolates Case (unverified)", "high", "", "ESTABLISHED"),
 "FE2_26": ("1894", "William Heinemann", "London", "", "Wikipedia: The King of Schnorrers (unverified)", "high", "", "ESTABLISHED"),
 "FE2_27": ("1893", "David Nutt", "London", "Charles Scribner's Sons, New York 1892", "", "medium", "Not fiction (ethnography)", "ESTABLISHED"),
 "FE2_28": ("1936", "Chatto & Windus", "London", "Alfred A. Knopf, New York 1935",
            "Wikipedia: Life with Father (unverified)", "medium",
            "OL author 'O. Henry' is wrong; the author is Clarence Day", "ESTABLISHED"),
 "FE2_29": ("", "", "", "English translation: E. P. Dutton, New York 1924; Russian text: Chekhov Publishing, New York 1952",
            "Wikipedia: We (novel)", "medium",
            "OL title is Russian; first UK edition of the English translation not established (Cape 1970?)", "NO_EVIDENCE"),
 "FE2_30": ("1915", "Methuen", "London", "Something New: D. Appleton, New York 1915 (months earlier)",
            "Wikipedia: Something Fresh; McIlvaine bibliography (unverified)", "high", "", "ESTABLISHED"),
}


def main() -> int:
    df = pd.read_csv(P, sep="\t", dtype=str, keep_default_na=False)
    if (df["status"] != "PENDING").any():
        print("table already filled; refusing to overwrite", file=sys.stderr)
        return 1
    if set(df["fe_id"]) != set(V):
        print("fe_id mismatch", file=sys.stderr)
        return 1
    if "verified" not in df.columns:
        df.insert(df.columns.get_loc("status"), "verified", "no")
    for i, r in df.iterrows():
        y, pub, place, earlier, src, conf, notes, status = V[r["fe_id"]]
        df.loc[i, ["uk_first_edition_year", "uk_first_edition_publisher", "uk_first_edition_place",
                   "earlier_non_uk_edition", "evidence_sources", "evidence_confidence",
                   "notes", "status"]] = [y, pub, place, earlier, src, conf, notes, status]
        df.loc[i, "verified"] = "no"
        df.loc[i, "notes"] = ("Drafted 2026-10-21 from general knowledge, BL catalogue not consulted. "
                              + notes).strip()
    df.to_csv(P, sep="\t", index=False, lineterminator="\n")
    print(df["status"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
