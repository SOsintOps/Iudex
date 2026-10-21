# Iudex

Interfaccia locale per interrogare **SentenzeWeb**, la banca dati pubblica delle sentenze
civili e penali della Corte Suprema di Cassazione (<https://www.italgiure.giustizia.it/sncass/>).

Iudex non è un archivio e non copia la banca dati: ogni ricerca interroga il server della
Corte come farebbe il browser, ma con un'interfaccia pensata per leggere e confrontare,
una cronologia, i preferiti, l'esportazione e una cache locale dei testi già aperti.

![Iudex: pagina dei risultati](docs/immagini/risultati.png)

## Che cosa fa

- **Ricerca** per parole, frase esatta, troncamento, operatori `AND`/`OR`/`NOT`, estremi
  (`12345/2024`, `sent. n. 99 del 2025`) e **riferimento normativo** (`art. 18 legge 300/1970`),
  con la stessa sintassi e gli stessi risultati del sito ufficiale.
- **Filtri** per archivio (civile/penale), tipo di provvedimento, sezione, anno e
  sottosezione, con i conteggi, in selezione multipla.
- **Testo integrale** in un pannello di lettura accanto ai risultati, con le occorrenze
  evidenziate e navigabili (`n`/`p` da tastiera), la massima e i riferimenti normativi
  indicizzati dal CED; collegamento al **PDF ufficiale**.
- **Cronologia**, **ricerche salvate** e **preferiti**; ogni ricerca ha un indirizzo
  ricaricabile (`http://127.0.0.1:8765/#testo=…&kind=snciv&anno=2026`).
- **Esportazione** della pagina di risultati in CSV, JSON o Markdown e della singola
  sentenza in Markdown o JSON, con la citazione pronta da copiare.
- Tema chiaro e scuro, righe compatte, nessuna dipendenza esterna nel browser.

## Come interroga il sito (e perché è più leggero del sito stesso)

Il sito ufficiale, per una sola ricerca, invia al server circa venti richieste: una per
ogni lettera digitata (suggerimenti), la ricerca, quattro chiamate per i conteggi dei
filtri e una di telemetria. Iudex ne invia **una**, perché chiede i conteggi dei filtri
nella stessa richiesta della ricerca. Inoltre:

| Regola | Valore |
|--------|--------|
| Richieste in parallelo | 1 |
| Intervallo minimo fra due richieste | 2 secondi (`IUDEX_INTERVALLO`) |
| Nuovi tentativi | 1 solo, su errore di rete o 5xx; nessuno su 403/429 |
| Suggerimenti mentre si digita | nessuna richiesta al server: la lista delle sigle normative è scaricata una volta e tenuta 30 giorni |
| Risposte di ricerca | in cache locale per un'ora: ripetere o ricaricare una ricerca non chiama il server |
| Testi aperti | conservati in locale per sempre: riaprire una sentenza non chiama il server |
| PDF | non scaricati da Iudex: il collegamento apre il documento sul sito della Corte |
| Telemetria del sito (`xway`) | non replicata (`IUDEX_TELEMETRIA=1` per replicarla) |
| Identità dichiarata | User-Agent e header di Chrome, come dal sito ufficiale |

Non c'è alcuna funzione di scaricamento massivo o di scansione dell'archivio, e non va
aggiunta: la banca dati è della Corte, che la pubblica per la consultazione.

I dettagli degli endpoint, dei parametri e dei campi sono in
[docs/analisi-sito.md](docs/analisi-sito.md).

## Installazione

Serve Python 3.11 o successivo.

```bat
git clone https://github.com/SOsintOps/Iudex.git
cd Iudex
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
avvia.cmd
```

`avvia.cmd` apre il browser su <http://127.0.0.1:8765/> e avvia il server; su Linux o
macOS: `.venv/bin/python -m iudex`. I dati locali (cronologia, preferiti, cache) stanno in
`dati/iudex.sqlite`.

Variabili d'ambiente: `IUDEX_PORTA` (8765), `IUDEX_HOST` (127.0.0.1), `IUDEX_DATI`
(cartella dei dati), `IUDEX_INTERVALLO` (secondi fra le richieste), `IUDEX_TTL_RICERCHE`
(secondi di validità della cache delle ricerche), `IUDEX_TELEMETRIA`.

### Certificato TLS

Il server della Corte invia una catena di certificati incompleta (manca l'intermedio
"TI Trust Technologies OV CA"). I browser la completano da soli, Python no: Iudex include
l'intermedio in `iudex/certs/ti_trust_ov_ca.pem` e lo aggiunge al contesto TLS, senza
disattivare la verifica.

## Sviluppo

```bat
.venv\Scripts\python.exe -m pip install -e .[dev]
.venv\Scripts\python.exe -m ruff check iudex tests
.venv\Scripts\python.exe -m pytest
```

I test non toccano la rete (le risposte del server sono simulate).

Struttura:

| Modulo | Compito |
|--------|---------|
| `iudex/query.py` | costruzione delle query Solr, trascritta dal JavaScript del sito |
| `iudex/client.py` | client HTTP con i limiti di cortesia e il contesto TLS |
| `iudex/cache.py` | SQLite: cronologia, ricerche salvate, preferiti, testi, cache |
| `iudex/export.py` | CSV, JSON, Markdown |
| `iudex/app.py` | server FastAPI e API JSON |
| `iudex/static/` | interfaccia (HTML, CSS, JavaScript senza dipendenze) |

## Privacy

Le sentenze contengono nomi e, talvolta, dati sensibili: nel 2024 il Garante per la
protezione dei dati personali ha ammonito la Corte per la presenza, nei testi pubblicati,
di dati sanitari e di vittime di reati (provvedimento n. 435 del 9 maggio 2024). Iudex
conserva in locale solo le sentenze che l'utente apre e non costruisce indici per nome di
persona. Non usarlo per cercare persone.

## Licenza

MIT. I testi delle sentenze sono della Corte Suprema di Cassazione e restano soggetti
alle condizioni con cui la Corte li pubblica.
