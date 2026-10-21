# Contribuire a Iudex

Grazie dell'interesse. Poche regole, per tenere il progetto coerente.

## Prima di scrivere codice

- Apri una segnalazione per descrivere il problema o l'idea, così si evita lavoro doppio.
- Iudex interroga un server pubblico della Corte di Cassazione: ogni modifica che
  aggiunge richieste al server va discussa prima. Non sono accettate funzioni di
  scaricamento massivo, scansione dell'archivio o ricerca per nome di persona.

## Ambiente

```bat
git clone https://github.com/SOsintOps/Iudex.git
cd Iudex
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .[dev]
```

Su Linux e macOS: `.venv/bin/python`. Serve Python 3.11 o successivo.

## Stile

- Testi, commenti, messaggi di commit e interfaccia in **italiano**; identificatori di
  codice in inglese.
- `ruff check iudex tests` deve passare (configurazione in `pyproject.toml`, righe da
  100 caratteri).
- I test (`pytest`) non toccano la rete: le risposte del server sono simulate con `respx`.
- Ogni modifica visibile a chi usa l'app va nel `CHANGELOG.md` e nella pagina
  `iudex/static/versioni.html`, che riporta lo stesso registro dentro l'app.

## Struttura del repository

| Percorso | Contenuto |
|----------|-----------|
| `iudex/` | il pacchetto Python: server, client HTTP, query, cache, esportazioni, MCP, finestra |
| `iudex/static/` | interfaccia (HTML, CSS, JavaScript senza dipendenze), pagine di aiuto, font, icone |
| `iudex/certs/` | certificato intermedio per la catena TLS del server della Corte |
| `tests/` | test automatici |
| `docs/` | analisi del sito, domande frequenti, guida, software simili, immagini del README |
| `assets/logo/` | logo originale e script che genera logo, marchio e favicon |
| `scripts/` | avviatori per Windows |
| `.github/` | integrazione continua, Dependabot, modelli per segnalazioni e pull request |

## Pull request

Una pull request per argomento, con una descrizione breve di che cosa cambia e come è
stata verificata. Il modello in `.github/PULL_REQUEST_TEMPLATE.md` ricorda i controlli.
