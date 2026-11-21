"""Follow the Fake – demonstrator (serwer WWW + API).

Uruchom:  python app.py   →   http://localhost:8000
Zmienne środowiskowe (opcjonalne):
  PORT=8000, FTF_DB=ścieżka do bazy SQLite, ANTHROPIC_API_KEY (opis kreacji modelem),
  META_ACCESS_TOKEN (scheduler – Biblioteka Reklam Meta), OCR_LANGS=pol+eng
"""
import base64
import io
import json
import mimetypes
import os
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PIL import Image

from ftf import engine, evaluate, export, extract, importer, llm, scheduler, store, visual

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(ROOT, "static")
DEMO = os.path.join(ROOT, "data", "demo")
_lock = threading.RLock()
_cache = {"eng": None, "camps": None, "version": 0, "built": -1}
_jobs = {}


# ---------------------------------------------------------------- engine cache
def invalidate():
    with _lock:
        _cache["version"] += 1


def get_engine():
    with _lock:
        if _cache["built"] != _cache["version"] or _cache["eng"] is None:
            items = store.all_items()
            e = engine.Engine(items)
            e.matrix()
            e.cluster()
            _cache["camps"] = e.campaigns()
            _cache["eng"] = e
            _cache["built"] = _cache["version"]
        return _cache["eng"], _cache["camps"]


def make_thumb(files):
    for f in files or []:
        raw = f.get("bytes") or (base64.b64decode(f["b64"].split(",", 1)[-1]) if f.get("b64") else None)
        if not raw:
            continue
        kind = extract._guess_kind(f.get("name"), f.get("mime"))
        try:
            if kind == "image":
                im = Image.open(io.BytesIO(raw)).convert("RGB")
            elif kind == "video" and visual.cv2 is not None:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as t:
                    t.write(raw)
                cap = visual.cv2.VideoCapture(t.name)
                ok, fr = cap.read()
                cap.release()
                os.remove(t.name)
                if not ok:
                    continue
                im = Image.fromarray(visual.cv2.cvtColor(fr, visual.cv2.COLOR_BGR2RGB))
            else:
                continue
            im.thumbnail((360, 360))
            b = io.BytesIO()
            im.save(b, "JPEG", quality=72)
            return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
        except Exception:
            continue
    return None


# ---------------------------------------------------------------- serializacja
def item_summary(e, k, thumbs=None):
    it = e.items[k]
    return {
        "thumb": e.ids[k] in thumbs if thumbs is not None else False,
        "id": e.ids[k], "title": it["title"][:140], "date": (it.get("date") or "")[:10], "kinds": it["kinds"], "source": it.get("source"),
        "label": it.get("label"), "campaign": int(e.labels[k]), "persons": it["entities"]["persons"], "topics": it["narrative"]["topics"],
        "domains": it["infra"]["domains"][:4], "trackers": it["infra"]["trackers"][:3], "completeness": it["quality"]["completeness"],
        "missing": it["quality"]["missing"], "external_id": it.get("external_id"),
    }


def state():
    e, camps = get_engine()
    n = len(e.items)
    dups = sum(1 for v in e.edges.values() if v["relation"] == "duplikat")
    doms = {d for it in e.items for d in it["infra"]["domains"]}
    return {
        "stats": {"materials": n, "campaigns": sum(1 for c in camps if c["size"] > 1), "singletons": sum(1 for c in camps if c["size"] == 1),
                  "duplicates": dups, "domains": len(doms), "links": sum(1 for v in e.edges.values() if v["score"] >= engine.LINK_T)},
        "campaigns": camps, "families": getattr(e, "families", []),
        "items": [item_summary(e, k, store.thumb_ids()) for k in range(n)] if n else [],
        "config": {"link_t": engine.LINK_T, "family_t": engine.FAMILY_T, "assign_t": engine.ASSIGN_T, "weights": engine.WEIGHTS},
        "capabilities": {"llm": llm.enabled(), "faces": visual.face_status(), "ocr": bool(visual.shutil.which("tesseract") or os.environ.get("TESSERACT_CMD")),
                         "opencv": visual.cv2 is not None, "meta_token": bool(os.environ.get("META_ACCESS_TOKEN"))},
    }


