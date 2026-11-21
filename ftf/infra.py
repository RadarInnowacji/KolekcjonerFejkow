"""Pozyskiwanie publicznie dostępnych metadanych infrastruktury.

Wszystko na bibliotece standardowej Pythona (urllib, socket, ssl), z krótkimi timeoutami.
Każde źródło jest niezależne: brak jednego (strona nie działa, RDAP milczy) nie przerywa
analizy – zapisujemy tylko to, co udało się zdobyć, plus informację o błędzie.

Źródła:
- łańcuch przekierowań HTTP + przekierowania meta-refresh / JS (location=…)
- HTML strony: tytuł, linki wychodzące, formularze, trackery, odcisk struktury DOM
- favicon (hash SHA-256)
- DNS (adresy A) – socket.getaddrinfo
- RDAP (rdap.org) – rejestrator, data rejestracji, serwery nazw
- certyfikat TLS (moduł ssl) – wystawca, SAN, ważność
- crt.sh – historia certyfikatów dla domeny (inne subdomeny / powiązane nazwy)
"""
import hashlib
import json
import re
import socket
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 FollowTheFake-research"
TIMEOUT = 8

# Domeny „wspólne dla wszystkich” – nie mogą łączyć kampanii (każda reklama linkuje do FB itp.)
GENERIC_DOMAINS = {
    "facebook.com", "fb.com", "fb.me", "instagram.com", "google.com", "googleapis.com", "gstatic.com", "youtube.com",
    "youtu.be", "tiktok.com", "twitter.com", "x.com", "t.co", "bit.ly", "tinyurl.com", "cutt.ly", "linktr.ee",
    "cloudflare.com", "cdnjs.cloudflare.com", "jsdelivr.net", "unpkg.com", "googletagmanager.com", "google-analytics.com",
    "doubleclick.net", "w3.org", "schema.org", "apple.com", "microsoft.com", "whatsapp.com", "wa.me", "t.me", "telegram.org",
    "gov.pl", "wikipedia.org", "fonts.googleapis.com", "jquery.com", "bootstrapcdn.com", "fontawesome.com",
}
SHORTENERS = {"bit.ly", "tinyurl.com", "cutt.ly", "is.gd", "t.co", "shorturl.at", "rb.gy", "tiny.cc", "ow.ly", "goo.gl"}
MULTI_SUFFIX = {
    "com.pl", "net.pl", "org.pl", "info.pl", "biz.pl", "waw.pl", "edu.pl", "gov.pl", "co.uk", "org.uk", "com.ua",
    "com.br", "com.au", "co.jp", "com.tr", "com.cn", "co.in", "com.mx", "com.ar", "co.za", "github.io", "netlify.app",
    "vercel.app", "pages.dev", "web.app", "firebaseapp.com", "herokuapp.com", "blogspot.com", "wixsite.com",
    "weebly.com", "glitch.me", "onrender.com", "azurewebsites.net", "cloudfront.net", "workers.dev",
}

TRACKER_PATTERNS = {
    "facebook_pixel": [r"fbq\(\s*['\"]init['\"]\s*,\s*['\"](\d{10,20})", r"facebook\.com/tr\?id=(\d{10,20})"],
    "google_analytics": [r"\b(UA-\d{4,10}-\d{1,4})\b", r"\b(G-[A-Z0-9]{8,12})\b"],
    "google_tag_manager": [r"\b(GTM-[A-Z0-9]{5,9})\b"],
    "google_ads": [r"\b(AW-\d{8,12})\b"],
    "tiktok_pixel": [r"ttq\.load\(\s*['\"]([A-Z0-9]{15,25})"],
    "yandex_metrika": [r"ym\(\s*(\d{6,10})\s*,\s*['\"]init"],
    "keitaro_tds": [r"(keitaro|kclick|/click\.php\?key=)"],
}


