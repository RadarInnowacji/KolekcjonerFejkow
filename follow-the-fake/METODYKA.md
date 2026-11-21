# Metodyka – Follow the Fake

Cel: z chaosu pojedynczych podejrzanych reklam wydobyć **kampanie**, czyli grupy materiałów pochodzących z jednego źródła lub mechanizmu, i każde powiązanie **uzasadnić konkretnymi przesłankami**. Nie budujemy detektora pojedynczej fałszywej reklamy, tylko metodę łączenia materiałów.

## 1. Przebieg analizy

1. **Wejście**: adres URL (również skrócony lub odczytany z kodu QR), tekst (treść reklamy, log komunikacji, nazwa produktu), zrzut ekranu lub kreacja, wideo, zapisana strona HTML, plik TXT/EML/LOG albo cały zbiór (ZIP/JSON/JSONL/CSV).
2. **Ekstrakcja cech** w 6 kanałach (sekcja 2), ujednolicona do jednego rekordu JSON.
3. **Podobieństwo** każdej pary materiałów w każdym kanale, z wynikiem łącznym i listą przesłanek (sekcja 3).
4. **Duplikaty i warianty**: klasyfikacja relacji pary.
5. **Grupowanie w kampanie** (sekcja 4) oraz wykrywanie **kampanii podobnych** (ta sama rodzina, operator lub szablon).
6. **Nowy materiał**: porównanie ze zbiorem i decyzja: *duplikat*, *znana kampania* albo *nowy wzorzec* (sekcja 5).
7. **Prezentacja**: karty kampanii, graf powiązań, lista podobnych incydentów, eksport do Neo4j, CSV i JSON.

## 2. Cechy i źródła danych

| Kanał | Cechy | Jak pozyskiwane |
|---|---|---|
| **Tekst** | pełna treść (wpisana + OCR + tekst strony), odcisk znormalizowanego tekstu | Tesseract OCR (pol+eng), parser HTML, opcjonalnie model wizyjny |
| **Narracja** | słowa kluczowe, tematy (inwestycje/krypto, zdrowie, dopłata do paczki, loteria, urząd/zwrot, energia, praca, polityka), chwyty manipulacyjne (gwarancja zysku, presja czasu, sensacja, fałszywy wywiad TV, prośba o dane), kwoty | słowniki w `ftf/lexicon.py`, wyrażenia regularne |
| **Byty** | wizerunki osób, marki/logotypy, **podszywanie się** (marka w tytule strony, a domena obca), telefony, e-maile, portfele kryptowalut | baza referencyjna osób (`data/persons.json`), słownik marek, opcjonalnie rozpoznawanie twarzy (SFace) z bazą `data/faces/` |
| **Wizual** | dHash i pHash kreacji (64 bity) liczone na **samej kreacji wyciętej ze zrzutu**, histogram kolorów HSV (szablon/paleta), hashe wycinków twarzy, hashe klatek wideo | Pillow, OpenCV (QR, twarze, klatki wideo) |
| **Domeny** | domeny zarejestrowane (eTLD+1), łańcuch przekierowań (HTTP 3xx, meta-refresh, JS), nazwy z certyfikatów TLS i crt.sh, wzorzec nazw domen, domeny docelowe linków | urllib (ręczne śledzenie przekierowań), ssl, crt.sh |
| **Infrastruktura** | identyfikatory śledzące (Facebook Pixel, Google Analytics, GTM, Google Ads, TikTok Pixel, Yandex Metrika, TDS Keitaro), favicon (SHA-256), IP i sieć (RDAP IP), serwery DNS, rejestrator i data rejestracji (RDAP), wiek domeny, **odcisk struktury DOM** (k-gramy sekwencji tagów, czyli „scam-kit”), formularze z polami wrażliwymi | socket, rdap.org, parser HTML |

Każde źródło działa niezależnie, z krótkim limitem czasu. Gdy strona już nie działa, zapisujemy tylko to, co udało się zdobyć (np. sama nazwa domeny z tekstu), a rekord dostaje informację o brakujących kanałach.

