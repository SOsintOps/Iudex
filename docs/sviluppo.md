# Sviluppo

Le linee guida per contribuire al progetto sono descritte in
[CONTRIBUTING.md](../CONTRIBUTING.md), le modalità di segnalazione delle vulnerabilità di
sicurezza in [SECURITY.md](../SECURITY.md) e il codice di condotta in
[CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md).

## Controlli di qualità e test

```bat
.venv\Scripts\python.exe -m pip install -e .[dev]
.venv\Scripts\python.exe -m ruff check src tests packaging
.venv\Scripts\python.exe -m pytest
```

La suite di test automatici opera interamente offline (le risposte dei server della Corte di
Cassazione e di Normattiva sono simulate).

## Struttura del progetto

| Modulo / Percorso | Compito |
|-------------------|---------|
| `src/iudex/query.py` | traduzione dei criteri di ricerca in query Apache Solr conformi alla sintassi di SentenzeWeb (implementazione autonoma); riconoscimento ed elaborazione dei riferimenti normativi |
| `src/iudex/client.py` | client HTTP con limitazione della frequenza delle richieste (*rate limiting*) e configurazione del contesto TLS con certificato intermedio |
| `src/iudex/norme.py` | acquisizione del testo degli articoli dall'API Open Data di Normattiva (client HTTP, parser dell'articolato e delle note), generazione dei collegamenti EUR-Lex (CELEX), estrazione delle disposizioni citate per l'esportazione FollowTheMoney |
| `src/iudex/cache.py` | banca dati locale SQLite con schema versionato e migrazioni automatiche: cronologia, esecuzioni e risultati, ricerche salvate, provvedimenti preferiti, motivazioni integrali, cache temporanea, diario di consultazione, pronunce consultate, PDF, impostazioni, postazioni di lavoro; fusione senza duplicati di archivi provenienti da altri computer |
| `src/iudex/export.py` | esportazione in formato CSV, JSON, Markdown, JSONL e pacchetto ZIP (incluso lo storico completo); ricostruzione strutturata dei paragrafi della motivazione e del dispositivo |
| `src/iudex/importazione.py` | acquisizione e unione di un pacchetto ZIP, di un file JSONL o di una copia del database SQLite proveniente da un'altra installazione di Iudex |
| `src/iudex/pdf.py` | gestione della cartella di archiviazione, denominazione e apertura delle copie ufficiali dei provvedimenti in formato PDF |
| `src/iudex/preferenze.py` | gestione delle opzioni configurabili nella scheda Impostazioni: valori predefiniti, convalida formale, variabili d'ambiente |
| `src/iudex/impronte.py` | profili di intestazioni HTTP (*User-Agent* e *Client Hints*) predefiniti e personalizzati |
| `src/iudex/accesso.py` | generazione e verifica del token di autenticazione locale per la finestra nativa e per il server MCP |
| `src/iudex/app.py` | server web FastAPI, endpoint API JSON, protezione degli accessi alle pagine e alle API locali |
| `src/iudex/mcp_server.py` | server conforme al *Model Context Protocol* (extra `mcp`) |
| `src/iudex/desktop.py` | finestra applicativa nativa multipiattaforma (extra `desktop`) |
| `src/iudex/autonoma/` | infrastruttura dell'applicazione autonoma: percorsi dati specifici per sistema operativo, server con endpoint `/health`, selezione della porta e monitoraggio del processo genitore, finestra con icona nell'area di notifica |
| `src/iudex/static/` | interfaccia utente e pagine informative integrate (HTML, CSS e JavaScript privi di dipendenze esterne), caratteri tipografici locali, icone |
| `tests/` | test automatici (eseguiti interamente senza connessione di rete) |
| `packaging/` | configurazione per la generazione dei pacchetti distribuibili: PyInstaller, Inno Setup (Windows), AppImage (Linux), manifesto `latest.json` |
| `docs/` | documentazione tecnica e manuale: analisi del sito della Corte, modalità di consultazione, integrazione Normattiva, guida all'utilizzo, domande frequenti, installazione, sviluppo, software simili, immagini |
| `assets/logo/` | grafica vettoriale originale e script di generazione di logo, marchio, favicon e immagine di anteprima social (`docs/immagini/anteprima-social.png`) |
| `scripts/` | script di avvio rapido per ambiente Windows |
| `.github/` | flussi di integrazione continua (ruff + pytest), configurazione Dependabot, modelli per segnalazioni e pull request |

## Vedi anche

- [Pagina principale (README)](../README.md)
- [Linee guida per contribuire (CONTRIBUTING.md)](../CONTRIBUTING.md)
- [Installazione](installazione.md)
- [Analisi tecnica di SentenzeWeb](analisi-sito.md)
