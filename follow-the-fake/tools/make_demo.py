"""Generator SYNTETYCZNEGO zbioru demonstracyjnego (nie są to prawdziwe reklamy).

Cel: pokazać działanie metody, gdy zbiór organizatora nie jest jeszcze wczytany.
Zbiór celowo zawiera trudności opisane w wyzwaniu:
- warianty tej samej kreacji (inny nagłówek, przycięcie, kompresja, ramka telefonu),
- duplikaty, materiały bez obrazu, bez strony (domena „nie działa”), bez metadanych,
- dwie różne kampanie tego samego operatora (wspólne DNS/rejestrator – „rodzina”),
- materiały legalne / niepowiązane, które NIE powinny się z niczym łączyć.

Uruchom:  python tools/make_demo.py   →  data/demo/manifest.json + obrazy
"""
import json
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "demo")
random.seed(7)


def font(size, bold=False):
    for name in (["DejaVuSans-Bold.ttf", "arialbd.ttf"] if bold else ["DejaVuSans.ttf", "arial.ttf"]):
        for d in ("/usr/share/fonts/truetype/dejavu", "C:/Windows/Fonts", "/Library/Fonts", ""):
            try:
                return ImageFont.truetype(os.path.join(d, name) if d else name, size)
            except Exception:
                pass
    return ImageFont.load_default(size=size)


def wrap(draw, text, f, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def face(draw, cx, cy, r, skin, hair):
    draw.ellipse([cx - r, cy - r * 1.2, cx + r, cy + r * 1.1], fill=skin)
    draw.chord([cx - r * 1.05, cy - r * 1.35, cx + r * 1.05, cy + r * 0.2], 180, 360, fill=hair)
    for dx in (-0.4, 0.4):
        draw.ellipse([cx + dx * r - 7, cy - 10, cx + dx * r + 7, cy + 4], fill=(30, 30, 30))
    draw.arc([cx - r * 0.45, cy + r * 0.2, cx + r * 0.45, cy + r * 0.65], 10, 170, fill=(120, 40, 40), width=5)


def creative(tpl, headline, sub, cta, seed=0):
    W, H = 720, 720
    im = Image.new("RGB", (W, H), tpl["bg"])
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 90], fill=tpl["bar"])
    d.text((28, 26), tpl["brand"], font=font(34, True), fill=(255, 255, 255))
    if tpl.get("live"):
        d.rectangle([W - 170, 24, W - 28, 66], fill=(220, 20, 40))
        d.text((W - 156, 30), "NA ŻYWO", font=font(26, True), fill=(255, 255, 255))
    if tpl.get("face"):
        skin, hair = tpl["face"]
        d.rectangle([40, 120, 330, 470], fill=tpl["photo_bg"])
        face(d, 185, 300, 95, skin, hair)
    x0 = 360 if tpl.get("face") else 40
    y = 130
    for line in wrap(d, headline, font(40, True), W - x0 - 40):
        d.text((x0, y), line, font=font(40, True), fill=tpl["fg"])
        y += 50
    y += 10
    for line in wrap(d, sub, font(26), W - x0 - 40):
        d.text((x0, y), line, font=font(26), fill=tpl["fg2"])
        y += 34
    d.rectangle([40, H - 150, W - 40, H - 70], fill=tpl["cta"])
    tw = d.textlength(cta, font=font(36, True))
    d.text(((W - tw) / 2, H - 132), cta, font=font(36, True), fill=(255, 255, 255))
    return im


def variant(im, kind):
    if kind == "crop":
        w, h = im.size
        return im.crop((18, 14, w - 22, h - 10)).resize((640, 640))
    if kind == "small":
        return im.resize((420, 420))
    if kind == "blur":
        return im.filter(ImageFilter.GaussianBlur(1.2))
    if kind == "phone":  # zrzut ekranu z „aplikacji” – kreacja w ramce
        frame = Image.new("RGB", (760, 1350), (250, 250, 250))
        d = ImageDraw.Draw(frame)
        d.rectangle([0, 0, 760, 120], fill=(255, 255, 255))
        d.ellipse([24, 30, 84, 90], fill=(200, 200, 210))
        d.text((100, 40), "Sponsorowane", font=font(28), fill=(90, 90, 90))
        frame.paste(im.resize((760, 760)), (0, 160))
        d.text((24, 960), "Lubię to   Komentarz   Udostępnij", font=font(30), fill=(90, 90, 90))
        return frame
    return im