### Dlaczego wycinamy kreację ze zrzutu ekranu
Zrzuty z Facebooka i Instagrama mają wspólną ramkę interfejsu („Sponsorowane”, „Lubię to”). Hash całego zrzutu porównywałby ramki, a nie reklamy: w testach dwa różne zrzuty z różnych kampanii dawały odległość Hamminga 6/64, czyli fałszywy „wariant tej samej kreacji”. Dlatego `content_crop` obcina jednolite marginesy i z wysokich zrzutów wybiera najdłuższy pas wierszy różniący się od tła interfejsu. Hash całego zrzutu zostaje tylko do wykrywania dokładnych duplikatów.

## 3. Podobieństwo pary materiałów

Dla pary *(a, b)* każdy kanał zwraca wartość 0–1 albo **brak danych** (None), np. gdy jeden z materiałów nie ma obrazu.

| Kanał | Waga | Sposób liczenia |
|---|---|---|
| tekst | 0.26 | 0.5 · cos(TF-IDF słów 1–2) + 0.5 · cos(TF-IDF n-gramów znakowych 3–5); n-gramy znakowe są odporne na odmianę słów i literówki |
| wizual | 0.20 | odległość Hamminga *d* = max(d_dHash, d_pHash), oba algorytmy muszą się zgadzać: d ≤ 4 → 1.0, potem liniowo do 0 przy d = 22; szablon: przecięcie histogramów |
| osoby | 0.12 | Jaccard zbiorów osób; to samo zdjęcie twarzy (hash wycinka ≤ 8) → 0.9 |
| narracja | 0.10 | ważony Jaccard: tematy 0.5, chwyty 0.3, marki 0.2 |
| domeny | 0.14 | noisy-OR sygnałów: wspólna domena 1.0, wspólny węzeł przekierowań 0.9, wspólne nazwy w certyfikatach 0.85, wspólne domeny docelowe 0.6, podobny wzorzec nazw (Jaccard tokenów ≥ 0.3) |
| infrastruktura | 0.18 | noisy-OR: wspólny tracker 1.0, favicon 0.85, IP 0.7 (0.3 dla CDN), DNS 0.6 (0.2 dla domyślnych DNS rejestratora), szkielet DOM ≥ 0.5, ten sam rejestrator i rejestracja w ciągu 3 dni 0.5, wspólny telefon, e-mail lub portfel 1.0 |

**Wynik łączny** to średnia ważona tylko po kanałach dostępnych w obu materiałach:

```
raw      = Σ w_k · s_k / Σ w_k            (k – kanały z danymi w obu materiałach)
pokrycie = Σ w_k / Σ wszystkich wag
wynik    = raw · (0.6 + 0.4 · min(1, pokrycie / 0.5))
```

- **Niekompletne dane nie są karane jak różnica.** Brak obrazu nie znaczy, że obrazy są różne. Kara za niskie pokrycie jest łagodna: materiał tylko z tekstem może się połączyć, ale potrzebuje silniejszego sygnału.
- **Zgodność wielu kanałów:** gdy co najmniej 3 niezależne kanały mają sygnał ≥ 0.5, wynik dostaje premię (+0.08 za każdy kanał ponad 2).
- **Twarde dowody** podnoszą wynik do 0.85: ten sam identyfikator śledzący, ten sam klucz kampanii, wspólny portfel, telefon lub e-mail, ta sama domena, prawie identyczna kreacja (d ≤ 4), prawie identyczny tekst (cos ≥ 0.9), ten sam scam-kit (DOM ≥ 0.9) na tej samej infrastrukturze.

**Relacja pary**: *duplikat* (tekst ≥ 0.95 i obraz ≥ 0.9, albo identyczny tekst, albo identyczna kreacja i tekst ≥ 0.85), *wariant* (≥ 0.70), *powiązanie* (≥ 0.45), *podobieństwo* (≥ 0.22).

