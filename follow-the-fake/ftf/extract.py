"""Zamiana dowolnego materiału wejściowego na ujednolicony rekord cech.

Wejście (dowolna kombinacja): adres URL, tekst / log komunikacji / nazwa produktu,
pliki (zrzut ekranu, kreacja, wideo, zapisana strona HTML, .txt/.eml/.log), oraz – przy
imporcie zbioru – gotowe metadane i etykieta kampanii.

Wyjście: słownik z grupami cech:
  text       – połączony tekst (wpisany + OCR + treść strony)
  narrative  – słowa kluczowe, tematy, sygnały manipulacji, kwoty
  entities   – osoby (wizerunki), marki/logotypy, telefony, e-maile, portfele krypto
  visual     – hashe percepcyjne kreacji/klatek, histogram kolorów, hashe twarzy
  infra      – domeny, przekierowania, IP, NS, rejestrator, wiek domeny, TLS/SAN, crt.sh,
               trackery (Pixel/GA/GTM…), favicon, odcisk struktury DOM, formularze
  quality    – które kanały są dostępne, a których brakuje (niekompletne dane)
"""
import base64
import hashlib
import mimetypes
import re
from collections import Counter
from datetime import datetime, timezone

from . import infra, lexicon, llm, visual

PHONE_RE = re.compile(r"(?<!\d)(?:\+?48[\s-]?)?(?:\d{3}[\s-]?\d{3}[\s-]?\d{3})(?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
WALLET_RE = re.compile(r"\b(bc1[a-z0-9]{25,59}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}|0x[a-fA-F0-9]{40}|T[1-9A-HJ-NP-Za-km-z]{33})\b")
AMOUNT_RE = re.compile(r"(\d[\d\s.,]{0,12})\s?(zł|pln|€|eur|\$|usd)", re.I)


def keywords(text, n=15):
    text = infra.URL_RE.sub(" ", text or "")
    words = re.findall(r"[a-ząćęłńóśźż]{4,}", (text or "").lower())
    words = [w for w in words if w not in lexicon.STOPWORDS and lexicon.norm(w) not in lexicon.STOPWORDS]
    return [w for w, _ in Counter(words).most_common(n)]


def text_fingerprint(text):
    t = re.sub(r"[^a-z0-9 ]", " ", lexicon.norm(text))
    t = re.sub(r"\s+", " ", t).strip()
    return hashlib.sha1(t.encode()).hexdigest()[:16] if len(t) > 20 else None


def _guess_kind(name, mime):
    name = (name or "").lower()
    mime = mime or mimetypes.guess_type(name)[0] or ""
    if mime.startswith("image/") or name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")):
        return "image"
    if mime.startswith("video/") or name.endswith((".mp4", ".mov", ".webm", ".avi", ".mkv")):
        return "video"
    if "html" in mime or name.endswith((".html", ".htm", ".mhtml")):
        return "html"
    if mime.startswith("text/") or name.endswith((".txt", ".log", ".eml", ".csv", ".md", ".json")):
        return "text"
    return "other"


def build_material(*, text="", url="", files=None, meta=None, label=None, source="upload",
                   title=None, date=None, network=True, deep=True, external_id=None):
    files = files or []
    meta = meta or {}
    log, texts, kinds = [], [], []
    vis = {"images": [], "frames": [], "faces": [], "hist": None}
    qr_urls, llm_persons, llm_brands, llm_urls, narrative_hints = [], [], [], [], []

    if text:
        texts.append(text)
        kinds.append("text")

    # ---------------------------------------------------------------- pliki
    page_from_html = None
    for f in files:
        raw = f.get("bytes")
        if raw is None and f.get("b64"):
            b64 = f["b64"].split(",", 1)[-1]
            raw = base64.b64decode(b64)
        if not raw:
            continue
        kind = _guess_kind(f.get("name"), f.get("mime"))
        kinds.append(kind)
        try:
            if kind == "image":
                r = visual.analyze_image_bytes(raw)
                vis["images"].append({k: r[k] for k in ("dhash", "phash", "dhash_full", "w", "h") if k in r})
                vis["hist"] = vis["hist"] or r["hist"]
                vis["faces"] += r["faces"]
                qr_urls += r["qr"]
                if r["ocr"]:
                    texts.append(r["ocr"])
                    log.append(f"OCR: {len(r['ocr'])} znaków z {f.get('name') or 'obrazu'}")
                if r["qr"]:
                    log.append(f"Kod QR: {', '.join(r['qr'])}")
                d = llm.describe_image(raw, f.get("mime") or "image/jpeg")
                if d and not d.get("error"):
                    if d.get("text") and len(d["text"]) > len(r["ocr"] or "") * 0.8:
                        texts.append(d["text"])
                    llm_persons += d.get("persons") or []
                    llm_brands += d.get("brands") or []
                    llm_urls += d.get("urls") or []
                    narrative_hints += [x for x in (d.get("narrative"), d.get("template")) if x]
                    log.append("Model wizyjny: opis kreacji dodany")
            elif kind == "video":
                r = visual.analyze_video_bytes(raw)
                if r.get("error"):
                    log.append(r["error"])
                else:
                    vis["frames"] += r["frames"]
                    vis["faces"] += r["faces"]
                    qr_urls += r["qr"]
                    if r["ocr"]:
                        texts.append(r["ocr"])
                    log.append(f"Wideo: {len(r['frames'])} klatek, {r.get('duration')} s")
            elif kind == "html":
                html = raw.decode("utf-8", "replace")
                page_from_html = infra.parse_html(html, f.get("url") or "")
                texts.append(page_from_html["title"] + "\n" + page_from_html["text"][:5000])
                log.append("Strona HTML: struktura, trackery, linki")
            elif kind == "text":
                texts.append(raw.decode("utf-8", "replace")[:50000])
        except Exception as e:
            log.append(f"Błąd pliku {f.get('name')}: {type(e).__name__}")

    full_text = "\n".join(t for t in texts if t).strip()

    # ---------------------------------------------------------------- URL-e
    urls = []
    if url:
        urls.append(url.strip())
    urls += qr_urls + llm_urls + infra.find_urls(full_text)
    if meta.get("urls"):
        urls += list(meta["urls"])
    seen, uniq = set(), []
    for u in urls:
        k = u.lower().rstrip("/")
        if k and k not in seen:
            seen.add(k)
            uniq.append(u)
    urls = uniq[:30]

    investigations = []
    if network:
        targets = [u for u in urls if infra.registered_domain(infra.host_of(u)) not in infra.GENERIC_DOMAINS or infra.registered_domain(infra.host_of(u)) in infra.SHORTENERS]
        for i, u in enumerate(targets[:3]):
            inv = infra.investigate_url(u, deep=deep and i == 0)
            investigations.append(inv)
            log.append(f"URL {inv['host']}: {inv['status']}" + (f" → {inv.get('final_domain')}" if inv.get('final_domain') and inv.get('final_domain') != inv.get('domain') else ""))
            if inv.get("page") and inv["page"].get("text"):
                full_text = (full_text + "\n" + inv["page"]["title"] + "\n" + inv["page"]["text"][:5000]).strip()

    # ---------------------------------------------------------------- infrastruktura
    I = {
        "domains": set(), "hosts": set(), "redirect_domains": [], "ips": set(), "nameservers": set(), "registrars": set(),
        "created": [], "tls_issuers": set(), "cert_names": set(), "trackers": set(), "favicons": set(),
        "dom_shingles": [], "titles": [], "out_domains": set(), "sensitive_inputs": set(), "status": [], "ip_nets": set(),
        "campaign_keys": set(),
    }
    for u in urls:
        h = infra.host_of(u)
        if h:
            I["hosts"].add(h)
            I["domains"].add(infra.registered_domain(h))
    for inv in investigations:
        I["status"].append(inv.get("status"))
        for step in inv.get("redirect_chain", []):
            d = infra.registered_domain(infra.host_of(step["url"]))
            if d and d not in I["redirect_domains"]:
                I["redirect_domains"].append(d)
            I["domains"].add(d)
        if inv.get("final_domain"):
            I["domains"].add(inv["final_domain"])
        I["ips"].update(inv.get("ips", []))
        if inv.get("ip_net", {}).get("net_name"):
            I["ip_nets"].add(inv["ip_net"]["net_name"])
        for d, rd in (inv.get("rdap") or {}).items():
            if rd.get("registrar"):
                I["registrars"].add(rd["registrar"])
            if rd.get("created"):
                I["created"].append(rd["created"])
            I["nameservers"].update(rd.get("nameservers", []))
        t = inv.get("tls") or {}
        if t.get("issuer"):
            I["tls_issuers"].add(t["issuer"])
        I["cert_names"].update(t.get("sans", []))
        I["cert_names"].update(inv.get("crtsh", []))
        if inv.get("favicon_sha"):
            I["favicons"].add(inv["favicon_sha"])
        p = inv.get("page")
        if p:
            I["trackers"].update(p["trackers"])
            I["dom_shingles"] = I["dom_shingles"] or p["dom_shingles"]
            if p["title"]:
                I["titles"].append(p["title"])
            I["out_domains"].update(p["out_domains"])
            I["sensitive_inputs"].update(p["sensitive_inputs"])
            if p["meta"].get("x-campaign-key"):
                I["campaign_keys"].add(p["meta"]["x-campaign-key"])
    if page_from_html:
        I["trackers"].update(page_from_html["trackers"])
        I["dom_shingles"] = I["dom_shingles"] or page_from_html["dom_shingles"]
        I["out_domains"].update(page_from_html["out_domains"])
        I["sensitive_inputs"].update(page_from_html["sensitive_inputs"])
        if page_from_html["title"]:
            I["titles"].append(page_from_html["title"])
    # metadane dostarczone w zbiorze danych (np. wcześniej zebrane WHOIS) – łączymy z pozyskanymi
    for k_src, k_dst in (("ips", "ips"), ("nameservers", "nameservers"), ("trackers", "trackers"), ("favicons", "favicons"),
                         ("registrars", "registrars"), ("cert_names", "cert_names"), ("domains", "domains"), ("out_domains", "out_domains")):
        v = meta.get(k_src)
        if v:
            I[k_dst].update(v if isinstance(v, (list, tuple, set)) else [v])
    if meta.get("registrar"):
        I["registrars"].add(meta["registrar"])
    if meta.get("created"):
        I["created"].append(meta["created"])
    if meta.get("redirect_domains"):
        I["redirect_domains"] += [d for d in meta["redirect_domains"] if d not in I["redirect_domains"]]
    if meta.get("dom_shingles"):
        I["dom_shingles"] = meta["dom_shingles"]

    I["domains"].discard("")
    domains_specific = sorted(d for d in I["domains"] if d not in infra.GENERIC_DOMAINS)
    ages = [a for a in (infra.domain_age_days(c) for c in I["created"]) if a is not None]

    # ---------------------------------------------------------------- byty i narracja
    persons = set(lexicon.find_persons(full_text)) | {p for p in llm_persons if p}
    persons |= {f["person"] for f in vis["faces"] if f.get("person")}
    if meta.get("persons"):
        persons |= set(meta["persons"])
    brands = set(lexicon.find_brands(full_text)) | set(llm_brands)
    # marka w tytule strony, a domena obca = podszywanie (np. „NASK | …” na nuvio.group)
    impersonation = []
    for b in brands:
        bn = lexicon.norm(b).replace(" ", "")
        if bn and len(bn) >= 3 and any(lexicon.norm(t).find(lexicon.norm(b)) >= 0 for t in I["titles"]) and not any(bn in d.replace("-", "").replace(".", "") for d in domains_specific):
            impersonation.append(b)

    amounts = sorted({re.sub(r"\s", "", a) + c.lower() for a, c in AMOUNT_RE.findall(full_text)})[:10]
    rec = {
        "external_id": external_id,
        "source": source,
        "label": label,
        "title": title or (I["titles"][0] if I["titles"] else (full_text[:80].replace("\n", " ") if full_text else (urls[0] if urls else "materiał"))),
        "date": date or datetime.now(timezone.utc).isoformat()[:19],
        "kinds": sorted(set(kinds + (["url"] if urls else []))),
        "text": full_text[:30000],
        "text_fp": text_fingerprint(full_text),
        "urls": urls,
        "narrative": {
            "keywords": keywords(full_text),
            "topics": lexicon.find_topics(full_text),
            "manipulation": lexicon.find_manipulation(full_text),
            "amounts": amounts,
            "hints": narrative_hints[:4],
        },
        "entities": {
            "persons": sorted(persons),
            "brands": sorted(brands),
            "impersonation": sorted(impersonation),
            "phones": sorted({re.sub(r"[\s-]", "", p) for p in PHONE_RE.findall(full_text)})[:10],
            "emails": sorted(set(EMAIL_RE.findall(full_text)))[:10],
            "wallets": sorted(set(WALLET_RE.findall(full_text)))[:10],
        },
        "visual": {
            "images": vis["images"] + (meta.get("images") or []),
            "frames": vis["frames"][:12],
            "faces": [{"hash": f["hash"], "person": f.get("person")} for f in vis["faces"]][:10],
            "hist": vis["hist"] or meta.get("hist"),
        },
        "infra": {
            "domains": domains_specific,
            "hosts": sorted(I["hosts"])[:20],
            "redirect_domains": I["redirect_domains"][:15],
            "ips": sorted(I["ips"])[:10],
            "ip_nets": sorted(I["ip_nets"]),
            "nameservers": sorted(I["nameservers"])[:8],
            "registrars": sorted(I["registrars"]),
            "created": sorted(set(I["created"])),
            "min_age_days": min(ages) if ages else None,
            "tls_issuers": sorted(I["tls_issuers"]),
            "cert_names": sorted(I["cert_names"])[:80],
            "trackers": sorted(I["trackers"]),
            "favicons": sorted(I["favicons"]),
            "dom_shingles": I["dom_shingles"],
            "titles": I["titles"][:3],
            "out_domains": sorted(d for d in I["out_domains"] if d not in infra.GENERIC_DOMAINS)[:30],
            "sensitive_inputs": sorted(I["sensitive_inputs"]),
            "campaign_keys": sorted(I["campaign_keys"]),
            "reachability": I["status"],
        },
        "investigations": [{k: v for k, v in inv.items() if k != "page"} | ({"page_title": inv["page"]["title"], "trackers": inv["page"]["trackers"], "forms": inv["page"]["forms"]} if inv.get("page") else {}) for inv in investigations],
        "log": log,
    }
    rec["quality"] = channel_availability(rec)
    return rec


def channel_availability(rec):
    v, i, e, n = rec["visual"], rec["infra"], rec["entities"], rec["narrative"]
    ch = {
        "tekst": len(rec["text"]) >= 30,
        "wizual": bool(v["images"] or v["frames"]),
        "osoby": bool(e["persons"] or v["faces"]),
        "domeny": bool(i["domains"]),
        "infrastruktura": bool(i["ips"] or i["nameservers"] or i["trackers"] or i["favicons"] or i["dom_shingles"] or i["registrars"] or i["cert_names"]),
        "narracja": bool(n["topics"] or n["manipulation"]),
    }
    missing = [k for k, ok in ch.items() if not ok]
    unreachable = [s for s in i["reachability"] if s == "unreachable"]
    return {"channels": ch, "missing": missing, "unreachable_pages": len(unreachable), "completeness": round(sum(ch.values()) / len(ch), 2)}
