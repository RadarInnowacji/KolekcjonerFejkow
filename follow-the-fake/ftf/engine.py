"""Silnik korelacji: podobieństwo wielokanałowe → duplikaty → kampanie → przypisanie nowych.

Metoda (szczegóły w METODYKA.md):

1. Dla każdej pary materiałów liczymy podobieństwo w 6 kanałach (0..1 albo None = brak danych):
     tekst (TF-IDF słowa+n-gramy znakowe, cosinus) · wizual (hashe percepcyjne, paleta)
     osoby (zbiory wizerunków, hashe twarzy) · narracja (tematy, chwyty manipulacyjne, marki)
     domeny (wspólne domeny/przekierowania/certyfikaty, podobne nazwy) · infrastruktura
     (trackery, favicon, IP, NS, szkielet DOM, rejestrator+data, wspólne kontakty/portfele)
2. Wynik pary = średnia ważona TYLKO po kanałach dostępnych w obu materiałach
   (odporność na niekompletne dane), z łagodną karą za niskie pokrycie kanałów.
3. „Twarde dowody” (ten sam Pixel/GA, ten sam portfel, ta sama domena docelowa, prawie
   identyczna kreacja, prawie identyczny tekst) podnoszą wynik do poziomu pewnego powiązania.
4. Grupowanie dwuetapowe: (a) twarde dowody łączą materiały w „atomy” (union-find),
   (b) atomy łączymy aglomeracyjnie metodą średniego wiązania (average linkage) – to
   ogranicza efekt łańcuchowania, w którym jedna słaba krawędź skleja dwie kampanie.
5. Kampanie powiązane: średnie podobieństwo między klastrami ≥ próg rodziny.
6. Nowy materiał: podobieństwo do wszystkich → średnia i maksimum per kampania →
   przypisanie albo „nowy wzorzec”, zawsze z listą przesłanek.
"""
import math
import re
from collections import Counter, defaultdict

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

from . import infra, lexicon
from .visual import hamming, hist_sim

WEIGHTS = {"tekst": 0.26, "wizual": 0.20, "osoby": 0.12, "narracja": 0.10, "domeny": 0.14, "infrastruktura": 0.18}
LINK_T = 0.45        # próg łączenia w kampanię
FAMILY_T = 0.22      # próg „kampanie podobne / ta sama rodzina”
VARIANT_T = 0.70     # wariant tego samego przekazu
ASSIGN_T = 0.40      # przypisanie nowego materiału (średnia do kampanii)
HARD_SCORE = 0.85    # wynik pary z twardym dowodem


def _clean_text(t):
    t = infra.URL_RE.sub(" ", t or "")
    t = re.sub(r"\d+", " 0 ", lexicon.norm(t))
    return re.sub(r"\s+", " ", t)


def _jacc(a, b):
    a, b = set(a or []), set(b or [])
    if not a or not b:
        return None
    return len(a & b) / len(a | b)


def _noisy_or(vals):
    p = 1.0
    for v in vals:
        p *= 1 - max(0.0, min(1.0, v))
    return 1 - p


def _domain_tokens(d):
    label = d.split(".")[0]
    return {t for t in re.split(r"[-_\d]+", label) if len(t) >= 3}


GENERIC_NS = re.compile(r"(registrar-servers|domaincontrol|dns\.(home|ovh)|ovh\.net|hostinger|nazwa\.pl|home\.pl|cyberfolks|dhosting|awsdns|azure-dns|googledomains|namecheaphosting)", re.I)
SHARED_NETS = re.compile(r"(cloudflare|amazon|aws|google|microsoft|azure|akamai|fastly|ovh|hetzner|digitalocean)", re.I)


