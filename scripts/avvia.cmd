@echo off
rem Avvia Iudex e apre il browser quando il server risponde.
rem Porta e indirizzo: variabili IUDEX_PORTA (predefinita 8765) e IUDEX_HOST, lette da Iudex.
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe (
  echo Ambiente virtuale assente: eseguo l'installazione.
  python -m venv .venv || exit /b 1
  .venv\Scripts\python.exe -m pip install -q -e . || exit /b 1
)
.venv\Scripts\python.exe -m iudex --apri
