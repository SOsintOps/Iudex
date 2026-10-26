# Registro delle modifiche

## Da rilasciare

### App autonoma
- Pacchetto `iudex/autonoma/`, usato anche da Praeco: cartella dei dati per sistema quando
  Iudex gira da un eseguibile (`%APPDATA%\Iudex`, `~/Library/Application Support/Iudex`,
  `~/.local/share/iudex`; dai sorgenti resta `dati/`), con le sottocartelle `backup/` e
  `log/`; `GET /health` riconoscibile (`{"app": "iudex", "versione", "pid"}`); scelta della
  porta (riuso dell'istanza già accesa, altrimenti la prima porta libera); sorveglianza del
  processo genitore; log su file con rotazione.
- `python -m iudex` accetta `--data-dir`, `--port` e `--parent-pid` (backend di un'app, come
  in Voicebox).
- Copia di sicurezza settimanale del database con `VACUUM INTO` in `backup/` nella cartella dei
  dati (le ultime otto), all'avvio.
- Aggiornamenti dell'app installata: all'avvio Iudex legge `latest.json` della release più
  recente su GitHub e, se c'è una versione nuova, lo dice nella scheda Stato e nel piè di
  pagina; "Scarica e installa" prende l'installer, ne controlla lo sha256 pubblicato in
  `latest.json` e lo avvia. Niente aggiornamenti silenziosi. Dai sorgenti il controllo è
  spento (si aggiorna con git); `IUDEX_AGGIORNAMENTI=0` lo spegne anche nell'app installata.
- La finestra nativa (`python -m iudex.desktop`) ha un'icona nell'area di notifica con Apri,
  Mantieni in esecuzione ed Esci; l'extra `desktop` aggiunge `pystray` e `pillow`.

### Rete
- **Impronta browser del giorno**: Iudex dichiara gli header (User-Agent, Accept-Language,
  client hints, Accept della pagina) di un browser installato su Windows, Chrome 155, Edge
  157 o Firefox 158, scelto dalla data del calendario: lo stesso per tutta la giornata anche
  riavviando, un altro a mezzanotte, quando la sessione (cookie) si riapre. `IUDEX_IMPRONTA`
  (`chrome`, `edge`, `firefox`) ne fissa uno; la scheda Stato e `/api/stato` mostrano quello
  in uso. I `sec-ch-ua` di Chromium si calcolano dalla versione con l'algoritmo del browser
  (`iudex/impronte.py`). Cambiano solo gli header: l'impronta TLS resta quella di Python.

### Manutenzione
- Versioni minime delle dipendenze alzate: `fastapi` ≥0.157, `uvicorn[standard]` ≥0.54,
  `httpx` ≥0.28.1, `mcp` ≥2.3, `pywebview` ≥6.2.1, `setuptools` ≥84.2.1; nella CI `actions/checkout` e `actions/setup-python` v7.
- La versione del pacchetto si legge da `iudex/__init__.py`: `pyproject.toml` diceva
  ancora 0.4.0.
- Dependabot raggruppa gli aggiornamenti: una PR al mese per pip e una per le Actions.

## 0.6.0 — 2026-10-22

### Ricerca
- **Segnali di orientamento**: in cima ai filtri, quanti provvedimenti fra i risultati
  dichiarano un contrasto («contrasto giurisprudenziale», «difforme orientamento») o
  richiamano un orientamento consolidato («orientamento consolidato», «in senso conforme»).
  I conteggi sono `facet.query` nella stessa richiesta della ricerca; la spunta filtra e
  evidenzia le frasi. Senza spunta i risultati restano quelli del sito. Idea ed elenco delle
  frasi da mcp-legal-it (capazme, Apache-2.0).

### Esportazione
- **FollowTheMoney**: le sentenze consultate come entità `.ftm` (CourtCase, Document,
  Person, CourtCaseParty), per `ftm` e Aleph; validato con followthemoney 4.11.1.

### Server MCP
- Errori come `ToolError` (il modello legge il messaggio), annotazioni di sola lettura,
  parametri con valori ammessi nello schema, filtro `segnale` e conteggi dei segnali.
- `leggi_sentenza` alla prima lettura di un testo lungo restituisce l'inizio e la parte
  dal P.Q.M., con i caratteri omessi indicati. Richiede `mcp` 2.x.
- Test in memoria con `Client(mcp)`; la CI installa l'extra `mcp`.

### Robustezza
- Dopo un 403 o un 429 Iudex non manda richieste per il tempo di `Retry-After` (secondi o
  data HTTP; un minuto se manca, al più un'ora) e lo mostra nella scheda Stato; il 403 e
  una pagina HTML al posto del JSON fanno riaprire la sessione.
- Risposte del server senza l'elenco dei documenti e risposte HTML del servizio dei
  riferimenti normativi sono errori espliciti e non finiscono in cache.
- Errori imprevisti in JSON («errore interno di Iudex»), dati non validi con 422 e campo;
  corpi di POST e PUT validati con Pydantic.
- Voci di cache scadute tolte all'avvio (indici su `quando`), seguite da `VACUUM` così
  il file si riduce e i dati cancellati non restano recuperabili.
- `python -m iudex --apri` apre il browser quando il server risponde, sulla porta di
  `IUDEX_PORTA`; se Iudex è già avviato apre quello. `avvia.cmd` lo usa.

### Documentazione
- Revisione terminologica dei testi; guida, domande frequenti e README aggiornati;
  anteprima social `docs/immagini/anteprima-social.png`.

## 0.5.0 — 2026-10-21

### Diario delle consultazioni
- Scheda **Diario**: archivio personale permanente, per giorno, delle ricerche fatte
  (parole, filtri, risultati, pagina) e delle sentenze aperte da ciascuna. La stessa
  sentenza aperta in giorni diversi da ricerche diverse compare sotto ognuna (tabella
  `diario`, una riga per azione).
- Delle sentenze aperte Iudex conserva la **risposta intera del server**, testo compreso,
  una volta sola per sentenza (tabella `consultate`, JSON compresso con zlib); dei risultati
  non aperti solo il conteggio. Una sentenza già in cache ma mai consultata viene richiesta
  una volta per acquisire la risposta JSON integrale. Nessun pulsante della cache tocca le due tabelle.
- Nel pannello di lettura: «Aperta *N* volte», prima apertura e ricerche di provenienza
  cliccabili (`/api/sentenza/{id}?da=<permalink>`).
- API: `GET /api/diario` (per giorno o per sentenza), `GET /api/diario/giorni`,
  `GET /api/consultate`, `GET /api/consultate/{id}/grezzo`, `GET /api/export/diario`
  (JSONL, CSV), `GET /api/export/consultate` (zip con `<id>.json` e `<id>.txt`),
  `POST /api/backup` (`VACUUM INTO dati/iudex-AAAAMMGG-HHMMSS.sqlite`).
- Guida, domande frequenti e README aggiornati; i testi conservati contengono dati
  personali in chiaro e restano solo in `dati/`.

### Correzioni
- `query.py`: parentesi attorno alle due clausole `tipoprov` delle ordinanze; senza,
  `ord. 5/2023` restituiva tutte le ordinanze interlocutorie (in Solr `AND` lega più forte
  di `OR`).
- Nessun collegamento al PDF per i provvedimenti «in fase di oscuramento», come sul sito.
- `client.py`: il `GET` iniziale della pagina avviene dentro il lock (`_invia` +
  `_richiesta`); `app.py`: controllo dell'header `Host` contro il DNS rebinding, lista
  delle sigle in memoria; `mcp_server.py`: host e porta dalle impostazioni.

## 0.4.0 — 2026-10-21

### Interfaccia
- Il menu **Informazioni** si chiama **Help** e contiene due pagine nuove: la **Guida
  all'utilizzo** (flusso di lavoro e funzione di ogni voce) e la **Licenza** (MIT, testi
  della Corte, componenti di terzi).
- **Logo** nella barra di navigazione, a sinistra del nome, con variante per il tema scuro.
- Il piè di pagina mostra solo la versione; il conteggio delle richieste e della cache
  resta nella scheda Stato.

### Repository
- Riordino secondo le convenzioni di GitHub: avviatori in `scripts/`, logo originale e
  script di generazione in `assets/logo/`, `CONTRIBUTING.md`, `SECURITY.md`,
  `.editorconfig`, `.gitattributes`, integrazione continua (ruff + pytest su Python 3.11 e
  3.13), Dependabot mensile e modelli per segnalazioni e pull request in `.github/`.
- `docs/analisi-sito.md`: sezione sulle chiamate e pagine del sito che Iudex non usa
  (permalink `detail.html`, telemetria `app.document`, requisitoria, precedenti collegati,
  liste dei filtri con `facet.prefix`, suggerimenti con `kind:"key"`, provvedimenti in
  fase di oscuramento).

### Ricerca
- Costruttore delle query riscritto **dalla specifica della sintassi** (`docs/analisi-sito.md`),
  senza codice derivato dal JavaScript del sito (che è GPL-3). Stesse clausole del sito e tre
  miglioramenti: `NOT parola` e `-parola` **escludono davvero** (sul sito finivano dentro una
  frase); i caratteri speciali sono protetti anche con gli operatori (`a:b OR c`); gli
  estremi accettano `Cass. civ.` davanti, il tipo in fondo (`n. 99 del 2025 sent.`) e il
  trattino (`123-2024`).

## 0.3.1 — 2026-10-21

### Grafica
- **Logo** di Iudex (bilancia con corona d'alloro e circuiti) nel README, con sfondo
  trasparente e variante per il tema scuro di GitHub.
- **Favicon** ricavata dal logo: tratti bianchi su quadrato blu, leggibile anche a 16 px,
  al posto della "I" provvisoria.
- La voce Informazioni della barra ha la stessa grandezza delle altre voci (era rimasta
  più piccola).
- Schermate del README rifatte con la barra attuale (icone sole e luna).
- Tolto l'avviso sul Garante dalla pagina iniziale; la risposta sui dati personali resta
  nelle domande frequenti.

## 0.3.0 — 2026-10-21

### Grafica
- Interfaccia allineata a **Exploratores**: stesse variabili di colore (`#0066ff`, `#333`,
  `#888`, `#f9f9f9`), font Inter ospitato in locale, barra di navigazione fissa con
  sottomenu, riquadro di ricerca, pulsanti bianchi con passaggio in blu, tabelle con righe
  alternate, piè di pagina fisso. Sparisce il carattere Palatino e la palette porpora.
- **Tema scuro** con scelta **automatica in base all'orario**: per impostazione predefinita
  scuro dalle 19 alle 7 (ora del computer), orari modificabili nella scheda Stato; il
  tema si sceglie con le icone sole e luna nella barra; un secondo clic su quella attiva
  torna all'automatico.
- Le voci Cronologia, Ricerche salvate, Preferiti e Stato stanno nella barra di navigazione;
  le pagine informative sono nel sottomenu Informazioni. Indirizzi `#cronologia`,
  `#salvate`, `#preferiti`, `#stato` per aprire direttamente una scheda.

## 0.2.0 — 2026-10-21

### Novità
- Filtro per **materia** (classificazione del CED), nella stessa risposta della ricerca.
- Pannello di lettura: testo in **paragrafi**, salto al **P.Q.M.**, carattere regolabile,
  evidenziazione calcolata dal server anche per frasi, troncamenti e riferimenti normativi.
- **Riferimenti normativi** del provvedimento leggibili e cliccabili (ricerca per norma).
- **Colonne ridimensionabili** trascinando le maniglie: pannelli dei filtri e del testo,
  tabelle di cronologia, ricerche salvate e preferiti; larghezze conservate nel browser,
  doppio clic per ripristinare, frecce da tastiera.
- Cronologia, ricerche salvate e preferiti in tabelle; **note** sui preferiti; eliminazione
  delle singole voci di cronologia.
- **Controllo delle novità** delle ricerche salvate, su richiesta (una chiamata per ricerca).
- **Esportazione** fino ai primi 100 risultati (al più due richieste).
- Barre proporzionali nei filtri; scorciatoie `j`/`k`, `Invio`, `Alt+→`/`Alt+←`.
- Pulsanti per svuotare la cache; percorso dell'archivio nella scheda Stato.
- Pagine informative: domande frequenti, versioni, software simili (anche in `docs/`).
- **Finestra nativa** (`avvia-finestra.cmd`, extra `desktop`, pywebview).
- **Server MCP** (`python -m iudex.mcp_server`, extra `mcp`) per assistenti e LLM locali.

### Sicurezza
- Le API rispondono solo all'interfaccia di Iudex (header `X-Iudex`): una pagina di un
  altro sito non può usare Iudex per interrogare la Corte.

### Correzioni
- Il piè di pagina non si sovrappone più all'elenco dei risultati.
- La navigazione fra le occorrenze scorre solo il pannello del testo.

## 0.1.0 — 2026-10-21

Prima versione.

- Ricerca su SentenzeWeb per parole, estremi e riferimento normativo con la stessa sintassi
  del sito ufficiale; filtri per archivio, tipo, sezione, anno e sottosezione.
- Una sola richiesta al server per ricerca (conteggi dei filtri inclusi), intervallo minimo
  di 2 secondi, nessun suggerimento inviato al server, un solo nuovo tentativo.
- Pannello di lettura con testo integrale, occorrenze evidenziate e navigabili, massima,
  riferimenti normativi indicizzati, collegamento al PDF ufficiale, citazione da copiare.
- Cronologia, ricerche salvate, preferiti, indirizzi ricaricabili.
- Esportazione CSV, JSON e Markdown; cache locale SQLite dei testi aperti.
- Documentazione dell'analisi del sito in `docs/analisi-sito.md`.
