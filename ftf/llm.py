"""Opcjonalne wsparcie modelem językowo-wizyjnym (Claude) – NIE jest wymagane do działania.

Gdy ustawiono ANTHROPIC_API_KEY, kreacje graficzne są dodatkowo opisywane przez model:
tekst (lepszy niż OCR przy stylizowanych napisach), rozpoznane osoby publiczne, logotypy,
narracja. Wynik trafia do tych samych pól co cechy z OCR/słowników, więc metoda
podobieństwa pozostaje identyczna i wyjaśnialna.
"""
import base64
import json
import os
import urllib.request

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")

PROMPT = """Analizujesz kreację podejrzanej reklamy internetowej na potrzeby badań nad kampaniami oszustw.
Zwróć WYŁĄCZNIE JSON:
{"text": "cały widoczny tekst", "persons": ["osoby publiczne widoczne lub wymienione"],
 "brands": ["marki/logotypy/instytucje"], "urls": ["widoczne adresy"],
 "narrative": "1 zdanie: jaki schemat/obietnica", "template": "1 zdanie: układ graficzny (np. fałszywy artykuł TV, post z cytatem)"}
Wymieniaj osoby tylko gdy rozpoznajesz je z dużą pewnością lub są podpisane."""


def enabled():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def describe_image(data: bytes, mime="image/jpeg"):
    if not enabled():
        return None
    body = {
        "model": MODEL, "max_tokens": 1200,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": mime, "data": base64.b64encode(data).decode()}},
            {"type": "text", "text": PROMPT}]}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), method="POST",
        headers={"content-type": "application/json", "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.loads(r.read())
        t = "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text")
        return json.loads(t[t.index("{"): t.rindex("}") + 1])
    except Exception as e:
        return {"error": f"LLM: {type(e).__name__}"}
