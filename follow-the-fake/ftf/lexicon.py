"""Słowniki referencyjne: osoby, marki/logotypy, tematy (narracje), sygnały manipulacji.

Baza osób jest celowo mała – zgodnie z treścią wyzwania ma pokazać użyteczność metody,
a nie być kompletna. Można ją rozszerzać w data/persons.json bez zmian w kodzie.
"""
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")


def strip_accents(s: str) -> str:
    s = s.replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(s: str) -> str:
    return strip_accents(s or "").lower()


# --- Osoby (wizerunki najczęściej wykorzystywane w fałszywych reklamach w PL) ---
DEFAULT_PERSONS = {
    "Robert Lewandowski": ["lewandowsk"],
    "Anna Lewandowska": ["anna lewandowsk", "ania lewandowsk"],
    "Iga Świątek": ["swiatek"],
    "Rafał Brzoska": ["brzosk"],
    "Omenaa Mensah": ["omenaa", "mensah"],
    "Magda Gessler": ["gessler"],
    "Kuba Wojewódzki": ["wojewodzk"],
    "Dawid Podsiadło": ["podsiadl"],
    "Adam Małysz": ["malysz"],
    "Jerzy Owsiak": ["owsiak"],
    "Krzysztof Stanowski": ["stanowsk"],
    "Marcin Prokop": ["prokop"],
    "Dorota Wellman": ["wellman"],
    "Ewa Chodakowska": ["chodakowsk"],
    "Michał Sołowow": ["solowow"],
    "Zygmunt Solorz": ["solorz"],
    "Dominika Kulczyk": ["kulczyk"],
    "Adam Glapiński": ["glapinsk"],
    "Donald Tusk": ["tusk"],
    "Andrzej Duda": ["andrzej duda", "prezydent duda"],
    "Karol Nawrocki": ["nawrock"],
    "Rafał Trzaskowski": ["trzaskowsk"],
    "Szymon Hołownia": ["holowni"],
    "Sławomir Mentzen": ["mentzen"],
    "Elon Musk": ["elon musk", "musk"],
}

# --- Marki / logotypy (podszywanie się pod instytucje i firmy) ---
BRANDS = {
    "NASK": ["nask"], "CERT Polska": ["cert polska", "cert.pl"], "mObywatel": ["mobywatel"],
    "ZUS": [r"\bzus\b"], "Ministerstwo Finansów": ["ministerstwo finansow"], "KNF": [r"\bknf\b"],
    "NBP": [r"\bnbp\b", "narodowy bank polski"], "Policja": ["policj"],
    "PKO BP": [r"\bpko\b", "ipko"], "mBank": ["mbank"], "Santander": ["santander"], "ING": [r"\bing bank", r"\bing\b"],
    "Pekao": ["pekao"], "BLIK": [r"\bblik\b"], "Revolut": ["revolut"],
    "InPost": ["inpost", "paczkomat"], "DPD": [r"\bdpd\b"], "Poczta Polska": ["poczta polska"], "DHL": [r"\bdhl\b"],
    "Allegro": ["allegro"], "OLX": [r"\bolx\b"], "Vinted": ["vinted"],
    "Orlen": ["orlen"], "PGE": [r"\bpge\b"], "PGNiG": ["pgnig"], "Tauron": ["tauron"], "Energa": ["energa"],
    "Biedronka": ["biedronk"], "Lidl": [r"\blidl\b"], "Żabka": ["zabk"], "Rossmann": ["rossmann"],
    "TVN": [r"\btvn\b"], "Polsat": ["polsat"], "TVP": [r"\btvp\b"], "Onet": ["onet"], "WP": [r"\bwp\.pl\b", "wirtualna polska"],
    "Facebook": ["facebook"], "Instagram": ["instagram"], "Netflix": ["netflix"], "Disney+": ["disney"],
    "Bitcoin": ["bitcoin", r"\bbtc\b"], "Binance": ["binance"],
}

# --- Tematy / narracje kampanii ---
TOPICS = {
    "inwestycje/krypto": ["inwest", "krypto", "bitcoin", "trading", "zysk", "zarob", "platform", "dochod", "pasywn", "gield", "akcj", "baltic pipe", "orlen inwest", "algorytm"],
    "zdrowie/cudowny lek": ["lek", "lecz", "cukrzyc", "staw", "nadcisnien", "odchudz", "kardiolog", "lekarz", "suplement", "kuracj", "prostat", "wzrok", "sluch"],
    "dopłata/przesyłka": ["paczk", "przesylk", "doplat", "kurier", "dostaw", "adres doreczenia"],
    "loteria/nagroda": ["wygral", "nagrod", "losowan", "konkurs", "giveaway", "za darmo", "darmow", "prezent", "kupon", "voucher"],
    "energia/rachunki": ["prad", "rachunk", "energi", "fotowolt", "gaz", "zwrot nadplat", "dofinans"],
    "urząd/zwrot": ["zwrot", "podatk", "urzad", "e-urzad", "mobywatel", "zus", "swiadczen", "blokad konta"],
    "praca/zarobek": ["praca zdaln", "oferta pracy", "zarabiaj", "dodatkow", "lajk", "zadani"],
    "polityka/dezinformacja": ["wybor", "rzad", "premier", "prezydent", "sejm", "unia", "ukrain", "imigrant", "szczepion"],
}

