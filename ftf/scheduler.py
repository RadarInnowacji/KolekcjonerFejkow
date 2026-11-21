"""Harmonogram (scheduler): cykliczne wyszukiwanie reklam i aktualizacja informacji.

1. Biblioteka Reklam Meta (Ad Library API, endpoint ads_archive) – wyszukiwanie po słowach
   kluczowych dla reklam, które dotarły do PL. Wymaga tokenu dostępu (META_ACCESS_TOKEN):
   konto deweloperskie Meta + potwierdzenie tożsamości (https://www.facebook.com/ads/library/api).
   Reklamy komercyjne są dostępne w API, gdy dotarły do UE (przepisy DSA).
2. Każda pobrana reklama przechodzi ekstrakcję cech i porównanie ze zbiorem. Zapisywane są
   tylko materiały podejrzane: powiązane z istniejącą kampanią albo z sygnałami oszustwa.
3. Ponowne sprawdzanie znanych domen (czy działają, dokąd przekierowują) – krótko żyjące
   domeny znikają, a nowe przekierowania ujawniają kolejne odsłony kampanii.
"""
import json
import os
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime

from . import infra, store

DEFAULT = {"enabled": False, "interval_min": 60, "keywords": ["inwestycja zysk", "Lewandowski inwestuje", "dopłata paczka", "zwrot podatku"],
           "countries": ["PL"], "recheck_domains": True, "api_version": "v21.0"}
_state = {"running": False, "thread": None, "last_run": None}


def config():
    c = dict(DEFAULT)
    c.update(store.kv_get("scheduler", {}) or {})
    c["token_present"] = bool(os.environ.get("META_ACCESS_TOKEN"))
    return c


def save_config(c):
    keep = {k: c[k] for k in DEFAULT if k in c}
    store.kv_set("scheduler", keep)
    return config()


def _log(msg):
    log = store.kv_get("scheduler_log", []) or []
    log.insert(0, {"t": datetime.now().isoformat()[:19], "msg": msg})
    store.kv_set("scheduler_log", log[:100])


def fetch_meta_ads(keyword, cfg, limit=25):
    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("Brak META_ACCESS_TOKEN – ustaw token Ad Library API")
    q = {
        "search_terms": keyword, "ad_type": "ALL", "ad_active_status": "ALL",
        "ad_reached_countries": json.dumps(cfg.get("countries") or ["PL"]),
        "fields": "id,page_id,page_name,ad_creative_bodies,ad_creative_link_titles,ad_creative_link_captions,ad_creative_link_descriptions,ad_delivery_start_time,ad_snapshot_url,publisher_platforms",
        "limit": str(limit), "access_token": token,
    }
    url = f"https://graph.facebook.com/{cfg.get('api_version', 'v21.0')}/ads_archive?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": infra.UA}), timeout=30) as r:
        return json.loads(r.read()).get("data", [])


def run_once(app):
    """app: obiekt z metodami analyze_and_maybe_save(rec_kwargs) i known_domains()."""
    cfg = config()
    added = checked = 0
    if os.environ.get("META_ACCESS_TOKEN"):
        seen = set(store.kv_get("seen_ads", []) or [])
        for kw in cfg["keywords"]:
            try:
                ads = fetch_meta_ads(kw, cfg)
            except Exception as e:
                _log(f"Ad Library ({kw}): błąd {type(e).__name__}: {str(e)[:120]}")
                continue
            for ad in ads:
                if ad.get("id") in seen:
                    continue
                seen.add(ad.get("id"))
                checked += 1
                text = "\n".join((ad.get("ad_creative_bodies") or []) + (ad.get("ad_creative_link_titles") or []) +
                                 (ad.get("ad_creative_link_captions") or []) + (ad.get("ad_creative_link_descriptions") or []))
                caption_urls = [c for c in (ad.get("ad_creative_link_captions") or []) if "." in c]
                kw_args = dict(text=text, url=caption_urls[0] if caption_urls else "", source=f"Meta Ad Library: „{kw}”",
                               title=(ad.get("page_name") or "") + ": " + (text[:80] if text else ""),
                               date=ad.get("ad_delivery_start_time"), external_id=ad.get("id"))
                if app.analyze_and_maybe_save(kw_args, only_suspicious=True):
                    added += 1
        store.kv_set("seen_ads", sorted(seen)[-5000:])
    else:
        _log("Ad Library pominięte – brak tokenu META_ACCESS_TOKEN")
    if cfg.get("recheck_domains"):
        status = store.kv_get("domain_status", {}) or {}
        for d in app.known_domains()[:40]:
            try:
                chain, final, _, st, _ = infra.fetch_chain("https://" + d, max_hops=5)
                entry = {"t": datetime.now().isoformat()[:16], "status": st, "final": infra.registered_domain(infra.host_of(final))}
            except Exception as e:
                entry = {"t": datetime.now().isoformat()[:16], "status": "nie działa", "error": type(e).__name__}
            hist = status.get(d, [])
            if not hist or hist[-1].get("status") != entry["status"] or hist[-1].get("final") != entry.get("final"):
                hist.append(entry)
            status[d] = hist[-10:]
        store.kv_set("domain_status", status)
    _state["last_run"] = datetime.now().isoformat()[:19]
    _log(f"Przebieg zakończony: sprawdzono {checked} nowych reklam, dodano {added} podejrzanych.")
    return {"checked": checked, "added": added}


def start(app):
    if _state["thread"]:
        return

    def loop():
        while True:
            cfg = config()
            if cfg.get("enabled"):
                _state["running"] = True
                try:
                    run_once(app)
                except Exception as e:
                    _log(f"Błąd przebiegu: {type(e).__name__}: {e}")
                _state["running"] = False
                time.sleep(max(5, int(cfg.get("interval_min", 60))) * 60)
            else:
                time.sleep(20)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    _state["thread"] = t


def status():
    return {"config": config(), "running": _state["running"], "last_run": _state["last_run"],
            "log": store.kv_get("scheduler_log", [])[:30], "domains": store.kv_get("domain_status", {})}
