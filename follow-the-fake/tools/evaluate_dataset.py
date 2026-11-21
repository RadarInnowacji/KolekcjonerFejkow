"""Ocena metody na zbiorze z etykietami (np. zbiór organizatora) – z linii poleceń.

Użycie:
  python tools/evaluate_dataset.py data/demo                 # folder z manifestem
  python tools/evaluate_dataset.py zbior.zip --network       # ZIP, z pobieraniem metadanych z sieci
  python tools/evaluate_dataset.py data/demo --show-pairs    # szczegóły błędów

Etykieta kampanii jest czytana z pola label/campaign/cluster (patrz ftf/importer.py).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ftf import engine, evaluate, importer  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--network", action="store_true", help="pobieraj metadane domen (wolniej)")
    ap.add_argument("--show-pairs", action="store_true")
    ap.add_argument("--json", help="zapisz wynik do pliku JSON")
    a = ap.parse_args()

    t0 = time.time()
    if a.path.lower().endswith(".zip"):
        with open(a.path, "rb") as f:
            rows, src = importer.load(zbytes=f.read())
    elif os.path.isdir(a.path):
        rows, src = importer.load(path=a.path)
    else:
        with open(a.path, encoding="utf-8-sig") as f:
            rows, src = importer.load(raw=f.read(), name=a.path)
    items = []
    for k, r in enumerate(rows):
        rec, _ = importer.to_material(r, src, network=a.network)
        rec["id"] = k + 1
        items.append(rec)
    t1 = time.time()
    e = engine.Engine(items)
    e.matrix()
    e.cluster()
    camps = e.campaigns()
    res = evaluate.evaluate(e)
    t2 = time.time()

    print(f"Materiałów: {len(items)} | ekstrakcja {t1 - t0:.1f}s | korelacja {t2 - t1:.1f}s")
    for c in camps:
        print(f"  {c['code']}  n={c['size']:<3} spójność={c['cohesion']:.2f}  {c['name'][:60]:<60} etykiety={c['labels']}")
    if res.get("available"):
        keys = ["n", "true_campaigns", "found_campaigns", "ari", "nmi", "homogeneity", "completeness", "pair_precision", "pair_recall",
                "pair_f1", "bcubed_f1", "loo_assign_acc", "loo_new_acc"]
        print("\nWYNIKI:\n" + "\n".join(f"  {k:<18} {res[k]}" for k in keys))
        if a.show_pairs:
            for m in res["mistakes"]:
                print("  błąd:", m)
    else:
        print(res["reason"])
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"campaigns": camps, "evaluation": res}, f, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