**Wyjaśnialność:** każdy kanał dopisuje przesłankę zrozumiałą dla analityka, np. „Wspólny identyfikator śledzący: facebook_pixel:7042…”, „Ten sam szkielet strony (scam-kit), podobieństwo DOM = 1.00”, „Wariant tej samej kreacji (odległość hashy = 9/64)”. Przesłanki są sortowane według siły i trafiają do interfejsu, CSV oraz krawędzi grafu Neo4j.

### Pułapki, które metoda omija
- Domeny „wspólne dla wszystkich” (facebook.com, bit.ly, googletagmanager.com…) nie łączą kampanii.
- Adres IP w sieci CDN (Cloudflare, AWS, Google…) to słaby sygnał, bo dzielą go tysiące stron.
- Domyślne serwery DNS rejestratora to słaby sygnał.
- Wspólny temat albo nazwisko w zwykłym tekście (np. wywiad z piłkarzem) nie wystarczy do połączenia, gdy brak zgodności w innych kanałach.

## 4. Grupowanie w kampanie

1. **Atomy z twardych dowodów** (union-find): materiały połączone twardym dowodem trafiają do jednej grupy, nawet jeśli wyglądają inaczej. Przykład: inna kreacja i inny nagłówek, ale ten sam Facebook Pixel na stronie docelowej.
2. **Średnie wiązanie (average linkage)** na atomach, próg 0.45 (odległość = 1 − podobieństwo). Średnie wiązanie zamiast pojedynczego ogranicza **efekt łańcuchowania**, w którym jedna słaba krawędź skleja dwie różne kampanie.
3. **Kampanie podobne:** para kampanii o średnim podobieństwie ≥ 0.22 lub z najsilniejszym połączeniem ≥ 0.6 jest pokazywana jako możliwa wspólna „rodzina”, np. ten sam operator (wspólne DNS i rejestrator) z inną narracją.
4. **Opis kampanii:** dominujące osoby, tematy, domeny, trackery, słowa kluczowe, chwyty, rodzaje przesłanek, okres aktywności, liczba duplikatów i spójność (średnie podobieństwo wewnątrz).

## 5. Nowy materiał: znana kampania czy nowy wzorzec

Dla nowego materiału liczymy podobieństwo do całego zbioru (TF-IDF wyuczone na zbiorze, bez ponownego trenowania) i dla każdej kampanii średnią oraz maksimum.

- Jeśli istnieje twardy dowód, wygrywa kampania z tym dowodem.
- **Znana kampania**, gdy średnia ≥ 0.40 albo maksimum ≥ 0.85; **duplikat**, gdy któraś para jest duplikatem.
- W przeciwnym razie **nowy wzorzec**. Jeśli maksimum ≥ 0.22, system dopisuje, że to może być nowa odsłona istniejącej rodziny.
- Wynik zawiera pewność, 8 najbardziej podobnych incydentów z przesłankami i ranking kampanii.

## 6. Ocena jakości

Gdy materiały mają etykietę kampanii, system liczy:
- **ARI, NMI, jednorodność, kompletność** (scikit-learn),
- **precyzję, czułość i F1 par** oraz **B-cubed F1**,
- **test nowego materiału (leave-one-out)**: każdy materiał udaje nowy i sprawdzamy, czy trafia do właściwej kampanii, a materiał z kampanii jednoelementowej, czy **nie zostaje z niczym połączony**.

Uwaga: w teście leave-one-out kampanie pochodzą z grupowania całego zbioru, w którym ten materiał też uczestniczył, więc wynik jest lekko optymistyczny. Uczciwszy jest `tools/holdout_test.py`: materiały naprawdę nowe, w tym pułapki.

