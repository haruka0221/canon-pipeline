#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

ADJ = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_remediation_adjudication_v1"
    / "openlibrary_r2a1_target_identity_remediation_adjudication_v1.tsv"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_component_registry_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openlibrary_r2a1_split_component_registry_v1.tsv"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openlibrary_r2a1_split_component_registry_v1_manifest.json"
)

EXPECTED_SPLIT_WORKS = 17
EXPECTED_COMPONENTS = 82

CREATED_AT = "2026-10-11"

VALID_HINTS = {
    "SUCCESSOR",
    "PRIMARY_SUCCESSOR_HINT",
    "DETACH",
    "EXCLUDE_APPARATUS",
}


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def atomic_tsv(df, path):
    tmp = path.with_name(path.name + ".tmp")

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(tmp, path)


def atomic_json(obj, path):
    tmp = path.with_name(path.name + ".tmp")

    tmp.write_text(
        json.dumps(
            obj,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    os.replace(tmp, path)


# ------------------------------------------------------------
# Fixed human-defined component boundaries.
#
# IMPORTANT:
# - These are routing components, not yet project W IDs.
# - PRIMARY_SUCCESSOR_HINT preserves wording from human
#   adjudication but does NOT authorize re-use of the old W ID.
# - DETACH means detach from the erroneous predecessor target;
#   it is not a corpus-scope exclusion.
# - EXCLUDE_APPARATUS is for explicitly identified study /
#   catalogue / apparatus material in the frozen human plan.
# ------------------------------------------------------------

COMPONENTS = {

    "W000014024": [
        (
            "C01",
            "Autobiography",
            "SUCCESSOR",
            "Henry James editions identified as autobiography."
        ),
        (
            "C02",
            "Letters to A.C. Benson and Auguste Monod",
            "SUCCESSOR",
            "The correspondence volume Letters to A.C. Benson and Auguste Monod."
        ),
        (
            "C03",
            "A Life in Letters",
            "SUCCESSOR",
            "Editions of A Life in Letters."
        ),
        (
            "C04",
            "Stories and tales selections",
            "SUCCESSOR",
            "Collected Stories, Selected Tales, stories of the supernatural, "
            "seven stories and studies, and substantially equivalent story/tale selections."
        ),
        (
            "C05",
            "Selected-fiction / selected-novels omnibus",
            "SUCCESSOR",
            "Omnibus or selected-fiction editions combining named Henry James fiction, "
            "including Daisy Miller, Washington Square, The Portrait of a Lady, "
            "The Bostonians, and The Aspern Papers. Treat the omnibus as one edition-level "
            "component; do not split it into constituent novels."
        ),
        (
            "C06",
            "Critical essays / essays on art and drama",
            "SUCCESSOR",
            "Critical-essay collections and essays on art or drama."
        ),
        (
            "C07",
            "The Spoils of Poynton — Bodley Head volume",
            "SUCCESSOR",
            "The Bodley Head volume explicitly identified as The Spoils of Poynton."
        ),
        (
            "C08",
            "Representative selections",
            "SUCCESSOR",
            "The 1941 representative-selections publication and clear manifestations of it."
        ),
    ],

    "W000031472": [
        (
            "C01",
            "On the Properties of Foodstuffs",
            "SUCCESSOR",
            "On the Properties of Foodstuffs / De alimentorum facultatibus."
        ),
        (
            "C02",
            "On Diseases and Symptoms",
            "SUCCESSOR",
            "On Diseases and Symptoms."
        ),
        (
            "C03",
            "On Antecedent Causes",
            "SUCCESSOR",
            "On Antecedent Causes."
        ),
    ],

    "W000030498": [
        (
            "C01",
            "Selected Poems",
            "SUCCESSOR",
            "Selected Poems and clearly equivalent selected-poetry editions."
        ),
        (
            "C02",
            "Novel omnibus",
            "SUCCESSOR",
            "Editions combining multiple Lawrence fictional works or novels, "
            "including the named Sons and Lovers / Fox / Love Among the Haystacks / "
            "Aaron's Rod / Ladybird / Women in Love groupings and Rainbow/Women in Love. "
            "Do not route by one constituent novel."
        ),
        (
            "C03",
            "Short-story collections / Selected Tales",
            "SUCCESSOR",
            "Short-story collections, short stories, and Selected Tales."
        ),
        (
            "C04",
            "Selected literary criticism / critical essays",
            "SUCCESSOR",
            "Selected literary criticism, critical essays, and equivalent criticism collections."
        ),
        (
            "C05",
            "Biography / reminiscences / correspondence",
            "SUCCESSOR",
            "Composite biography, reminiscences, correspondence, or equivalent biographical collections."
        ),
        (
            "C06",
            "Rare-book catalogue",
            "EXCLUDE_APPARATUS",
            "The 1934 catalogue or analogous catalogue of first editions, manuscripts, "
            "paintings, photographs, or association material."
        ),
    ],

    "W000023649": [
        (
            "C01",
            "Passages from his writings",
            "SUCCESSOR",
            "Passages from his writings with a brief life sketch and reading guide."
        ),
        (
            "C02",
            "Representative selections",
            "SUCCESSOR",
            "Representative Selections, especially the 1934 American Book Company selection."
        ),
        (
            "C03",
            "Selected Essays / Essays, Lectures and Poems",
            "SUCCESSOR",
            "Selected Essays and Selected Essays, Lectures and Poems type selections."
        ),
        (
            "C04",
            "Essays and journals",
            "SUCCESSOR",
            "Editions explicitly identified as essays and journals."
        ),
        (
            "C05",
            "Selected prose and poetry / Poems and Essays",
            "SUCCESSOR",
            "Selected prose and poetry, Poems and Essays, or equivalent mixed selections."
        ),
    ],

    "W000003023": [
        (
            "C01",
            "Poetry and prose",
            "SUCCESSOR",
            "The poetry & prose / poetry and prose selection represented by the 1939/1946 editions."
        ),
        (
            "C02",
            "Poems — Everyman's",
            "SUCCESSOR",
            "Poems editions in the Everyman's Library or Everyman's University Paperbacks lineage."
        ),
        (
            "C03",
            "Poetical works",
            "SUCCESSOR",
            "Edition explicitly identified as poetical works."
        ),
    ],

    "W000005351": [
        (
            "C01",
            "Canterbury Tales selections",
            "SUCCESSOR",
            "The Canterbury Tales prologue or individual-tale selections, including "
            "General Prologue, Knight's Tale, Nun's Priest's Tale, Wife of Bath's Prologue, "
            "and Prioress/Sir Thopas/Monk/Clerk/Squire selections."
        ),
        (
            "C02",
            "The Legend of Good Women",
            "SUCCESSOR",
            "The Legend of Good Women."
        ),
        (
            "C03",
            "Canterbury Tales / Troilus and Criseyde selection",
            "SUCCESSOR",
            "A combined selection from The Canterbury Tales and Troilus and Criseyde."
        ),
        (
            "C04",
            "Study apparatus / CD-ROM manual",
            "EXCLUDE_APPARATUS",
            "Sources and backgrounds, CD-ROM manuals, or analogous study/apparatus publications."
        ),
    ],

    "W000013400": [
        (
            "C01",
            "Fairy-tale / story collections",
            "SUCCESSOR",
            "The Complete Fairy Tales and Stories, The Complete Stories, "
            "Stories and Fairy Tales, or clearly equivalent tale/story collections."
        ),
        (
            "C02",
            "His Poems and the Story of His Life",
            "SUCCESSOR",
            "His Poems and the Story of His Life."
        ),
        (
            "C03",
            "Oeuvres, tome 2",
            "SUCCESSOR",
            "The edition identified as Oeuvres, tome 2."
        ),
        (
            "C04",
            "The maker of fairy tales",
            "SUCCESSOR",
            "The 1942 biographical publication identified as the maker of fairy tales."
        ),
    ],

    "W000014515": [
        (
            "C01",
            "Her Life, Letters, and Journals",
            "PRIMARY_SUCCESSOR_HINT",
            "Ednah D. Cheney (ed.), Louisa May Alcott: Her Life, Letters, and Journals, "
            "including title variants and reissues."
        ),
        (
            "C02",
            "Little Women / Little Men / Jo's Boys omnibus",
            "DETACH",
            "The omnibus combining Little Women, Little Men, and Jo's Boys."
        ),
        (
            "C03",
            "Works / Selected Fiction",
            "DETACH",
            "Works of Louisa May Alcott, Selected Fiction, and equivalent broad fiction selections."
        ),
        (
            "C04",
            "An intimate anthology",
            "DETACH",
            "The publication identified as an intimate anthology."
        ),
        (
            "C05",
            "American Men & Women of Letters biography",
            "DETACH",
            "The Chelsea House / American Men & Women of Letters biographical publication."
        ),
        (
            "C06",
            "Childhood-diary excerpts",
            "DETACH",
            "The book represented by the description of excerpts from Alcott's childhood diaries."
        ),
    ],

    "W000005682": [
        (
            "C01",
            "Complete works",
            "SUCCESSOR",
            "Oeuvres complètes / Complete Works, including Perennial or P.S. editions."
        ),
        (
            "C02",
            "Selected works / anthologies",
            "SUCCESSOR",
            "Oeuvres choisies, présentation et anthologie, illustrated Poèmes et textes, "
            "and equivalent selected-work anthologies."
        ),
        (
            "C03",
            "A Season in Hell",
            "SUCCESSOR",
            "A Season in Hell."
        ),
        (
            "C04",
            "Secondary studies of Rimbaud",
            "DETACH",
            "Critical or biographical studies such as une étude, Leben und Dichtung, "
            "and Al Athar Al-Shi'rya when functioning as secondary study rather than an edition of his works."
        ),
    ],

    "W000004772": [
        (
            "C01",
            "The Jewish War",
            "SUCCESSOR",
            "The Jewish War, including Loeb volumes and book-range manifestations."
        ),
        (
            "C02",
            "Jewish Antiquities",
            "SUCCESSOR",
            "Jewish Antiquities, including Loeb volumes and book-range manifestations."
        ),
        (
            "C03",
            "Multi-volume Loeb Josephus",
            "SUCCESSOR",
            "The collected multi-volume Josephus set in nine or ten volumes, "
            "including Thackeray and successor Loeb volumes when presented as the broad collected set."
        ),
        (
            "C04",
            "Modern selections / essential writings",
            "SUCCESSOR",
            "The Essential Works, The Essential Writings, Jewish War and other selections, "
            "and comparable modern selections."
        ),
    ],

    "W000030489": [
        (
            "C01",
            "Selected Works / selections from his works",
            "SUCCESSOR",
            "The Selected Works / selections from his works publications."
        ),
        (
            "C02",
            "An Alphabet of Quijote",
            "SUCCESSOR",
            "Un Abecedario De El Quijote / An Alphabet of Quijote."
        ),
        (
            "C03",
            "Prologues and epilogue",
            "SUCCESSOR",
            "The publication identified as prologues and epilogue."
        ),
    ],

    "W000003030": [
        (
            "C01",
            "Five Complete Novels omnibus",
            "PRIMARY_SUCCESSOR_HINT",
            "The five-novel omnibus containing The Return of Jeeves, Bertie Wooster Sees It Through, "
            "Spring Fever, The Butler Did It, and The Old Reliable. "
            "Treat the omnibus as one component rather than five constituent novels."
        ),
        (
            "C02",
            "Selected Short Stories",
            "SUCCESSOR",
            "Selected Short Stories."
        ),
    ],

    "W000002404": [
        (
            "C01",
            "Twenty stories and seven poems",
            "PRIMARY_SUCCESSOR_HINT",
            "The Colin Roderick selection of twenty stories and seven poems, including 1947/1950 manifestations."
        ),
        (
            "C02",
            "Selected Stories",
            "SUCCESSOR",
            "Selected Stories, including the Angus & Robertson Classics edition."
        ),
        (
            "C03",
            "Illustrated poems",
            "SUCCESSOR",
            "The publication explicitly identified as illustrated poems."
        ),
        (
            "C04",
            "Master story-teller / literary heritage",
            "SUCCESSOR",
            "The master story-teller and a literary heritage selections/appreciations."
        ),
    ],

    "W000021761": [
        (
            "C01",
            "Collected Poems 1914-1947",
            "SUCCESSOR",
            "Collected Poems 1914-1947 and direct manifestations of that collection."
        ),
        (
            "C02",
            "Poems 1938-1945",
            "SUCCESSOR",
            "Poems 1938-1945."
        ),
        (
            "C03",
            "Later Collected / Complete Poems",
            "SUCCESSOR",
            "Collected Poems 1965/1975, Complete Poems, and comparable later collected-poems editions."
        ),
        (
            "C04",
            "Poems 1968-1970 / 1970-1972",
            "SUCCESSOR",
            "Poems 1968-1970 and Poems 1970-1972."
        ),
        (
            "C05",
            "Selected poems",
            "SUCCESSOR",
            "Editions explicitly presented as selected poems or poems selected by the author."
        ),
        (
            "C06",
            "Marie Powell / Islands of Unwisdom fiction pairing",
            "DETACH",
            "The fiction publication pairing The Story of Marie/Mary Powell, Wife to Mr Milton "
            "with The Islands of Unwisdom."
        ),
    ],

    "W000004821": [
        (
            "C01",
            "Collected / complete verse",
            "SUCCESSOR",
            "Poems 1886-1929, Collected Verse, Complete Verse, Definitive Edition, "
            "and closely equivalent comprehensive verse collections."
        ),
        (
            "C02",
            "A Choice of Kipling's Verse",
            "SUCCESSOR",
            "A Choice of Kipling's Verse."
        ),
        (
            "C03",
            "Departmental Ditties and Other Verses",
            "SUCCESSOR",
            "Departmental Ditties and Other Verses."
        ),
        (
            "C04",
            "The Seven Seas",
            "SUCCESSOR",
            "The Seven Seas."
        ),
        (
            "C05",
            "Barrack-Room Ballads",
            "SUCCESSOR",
            "Barrack-Room Ballads and Other Poems."
        ),
        (
            "C06",
            "Selected Poems / Poetry for Young People",
            "SUCCESSOR",
            "Selected Poems, Poetry for Young People, and comparable bounded poetry selections."
        ),
        (
            "C07",
            "Something of Myself / autobiographical writings",
            "DETACH",
            "Something of Myself and other autobiographical writings."
        ),
        (
            "C08",
            "Stories from India / broad selected works",
            "DETACH",
            "Stories from India, broad Selected Works, or equivalent prose/mixed selections "
            "that are not a bounded verse collection."
        ),
    ],

    "W000005423": [
        (
            "C01",
            "Poems / Collected Poems",
            "SUCCESSOR",
            "Poems / Collected Poems containing Underwoods, Ballads, Songs of Travel, "
            "A Child's Garden of Verses, or substantially equivalent broad poetry collections."
        ),
        (
            "C02",
            "Poems and ballads",
            "SUCCESSOR",
            "Poems and ballads."
        ),
        (
            "C03",
            "Selected Poems / Poetry for Young People",
            "SUCCESSOR",
            "Selected Poems, Poetry for Young People, including the illustrated 32-poem selection."
        ),
        (
            "C04",
            "Hitherto unpublished prose writings",
            "DETACH",
            "Robert Louis Stevenson: hitherto unpublished prose writings."
        ),
        (
            "C05",
            "Fiction / Pacific writings",
            "DETACH",
            "Four Complete Novels, The Complete Shorter Fiction, His Best Pacific Writings, "
            "and equivalent fiction/prose publications."
        ),
        (
            "C06",
            "Treasure Island study apparatus",
            "EXCLUDE_APPARATUS",
            "Treasure Island Monarch Notes or analogous study-guide apparatus."
        ),
    ],

    "W000004923": [
        (
            "C01",
            "Azul",
            "SUCCESSOR",
            "Azul / Azul... editions, including Valera-prologued manifestations."
        ),
        (
            "C02",
            "Prosas profanas",
            "SUCCESSOR",
            "Prosas profanas."
        ),
        (
            "C03",
            "Cantos de vida y esperanza",
            "SUCCESSOR",
            "Cantos de vida y esperanza."
        ),
        (
            "C04",
            "Complete poetry / complete works",
            "SUCCESSOR",
            "Poesías completas, Obra completa, libros poéticos completos, "
            "and equivalent comprehensive collections."
        ),
        (
            "C05",
            "Poetry anthologies and selections",
            "SUCCESSOR",
            "Antología poética, Selección poética, Eleven poems, Rubén Darío enamorado / "
            "Rubén Darío y el amor, La princesa está triste, semblanza y florilegio, "
            "and comparable bounded anthologies."
        ),
        (
            "C06",
            "Cuentos / prose stories",
            "DETACH",
            "Cuentos and prose-story material that is not part of the poetry identity."
        ),
    ],
}


def main():

    if not ADJ.exists():
        raise FileNotFoundError(ADJ)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    adj = pd.read_csv(
        ADJ,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    split = adj.loc[
        adj["resolution_decision"].eq("SPLIT")
    ].copy()

    assert len(split) == EXPECTED_SPLIT_WORKS
    assert split["project_work_id"].is_unique

    split_ids = set(
        split["project_work_id"]
    )

    assert set(COMPONENTS) == split_ids, {
        "missing_from_registry":
            sorted(split_ids - set(COMPONENTS)),
        "extra_in_registry":
            sorted(set(COMPONENTS) - split_ids),
    }

    adj_map = (
        split
        .set_index("project_work_id")
        .to_dict("index")
    )

    rows = []

    for project_work_id, components in COMPONENTS.items():

        a = adj_map[project_work_id]

        for (
            local_id,
            label,
            role_hint,
            definition,
        ) in components:

            if role_hint not in VALID_HINTS:
                raise RuntimeError(
                    f"Invalid role hint: {role_hint}"
                )

            rows.append({
                "remediation_priority_rank":
                    int(
                        a[
                            "remediation_priority_rank"
                        ]
                    ),

                "project_work_id":
                    project_work_id,

                "r2_target_title":
                    a[
                        "r2_target_title"
                    ],

                "r2_target_author":
                    a[
                        "r2_target_author"
                    ],

                "component_id":
                    f"{project_work_id}_{local_id}",

                "component_local_id":
                    local_id,

                "component_label":
                    label,

                "human_role_hint":
                    role_hint,

                "component_definition":
                    definition,

                "human_resolution_confidence":
                    a[
                        "resolution_confidence"
                    ],

                "human_resolution_plan":
                    a[
                        "resolution_plan"
                    ],
            })

    out = pd.DataFrame(rows)

    out = out.sort_values(
        [
            "remediation_priority_rank",
            "project_work_id",
            "component_local_id",
        ],
        kind="stable",
    ).reset_index(drop=True)

    assert len(out) == EXPECTED_COMPONENTS
    assert out["component_id"].is_unique
    assert out["component_definition"].ne("").all()

    counts = (
        out.groupby("project_work_id")
        .size()
        .to_dict()
    )

    assert set(counts) == split_ids

    OUT_DIR.mkdir(
        parents=True,
    )

    atomic_tsv(
        out,
        OUT_TSV,
    )

    manifest = {
        "release":
            "openlibrary-r2a1-split-component-registry-v1",

        "status":
            "human_defined_routing_component_registry",

        "created_at":
            CREATED_AT,

        "counts": {
            "split_project_works":
                int(
                    out[
                        "project_work_id"
                    ].nunique()
                ),

            "components":
                len(out),

            "components_by_role_hint": {
                str(k): int(v)
                for k, v
                in out[
                    "human_role_hint"
                ]
                .value_counts()
                .sort_index()
                .items()
            },

            "components_by_project_work":
                {
                    str(k): int(v)
                    for k, v
                    in sorted(
                        counts.items()
                    )
                },
        },

        "semantics": [
            (
                "Component boundaries are fixed from the "
                "frozen human remediation adjudication."
            ),
            (
                "A component_id is an edition-routing label, "
                "not a project_work_id and not a new source entity."
            ),
            (
                "PRIMARY_SUCCESSOR_HINT records the human "
                "reviewer's wording only. It does not authorize "
                "reuse of the predecessor W identifier."
            ),
            (
                "DETACH means detach from the erroneous "
                "predecessor target; it is not a temporal, "
                "language, genre, or fiction-scope exclusion."
            ),
            (
                "EXCLUDE_APPARATUS is limited to material "
                "explicitly identified as catalogue/study/"
                "apparatus in the frozen human plan."
            ),
            (
                "An LLM may route editions only to these fixed "
                "components or HOLD_UNRESOLVED; it may not invent "
                "new successor boundaries."
            ),
        ],

        "inputs": {
            str(
                ADJ.relative_to(ROOT)
            ):
                sha256_file(ADJ),
        },

        "outputs": {
            OUT_TSV.name:
                sha256_file(OUT_TSV),
        },
    }

    atomic_json(
        manifest,
        OUT_MANIFEST,
    )

    print(
        "=== SPLIT COMPONENT REGISTRY V1 ==="
    )

    print(
        "split project works:",
        out["project_work_id"].nunique(),
    )

    print(
        "components:",
        len(out),
    )

    print()
    print("=== ROLE HINT COUNTS ===")

    print(
        out[
            "human_role_hint"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print("=== COMPONENTS BY PROJECT ===")

    print(
        out.groupby(
            [
                "remediation_priority_rank",
                "project_work_id",
                "r2_target_title",
            ]
        )
        .size()
        .rename("components")
        .reset_index()
        .sort_values(
            "remediation_priority_rank"
        )
        .to_string(index=False)
    )

    print()
    print("QC STATUS: PASSED")


if __name__ == "__main__":
    main()