def graph():
    e, camps = get_engine()
    th = store.thumb_ids()
    nodes = [{"id": e.ids[k], "c": int(e.labels[k]), "t": it["title"][:80], "p": it["entities"]["persons"][:2], "d": it["infra"]["domains"][:2],
              "img": e.ids[k] in th} for k, it in enumerate(e.items)]
    edges = [{"a": e.ids[i], "b": e.ids[j], "s": v["score"], "r": v["relation"], "h": bool(v["hard"]),
              "ev": [x["text"] for x in v["evidence"][:5]], "ch": v["channels"]} for (i, j), v in e.edges.items()]
    return {"nodes": nodes, "edges": edges, "campaigns": [{"id": c["id"], "code": c["code"], "name": c["name"], "size": c["size"]} for c in camps],
            "families": getattr(e, "families", [])}


def item_detail(rid):
    e, camps = get_engine()
    if rid not in e.idx:
        return None
    k = e.idx[rid]
    it = dict(e.items[k])
    neigh = []
    for (i, j), v in e.edges.items():
        if k in (i, j):
            o = j if i == k else i
            neigh.append({"id": e.ids[o], "title": e.items[o]["title"][:100], "campaign": int(e.labels[o]), **{x: v[x] for x in ("score", "relation", "evidence", "hard", "channels")}})
    neigh.sort(key=lambda x: -x["score"])
    it["campaign"] = int(e.labels[k])
    it["neighbors"] = neigh[:15]
    it["thumb"] = store.thumb(rid)
    it.pop("text_fp", None)
    return it


# ---------------------------------------------------------------- akcje
class App:
    def analyze(self, body):
        files = body.get("files") or []
        rec = extract.build_material(text=body.get("text", ""), url=body.get("url", ""), files=files,
                                     network=bool(body.get("network", True)), deep=True, source="analiza ręczna",
                                     label=body.get("label") or None)
        e, camps = get_engine()
        res = e.assign(rec)
        saved_id = None
        if body.get("save", True) and (rec["text"] or rec["urls"] or rec["visual"]["images"] or rec["visual"]["frames"]):
            saved_id = store.add(rec, make_thumb(files))
            invalidate()
            e2, camps2 = get_engine()
            res["saved_id"] = saved_id
            res["final_campaign"] = int(e2.labels[e2.idx[saved_id]])
            res["final_campaign_code"] = f"K-{res['final_campaign'] + 1:03d}"
        if res.get("campaign") is not None:
            c = camps[res["campaign"]]
            res["campaign_code"], res["campaign_name"] = c["code"], c["name"]
        rec.pop("text_fp", None)
        res["material"] = rec
        res["thumb"] = make_thumb(files)
        return res

    def analyze_and_maybe_save(self, kw, only_suspicious=True):
        rec = extract.build_material(network=True, deep=False, **kw)
        e, _ = get_engine()
        res = e.assign(rec)
        suspicious = res["decision"] != "nowy wzorzec" or rec["narrative"]["manipulation"] or (rec["entities"]["persons"] and rec["narrative"]["topics"])
        if suspicious or not only_suspicious:
            store.add(rec)
            invalidate()
            return True
        return False

    def known_domains(self):
        e, _ = get_engine()
        return sorted({d for it in e.items for d in it["infra"]["domains"]})

    def import_rows(self, rows, src, network, job):
        n = len(rows)
        job.update(total=n, done=0)
        for k, r in enumerate(rows):
            try:
                rec, files = importer.to_material(r, src, network=network)
                store.add(rec, make_thumb(files))
            except Exception as ex:
                job.setdefault("errors", []).append(f"wiersz {k + 1}: {type(ex).__name__}: {ex}")
            job["done"] = k + 1
        invalidate()
        get_engine()
        job["finished"] = True


APP = App()


def start_import(rows, src, network):
    jid = str(int(time.time() * 1000))
    job = {"id": jid, "finished": False, "done": 0, "total": len(rows)}
    _jobs[jid] = job
    threading.Thread(target=APP.import_rows, args=(rows, src, network, job), daemon=True).start()
    return job