def registered_domain(host: str) -> str:
    host = (host or "").lower().strip(".").split(":")[0]
    if re.fullmatch(r"[\d.]+", host) or ":" in host:  # adres IP – zostaje bez zmian
        return host
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    last2 = ".".join(parts[-2:])
    if last2 in MULTI_SUFFIX:
        return ".".join(parts[-3:])
    return last2


def host_of(url: str) -> str:
    try:
        u = urllib.parse.urlparse(url if "://" in url else "http://" + url)
        return (u.hostname or "").lower()
    except Exception:
        return ""


def normalize_url(url: str) -> str:
    url = url.strip().strip("\"'<>()[]")
    if not re.match(r"^[a-z]+://", url, re.I):
        url = "https://" + url
    return url


URL_RE = re.compile(
    r"((?:https?://|www\.)[^\s<>\"'()\]]+|\b[a-z0-9][a-z0-9-]{1,62}(?:\.[a-z0-9-]{1,62})*\.(?:pl|com|net|org|info|online|site|shop|top|xyz|click|live|store|app|io|me|co|icu|buzz|cfd|sbs|lol|pro|biz|group|club|space|website|fun|today|news|life|world|eu|cz|de|ru|ua)\b(?:/[^\s<>\"'()]*)?)",
    re.I,
)


def find_urls(text: str):
    out = []
    for m in URL_RE.findall(text or ""):
        u = m.rstrip(".,;:!?)")
        if "@" in u:
            continue
        out.append(u)
    seen, res = set(), []
    for u in out:
        k = u.lower()
        if k not in seen:
            seen.add(k)
            res.append(u)
    return res[:50]


# ---------------------------------------------------------------- HTML parsing
class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self._in_title = "", False
        self.links, self.scripts, self.iframes, self.forms, self.inputs = [], [], [], 0, []
        self.icons, self.meta, self.tags, self.text = [], {}, [], []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append(tag)
        if tag == "title":
            self._in_title = True
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "script":
            self._skip += 1
            if a.get("src"):
                self.scripts.append(a["src"])
        elif tag == "style":
            self._skip += 1
        elif tag == "iframe" and a.get("src"):
            self.iframes.append(a["src"])
        elif tag == "form":
            self.forms += 1
        elif tag in ("input", "select", "textarea"):
            self.inputs.append((a.get("name") or a.get("type") or a.get("id") or "").lower()[:30])
        elif tag == "link" and "icon" in (a.get("rel") or "").lower() and a.get("href"):
            self.icons.append(a["href"])
        elif tag == "meta":
            k = (a.get("name") or a.get("property") or a.get("http-equiv") or "").lower()
            if k:
                self.meta[k] = (a.get("content") or "")[:300]

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip and data.strip():
            self.text.append(data.strip())


def dom_shingles(tags, k=4, limit=400):
    """Odcisk struktury strony: zbiór k-gramów sekwencji tagów (hashowanych do int).
    Strony z tego samego „zestawu do oszustw” (scam kit) mają bardzo podobny szkielet,
    nawet gdy treść i domena są inne."""
    seq = [t for t in tags if t not in ("br", "hr", "wbr")][:3000]
    out = set()
    for i in range(len(seq) - k + 1):
        out.add(int(hashlib.md5("/".join(seq[i:i + k]).encode()).hexdigest()[:8], 16))
    return sorted(out)[:limit] if len(out) > limit else sorted(out)


def extract_trackers(html: str):
    found = {}
    for name, pats in TRACKER_PATTERNS.items():
        for p in pats:
            for m in re.findall(p, html, re.I):
                v = m if isinstance(m, str) else m[0]
                found.setdefault(name, set()).add(v if name != "keitaro_tds" else "keitaro")
    return sorted(f"{k}:{v}" for k, vals in found.items() for v in vals)


