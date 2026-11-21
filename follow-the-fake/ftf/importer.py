"""Import zbiorów danych w różnych formatach (odporność na „różnice w formacie materiałów”).

Obsługiwane: manifest JSON (lista obiektów lub {"items": [...]}), JSON Lines, CSV,
folder z plikami, archiwum ZIP z dowolną z powyższych struktur.
Nazwy pól są mapowane elastycznie (np. text/body/ad_creative_bodies, url/link/landing_url,
image/screenshot/file, label/campaign/cluster).
"""
import csv
import io
import json
import os
import zipfile

from . import extract

TEXT_KEYS = ["text", "body", "content", "ad_text", "ad_creative_bodies", "ad_creative_body", "description", "caption", "message", "opis", "tresc", "treść", "log"]
TITLE_KEYS = ["title", "headline", "ad_creative_link_titles", "ad_creative_link_title", "page_name", "tytul", "tytuł", "name"]
URL_KEYS = ["url", "link", "landing_url", "link_url", "landing", "domain", "final_url", "adres", "ad_snapshot_url"]
FILE_KEYS = ["image", "screenshot", "file", "path", "image_path", "media", "plik", "zrzut", "video", "html"]
LABEL_KEYS = ["label", "campaign", "campaign_id", "cluster", "kampania", "group", "ground_truth"]
DATE_KEYS = ["date", "created", "ad_delivery_start_time", "ad_creation_time", "timestamp", "data"]
ID_KEYS = ["id", "ad_id", "ad_archive_id", "external_id", "uid"]
MEDIA_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".mp4", ".mov", ".webm", ".html", ".htm", ".txt", ".eml", ".log")


def _first(d, keys):
    low = {str(k).lower(): v for k, v in d.items() if k is not None}
    for k in keys:
        v = low.get(k.lower())
        if v not in (None, "", []):
            if isinstance(v, list):
                v = "\n".join(str(x) for x in v if x)
            return v
    return None


class Source:
    """Abstrakcja nad folderem / ZIP-em – pozwala odczytać plik po ścieżce względnej."""

    def __init__(self, path=None, zbytes=None):
        self.path, self.zip = path, None
        if zbytes is not None:
            self.zip = zipfile.ZipFile(io.BytesIO(zbytes))
            names = self.zip.namelist()
            tops = {n.split("/")[0] for n in names if "/" in n}
            self.prefix = (tops.pop() + "/") if len(tops) == 1 and all(n.startswith(next(iter(tops | {""}), "")) for n in names) else ""

    def list(self):
        if self.zip:
            return [n[len(self.prefix):] for n in self.zip.namelist() if not n.endswith("/") and n.startswith(self.prefix)]
        out = []
        for r, _, fs in os.walk(self.path):
            for f in fs:
                out.append(os.path.relpath(os.path.join(r, f), self.path).replace("\\", "/"))
        return out

    def read(self, rel):
        rel = rel.replace("\\", "/").lstrip("./")
        if self.zip:
            for cand in (self.prefix + rel, rel):
                try:
                    return self.zip.read(cand)
                except KeyError:
                    pass
            base = os.path.basename(rel)
            for n in self.zip.namelist():
                if n.endswith("/" + base) or n == base:
                    return self.zip.read(n)
            return None
        p = os.path.join(self.path, rel)
        if os.path.exists(p):
            with open(p, "rb") as f:
                return f.read()
        return None


def _records_from_source(src: Source):
    files = src.list()
    manifest = next((f for f in files if os.path.basename(f).lower() in ("manifest.json", "dataset.json", "data.json", "metadata.json")), None)
    if not manifest:
        manifest = next((f for f in files if f.lower().endswith((".json", ".jsonl", ".csv"))), None)
    if manifest:
        raw = src.read(manifest).decode("utf-8-sig", "replace")
        return parse_table(raw, manifest), src
    # brak manifestu – każdy plik multimedialny to osobny materiał
    return [{"file": f, "id": os.path.splitext(os.path.basename(f))[0]} for f in files if f.lower().endswith(MEDIA_EXT)], src


def parse_table(raw, name=""):
    name = name.lower()
    if name.endswith(".csv") or name.endswith(".tsv"):
        try:
            dialect = csv.Sniffer().sniff(raw[:5000], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.DictReader(io.StringIO(raw), dialect=dialect))
        return [{k: v for k, v in r.items() if k is not None} for r in rows]
    if name.endswith(".jsonl"):
        return [json.loads(l) for l in raw.splitlines() if l.strip()]
    data = json.loads(raw)
    if isinstance(data, dict):
        for k in ("items", "data", "ads", "materials", "records"):
            if isinstance(data.get(k), list):
                return data[k]
        return [data]
    return data


def to_material(row, src=None, network=True, deep=False, source="import"):
    row = {k: v for k, v in row.items() if k is not None}
    files = []
    for k in FILE_KEYS:
        v = row.get(k)
        if not v:
            continue
        for p in (v if isinstance(v, list) else [v]):
            b = src.read(str(p)) if src else None
            if b:
                files.append({"name": os.path.basename(str(p)), "bytes": b})
    text = _first(row, TEXT_KEYS) or ""
    url = _first(row, URL_KEYS) or ""
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    for k in ("trackers", "nameservers", "ips", "registrar", "registrars", "created", "redirect_domains", "favicons", "persons", "cert_names"):
        if row.get(k) and k not in meta:
            meta[k] = row[k] if not isinstance(row[k], str) or k in ("registrar", "created") else [x.strip() for x in row[k].split(";") if x.strip()]
    return extract.build_material(
        text=str(text), url=str(url) if url and "facebook.com/ads/archive" not in str(url) else "", files=files, meta=meta,
        label=str(_first(row, LABEL_KEYS)) if _first(row, LABEL_KEYS) is not None else None,
        title=_first(row, TITLE_KEYS), date=str(_first(row, DATE_KEYS) or "") or None,
        external_id=str(_first(row, ID_KEYS)) if _first(row, ID_KEYS) is not None else None,
        network=network, deep=deep, source=source,
    ), files


def load(path=None, zbytes=None, raw=None, name=""):
    """Zwraca (lista wierszy, źródło plików)."""
    if raw is not None:
        return parse_table(raw, name), None
    src = Source(path=path, zbytes=zbytes)
    return _records_from_source(src)
