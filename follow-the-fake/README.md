# Follow the Fake – kolekcjoner fejków

Demonstrator rozwiązania wyzwania **„Kolekcjoner fejków / Follow the Fake”** (NASK PIB, HackNation).
Narzędzie łączy pojedyncze podejrzane reklamy w **kampanie** na podstawie śladów tekstowych, wizualnych, semantycznych i infrastrukturalnych. **Każde powiązanie jest uzasadnione** listą przesłanek.

Opis metody: **[METODYKA.md](METODYKA.md)** (również w zakładce *Metodyka* w aplikacji).

## Co potrafi

- **Wejście:** URL (również skrócony lub z kodu QR), tekst lub log komunikacji lub nazwa produktu, zrzut ekranu, kreacja, **wideo**, zapisana strona **HTML**, TXT/EML/LOG, cały zbiór (ZIP/JSON/JSONL/CSV, nazwy pól rozpoznawane automatycznie).
- **Ekstrakcja cech:**
  - treść: OCR (pol+eng), słowa kluczowe, tematy, chwyty manipulacyjne;
  - byty: osoby (baza referencyjna), marki/logotypy, **podszywanie się**, telefony, portfele krypto;
  - obraz: hashe percepcyjne kreacji wyciętej ze zrzutu, paleta, twarze, klatki wideo, **kody QR**;
  - infrastruktura: łańcuch przekierowań (HTTP + meta-refresh + JS), RDAP (rejestrator, data, DNS), IP i sieć, certyfikat TLS i crt.sh, **trackery** (FB Pixel, GA, GTM, TikTok…), favicon, **odcisk struktury DOM** (scam-kit), formularze z polami wrażliwymi.
- **Korelacja:** podobieństwo ważone w 6 kanałach, odporne na brak danych, twarde dowody, duplikaty i warianty, grupowanie dwuetapowe (union-find + average linkage), kampanie podobne.
- **Nowy materiał:** *duplikat* / *znana kampania* / *nowy wzorzec*, z pewnością, rankingiem kampanii i listą podobnych incydentów.
- **Prezentacja:** karty kampanii, interaktywny graf powiązań z przesłankami na krawędziach, szczegóły materiału.
- **Ocena:** ARI, NMI, F1 par, B-cubed, test przypisywania nowych materiałów.
- **Eksport:** Neo4j (Cypher), CSV z przesłankami, JSON.
- **Harmonogram:** cykliczne skanowanie Biblioteki Reklam Meta po słowach kluczowych i ponowne sprawdzanie znanych domen.

## Uruchomienie

### Windows – najprościej
Dwuklik na **`START.bat`**. Za pierwszym razem skrypt utworzy środowisko i zainstaluje biblioteki (1–3 minuty), potem otworzy przeglądarkę na `http://localhost:8000`.
W zakładce **Zbiór danych** kliknij **„Wczytaj zbiór demonstracyjny”**.

