"""Pobiera opcjonalne modele twarzy OpenCV (YuNet – wykrywanie, SFace – rozpoznawanie).

Źródło: OpenCV Zoo (licencja Apache 2.0 dla modeli YuNet i SFace).
Po pobraniu: umieść zdjęcia referencyjne w data/faces/<Imię Nazwisko>/*.jpg (1–5 zdjęć na osobę).
"""
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(ROOT, "models")
FILES = {
    "face_detection_yunet_2023mar.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}


def main():
    os.makedirs(MODELS, exist_ok=True)
    ok = True
    for name, url in FILES.items():
        path = os.path.join(MODELS, name)
        if os.path.exists(path) and os.path.getsize(path) > 100_000:
            print(f"✓ {name} już jest")
            continue
        print(f"Pobieram {name} …")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if len(data) < 100_000 or data[:200].lstrip().startswith(b"version https://git-lfs"):
                raise RuntimeError("otrzymano wskaźnik Git LFS zamiast pliku modelu")
            with open(path, "wb") as f:
                f.write(data)
            print(f"✓ zapisano {name} ({len(data) // 1024} KB)")
        except Exception as e:
            ok = False
            print(f"✕ nie udało się pobrać {name}: {e}\n  Pobierz ręcznie z {url} do folderu models/")
    os.makedirs(os.path.join(ROOT, "data", "faces"), exist_ok=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
