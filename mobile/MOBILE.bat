@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Follow the Fake - aplikacja mobilna
where node >nul 2>nul
if errorlevel 1 (
  echo Instaluje Node.js...
  winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
  echo Zamknij to okno i uruchom MOBILE.bat ponownie.
  pause
  exit /b
)
if not exist "ftf-app\package.json" (
  echo Tworze projekt aplikacji - 1-3 minuty...
  call npx --yes create-expo-app@latest ftf-app --template blank
  cd ftf-app
  call npx --yes expo install expo-image-picker @react-native-async-storage/async-storage @expo-google-fonts/archivo expo-font
  cd ..
)
copy /Y "App.js" "ftf-app\App.js" >nul
xcopy /E /I /Y "src" "ftf-app\src" >nul
cd ftf-app
echo.
echo Zeskanuj kod QR: Android - aplikacja Expo Go, iPhone - aparat.
echo W aplikacji: Ustawienia - wpisz adres komputera, np. http://192.168.1.23:8000
echo.
call npx expo start
pause
