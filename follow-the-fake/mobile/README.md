# Follow the Fake – aplikacja mobilna

Klient mobilny (React Native + Expo) dla serwera Follow the Fake. Robi to samo co strona WWW:
zrzut ekranu / zdjęcie / film / link / tekst → **znana kampania, duplikat albo nowy wzorzec**,
lista podobnych incydentów z przesłankami, przegląd kampanii i materiałów.

## Uruchomienie (Windows)
1. Uruchom serwer: `START.bat` w głównym folderze projektu.
2. Dwuklik na `mobile/MOBILE.bat` – za pierwszym razem tworzy projekt Expo i instaluje biblioteki.
3. Zeskanuj kod QR: Android – aplikacja **Expo Go**, iPhone – aparat (zaloguj się w Expo Go i w `npx expo login` tym samym kontem).
4. W aplikacji: **Ustawienia** → adres komputera, np. `http://192.168.1.23:8000` (IP z `ipconfig`). Telefon i komputer w tym samym Wi-Fi.

## Ręcznie
```bash
npx create-expo-app@latest ftf-app --template blank
cd ftf-app
npx expo install expo-image-picker @react-native-async-storage/async-storage @expo-google-fonts/archivo expo-font
# skopiuj App.js i folder src/ do ftf-app
npx expo start
```
Biblioteki: Expo (MIT), React Native (MIT), expo-image-picker (MIT), AsyncStorage (MIT), czcionka Archivo (SIL OFL 1.1).
