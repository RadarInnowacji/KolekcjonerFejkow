"""Cechy wizualne: hashe percepcyjne, kolorystyka, OCR, kody QR, twarze, klatki wideo.

- dHash/pHash (64 bity) – odporne na przeskalowanie, kompresję i drobne zmiany; odległość
  Hamminga ≤ 6 oznacza praktycznie ten sam obraz, ≤ 14 – ten sam szablon / kreację po edycji.
- histogram kolorów HSV – podobny „szablon produkcyjny” (paleta, układ barw).
- OCR (Tesseract, pol+eng) – tekst z kreacji, z niego linki i nazwiska.
- QR (OpenCV) – linki ukryte w kodach QR (wprost wskazane w opisie wyzwania).
- twarze: wykrycie (YuNet lub Haar) + hash wycinka twarzy; opcjonalnie rozpoznanie
  tożsamości (SFace) względem małej bazy referencyjnej data/faces/<Imię Nazwisko>/*.jpg.
"""
import glob
import io
import os
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageOps

try:
    import cv2
except Exception:  # OpenCV opcjonalne
    cv2 = None

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODELS = os.path.join(ROOT, "models")
FACES_DB = os.path.join(ROOT, "data", "faces")


# ------------------------------------------------------------------ hashing
def _to_gray(img: Image.Image, size):
    return np.asarray(ImageOps.grayscale(img).resize(size, Image.LANCZOS), dtype=np.float32)


def dhash(img: Image.Image) -> str:
    a = _to_gray(img, (9, 8))
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    return "%016x" % int("".join("1" if b else "0" for b in bits), 2)


def phash(img: Image.Image) -> str:
    a = _to_gray(img, (32, 32))
    if cv2 is not None:
        d = cv2.dct(a)[:8, :8]
    else:  # DCT-II przez macierz – wolniejsze, ale bez OpenCV
        n = 32
        k = np.arange(n)
        m = np.cos(np.pi * (2 * k[None, :] + 1) * k[:, None] / (2 * n))
        d = (m @ a @ m.T)[:8, :8]
    med = np.median(d.flatten()[1:])
    bits = (d > med).flatten()
    return "%016x" % int("".join("1" if b else "0" for b in bits), 2)


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def color_hist(img: Image.Image):
    """Znormalizowany histogram 4x4x4 w HSV (64 wartości)."""
    hsv = np.asarray(img.convert("RGB").resize((96, 96)).convert("HSV"), dtype=np.int32)
    h, s, v = hsv[..., 0] // 64, hsv[..., 1] // 64, hsv[..., 2] // 64
    idx = (h * 16 + s * 4 + v).flatten()
    hist = np.bincount(idx, minlength=64).astype(np.float32)
    hist /= hist.sum() or 1
    return [round(float(x), 4) for x in hist]


def hist_sim(a, b):
    if not a or not b:
        return None
    a, b = np.asarray(a), np.asarray(b)
    return float(np.minimum(a, b).sum())  # intersection, 0..1


