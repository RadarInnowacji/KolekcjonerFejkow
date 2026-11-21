"""Test „ukrytego zbioru” – symulacja tego, jak organizator będzie oceniał rozwiązanie.

Zbiór bazowy = data/demo. Nowe materiały (nieznane metodzie):
- nowe warianty znanych kampanii: nowe domeny, nowe nagłówki, inne kadrowanie, brak części danych,
- zupełnie nowa kampania (powinna zostać uznana za „nowy wzorzec”),
- legalne reklamy-pułapki o podobnym słownictwie (NIE powinny zostać połączone).
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ftf import engine, extract, importer  # noqa: E402
import make_demo as M  # noqa: E402


def jpg(img):
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=75)
    return b.getvalue()


CASES = [
    # (oczekiwana etykieta lub None = nowy wzorzec, opis, kwargs do build_material)
    ("A", "A: nowy nagłówek, nowa domena, ten sam Pixel", dict(
        text="Lewandowski w programie na żywo: zarabiam 9000 zł dziennie dzięki AI. Banki wściekłe! zysk-dzis.online",
        files=[{"name": "a.jpg", "bytes": jpg(M.variant(M.creative(M.TEMPLATES["tv"], "Lewandowski w programie na żywo: zarabiam 9000 zł dziennie", "Banki wściekłe. Bez ryzyka.", "SPRAWDŹ TERAZ"), "crop"))}],
        meta={"trackers": ["facebook_pixel:704211993018456"], "domains": ["zysk-dzis.online"]})),
    ("A", "A: sam zrzut ekranu (bez linku i metadanych)", dict(
        files=[{"name": "a2.jpg", "bytes": jpg(M.variant(M.creative(M.TEMPLATES["tv"], "Robert Lewandowski ujawnia: tak zarabiam 7000 zł dziennie", "Banki są wściekłe. Gwarantowany zysk bez ryzyka na nowej platformie AI.", "ZAREJESTRUJ SIĘ"), "small"))}])),
    ("C", "C: nowy SMS, nowa domena, ta sama infrastruktura", dict(
        text="InPost: paczka oczekuje na dopłatę 2,49 zł. Opłać w ciągu 24h: inpost-odbior.sbs",
        meta={"domains": ["inpost-odbior.sbs"], "nameservers": ["dora.ns.cloudflare.com", "rick.ns.cloudflare.com"], "dom_shingles": M.SHINGLES_KIT_C, "ips": ["104.21.66.10"]})),
    ("C", "C: tylko tekst zgłoszenia", dict(text="Dostałem SMS że moja paczka InPost jest wstrzymana i trzeba dopłacić 1,99 zł, link paczkomat-doplata.cfd")),
    ("F", "F: nowy wariant mObywatel", dict(
        text="mObywatel: przysługuje Ci zwrot nadpłaty podatku 980,20 zł. Potwierdź dane karty: zwrot-mobywatel.top",
        meta={"trackers": ["google_analytics:G-ZWROT2026X"]})),
    ("D", "D: suplement, inny nagłówek, ten sam wizerunek", dict(
        text="Ewa Chodakowska zdradza: ten suplement leczy cukrzycę, schudłam bez diety. Kuracja tylko dziś 99 zł. zdrowie-natura.store")),
    (None, "NOWA kampania: fałszywy Allegro (nieznana wcześniej)", dict(
        text="Allegro: Twoje konto zostanie zablokowane. Zweryfikuj płatność i podaj dane karty w ciągu 2 godzin: allegro-weryfikacja.online",
        meta={"trackers": ["google_tag_manager:GTM-NEW999"], "nameservers": ["ns1.other-host.ru", "ns2.other-host.ru"]})),
    (None, "PUŁAPKA: legalna reklama funduszu inwestycyjnego", dict(
        text="Fundusz obligacji skarbowych – inwestuj od 100 zł. Przeszłe wyniki nie gwarantują przyszłych zysków. Prospekt na stronie towarzystwa.", url="https://tfi-przyklad.pl")),
    (None, "PUŁAPKA: prawdziwe powiadomienie kurierskie", dict(
        text="Twoja przesyłka nr 6203 9988 zostanie doręczona jutro między 10:00 a 14:00. Śledź status w aplikacji przewoźnika.")),
    (None, "PUŁAPKA: wywiad z piłkarzem w serwisie sportowym", dict(
        text="Robert Lewandowski po meczu z Realem: drużyna zagrała świetnie w drugiej połowie, teraz skupiamy się na lidze.", url="https://sport-przyklad.pl/wywiad")),
]


def main():
    rows, src = importer.load(path=os.path.join(M.OUT))
    items = []
    for k, r in enumerate(rows):
        rec, _ = importer.to_material(r, src, network=False)
        rec["id"] = k + 1
        items.append(rec)
    e = engine.Engine(items)
    e.matrix()
    e.cluster()
    camps = {c["id"]: c for c in e.campaigns()}
    ok = 0
    for want, desc, kw in CASES:
        rec = extract.build_material(network=False, **kw)
        res = e.assign(rec)
        got = None
        if res["decision"] != "nowy wzorzec":
            lab = camps[res["campaign"]]["labels"]
            got = lab[0][0] if lab else "?"
        good = (got == want) or (want is None and got is None)
        ok += good
        top = res["similar"][0] if res["similar"] else None
        print(f"{'OK ' if good else 'ŹLE'}  {desc:<55} → {res['decision']:<15} {got or '':<3} pewność={res['confidence']:.2f}"
              + (f"  | {top['evidence'][0]['text'][:70]}" if top and top['evidence'] else ""))
    print(f"\nTrafność na nowych materiałach: {ok}/{len(CASES)}")


if __name__ == "__main__":
    main()