class Engine:
    def __init__(self, items):
        """items: lista rekordów z extract.build_material, każdy z polem 'id'."""
        self.items = items
        self.ids = [it["id"] for it in items]
        self.idx = {i: k for k, i in enumerate(self.ids)}
        self._fit_text()

    # ---------------------------------------------------------------- tekst
    def _fit_text(self):
        docs = [_clean_text(it["text"]) for it in self.items]
        self.has_text = np.array([len(d) >= 30 for d in docs])
        if len(docs) == 0 or not self.has_text.any():
            self.T = None
            return
        w = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True, min_df=1,
                            stop_words=sorted({lexicon.norm(s) for s in lexicon.STOPWORDS}), token_pattern=r"(?u)\b[a-z]{3,}\b")
        c = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1, max_features=60000)
        docs2 = [d if len(d) >= 30 else "pusty" for d in docs]
        try:
            Wm = w.fit_transform(docs2)
        except ValueError:
            Wm = None
        Cm = c.fit_transform(docs2)
        S = (Cm @ Cm.T).toarray()
        if Wm is not None:
            S = 0.5 * S + 0.5 * (Wm @ Wm.T).toarray()
        self.T = S
        self._vec = (w if Wm is not None else None, c)

    def text_sim_vector(self, rec):
        """Podobieństwo tekstu nowego materiału do korpusu (bez ponownego uczenia słownika)."""
        if self.T is None or len(_clean_text(rec["text"])) < 30:
            return None
        w, c = self._vec
        d = [_clean_text(rec["text"])]
        docs = [_clean_text(it["text"]) if len(_clean_text(it["text"])) >= 30 else "pusty" for it in self.items]
        sc = (c.transform(d) @ c.transform(docs).T).toarray()[0]
        if w is not None:
            sc = 0.5 * sc + 0.5 * (w.transform(d) @ w.transform(docs).T).toarray()[0]
        return sc

    # ---------------------------------------------------------------- para
    @staticmethod
    def pair(a, b, text_sim=None):
        """Zwraca (wynik, kanały, przesłanki, twarde_dowody, typ_relacji)."""
        ch, ev, hard = {}, [], []

        # --- tekst
        if text_sim is not None and len(a["text"]) >= 30 and len(b["text"]) >= 30:
            ts = float(max(0.0, min(1.0, text_sim)))
            ch["tekst"] = ts
            if ts >= 0.35:
                common = [k for k in a["narrative"]["keywords"] if k in set(b["narrative"]["keywords"])][:6]
                ev.append(("tekst", ts, f"Podobna treść (cos = {ts:.2f})" + (f"; wspólne słowa: {', '.join(common)}" if common else "")))
            if ts >= 0.90:
                hard.append("prawie identyczny tekst")
        if a.get("text_fp") and a["text_fp"] == b.get("text_fp"):
            ch["tekst"] = 1.0
            hard.append("identyczny tekst")

        # --- wizual
        # porównujemy dhash z dhash i phash z phash (różne algorytmy nie są porównywalne)
        def hashes(it, kind):
            out = [im.get(kind) for im in it["visual"]["images"] if im.get(kind)]
            if kind == "dhash":
                out += [f["dhash"] for f in it["visual"]["frames"]]
            return out
        da_, db_ = hashes(a, "dhash"), hashes(b, "dhash")
        pa_, pb_ = hashes(a, "phash"), hashes(b, "phash")
        if da_ and db_:
            dd = min(hamming(x, y) for x in da_ for y in db_)
            dp = min((hamming(x, y) for x in pa_ for y in pb_), default=64)
            # oba algorytmy muszą się zgadzać – ogranicza fałszywe trafienia jednego z nich
            d = max(dd, dp) if pa_ and pb_ else dd
            fa_, fb_ = [im["dhash_full"] for im in a["visual"]["images"] if im.get("dhash_full")], [im["dhash_full"] for im in b["visual"]["images"] if im.get("dhash_full")]
            if fa_ and fb_ and min(hamming(x, y) for x in fa_ for y in fb_) <= 2 and dd <= 4:
                d = 0
            hs = 1.0 if d <= 4 else max(0.0, (22 - d) / 18)
            hsim = hist_sim(a["visual"].get("hist"), b["visual"].get("hist"))
            tpl = max(0.0, (hsim - 0.6) / 0.4) * 0.55 if hsim is not None else 0.0
            ch["wizual"] = max(hs, tpl)
            if d <= 4:
                ev.append(("wizual", 1.0, f"Ta sama kreacja graficzna (odległość hashy = {d}/64)"))
                hard.append("identyczna kreacja")
            elif hs >= 0.4:
                ev.append(("wizual", hs, f"Wariant tej samej kreacji (odległość hashy = {d}/64)"))
            elif tpl >= 0.3:
                ev.append(("wizual", tpl, f"Podobny szablon / paleta barw (przecięcie histogramów = {hsim:.2f})"))

        # --- osoby
        pa, pb = set(a["entities"]["persons"]), set(b["entities"]["persons"])
        js = _jacc(pa, pb)
        face_match = None
        fa, fb = a["visual"]["faces"], b["visual"]["faces"]
        if fa and fb:
            dmin = min(hamming(x["hash"], y["hash"]) for x in fa for y in fb)
            if dmin <= 8:
                face_match = dmin
        if js is not None or face_match is not None:
            val = js or 0.0
            if face_match is not None:
                val = max(val, 0.9)
                ev.append(("osoby", 0.9, f"To samo zdjęcie twarzy (odległość {face_match}/64)"))
            ch["osoby"] = val
            if js:
                ev.append(("osoby", js, f"Wspólny wizerunek: {', '.join(sorted(pa & pb))}"))

        # --- narracja
        ta, tb = a["narrative"]["topics"], b["narrative"]["topics"]
        ma, mb = a["narrative"]["manipulation"], b["narrative"]["manipulation"]
        ba, bb = a["entities"]["brands"], b["entities"]["brands"]
        parts, wsum = [], 0.0
        for va, vb, w in ((ta, tb, 0.5), (ma, mb, 0.3), (ba, bb, 0.2)):
            j = _jacc(va, vb)
            if j is not None:
                parts.append(j * w)
                wsum += w
        if wsum:
            ns = sum(parts) / wsum
            ch["narracja"] = ns
            shared = sorted((set(ta) & set(tb)) | (set(ma) & set(mb)))
            if ns >= 0.4 and shared:
                ev.append(("narracja", ns, f"Ta sama narracja: {', '.join(shared[:5])}"))
            sb = sorted(set(ba) & set(bb))
            if sb:
                ev.append(("narracja", 0.3, f"Te same marki/logotypy: {', '.join(sb[:4])}"))

        # --- domeny
        ia, ib = a["infra"], b["infra"]
        da, db = set(ia["domains"]), set(ib["domains"])
        if da and db:
            sig = []
            shared = da & db
            if shared:
                sig.append(1.0)
                ev.append(("domeny", 1.0, f"Wspólna domena: {', '.join(sorted(shared)[:3])}"))
                hard.append("wspólna domena")
            red = (set(ia["redirect_domains"]) & set(ib["redirect_domains"])) - shared
            if red:
                sig.append(0.9)
                ev.append(("domeny", 0.9, f"Wspólny punkt w łańcuchu przekierowań: {', '.join(sorted(red)[:3])}"))
            cert = (set(ia["cert_names"]) & set(ib["cert_names"])) - {""}
            cert = {c for c in cert if infra.registered_domain(c) not in infra.GENERIC_DOMAINS}
            if cert:
                sig.append(0.85)
                ev.append(("domeny", 0.85, f"Wspólne nazwy w certyfikatach TLS: {', '.join(sorted(cert)[:3])}"))
            tok_a = set().union(*[_domain_tokens(d) for d in da])
            tok_b = set().union(*[_domain_tokens(d) for d in db])
            jt = _jacc(tok_a, tok_b)
            if jt and jt >= 0.3 and not shared:
                sig.append(0.55 * jt + 0.2)
                ev.append(("domeny", 0.55 * jt + 0.2, f"Podobny wzorzec nazw domen ({', '.join(sorted(tok_a & tok_b)[:3])})"))
            od = (set(ia["out_domains"]) & set(ib["out_domains"])) - shared
            if od:
                sig.append(0.6)
                ev.append(("domeny", 0.6, f"Wspólne domeny docelowe linków: {', '.join(sorted(od)[:3])}"))
            ch["domeny"] = _noisy_or(sig) if sig else 0.0

        # --- infrastruktura
        sig, any_data = [], False
        for key, label, val, is_hard in (
            ("trackers", "wspólny identyfikator śledzący", 1.0, True),
            ("campaign_keys", "wspólny klucz kampanii w metadanych", 1.0, True),
            ("favicons", "identyczny favicon", 0.85, False),
        ):
            xa, xb = set(ia.get(key) or []), set(ib.get(key) or [])
            if xa or xb:
                any_data = any_data or (xa and xb)
            common = xa & xb
            if common:
                sig.append(val)
                ev.append(("infrastruktura", val, f"{label.capitalize()}: {', '.join(sorted(common)[:3])}"))
                if is_hard:
                    hard.append(label)
        for key, label in (("wallets", "portfel kryptowalut"), ("phones", "numer telefonu"), ("emails", "adres e-mail")):
            common = set(a["entities"][key]) & set(b["entities"][key])
            if common:
                sig.append(1.0)
                any_data = True
                ev.append(("infrastruktura", 1.0, f"Wspólny {label}: {', '.join(sorted(common)[:2])}"))
                hard.append(f"wspólny {label}")
        if ia["ips"] and ib["ips"]:
            any_data = True
            common = set(ia["ips"]) & set(ib["ips"])
            if common:
                shared_net = any(SHARED_NETS.search(n or "") for n in ia["ip_nets"] + ib["ip_nets"])
                v = 0.3 if shared_net else 0.7
                sig.append(v)
                ev.append(("infrastruktura", v, f"Wspólny adres IP: {', '.join(sorted(common)[:2])}" + (" (współdzielony CDN – słaby sygnał)" if shared_net else "")))
        if ia["nameservers"] and ib["nameservers"]:
            any_data = True
            common = set(ia["nameservers"]) & set(ib["nameservers"])
            if common:
                generic = all(GENERIC_NS.search(n) for n in common)
                v = 0.2 if generic else (0.6 if len(common) >= 2 else 0.4)
                sig.append(v)
                ev.append(("infrastruktura", v, f"Wspólne serwery DNS: {', '.join(sorted(common)[:2])}" + (" (domyślne u rejestratora)" if generic else "")))
        dom_j = None
        if ia["dom_shingles"] and ib["dom_shingles"]:
            any_data = True
            dom_j = _jacc(ia["dom_shingles"], ib["dom_shingles"])
            if dom_j and dom_j >= 0.5:
                sig.append(dom_j * 0.85)
                ev.append(("infrastruktura", dom_j * 0.85, f"Ten sam szkielet strony (scam-kit), podobieństwo DOM = {dom_j:.2f}"))
        if ia["registrars"] and ib["registrars"]:
            any_data = True
            if set(ia["registrars"]) & set(ib["registrars"]) and ia["created"] and ib["created"]:
                try:
                    from datetime import date
                    dd = min(abs((date.fromisoformat(x) - date.fromisoformat(y)).days) for x in ia["created"] for y in ib["created"])
                    if dd <= 3:
                        sig.append(0.5)
                        ev.append(("infrastruktura", 0.5, f"Ten sam rejestrator i rejestracja domen w odstępie {dd} dni"))
                except Exception:
                    pass
        # ten sam scam-kit (prawie identyczny DOM) postawiony na tej samej infrastrukturze
        # (wspólne IP poza CDN lub wspólne, niedomyślne serwery DNS) = jeden operator
        if dom_j is not None and dom_j >= 0.9 and any(v >= 0.6 for v in sig if v not in (dom_j * 0.85,)):
            hard.append("ten sam scam-kit na tej samej infrastrukturze")
        if any_data or sig:
            ch["infrastruktura"] = _noisy_or(sig) if sig else 0.0

        # --- wynik
        avail = {k: v for k, v in ch.items() if v is not None}
        if not avail:
            return 0.0, ch, ev, hard, "brak danych"
        wsum = sum(WEIGHTS[k] for k in avail)
        raw = sum(WEIGHTS[k] * v for k, v in avail.items()) / wsum
        coverage = wsum / sum(WEIGHTS.values())
        score = raw * (0.6 + 0.4 * min(1.0, coverage / 0.5))
        # wielokanałowa zgodność: ≥3 niezależne kanały z sygnałem ≥ 0.5 → wzmocnienie
        strong_ch = sum(1 for v in avail.values() if v >= 0.5)
        if strong_ch >= 3:
            score = max(score, min(0.95, score + 0.08 * (strong_ch - 2)))
        if hard:
            score = max(score, HARD_SCORE)
        score = float(min(1.0, score))

        dup = ("identyczny tekst" in hard or (ch.get("tekst", 0) >= 0.95 and ch.get("wizual", 1.0) >= 0.9)) or \
              ("identyczna kreacja" in hard and ch.get("tekst", 1.0) >= 0.85)
        rel = "duplikat" if dup else "wariant" if score >= VARIANT_T else "powiązanie" if score >= LINK_T else "podobieństwo" if score >= FAMILY_T else "brak"
        ev.sort(key=lambda e: -e[1])
        return score, ch, ev, hard, rel

    # ---------------------------------------------------------------- macierz
    def matrix(self):
        n = len(self.items)
        S = np.zeros((n, n))
        self.edges = {}
        for i in range(n):
            S[i, i] = 1.0
            for j in range(i + 1, n):
                ts = self.T[i, j] if (self.T is not None and self.has_text[i] and self.has_text[j]) else None
                sc, ch, ev, hard, rel = self.pair(self.items[i], self.items[j], ts)
                S[i, j] = S[j, i] = sc
                if sc >= FAMILY_T or hard:
                    self.edges[(i, j)] = {"score": round(sc, 3), "channels": {k: round(v, 3) for k, v in ch.items() if v is not None},
                                          "evidence": [{"channel": c, "weight": round(w, 2), "text": t} for c, w, t in ev], "hard": hard, "relation": rel}
        self.S = S
        return S

    # ---------------------------------------------------------------- klastry
    def cluster(self, link_t=LINK_T):
        n = len(self.items)
        if not hasattr(self, "S"):
            self.matrix()
        if n == 0:
            self.labels = np.array([], dtype=int)
            return self.labels
        # (a) atomy z twardych dowodów
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for (i, j), e in self.edges.items():
            if e["hard"]:
                parent[find(i)] = find(j)
        roots = sorted({find(i) for i in range(n)})
        atom_of = {r: k for k, r in enumerate(roots)}
        atoms = [[] for _ in roots]
        for i in range(n):
            atoms[atom_of[find(i)]].append(i)
        m = len(atoms)
        # (b) średnie wiązanie na atomach
        if m == 1:
            atom_lab = np.array([0])
        else:
            A = np.zeros((m, m))
            for x in range(m):
                for y in range(x + 1, m):
                    A[x, y] = A[y, x] = self.S[np.ix_(atoms[x], atoms[y])].mean()
            D = 1 - A
            np.fill_diagonal(D, 0)
            atom_lab = AgglomerativeClustering(n_clusters=None, metric="precomputed", linkage="average",
                                               distance_threshold=1 - link_t).fit_predict(D)
        lab = np.zeros(n, dtype=int)
        for a, members in enumerate(atoms):
            for i in members:
                lab[i] = atom_lab[a]
        # numeracja stabilna: kampanie posortowane malejąco wg liczności, potem wg najstarszego id
        groups = defaultdict(list)
        for i, l in enumerate(lab):
            groups[l].append(i)
        order = sorted(groups.values(), key=lambda g: (-len(g), min(self.ids[i] for i in g)))
        self.labels = np.zeros(n, dtype=int)
        for k, g in enumerate(order):
            for i in g:
                self.labels[i] = k
        return self.labels

    # ---------------------------------------------------------------- opis kampanii
    def campaigns(self):
        lab = self.labels
        out = []
        for k in sorted(set(lab.tolist())):
            mem = [i for i in range(len(lab)) if lab[i] == k]
            its = [self.items[i] for i in mem]
            intra = [self.S[i, j] for x, i in enumerate(mem) for j in mem[x + 1:]]
            cnt = lambda f: Counter(v for it in its for v in f(it))
            persons = cnt(lambda it: it["entities"]["persons"]).most_common(4)
            topics = cnt(lambda it: it["narrative"]["topics"]).most_common(3)
            domains = cnt(lambda it: it["infra"]["domains"]).most_common(6)
            trackers = cnt(lambda it: it["infra"]["trackers"]).most_common(4)
            kws = cnt(lambda it: it["narrative"]["keywords"][:8]).most_common(8)
            manip = cnt(lambda it: it["narrative"]["manipulation"]).most_common(4)
            brands = cnt(lambda it: it["entities"]["brands"]).most_common(4)
            ev_types = Counter()
            for x, i in enumerate(mem):
                for j in mem[x + 1:]:
                    e = self.edges.get((min(i, j), max(i, j)))
                    if e:
                        for evd in e["evidence"]:
                            ev_types[evd["channel"]] += 1
            dates = sorted(it["date"][:10] for it in its if it.get("date"))
            dups = sum(1 for x, i in enumerate(mem) for j in mem[x + 1:] if self.edges.get((min(i, j), max(i, j)), {}).get("relation") == "duplikat")
            name_parts = [p for p, _ in persons[:1]] + [t for t, _ in topics[:1]] + [d for d, _ in domains[:1]]
            out.append({
                "id": int(k), "code": f"K-{k + 1:03d}", "size": len(mem), "members": [self.ids[i] for i in mem],
                "name": " · ".join(name_parts) or (kws[0][0] if kws else f"Kampania {k + 1}"),
                "cohesion": round(float(np.mean(intra)), 3) if intra else 1.0,
                "persons": persons, "topics": topics, "domains": domains, "trackers": trackers,
                "keywords": kws, "manipulation": manip, "brands": brands, "evidence_types": ev_types.most_common(),
                "first_seen": dates[0] if dates else None, "last_seen": dates[-1] if dates else None, "duplicates": dups,
                "labels": Counter(it.get("label") for it in its if it.get("label")).most_common(3),
            })
        # rodziny kampanii (podobne, ale nie te same)
        fam = []
        for a in out:
            for b in out:
                if a["id"] >= b["id"]:
                    continue
                block = self.S[np.ix_([self.idx[i] for i in a["members"]], [self.idx[i] for i in b["members"]])]
                mean = float(block.mean())
                if mean >= FAMILY_T or block.max() >= 0.6:
                    bi = np.unravel_index(block.argmax(), block.shape)
                    i, j = self.idx[a["members"][bi[0]]], self.idx[b["members"][bi[1]]]
                    e = self.edges.get((min(i, j), max(i, j)), {})
                    fam.append({"a": a["id"], "b": b["id"], "mean": round(mean, 3), "max": round(float(block.max()), 3),
                                "evidence": [x["text"] for x in e.get("evidence", [])[:3]]})
        self.families = fam
        return out

    # ---------------------------------------------------------------- nowy materiał
    def assign(self, rec):
        """Porównuje nowy materiał z przetworzonym zbiorem (bez dopisywania go)."""
        if not self.items:
            return {"decision": "nowy wzorzec", "reason": "Zbiór jest pusty – to pierwszy materiał.", "similar": [], "campaign": None,
                    "confidence": 1.0, "duplicate_of": None, "campaign_scores": []}
        tv = self.text_sim_vector(rec)
        rows = []
        for k, it in enumerate(self.items):
            ts = tv[k] if (tv is not None and self.has_text[k]) else None
            sc, ch, ev, hard, rel = self.pair(rec, it, ts)
            rows.append((k, sc, ch, ev, hard, rel))
        rows.sort(key=lambda r: -r[1])
        per = defaultdict(list)
        for k, sc, *_ in rows:
            per[int(self.labels[k])].append(sc)
        stats = sorted(((c, float(np.mean(v)), float(np.max(v))) for c, v in per.items()), key=lambda x: (-x[1], -x[2]))
        best_c, best_mean, best_max = stats[0]
        hard_hit = next((r for r in rows if r[4]), None)
        dup = next((r for r in rows if r[5] == "duplikat"), None)
        if hard_hit and int(self.labels[hard_hit[0]]) != best_c:
            best_c = int(self.labels[hard_hit[0]])
            best_mean = float(np.mean(per[best_c]))
            best_max = float(np.max(per[best_c]))
        if best_mean >= ASSIGN_T or best_max >= HARD_SCORE:
            decision = "duplikat" if dup else "znana kampania"
            reason = f"Średnie podobieństwo do kampanii {best_mean:.2f}, najbliższy materiał {best_max:.2f}."
            conf = min(0.99, 0.5 * best_mean + 0.5 * best_max)
        else:
            decision, best_c, conf = "nowy wzorzec", None, 1 - best_max
            reason = f"Żadna kampania nie przekracza progu (najlepsza średnia {best_mean:.2f}, maks. {best_max:.2f})."
            if best_max >= FAMILY_T:
                reason += " Materiał przypomina jednak istniejące kampanie – możliwa nowa odsłona tej samej rodziny."
        similar = [{
            "id": self.ids[k], "title": self.items[k]["title"], "score": round(sc, 3), "relation": rel,
            "campaign": int(self.labels[k]), "channels": {c: round(v, 2) for c, v in ch.items() if v is not None},
            "evidence": [{"channel": c, "weight": round(w, 2), "text": t} for c, w, t in ev[:6]], "hard": hard,
        } for k, sc, ch, ev, hard, rel in rows[:8] if sc >= 0.15]
        return {"decision": decision, "campaign": best_c, "confidence": round(conf, 3), "reason": reason,
                "duplicate_of": self.ids[dup[0]] if dup else None, "similar": similar,
                "campaign_scores": [{"campaign": c, "mean": round(m, 3), "max": round(x, 3)} for c, m, x in stats[:5]]}