# ------------------------------------------------------------------ OCR / QR
def ocr(img: Image.Image) -> str:
    exe = shutil.which("tesseract") or os.environ.get("TESSERACT_CMD")
    if not exe or not os.path.exists(exe):
        return ""
    im = img.convert("L")
    if im.width < 1000:  # małe zrzuty – powiększ dla lepszego OCR
        f = 1000 / im.width
        im = im.resize((int(im.width * f), int(im.height * f)), Image.LANCZOS)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as t:
        im.save(t.name)
        path = t.name
    try:
        langs = os.environ.get("OCR_LANGS", "pol+eng")
        r = subprocess.run([exe, path, "stdout", "-l", langs, "--psm", "3"], capture_output=True, timeout=60)
        if r.returncode != 0 and "pol" in langs:
            r = subprocess.run([exe, path, "stdout", "-l", "eng", "--psm", "3"], capture_output=True, timeout=60)
        return r.stdout.decode("utf-8", "replace").strip()
    except Exception:
        return ""
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def decode_qr(img: Image.Image):
    if cv2 is None:
        return []
    arr = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    found = set()
    det = cv2.QRCodeDetector()
    tries = [arr]
    h, w = arr.shape[:2]
    if max(h, w) < 400:
        tries.append(cv2.resize(arr, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    tries.append(cv2.copyMakeBorder(gray, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255))
    for t in tries:
        try:
            ok, vals, _, _ = det.detectAndDecodeMulti(t)
            if ok:
                found.update(v for v in vals if v)
        except Exception:
            pass
        try:
            v = det.detectAndDecode(t)[0]
            if v:
                found.add(v)
        except Exception:
            pass
        if found:
            break
    return sorted(found)


# ------------------------------------------------------------------ faces
_face = {"det": None, "rec": None, "haar": None, "db": None, "loaded": False}


def _load_face_models():
    if _face["loaded"] or cv2 is None:
        return
    _face["loaded"] = True
    yunet = glob.glob(os.path.join(MODELS, "face_detection_yunet*.onnx"))
    sface = glob.glob(os.path.join(MODELS, "face_recognition_sface*.onnx"))
    try:
        if yunet:
            _face["det"] = cv2.FaceDetectorYN.create(yunet[0], "", (320, 320), 0.8, 0.3, 50)
        if sface:
            _face["rec"] = cv2.FaceRecognizerSF.create(sface[0], "")
    except Exception:
        _face["det"] = _face["rec"] = None
    haar = os.path.join(getattr(getattr(cv2, "data", None), "haarcascades", "") or "", "haarcascade_frontalface_default.xml")
    if not _face["det"] and os.path.exists(haar):
        _face["haar"] = cv2.CascadeClassifier(haar)
    if _face["det"] is not None and _face["rec"] is not None and os.path.isdir(FACES_DB):
        db = []
        for person_dir in sorted(glob.glob(os.path.join(FACES_DB, "*"))):
            if not os.path.isdir(person_dir):
                continue
            for p in glob.glob(os.path.join(person_dir, "*")):
                try:
                    emb = _embed_faces(cv2.imread(p))
                    if emb:
                        db.append((os.path.basename(person_dir), emb[0][1]))
                except Exception:
                    pass
        _face["db"] = db


def _embed_faces(bgr):
    det, rec = _face["det"], _face["rec"]
    h, w = bgr.shape[:2]
    det.setInputSize((w, h))
    _, faces = det.detect(bgr)
    out = []
    if faces is None:
        return out
    for f in faces[:5]:
        box = [int(x) for x in f[:4]]
        emb = None
        if rec is not None:
            aligned = rec.alignCrop(bgr, f)
            emb = rec.feature(aligned).flatten()
        out.append((box, emb))
    return out


def faces(img: Image.Image):
    """Zwraca listę twarzy: {box, hash, person?, score?}."""
    if cv2 is None:
        return []
    _load_face_models()
    bgr = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    boxes = []
    try:
        if _face["det"] is not None:
            for box, emb in _embed_faces(bgr):
                ident, score = None, None
                if emb is not None and _face["db"]:
                    best = max(((n, float(_face["rec"].match(emb.reshape(1, -1), e.reshape(1, -1), 0))) for n, e in _face["db"]), key=lambda x: x[1])  # 0 = FR_COSINE
                    if best[1] >= 0.363:  # próg zalecany przez autorów SFace dla cosinusa
                        ident, score = best
                boxes.append((box, ident, score))
        elif _face["haar"] is not None:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            for (x, y, w, h) in _face["haar"].detectMultiScale(gray, 1.1, 6, minSize=(48, 48))[:5]:
                boxes.append(([int(x), int(y), int(w), int(h)], None, None))
    except Exception:
        return []
    out = []
    for (x, y, w, h), ident, score in boxes:
        x, y = max(0, x), max(0, y)
        crop = img.crop((x, y, x + w, y + h))
        if crop.width < 20 or crop.height < 20:
            continue
        out.append({"box": [x, y, w, h], "hash": dhash(crop), "person": ident, "score": round(score, 3) if score else None})
    return out


def face_status():
    _load_face_models()
    return {
        "detector": "YuNet" if _face["det"] is not None else ("Haar" if _face["haar"] is not None else None),
        "recognizer": "SFace" if _face["rec"] is not None else None,
        "reference_people": sorted({n for n, _ in (_face["db"] or [])}),
    }


# ------------------------------------------------------------------ kadrowanie kreacji
def content_crop(img: Image.Image):
    """Wycina samą kreację ze zrzutu ekranu aplikacji.

    Zrzuty z Facebooka/Instagrama mają wspólną ramkę interfejsu („Sponsorowane”, „Lubię to”).
    Hash całego zrzutu porównywałby ramki, a nie reklamy – dwie różne kampanie w tej samej
    ramce wyglądałyby podobnie. Szukamy najdłuższego pasa wierszy odróżniającego się od tła
    interfejsu; gdy się nie uda – bierzemy środkowy kadr. Zwraca (obraz, czy_przycięto)."""
    w, h = img.size
    g = np.asarray(ImageOps.grayscale(img).resize((max(1, w // 4), max(1, h // 4))), dtype=np.float32)
    # 1) obcięcie jednolitych marginesów
    bg = float(np.median(np.concatenate([g[0], g[-1], g[:, 0], g[:, -1]])))
    diff = np.abs(g - bg) > 12
    rows, cols = np.where(diff.any(axis=1))[0], np.where(diff.any(axis=0))[0]
    if len(rows) and len(cols):
        y0, y1, x0, x1 = rows[0] * 4, (rows[-1] + 1) * 4, cols[0] * 4, (cols[-1] + 1) * 4
    else:
        y0, y1, x0, x1 = 0, h, 0, w
    if h < w * 1.3:  # zwykła kreacja (kwadrat/poziom) – tylko marginesy
        changed = (y1 - y0) < h * 0.97 or (x1 - x0) < w * 0.97
        return (img.crop((x0, y0, x1, y1)) if changed else img), changed
    # 2) wysoki zrzut ekranu – najdłuższy pas „treściowych” wierszy (odbiegających od tła UI)
    row_content = (np.abs(g.mean(axis=1) - bg) > 10) | (g.std(axis=1) > 35)
    best, cur, start, bstart = 0, 0, 0, 0
    for i, v in enumerate(row_content):
        if v:
            if cur == 0:
                start = i
            cur += 1
            if cur > best:
                best, bstart = cur, start
        else:
            cur = 0
    if best * 4 >= h * 0.3:
        return img.crop((0, bstart * 4, w, min(h, (bstart + best) * 4))), True
    return img.crop((0, int(h * 0.12), w, int(h * 0.72))), True


# ------------------------------------------------------------------ public API
def analyze_image_bytes(data: bytes, do_ocr=True):
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    crop, cropped = content_crop(img)
    res = {
        "w": img.width, "h": img.height,
        # hashe liczone na samej kreacji (bez ramki aplikacji); hash całości zostaje do wykrywania
        # dokładnych duplikatów tego samego zrzutu
        "dhash": dhash(crop), "phash": phash(crop), "hist": color_hist(crop),
        "qr": decode_qr(img),
        "faces": faces(img),
        "ocr": ocr(img) if do_ocr else "",
    }
    if cropped:
        res["dhash_full"] = dhash(img)
    return res


def analyze_video_bytes(data: bytes, max_frames=8):
    """Próbkuje klatki wideo, liczy dla nich hashe, OCR na kilku klatkach."""
    if cv2 is None:
        return {"error": "Brak OpenCV – analiza wideo niedostępna"}
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as t:
        t.write(data)
        path = t.name
    frames, texts, qrs, fcs = [], [], set(), []
    try:
        cap = cv2.VideoCapture(path)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        idxs = sorted({int(n * (i + 0.5) / max_frames) for i in range(max_frames)}) if n > 0 else list(range(0, 250, 30))
        for j, i in enumerate(idxs):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, fr = cap.read()
            if not ok:
                continue
            img = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
            frames.append({"t": round(i / fps, 1), "dhash": dhash(img), "phash": phash(img)})
            if j in (0, len(idxs) // 2, len(idxs) - 1):
                tx = ocr(img)
                if tx:
                    texts.append(tx)
                qrs.update(decode_qr(img))
                fcs += faces(img)
        cap.release()
        return {"duration": round(n / fps, 1) if n else None, "frames": frames, "ocr": "\n".join(texts), "qr": sorted(qrs), "faces": fcs[:6]}
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