TEMPLATES = {
    "tv": {"bg": (12, 24, 54), "bar": (180, 0, 30), "brand": "FAKTY 24", "live": True, "fg": (255, 255, 255), "fg2": (200, 210, 230),
           "cta": (220, 30, 50), "face": ((236, 196, 170), (60, 40, 30)), "photo_bg": (40, 60, 110)},
    "energy": {"bg": (245, 247, 250), "bar": (230, 120, 0), "brand": "INWESTYCJE PL", "fg": (20, 20, 20), "fg2": (70, 70, 70),
               "cta": (230, 120, 0), "face": ((228, 190, 160), (120, 120, 120)), "photo_bg": (210, 220, 230)},
    "parcel": {"bg": (255, 214, 0), "bar": (30, 30, 30), "brand": "Paczka • Powiadomienie", "fg": (20, 20, 20), "fg2": (40, 40, 40), "cta": (30, 30, 30)},
    "health": {"bg": (255, 240, 245), "bar": (200, 40, 110), "brand": "ZDROWIE+", "fg": (60, 10, 30), "fg2": (90, 50, 70),
               "cta": (200, 40, 110), "face": ((240, 205, 185), (150, 90, 40)), "photo_bg": (250, 210, 225)},
    "lottery": {"bg": (225, 20, 40), "bar": (255, 200, 0), "brand": "WIELKIE LOSOWANIE", "fg": (255, 255, 255), "fg2": (255, 235, 200), "cta": (20, 140, 60)},
    "gov": {"bg": (255, 255, 255), "bar": (10, 50, 110), "brand": "e-Zwroty", "fg": (10, 30, 70), "fg2": (60, 70, 90), "cta": (10, 50, 110)},
    "legit1": {"bg": (20, 120, 100), "bar": (10, 80, 70), "brand": "KodujZNami", "fg": (255, 255, 255), "fg2": (210, 240, 230), "cta": (250, 160, 30)},
    "legit2": {"bg": (240, 240, 240), "bar": (40, 40, 40), "brand": "Buty&Co", "fg": (30, 30, 30), "fg2": (80, 80, 80), "cta": (40, 40, 40)},
}

SHINGLES_KIT_A = list(range(1000, 1240))          # szkielet strony scam-kitu A (inwestycje)
SHINGLES_KIT_C = list(range(5000, 5180))          # szkielet strony „paczka”
INFRA = {
    "A": {"trackers": ["facebook_pixel:704211993018456"], "nameservers": ["ns1.cheapdns-host.cc", "ns2.cheapdns-host.cc"], "registrars": ["NICENIC INTERNATIONAL"], "ips": ["185.244.10.17"], "dom_shingles": SHINGLES_KIT_A},
    "B": {"trackers": ["google_tag_manager:GTM-K7Q2XZ"], "nameservers": ["ns1.cheapdns-host.cc", "ns2.cheapdns-host.cc"], "registrars": ["NICENIC INTERNATIONAL"], "ips": ["185.244.10.29"], "dom_shingles": SHINGLES_KIT_A[:200] + list(range(2000, 2040))},
    "C": {"trackers": [], "nameservers": ["dora.ns.cloudflare.com", "rick.ns.cloudflare.com"], "registrars": ["Gname.com Pte. Ltd."], "ips": ["104.21.66.10"], "dom_shingles": SHINGLES_KIT_C},
    "D": {"trackers": ["facebook_pixel:1290455120034871"], "nameservers": ["ns1.hostvital.net", "ns2.hostvital.net"], "registrars": ["Hosting Concepts B.V."], "ips": ["91.215.85.40"], "dom_shingles": list(range(7000, 7150))},
    "E": {"trackers": ["tiktok_pixel:CK3PQRSTUVWXYZ01234"], "nameservers": ["ns-a.freedns.icu", "ns-b.freedns.icu"], "registrars": ["Namecheap, Inc."], "ips": ["45.89.124.9"], "dom_shingles": list(range(8000, 8120))},
    "F": {"trackers": ["google_analytics:G-ZWROT2026X"], "nameservers": ["ns1.gov-help.top", "ns2.gov-help.top"], "registrars": ["Gname.com Pte. Ltd."], "ips": ["193.233.48.77"], "dom_shingles": list(range(9000, 9200))},
}

