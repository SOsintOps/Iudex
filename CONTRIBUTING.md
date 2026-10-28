# Contribuire a Iudex

Grazie dell'interesse. Poche regole, per tenere il progetto coerente.

## Prima di scrivere codice

- Chi partecipa accetta il [codice di condotta](CODE_OF_CONDUCT.md).

- Apri una segnalazione per descrivere il problema o l'idea, così si evita lavoro doppio.
- Iudex interroga un server pubblico della Corte di Cassazione: ogni modifica che
  aggiunge richieste al server va discussa prima. Non sono accettate funzioni di
  scaricamento massivo, scansione dell'archivio o ricerca per nome di persona.

## Ambiente

```bat
git clone https://github.com/SOsintOps/Iudex.git
cd Iudex
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .[dev,desktop,mcp]
.venv\Scripts\python.exe -m iudex.desktop
```

Su Linux e macOS: `.venv/bin/python`. Serve Python 3.11 o successivo. Iudex si usa dalla sua
finestra (`iudex.desktop`); `python -m iudex` avvia il solo server, che risponde solo con il
token del file `token` nella cartella dei dati.

## Stile

- Testi, commenti, messaggi di commit, interfaccia e identificatori di codice in **italiano**.
- `ruff check src tests packaging` deve passare (configurazione in `pyproject.toml`, righe da
  100 caratteri).
- I test (`pytest`) non toccano la rete: le risposte del server sono simulate con `respx`.
- Ogni modifica visibile a chi usa l'app va nel `CHANGELOG.md` e nella pagina
  `src/iudex/static/versioni.html`, che riporta lo stesso registro dentro l'app.
- Lo schema del database cambia solo con una migrazione numerata nuova in `src/iudex/cache.py`
  (`VERSIONE_SCHEMA`, `MIGRAZIONI`), mai modificando quelle già rilasciate.
- I lavori lunghi si discutono prima in una segnalazione.

## Struttura del repository

| Percorso | Contenuto |
|----------|-----------|
| `src/iudex/` | il pacchetto Python (layout `src`): server, client HTTP, query, cache, esportazioni, MCP, finestra |
| `src/iudex/static/` | interfaccia (HTML, CSS, JavaScript senza dipendenze), pagine di aiuto, font, icone |
| `src/iudex/certs/` | certificato intermedio per la catena TLS del server della Corte |
| `tests/` | test automatici |
| `packaging/` | installer: PyInstaller, Inno Setup (Windows), AppImage (Linux), `latest.json` |
| `docs/` | analisi del sito, domande frequenti, guida, software simili, immagini del README |
| `assets/logo/` | logo originale e script che generano logo, marchio, favicon e anteprima social (`docs/immagini/anteprima-social.png`) |
| `scripts/` | avviatori per Windows |
| `.github/` | integrazione continua, Dependabot, modelli per segnalazioni e pull request |

## Pull request

Una pull request per argomento, con una descrizione breve di che cosa cambia e come è
stata verificata. Il modello in `.github/PULL_REQUEST_TEMPLATE.md` ricorda i controlli.
