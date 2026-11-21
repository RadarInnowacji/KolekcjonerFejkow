"""Ocena jakości grupowania, gdy materiały mają etykiety kampanii (np. zbiór organizatora).

Miary:
- ARI, NMI, jednorodność, kompletność (scikit-learn)
- precyzja / czułość / F1 par (czy pary z tej samej kampanii są razem, a z różnych osobno)
- B-cubed F1 (miara per materiał, odporna na nierówne rozmiary kampanii)
- test „nowego materiału” (leave-one-out): każdy materiał po kolei udaje nowy – czy
  zostaje przypisany do właściwej kampanii, a materiał z kampanii jednoelementowej
  poprawnie uznany za „nowy wzorzec” (czyli NIE połączony z niczym)
"""
from collections import Counter, defaultdict

import numpy as np
from sklearn import metrics

from . import engine as E


def pairwise(true, pred):
    tp = fp = fn = 0
    n = len(true)
    for i in range(n):
        for j in range(i + 1, n):
            st, sp = true[i] == true[j], pred[i] == pred[j]
            tp += st and sp
            fp += (not st) and sp
            fn += st and (not sp)
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def bcubed(true, pred):
    n = len(true)
    by_t, by_p = defaultdict(set), defaultdict(set)
    for i in range(n):
        by_t[true[i]].add(i)
        by_p[pred[i]].add(i)
    P = np.mean([len(by_t[true[i]] & by_p[pred[i]]) / len(by_p[pred[i]]) for i in range(n)])
    R = np.mean([len(by_t[true[i]] & by_p[pred[i]]) / len(by_t[true[i]]) for i in range(n)])
    return float(P), float(R), float(2 * P * R / (P + R)) if P + R else 0.0


def evaluate(eng: "E.Engine"):
    idx = [k for k, it in enumerate(eng.items) if it.get("label")]
    if len(idx) < 3:
        return {"available": False, "reason": "Za mało materiałów z etykietą kampanii (pole „label”)."}
    true = [eng.items[k]["label"] for k in idx]
    pred = [int(eng.labels[k]) for k in idx]
    p, r, f = pairwise(true, pred)
    bp, br, bf = bcubed(true, pred)

    # leave-one-out: przypisanie nowego materiału
    size = Counter(true)
    ok_assign = ok_new = n_assign = n_new = 0
    mistakes = []
    for k in idx:
        lab = eng.items[k]["label"]
        others = [j for j in range(len(eng.items)) if j != k]
        # kampanie liczone bez materiału k
        per = defaultdict(list)
        for j in others:
            per[int(eng.labels[j])].append(eng.S[k, j])
        stats = sorted(((c, float(np.mean(v)), float(np.max(v))) for c, v in per.items()), key=lambda x: (-x[1], -x[2]))
        c, mean, mx = stats[0]
        hard_c = None
        for j in others:
            e = eng.edges.get((min(k, j), max(k, j)))
            if e and e["hard"]:
                hard_c = int(eng.labels[j])
                break
        if hard_c is not None:
            c = hard_c
            mean = float(np.mean(per[c]))
            mx = float(np.max(per[c]))
        assigned = mean >= E.ASSIGN_T or mx >= E.HARD_SCORE
        if size[lab] == 1:
            n_new += 1
            if not assigned:
                ok_new += 1
            else:
                mistakes.append({"id": eng.ids[k], "label": lab, "error": "połączony, choć to osobna kampania"})
        else:
            n_assign += 1
            members = [j for j in others if eng.labels[j] == c]
            maj = Counter(eng.items[j].get("label") for j in members).most_common(1)
            if assigned and maj and maj[0][0] == lab:
                ok_assign += 1
            else:
                mistakes.append({"id": eng.ids[k], "label": lab, "error": "nie przypisany" if not assigned else f"przypisany do kampanii z etykietą {maj[0][0] if maj else '?'}"})
    return {
        "available": True, "n": len(idx), "true_campaigns": len(set(true)), "found_campaigns": len(set(pred)),
        "ari": round(metrics.adjusted_rand_score(true, pred), 3),
        "nmi": round(metrics.normalized_mutual_info_score(true, pred), 3),
        "homogeneity": round(metrics.homogeneity_score(true, pred), 3),
        "completeness": round(metrics.completeness_score(true, pred), 3),
        "pair_precision": round(p, 3), "pair_recall": round(r, 3), "pair_f1": round(f, 3),
        "bcubed_precision": round(bp, 3), "bcubed_recall": round(br, 3), "bcubed_f1": round(bf, 3),
        "loo_assign_acc": round(ok_assign / n_assign, 3) if n_assign else None, "loo_assign_n": n_assign,
        "loo_new_acc": round(ok_new / n_new, 3) if n_new else None, "loo_new_n": n_new,
        "mistakes": mistakes[:30],
    }