CAMPAIGNS = {
    "A": dict(tpl="tv", person="Robert Lewandowski", domains=["zysk-teraz.online", "zysk-teraz24.site", "szybki-zysk-pl.top"], created=["2026-10-02", "2026-10-03", "2026-10-11"],
              heads=["Robert Lewandowski ujawnia: tak zarabiam 7000 zł dziennie", "Lewandowski: ta platforma zmieniła moje życie", "Skandal w studiu! Lewandowski zdradził sekret zarabiania"],
              subs=["Banki są wściekłe. Gwarantowany zysk bez ryzyka na nowej platformie AI.", "Minimalna wpłata 1000 zł, zysk gwarantowany. Zostało tylko 12 miejsc!", "Wywiad na żywo: algorytm AI zarabia za Ciebie. Bez ryzyka."],
              cta="ZAREJESTRUJ SIĘ"),
    "B": dict(tpl="energy", person="Rafał Brzoska", domains=["energia-inwestuj.xyz", "orlen-zysk-pl.click"], created=["2026-10-05", "2026-10-06"],
              heads=["Rafał Brzoska: zainwestuj 900 zł w polską energię", "Nowy projekt Orlenu – zarób z Rafałem Brzoską"],
              subs=["Pasywny dochód nawet 25 000 zł miesięcznie. Platforma inwestycyjna dla Polaków.", "Inwestycja w Baltic Pipe – pewny zysk, liczba miejsc ograniczona."],
              cta="ZACZNIJ ZARABIAĆ"),
    "C": dict(tpl="parcel", person=None, domains=["inpost-dostawa.top", "inpost-paczka24.icu", "paczkomat-doplata.cfd"], created=["2026-10-20", "2026-10-21", "2026-10-25"],
              heads=["Twoja paczka została wstrzymana", "Przesyłka czeka – wymagana dopłata 1,99 zł", "Paczka nie może zostać doręczona"],
              subs=["Opłać dopłatę 1,99 zł w ciągu 24 godzin, inaczej przesyłka wróci do nadawcy. InPost.", "Zaktualizuj adres doręczenia i opłać 1,99 zł natychmiast. Paczkomat InPost.", "Wymagana dopłata do przesyłki InPost: 1,99 zł. Kliknij, aby opłacić."],
              cta="OPŁAĆ 1,99 ZŁ"),
    "D": dict(tpl="health", person="Ewa Chodakowska", domains=["cukrzyca-stop.shop", "zdrowie-natura.store"], created=["2026-09-15", "2026-09-29"],
              heads=["Ewa Chodakowska: schudłam 12 kg w 30 dni", "Lekarze nienawidzą tej metody na cukrzycę"],
              subs=["Naturalna kuracja leczy cukrzycę i nadciśnienie w 2 tygodnie. Suplement z apteki zakazany przez lekarzy.", "Cudowny suplement – kuracja odchudzanie i cukrzyca. Zamów dziś za 147 zł."],
              cta="ZAMÓW KURACJĘ"),
    "E": dict(tpl="lottery", person=None, domains=["biedronka-bon1000.live", "bon-biedronka.buzz"], created=["2026-10-28", "2026-10-30"],
              heads=["Biedronka rozdaje bony 1000 zł!", "Wygraj bon 1000 zł do Biedronki"],
              subs=["Wypełnij ankietę i odbierz nagrodę. Losowanie tylko dziś – zostało 37 bonów.", "Darmowy bon dla pierwszych 500 osób. Konkurs z okazji 30-lecia, nagroda za darmo."],
              cta="ODBIERZ BON"),
    "F": dict(tpl="gov", person=None, domains=["mobywatel-zwrot.top", "e-zwrot-podatku.sbs"], created=["2026-11-02", "2026-11-04"],
              heads=["Masz zwrot podatku 1 286,40 zł", "mObywatel: nadpłata podatku do odebrania"],
              subs=["Urząd skarbowy przygotował zwrot nadpłaty. Potwierdź dane karty, aby otrzymać środki. mObywatel.", "Zwrot podatku czeka. Podaj numer karty i kod BLIK, aby odebrać świadczenie. mObywatel."],
              cta="ODBIERZ ZWROT"),
}