# ---------------------------------------------------------------- HTTP
class H(BaseHTTPRequestHandler):
    server_version = "FollowTheFake/1.0"

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def _send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 300 * 1024 * 1024:
            raise ValueError("Za duże dane (limit 300 MB)")
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        try:
            if p in ("/", "/index.html"):
                return self._file(os.path.join(STATIC, "index.html"))
            if p.startswith("/static/"):
                return self._file(os.path.join(STATIC, os.path.normpath(p[8:]).lstrip("/\\.")))
            if p == "/api/state":
                return self._send(200, state())
            if p == "/api/graph":
                return self._send(200, graph())
            if p.startswith("/api/item/"):
                d = item_detail(int(p.rsplit("/", 1)[1]))
                return self._send(200 if d else 404, d or {"error": "nie ma takiego materiału"})
            if p.startswith("/api/thumb/"):
                t = store.thumb(int(p.rsplit("/", 1)[1]))
                if not t:
                    return self._send(404, {"error": "brak"})
                return self._send(200, base64.b64decode(t.split(",", 1)[1]), "image/jpeg", {"Cache-Control": "max-age=3600"})
            if p == "/api/evaluate":
                e, _ = get_engine()
                return self._send(200, evaluate.evaluate(e))
            if p.startswith("/api/job/"):
                return self._send(200, _jobs.get(p.rsplit("/", 1)[1], {"error": "brak zadania"}))
            if p == "/api/scheduler":
                return self._send(200, scheduler.status())
            if p == "/api/methodology":
                with open(os.path.join(ROOT, "METODYKA.md"), encoding="utf-8") as f:
                    return self._send(200, {"md": f.read()})
            if p.startswith("/api/export/"):
                e, camps = get_engine()
                kind = p.rsplit("/", 1)[1]
                if kind == "graph.cypher":
                    return self._send(200, export.cypher(e, camps), "text/plain; charset=utf-8", {"Content-Disposition": "attachment; filename=follow_the_fake.cypher"})
                if kind == "materialy.csv":
                    return self._send(200, export.csv_items(e), "text/csv; charset=utf-8", {"Content-Disposition": "attachment; filename=materialy.csv"})
                if kind == "powiazania.csv":
                    return self._send(200, export.csv_edges(e), "text/csv; charset=utf-8", {"Content-Disposition": "attachment; filename=powiazania.csv"})
                if kind == "wyniki.json":
                    data = {"campaigns": camps, "families": e.families, "items": [item_summary(e, k) for k in range(len(e.items))],
                            "edges": [{"a": e.ids[i], "b": e.ids[j], **v} for (i, j), v in e.edges.items()], "evaluation": evaluate.evaluate(e)}
                    return self._send(200, data, "application/json; charset=utf-8", {"Content-Disposition": "attachment; filename=wyniki.json"})
            return self._send(404, {"error": "nie znaleziono"})
        except Exception as ex:
            traceback.print_exc()
            return self._send(500, {"error": f"{type(ex).__name__}: {ex}"})

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            body = self._json()
            if p == "/api/analyze":
                return self._send(200, APP.analyze(body))
            if p == "/api/import":
                network = bool(body.get("network", False))
                if body.get("zip_b64"):
                    rows, src = importer.load(zbytes=base64.b64decode(body["zip_b64"].split(",", 1)[-1]))
                elif body.get("raw"):
                    rows, src = importer.load(raw=body["raw"], name=body.get("name", "data.json"))
                else:
                    return self._send(400, {"error": "Brak danych do importu"})
                return self._send(200, start_import(rows, src, network))
            if p == "/api/demo":
                rows, src = importer.load(path=DEMO)
                return self._send(200, start_import(rows, src, False))
            if p == "/api/clear":
                store.clear()
                invalidate()
                return self._send(200, {"ok": True})
            if p == "/api/delete":
                store.delete(int(body["id"]))
                invalidate()
                return self._send(200, {"ok": True})
            if p == "/api/scheduler":
                return self._send(200, {"config": scheduler.save_config(body)})
            if p == "/api/scheduler/run":
                threading.Thread(target=lambda: (scheduler.run_once(APP), invalidate()), daemon=True).start()
                return self._send(200, {"ok": True})
            return self._send(404, {"error": "nie znaleziono"})
        except Exception as ex:
            traceback.print_exc()
            return self._send(500, {"error": f"{type(ex).__name__}: {ex}"})

    def _file(self, path):
        path = os.path.abspath(path)
        if not path.startswith(STATIC) or not os.path.isfile(path):
            return self._send(404, {"error": "nie znaleziono"})
        with open(path, "rb") as f:
            data = f.read()
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        self._send(200, data, ctype)


def main():
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    scheduler.start(APP)
    srv = ThreadingHTTPServer((host, port), H)
    print(f"\n  Follow the Fake działa:  http://localhost:{port}\n  (zamknij to okno, aby zatrzymać)\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