OCR jest opcjonalny. Bez niego działa wszystko poza odczytem tekstu z obrazów. Aby go włączyć, zainstaluj Tesseract dla Windows (instalator UB Mannheim: https://github.com/UB-Mannheim/tesseract/wiki) i w kroku *Additional language data* zaznacz *Polish*. `START.bat` sam znajdzie go w `C:\Program Files\Tesseract-OCR`. Bez polskiego pakietu OCR działa w trybie angielskim.

### Docker (zalecane do oceny – zawiera OCR z językiem polskim)
```bash
docker compose up --build
# → http://localhost:8000
```

### Linux / macOS
```bash
./start.sh            # albo: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python app.py
```
Wymagania: Python 3.10+, opcjonalnie `tesseract-ocr` + `tesseract-ocr-pol`.

### Konfiguracja (zmienne środowiskowe, wszystkie opcjonalne)
| Zmienna | Znaczenie |
|---|---|
| `PORT`, `HOST` | port i interfejs serwera (domyślnie 8000, 0.0.0.0) |
| `FTF_DB` | ścieżka bazy SQLite (domyślnie `data/ftf.sqlite`) |
| `OCR_LANGS`, `TESSERACT_CMD` | języki OCR (`pol+eng`) i ścieżka do tesseract.exe |
| `ANTHROPIC_API_KEY`, `CLAUDE_MODEL` | opcjonalny opis kreacji modelem wizyjnym (tekst, osoby, logotypy) |
| `META_ACCESS_TOKEN` | token Ad Library API dla harmonogramu ([dostęp](https://www.facebook.com/ads/library/api)) |

### Rozpoznawanie twarzy (opcjonalne)
```bash
python tools/download_models.py      # modele YuNet + SFace (OpenCV Zoo)
# zdjęcia referencyjne: data/faces/Robert Lewandowski/1.jpg, data/faces/Rafał Brzoska/1.jpg …
```
Bez modeli działa wykrywanie osób z tekstu (OCR, `data/persons.json`) i porównanie wycinków twarzy.

## Aplikacja mobilna

Folder `mobile/` – klient React Native (Expo) robiący to samo co strona: zrzut ekranu, zdjęcie, film, link albo tekst
→ znana kampania / duplikat / nowy wzorzec z przesłankami, przegląd kampanii i materiałów.
Uruchomienie: serwer (`START.bat`), potem `mobile/MOBILE.bat` i kod QR w Expo Go. Szczegóły: [mobile/README.md](mobile/README.md).

## Ocena na zbiorze organizatora

Zbiór z polem etykiety (`label` / `campaign` / `cluster`) wczytaj w aplikacji, a wyniki pojawią się w zakładce *Ocena*. Można też z linii poleceń:
```bash
python tools/evaluate_dataset.py sciezka/do/zbioru            # folder z manifestem, .zip, .json lub .csv
python tools/evaluate_dataset.py zbior.zip --network --json wyniki.json
python tools/holdout_test.py                                 # test nowych wariantów i pułapek
```
Wyniki na syntetycznym zbiorze demonstracyjnym: ARI 1.0, F1 par 1.0, test nowych materiałów 10/10. To dowód, że metoda działa zgodnie z założeniami, **nie** prognoza skuteczności na danych organizatora. Patrz [METODYKA.md](METODYKA.md), sekcja 6.

### Format danych (elastyczny)
Manifest JSON (`{"items":[…]}` lub lista), JSONL albo CSV (separator `,` `;` lub tab). Rozpoznawane pola:
- tekst: `text`, `body`, `ad_creative_bodies`, `description`, `caption`…
- URL: `url`, `link`, `landing_url`, `link_url`…
- plik: `image`, `screenshot`, `file`, `video`, `html` (ścieżka względna w ZIP/folderze)
- etykieta: `label`, `campaign`, `cluster`; data: `date`, `ad_delivery_start_time`; id: `id`, `ad_id`
- opcjonalnie gotowe metadane: `meta: {trackers, nameservers, ips, registrar, created, …}`

Folder bez manifestu też zadziała: każdy plik to osobny materiał.

## Struktura

```
app.py                 serwer WWW + API (biblioteka standardowa, ThreadingHTTPServer)
ftf/extract.py         ujednolicony rekord cech z dowolnego wejścia
ftf/infra.py           przekierowania, HTML, trackery, DOM, RDAP, DNS, TLS, crt.sh
ftf/visual.py          hashe percepcyjne, wycinanie kreacji, OCR, QR, twarze, wideo
ftf/lexicon.py         osoby, marki, tematy, chwyty manipulacyjne
ftf/engine.py          podobieństwo, duplikaty, grupowanie, przypisanie nowych
ftf/evaluate.py        miary jakości
ftf/importer.py        import zbiorów (ZIP/JSON/JSONL/CSV/folder)
ftf/scheduler.py       Biblioteka Reklam Meta + ponowne sprawdzanie domen
ftf/export.py          Neo4j Cypher, CSV, JSON
static/                interfejs WWW (HTML/CSS/JS bez zależności)
mobile/                aplikacja mobilna (Expo / React Native)
tools/                 zbiór demo, ocena, test hold-out, pobieranie modeli
```

## Biblioteki, modele i usługi (licencje)

| Komponent | Zastosowanie | Licencja |
|---|---|---|
| Python (stdlib: http.server, urllib, ssl, sqlite3) | serwer, sieć, baza | PSF |
| NumPy | obliczenia | BSD-3 |
| scikit-learn | TF-IDF, klastrowanie, miary | BSD-3 |
| Pillow | obrazy, hashe percepcyjne | MIT-CMU (HPND) |
| OpenCV (opencv-python-headless) | QR, wideo, twarze | Apache 2.0 |
| Tesseract OCR (opcjonalny) | OCR pol+eng | Apache 2.0 |
| YuNet, SFace – OpenCV Zoo (opcjonalne) | wykrywanie i rozpoznawanie twarzy | Apache 2.0 |
| Czcionka Archivo (Google Fonts) | interfejs WWW i mobilny | SIL OFL 1.1 |
| Expo, React Native, expo-image-picker, AsyncStorage | aplikacja mobilna | MIT |
| rdap.org | dane rejestracyjne domen i IP | usługa publiczna, bez klucza; limity zapytań |
| crt.sh | Certificate Transparency | usługa publiczna, bez klucza; bywa przeciążona |
| Meta Ad Library API (opcjonalne) | harmonogram | wymaga tokenu i weryfikacji tożsamości; regulamin Meta |
| Anthropic Claude API (opcjonalne) | opis kreacji | wymaga klucza API, płatne za użycie |

Do oceny nie są potrzebne żadne klucze API: wszystkie funkcje podstawowe działają bez nich.

## Zbiór demonstracyjny
`data/demo` to **zbiór syntetyczny** wygenerowany przez `tools/make_demo.py`: 30 materiałów, 6 kampanii i 3 legalne reklamy. Zawiera warianty, duplikaty, zrzuty z telefonu, materiały bez metadanych i dwie kampanie jednego operatora. Nie są to prawdziwe reklamy ani wizerunki. Materiały organizatora nie są dołączone (zasady wyzwania zabraniają ich rozpowszechniania).
