@echo off
rem Avvia Iudex sulla porta 8765 e apre il browser.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Ambiente virtuale assente: eseguo l'installazione.
  python -m venv .venv || exit /b 1
  .venv\Scripts\python.exe -m pip install -q -e . || exit /b 1
)
start "" http://127.0.0.1:8765/
.venv\Scripts\python.exe -m iudex