def parse_html(html: str, base_url: str = ""):
    p = _PageParser()
    try:
        p.feed(html)
    except Exception:
        pass
    abs_links = []
    for href in p.links + p.iframes:
        if href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        abs_links.append(urllib.parse.urljoin(base_url, href) if base_url else href)
    out_domains = sorted({registered_domain(host_of(u)) for u in abs_links if host_of(u)})
    script_domains = sorted({registered_domain(host_of(urllib.parse.urljoin(base_url, s))) for s in p.scripts if s.startswith(("http", "//"))})
    js_redirects = re.findall(r"(?:window\.)?location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]", html)[:5]
    refresh = p.meta.get("refresh", "")
    m = re.search(r"url\s*=\s*['\"]?([^'\";]+)", refresh, re.I)
    if m:
        js_redirects.insert(0, m.group(1))
    sensitive = [i for i in p.inputs if re.search(r"(card|karta|cvv|cvc|pesel|phone|tel|blik|pass|haslo|iban|konto)", i)]
    return {
        "title": re.sub(r"\s+", " ", p.title).strip()[:200],
        "text": " ".join(p.text)[:20000],
        "out_domains": out_domains[:60],
        "script_domains": script_domains[:40],
        "forms": p.forms,
        "inputs": sorted(set(p.inputs))[:40],
        "sensitive_inputs": sorted(set(sensitive)),
        "icons": p.icons[:3],
        "meta": {k: v for k, v in p.meta.items() if k in ("description", "og:title", "og:image", "og:site_name", "generator", "robots", "keywords", "x-campaign-key")},
        "dom_shingles": dom_shingles(p.tags),
        "trackers": extract_trackers(html),
        "client_redirects": [urllib.parse.urljoin(base_url, r) for r in js_redirects],
    }


# ---------------------------------------------------------------- network
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def _open(url, method="GET", accept="text/html,*/*"):
    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=ctx))
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": accept, "Accept-Language": "pl,en;q=0.8"})
    try:
        return opener.open(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as e:
        return e  # 3xx/4xx/5xx – nadal mają nagłówki


def fetch_chain(url, max_hops=8):
    """Podąża za przekierowaniami ręcznie, zapisując każdy krok."""
    chain, cur, html, final_status, ctype = [], url, "", None, ""
    for _ in range(max_hops):
        r = _open(cur)
        status = getattr(r, "status", None) or getattr(r, "code", None)
        chain.append({"url": cur, "status": status})
        loc = r.headers.get("Location") if r.headers else None
        if status in (301, 302, 303, 307, 308) and loc:
            cur = urllib.parse.urljoin(cur, loc)
            continue
        final_status = status
        ctype = (r.headers.get("Content-Type") or "") if r.headers else ""
        try:
            raw = r.read(3_000_000)
            enc = "utf-8"
            m = re.search(r"charset=([\w-]+)", ctype)
            if m:
                enc = m.group(1)
            html = raw.decode(enc, errors="replace")
        except Exception:
            html = ""
        break
    return chain, cur, html, final_status, ctype


def fetch_bytes(url, limit=2_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read(limit)


def dns_a(host):
    try:
        return sorted({ai[4][0] for ai in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)})[:8]
    except Exception:
        return []


def rdap_domain(domain):
    try:
        data = json.loads(fetch_bytes(f"https://rdap.org/domain/{domain}", 500_000).decode("utf-8", "replace"))
    except Exception as e:
        return {"error": f"RDAP: {type(e).__name__}"}
    out = {"registrar": None, "created": None, "nameservers": []}
    for ev in data.get("events", []):
        if ev.get("eventAction") == "registration":
            out["created"] = (ev.get("eventDate") or "")[:10]
    for ent in data.get("entities", []):
        if "registrar" in (ent.get("roles") or []):
            v = ent.get("vcardArray")
            if v and len(v) > 1:
                for item in v[1]:
                    if item[0] == "fn":
                        out["registrar"] = str(item[3])[:120]
            out["registrar"] = out["registrar"] or ent.get("handle")
    out["nameservers"] = sorted({(ns.get("ldhName") or "").lower().strip(".") for ns in data.get("nameservers", []) if ns.get("ldhName")})
    return out


def rdap_ip(ip):
    try:
        data = json.loads(fetch_bytes(f"https://rdap.org/ip/{ip}", 300_000).decode("utf-8", "replace"))
        return {"net_name": data.get("name"), "country": data.get("country"), "net_handle": data.get("handle")}
    except Exception:
        return {}


def tls_info(host):
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=TIMEOUT) as s:
            with ctx.wrap_socket(s, server_hostname=host) as ss:
                c = ss.getpeercert()
        issuer = dict(x[0] for x in c.get("issuer", []))
        sans = sorted({v.lower() for t, v in c.get("subjectAltName", []) if t == "DNS"})
        return {"issuer": issuer.get("organizationName") or issuer.get("commonName"), "not_before": c.get("notBefore"), "sans": sans[:50]}
    except Exception as e:
        return {"error": f"TLS: {type(e).__name__}"}


