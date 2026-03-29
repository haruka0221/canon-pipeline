import pandas as pd

targets = {
    "/works/OL15345521W": "The Good Soldier (Ford Madox Ford?)",
    "/works/OL15062619W": "Dracula (Bram Stoker?)",
    "/works/OL9056552W":  "The Prisoner of Zenda (Anthony Hope?)",
}

pop = pd.read_csv("derived/ol_dump_population_with_author.tsv", sep="\t")

for wid, label in targets.items():
    bare = wid.replace("/works/", "")
    row = pop[pop["work_key"].astype(str).str.strip().isin([wid, bare])]
    if len(row):
        r = row.iloc[0]
        print(f"{label}")
        print(f"  work_key: {r.get('work_key','?')}")
        print(f"  title   : {r.get('title','?')}")
        print(f"  author  : {r.get('author_name', r.get('author','?'))}")
    else:
        print(f"{label} → NOT FOUND in population")
    print()