LEGIT = [
    dict(label="X1", tpl="legit1", head="Kurs programowania w Pythonie od podstaw", sub="12 tygodni zajęć online, certyfikat ukończenia, raty 0%.", cta="SPRAWDŹ PROGRAM", url="https://kodujznami.pl/kurs-python"),
    dict(label="X2", tpl="legit2", head="Nowa kolekcja butów jesień/zima", sub="Darmowa dostawa od 199 zł i 30 dni na zwrot w naszych salonach.", cta="ZOBACZ KOLEKCJĘ", url="https://butyandco.pl/jesien"),
    dict(label="X3", tpl=None, head="Szkoła językowa Lingwista – zapisy na semestr zimowy", sub="Kursy angielskiego i niemieckiego dla dorosłych, małe grupy, Kraków.", cta="", url="https://lingwista-krakow.pl"),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    items = []
    n = 0

    def save(img, name):
        p = os.path.join(OUT, name)
        img.convert("RGB").save(p, "JPEG", quality=random.choice([70, 80, 90]))
        return name

    for key, c in CAMPAIGNS.items():
        tpl = TEMPLATES[c["tpl"]]
        nvar = len(c["heads"])
        for v in range(nvar):
            base = creative(tpl, c["heads"][v], c["subs"][v % len(c["subs"])], c["cta"], seed=v)
            dom = c["domains"][v % len(c["domains"])]
            url = f"https://{dom}/{random.choice(['pl', 'start', 'lp', 'oferta'])}/?utm_source=fb&cid={random.randint(1000, 9999)}"
            meta = dict(INFRA[key])
            meta["created"] = c["created"][v % len(c["created"])]
            meta["domains"] = [dom]
            text = f"{c['heads'][v]}. {c['subs'][v % len(c['subs'])]} {c['cta'].capitalize()}: {dom}"
            kinds = ["phone", "plain", "crop", "small", "blur"]
            # 1) główny materiał – kreacja + tekst + metadane
            n += 1
            items.append(dict(id=f"{key}{v + 1}", label=key, title=c["heads"][v], text=text, url=url,
                              image=save(variant(base, kinds[v % len(kinds)]), f"{key}{v + 1}.jpg"), meta=meta, date=meta["created"]))
        # 2) wariant bez strony i bez metadanych – tylko zrzut (np. reklama zgłoszona przez użytkownika)
        base = creative(tpl, c["heads"][0], c["subs"][0], c["cta"])
        items.append(dict(id=f"{key}-screen", label=key, title=f"Zrzut ekranu ({key})", text="", url="",
                          image=save(variant(base, "phone"), f"{key}-screen.jpg"), meta={}, date=c["created"][0]))
        # 3) tylko tekst (log / opis zgłoszenia), domena już nie działa
        items.append(dict(id=f"{key}-txt", label=key, title=f"Zgłoszenie tekstowe ({key})",
                          text=f"Zgłoszenie użytkownika: widziałem reklamę – {c['heads'][-1].lower()}. {c['subs'][-1]} Link prowadził do {c['domains'][-1]} (strona już nie działa).",
                          url="", image=None, meta={"domains": [c["domains"][-1]]}, date=c["created"][-1]))
    # 4) dokładny duplikat (ponowne zgłoszenie tej samej reklamy)
    dup = dict(items[0])
    dup["id"] = "A1-dup"
    items.append(dup)
    # 5) materiały niepowiązane / legalne
    for lg in LEGIT:
        img = save(creative(TEMPLATES[lg["tpl"]], lg["head"], lg["sub"], lg["cta"]), f"{lg['label']}.jpg") if lg["tpl"] else None
        items.append(dict(id=lg["label"], label=lg["label"], title=lg["head"], text=f"{lg['head']}. {lg['sub']}", url=lg["url"], image=img, meta={}, date="2026-10-15"))

    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"description": "SYNTETYCZNY zbiór demonstracyjny Follow the Fake – wygenerowany, nie są to prawdziwe reklamy.", "items": items}, f, ensure_ascii=False, indent=1)
    print(f"Zapisano {len(items)} materiałów do {OUT}")


if __name__ == "__main__":
    sys.exit(main())