def crtsh(domain):
    try:
        data = json.loads(fetch_bytes(f"https://crt.sh/?q=%25.{domain}&output=json", 3_000_000).decode("utf-8", "replace"))
        names = set()
        for row in data[:500]:
            for n in (row.get("name_value") or "").split("\n"):
                names.add(n.strip().lower().lstrip("*."))
        return sorted(names)[:80]
    except Exception:
        return []


def domain_age_days(created):
    try:
        d = datetime.fromisoformat(created[:10]).replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - d).days
    except Exception:
        return None


def investigate_url(url, deep=True):
    """Pełne „śledztwo” dla jednego adresu URL. Zwraca słownik; nigdy nie rzuca wyjątku."""
    url = normalize_url(url)
    res = {"input_url": url, "status": "unknown", "errors": []}
    host = host_of(url)
    res["host"] = host
    res["domain"] = registered_domain(host)
    try:
        chain, final, html, status, ctype = fetch_chain(url)
        res["redirect_chain"] = chain
        res["final_url"] = final
        res["http_status"] = status
        res["status"] = "ok" if status and status < 400 else "error"
        if html and "html" in (ctype or "html"):
            page = parse_html(html, final)
            res["page"] = page
            # przekierowanie po stronie klienta (meta refresh / JS) – próbujemy jeden krok
            if page["client_redirects"] and deep:
                nxt = page["client_redirects"][0]
                if host_of(nxt) and nxt.split("#")[0].rstrip("/") != final.split("#")[0].rstrip("/"):
                    try:
                        c2, f2, h2, s2, t2 = fetch_chain(nxt)
                        res["redirect_chain"] += [{"url": x["url"], "status": x["status"], "client_side": True} for x in c2]
                        res["final_url"] = f2
                        if h2:
                            p2 = parse_html(h2, f2)
                            p2["trackers"] = sorted(set(p2["trackers"]) | set(page["trackers"]))
                            res["page"] = p2
                    except Exception as e:
                        res["errors"].append(f"client redirect: {type(e).__name__}")
            # favicon
            icon = (res["page"]["icons"] or ["/favicon.ico"])[0]
            try:
                b = fetch_bytes(urllib.parse.urljoin(res["final_url"], icon), 300_000)
                if b and len(b) > 50:
                    res["favicon_sha"] = hashlib.sha256(b).hexdigest()[:16]
            except Exception:
                pass
    except Exception as e:
        res["status"] = "unreachable"
        res["errors"].append(f"HTTP: {type(e).__name__}: {str(e)[:80]}")

    final_host = host_of(res.get("final_url") or url)
    res["final_domain"] = registered_domain(final_host)
    res["ips"] = dns_a(final_host) if final_host else []
    if not deep:
        return res
    if res["ips"]:
        res["ip_net"] = rdap_ip(res["ips"][0])
    doms = {res["domain"], res["final_domain"]} - {""}
    res["rdap"] = {d: rdap_domain(d) for d in doms if d not in GENERIC_DOMAINS}
    if final_host and res["status"] != "unreachable":
        res["tls"] = tls_info(final_host)
    res["crtsh"] = crtsh(res["final_domain"]) if res["final_domain"] and res["final_domain"] not in GENERIC_DOMAINS else []
    return res
