@echo off
rem Avvia Iudex come finestra nativa (richiede l'extra desktop: pip install -e .[desktop]).
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe (
  python -m venv .venv || exit /b 1
  .venv\Scripts\python.exe -m pip install -q -e .[desktop] || exit /b 1
)
.venv\Scripts\python.exe -m iudex.desktop