Wyniki na **syntetycznym** zbiorze demonstracyjnym (30 materiałów, 6 kampanii i 3 materiały niepowiązane): ARI 1.0, F1 par 1.0. Test materiałów nowych (`tools/holdout_test.py`): 10/10 (nowe warianty znanych kampanii, nowa kampania, 3 legalne reklamy-pułapki). **Zbiór syntetyczny jest łatwiejszy od prawdziwego.** Te liczby pokazują, że metoda działa zgodnie z założeniami, a nie jaka będzie skuteczność na danych organizatora. Do oceny na prawdziwym zbiorze służy `python tools/evaluate_dataset.py <zbiór>`.

## 7. Skalowalność i wdrożenie

- Obecnie macierz podobieństwa ma złożoność O(n²): kilkaset materiałów liczy się w ułamku sekundy, a najdroższa jest ekstrakcja (OCR, sieć).
- Dla dziesiątek tysięcy materiałów: **blokowanie** po kluczach (domena, tracker, osoba, prefiks hasha obrazu, MinHash-LSH dla tekstu) i liczenie pełnego podobieństwa tylko w blokach; embeddingi tekstu i obrazu (np. sentence-transformers, CLIP/SigLIP) w indeksie ANN (FAISS); przechowywanie w Neo4j.
- Eksport do Neo4j: węzły `Material`, `Campaign`, `Domain`, `Person`, `Tracker`, `IP`, `NameServer` i krawędzie `SIMILAR {score, relation, why}`.
- **Harmonogram:** cykliczne zapytania do Biblioteki Reklam Meta (Ad Library API, `ads_archive`, słowa kluczowe, kraj PL; reklamy komercyjne dostępne, gdy dotarły do UE). Zapisywane są tylko materiały podejrzane albo powiązane z istniejącą kampanią. Znane domeny są ponownie sprawdzane: czy działają i dokąd przekierowują.

## 8. Przydatne źródła metadanych

- **RDAP** (rdap.org): rejestrator, data rejestracji, serwery DNS. Bezpłatne i ustrukturyzowane, w przeciwieństwie do WHOIS.
- **crt.sh** (Certificate Transparency): inne nazwy w tych samych certyfikatach, często kolejne domeny kampanii.
- **Identyfikatory śledzące** w kodzie strony: jeden z najsilniejszych sygnałów wspólnego operatora, bo konto reklamowe trudno zmieniać.
- **Odcisk DOM i favicon:** zestawy do oszustw (scam-kity) są wdrażane wielokrotnie bez zmian w strukturze.
- **Kody QR na kreacjach** prowadzą do stron, których nie widać w samym tekście reklamy.
- **Biblioteka Reklam Meta**: źródło nowych materiałów, przez API z tokenem.

### Przykład z materiałów wyzwania
Kod QR z opisu wyzwania prowadzi do `loyalty.nuvio.group/enroll/…`, strony z tytułem „NASK | Program lojalnościowy” na domenie niezwiązanej z NASK, z osadzonym Facebook Pixel. Metoda oznacza to jako **podszywanie się** (marka w tytule, a domena obca) i zapisuje identyfikator Pixela jako silną cechę łączącą z innymi stronami tego samego operatora.

## 9. Ograniczenia

- Bez danych organizatora wagi i progi dobrano na podstawie wiedzy o kampaniach i zbioru syntetycznego. Trzeba je skalibrować na zbiorze z etykietami (`tools/evaluate_dataset.py`).
- OCR gubi stylizowane napisy. Opcjonalny model wizyjny (`ANTHROPIC_API_KEY`) poprawia tekst, osoby i logotypy, ale nie jest wymagany.
- Rozpoznawanie tożsamości twarzy wymaga modeli SFace/YuNet (`tools/download_models.py`) i zdjęć referencyjnych w `data/faces/<Imię Nazwisko>/`. Bez nich działa wykrywanie twarzy i porównanie wycinków (to samo zdjęcie), ale nie identyfikacja.
- Strony oszustów często pokazują inną treść botom i użytkownikom z innych krajów (cloaking). Pobieranie z polskiego IP i z nagłówkiem przeglądarki zmniejsza, ale nie usuwa tego problemu.
