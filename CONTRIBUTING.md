# Contribuire a Iudex

Grazie dell'interesse. Poche regole, per tenere il progetto coerente.

## Prima di scrivere codice

- Chi partecipa accetta il [codice di condotta](CODE_OF_CONDUCT.md).

- Apri una segnalazione per descrivere il problema o l'idea, così si evita lavoro doppio.
- Iudex interroga un server pubblico della Corte di Cassazione: ogni modifica che
  aggiunge richieste al server va discussa prima. Non sono accettate funzioni di
  scaricamento massivo o di scansione dell'archivio.
- Le stesse regole valgono per **Normattiva**, da cui Iudex legge il testo delle norme: solo
  l'**API Open Data** (`api.normattiva.it`), mai il sito `www.normattiva.it`, che resta un
  link da aprire nel browser; intervallo minimo di **2 secondi** fra due richieste
  (`IUDEX_INTERVALLO_NORMATTIVA`), una richiesta alla volta, pausa quando la fonte la chiede;
  **mai richieste senza un'azione dell'utente** (nessuna lettura anticipata, nessun nuovo
  tentativo automatico dall'interfaccia, nessuno scaricamento di atti interi). I testi sono
  dati IPZS in licenza CC BY 4.0: ovunque compaiano va lasciata l'attribuzione
  "Fonte: Normattiva (IPZS), CC BY 4.0". Verso EUR-Lex Iudex produce solo link, senza
  richieste.

## Ambiente

```bat
git clone https://github.com/SOsintOps/Iudex.git
cd Iudex
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .[dev,desktop,mcp]
.venv\Scripts\python.exe -m iudex.desktop
```

Su Windows l'extra `dev` installa `followthemoney`, che richiede PyICU: PyPI non ha wheel di
PyICU per Windows, quindi dopo aver creato il venv e prima di `pip install -e .[dev,desktop,mcp]`
va installato il wheel per la propria versione di Python da
<https://github.com/cgohlke/pyicu-build/releases> (la fonte indicata dal README di PyICU), con
`.venv\Scripts\python.exe -m pip install <file .whl scaricato>`.
Su Linux e macOS basta il pacchetto `libicu` del sistema (per esempio `libicu-dev` su Debian
e Ubuntu, `icu4c` con Homebrew).

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
| `docs/` | analisi del sito, consultazione del sito, Normattiva, installazione, sviluppo, domande frequenti, guida, software simili, immagini del README |
| `assets/logo/` | logo originale e script che generano logo, marchio, favicon e anteprima social (`docs/immagini/anteprima-social.png`) |
| `scripts/` | avviatori per Windows |
| `.github/` | integrazione continua, Dependabot, modelli per segnalazioni e pull request |

## Pull request

Una pull request per argomento, con una descrizione breve di che cosa cambia e come è
stata verificata. Il modello in `.github/PULL_REQUEST_TEMPLATE.md` ricorda i controlli.