# --- Sygnały manipulacji (pomocnicze cechy narracyjne) ---
MANIPULATION = {
    "gwarancja zysku": r"(gwarant\w*|pewn\w* zysk|bez ryzyka|zero ryzyka)",
    "kwota w krótkim czasie": r"\d[\d\s.,]*\s?(zł|pln|€|eur|\$|usd)\s*(dziennie|tygodniowo|miesięcznie|na dzień|w tydzień|w miesiąc|w \d+ dni)",
    "presja czasu": r"(tylko dziś|ostatni\w* miejsc|ograniczon\w*|zostało (tylko )?\d+|pospiesz|natychmiast|zanim (to )?usuną|w ciągu 24)",
    "sensacja/sekret": r"(szok\w*|skandal\w*|sekret\w*|tajn\w*|ukrywa\w*|banki? (są )?wściekł\w*|nie chcą,? (żebyś|aby))",
    "fałszywy wywiad/TV": r"(wywiad\w*|na żywo|na antenie|w programie)",
    "prośba o dane": r"(numer\w* kart\w*|kod\w* blik|pesel|hasł\w*|dane logowania|cvv)",
    "minimalna wpłata": r"(wpłać|wpłata|depozyt|minimaln\w*)\s*\w*\s*\d+",
}

STOPWORDS = set("""a aby ach acz aczkolwiek aj albo ale ależ ani aż bardziej bardzo bez bo bowiem by byli bym bynajmniej być był była było były będzie będą cali cała cały chce ci cię ciebie co cokolwiek coś czasami czasem czemu czy czyli daleko dla dlaczego dlatego do dobrze dokąd dość dużo dwa dwaj dwie dwoje dziś dzisiaj gdy gdyby gdyż gdzie gdziekolwiek gdzieś go i ich ile im inna inne inny innych iż ja ją jak jakaś jakby jaki jakichś jakie jakiś jakiż jakkolwiek jako jakoś je jeden jedna jedno jednak jednakże jego jej jemu jest jestem jeszcze jeśli jeżeli już ją każdy kiedy kilka kimś kto ktokolwiek ktoś która które którego której który których którym którzy ku lat lecz lub ma mają mało mam mi mimo między mną mnie mogą moi moim moja moje może możliwe można mój mu musi my na nad nam nami nas nasi nasz nasza nasze naszego naszych natomiast natychmiast nawet nią nic nich nie niech niego niej niemu nigdy nim nimi niż no o obok od około on ona one oni ono oraz oto owszem pan pana pani po pod podczas pomimo ponad ponieważ powinien powinna powinni powinno poza prawie przecież przed przede przedtem przez przy roku również sam sama są się skąd sobie sobą sposób swoje ta tak taka taki takie także tam te tego tej temu ten teraz też to tobą tobie toteż trzeba tu tutaj twoi twoim twoja twoje twym twój ty tych tylko tym u w wam wami was wasz wasza wasze we według wiele wielu więc więcej wszyscy wszystkich wszystkie wszystkim wszystko wtedy wy właśnie z za zapewne zawsze ze zł znowu znów został żaden żadna żadne żadnych że żeby the and or of to in is for on with this that you your are be it at as by from www http https com pl""".split())


def load_persons():
    path = os.path.join(DATA, "persons.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_PERSONS


def _match_dict(text_norm: str, d: dict):
    out = []
    for name, pats in d.items():
        for p in pats:
            p = norm(p)
            if (p.startswith("\\b") and re.search(p, text_norm)) or (not p.startswith("\\b") and p in text_norm):
                out.append(name)
                break
    return sorted(set(out))


def find_persons(text: str):
    return _match_dict(norm(text), load_persons())


def find_brands(text: str):
    return _match_dict(norm(text), BRANDS)


def find_topics(text: str):
    t = norm(text)
    # dopasowanie od początku słowa (prefiks), żeby „staw” nie łapało „dostawa”
    scores = {k: sum(1 for w in v if re.search(r"\b" + re.escape(w), t)) for k, v in TOPICS.items()}
    return sorted([k for k, s in scores.items() if s >= 2 or (s == 1 and len(t) < 200)], key=lambda k: -scores[k])


def find_manipulation(text: str):
    return [k for k, rx in MANIPULATION.items() if re.search(rx, text or "", re.I)]
