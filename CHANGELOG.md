# Registro delle modifiche

## Da rilasciare

### Documentazione
- Domande frequenti: nuova sezione "Lo sviluppo" sull'uso dell'intelligenza artificiale.
- Il repository contiene solo il materiale per chi usa e sviluppa l'app: tolti piani di
  lavoro, avanzamento e liste di prova interne.

## 0.8.0 — 2026-10-28

### Archivio
- Versione dello schema in `PRAGMA user_version` con migrazioni numerate; prima di migrare un
  database che contiene dati dell'utente se ne fa una copia in `backup/` (come promesso dalla
  0.7.0, finora non avveniva). Nuova tabella `impostazioni`.

### Impostazioni
- Nuova scheda Impostazioni (`GET/PUT /api/impostazioni`, modulo `iudex/preferenze.py`):
  conservazione dello storico, cartella e apertura dei PDF, modo dell'impronta del browser
  (rotazione giornaliera, fissa, personalizzata, personalizzate a rotazione). Le scelte si
  salvano nell'archivio; `IUDEX_IMPRONTA`, se impostata, vince e la scheda mostra il campo
  bloccato.
- Impronte del browser: oltre alla rotazione giornaliera delle predefinite, una predefinita
  fissa, una personalizzata o le personalizzate a rotazione (con o senza le predefinite).
  Un'impronta personalizzata (nome, User-Agent, Accept-Language, `sec-ch-ua` facoltativo) si
  salva solo se è coerente: per Chrome ed Edge `sec-ch-ua` con la stessa versione dello
  User-Agent (ricavato se manca), per Firefox nessun client hint. "Prova" mostra gli header
  senza contattare la Corte (`POST /api/impronta/prova`); quando l'impronta cambia, la
  richiesta successiva riapre la sessione. `ClientSentenzeWeb` accetta `scegli_impronta`
  (senza, il comportamento di prima, usato da Praeco).
- Nome di questo computer modificabile nelle Impostazioni (compare negli export).
- Gli orari del tema scuro automatico passano dalla scheda Stato alla scheda Impostazioni
  (gruppo Aspetto).

### Interfaccia
- Voci del menu in alto più piccole di circa due punti (1,5 rem, 1,15 rem sotto i 1400 px),
  così ci stanno tutte, Impostazioni compresa.
- Le pagine di aiuto (guida, domande frequenti, versioni, software simili, licenza) hanno lo
  stesso menu dell'app: prima mostravano solo Ricerca, Cronologia e Help.

### Memoria delle ricerche
- Ogni pagina di risultati vista (anche servita dalla cache, anche con "Controlla novità") è
  un'esecuzione permanente con le sentenze mostrate e la loro posizione (tabelle `esecuzioni`
  e `risultati`, schema 3): Iudex sa da quale o quali ricerche è uscita ogni sentenza. La
  cronologia conta quante volte si è fatta una ricerca (`volte`, `prima_volta`). Cancellare
  una ricerca cancella anche le sue esecuzioni.
- Con "Conserva lo storico" spento non si registra niente: cronologia, diario, esecuzioni,
  consultate, testi e risposte in cache.

### Consultazioni
- Badge "già vista" nei risultati, nei preferiti e nelle novità delle ricerche salvate: al
  passaggio del mouse dice quante volte e l'ultima volta che la sentenza è stata aperta (testo
  o PDF), da quali ricerche e in quali ricerche precedenti è uscita. Il pannello di lettura
  elenca le ricerche in cui la sentenza è uscita.
- Diario: nuovo tipo di voce `pdf` (apertura del PDF), contato nei giorni.
- Un'apertura fallita (rete caduta, sentenza non trovata) non finisce più nel diario né fra le
  consultate: prima vi finiva e, con il badge, la sentenza risultava "già vista".
- Una sentenza consultata il cui testo è stato tolto dalla cache si riapre dalla risposta
  intera conservata, senza una nuova richiesta al server.

### PDF
- Il pulsante PDF passa da Iudex (`POST /api/pdf/{id}`): la prima volta scarica il PDF
  ufficiale (una richiesta, con lo stesso ritmo e la stessa sessione delle altre) e lo salva
  come `<id>.pdf` nella cartella dei PDF (tabella `pdf` con dimensione e sha256, schema 4),
  poi lo apre sempre dalla copia locale. Si mostra nel pannello di lettura (`GET /pdf/{id}`,
  solo file locali) o con il programma PDF del computer, come scelto nelle Impostazioni.
  Ogni apertura è una consultazione (voce `pdf` del diario).
- Cartella dei PDF: `pdf/` nella cartella dei dati, oppure quella scritta dall'installer in
  `installazione.ini` (`[pdf] cartella = ...`) o scelta nelle Impostazioni; cambiandola, i PDF
  già salvati si spostano nella nuova. La scheda Stato mostra quanti PDF sono salvati e dove.
- Con lo storico spento il PDF si apre da un file provvisorio cancellato alla chiusura.
- Il vecchio `GET /api/pdf/{id}` (redirect al sito della Corte) è stato tolto.

### Esportazione dello storico
- `GET /api/export/ricerche` e i pulsanti nella scheda Cronologia: CSV per Excel (UTF-8 con
  BOM, punto e virgola; per impostazione predefinita la tabella ricerca→sentenza, con
  consultazioni e PDF), JSONL completo, pacchetto ZIP con i quattro CSV, il JSONL, la risposta
  intera e il testo delle sentenze consultate e i PDF salvati.
- Ogni ricerca, esecuzione e voce del diario registra la macchina su cui è stata fatta (id
  stabile e nome del computer, tabella `macchine`) ed esecuzioni e diario hanno un id stabile
  (`uid`): schema 5, per unire gli archivi di più computer.
- L'export del diario non si ferma più a 5000 voci.

### Importazione dello storico
- Scheda Impostazioni, "Importa uno storico" (`POST /api/importa`): unisce allo storico di
  questo computer il pacchetto ZIP, il JSONL o una copia del database (`.sqlite`, anche di una
  versione vecchia, migrata a parte) di un altro Iudex, senza duplicati: macchine e `uid` di
  esecuzioni e diario, permalink delle ricerche, id delle sentenze consultate. Prima una copia
  di sicurezza; poi un riepilogo di quanto è stato aggiunto e di quanto era già presente.
- I PDF del pacchetto si copiano nella cartella dei PDF se mancano, controllando lo sha256;
  un PDF diverso da quello locale lascia quello locale, uno danneggiato si scarta.

### Solo finestra (come Voicebox)
- Iudex si usa dalla sua finestra: pagine, API e PDF rispondono solo con il token del file
  `token` nella cartella dei dati (creato al primo avvio, rigenerabile con
  `POST /api/token/rigenera`). La finestra entra da `/accesso?codice=...`, che lascia un
  cookie di sessione HttpOnly e SameSite=Strict; il server MCP manda il token nell'header
  `X-Iudex-Token` (riletto dal file a ogni chiamata, oppure `IUDEX_TOKEN`). Un browser che
  apre l'indirizzo locale vede solo l'invito ad aprire Iudex dalla finestra. `/health` e i
  file statici restano liberi.
- Tolti `--apri` e `scripts/avvia.cmd` (la modalità browser): `python -m iudex` resta come
  backend senza finestra per chi integra Iudex; la finestra è `python -m iudex.desktop`.

### Installazione
- Installer per Windows: nuova pagina "Cartella dei PDF" (scritta in
  `%APPDATA%\Iudex\installazione.ini`, letta al primo avvio) e avviso se manca WebView2
  (Windows 10).
- AppImage per Linux: la finestra pywebview con GTK e WebKitGTK del sistema al posto del
  browser; se WebKitGTK manca, un messaggio con il comando per installarlo.
- Senza installer (Linux, sorgenti) la finestra chiede al primo avvio dove conservare i PDF.
- Su Linux Iudex spegne il renderer DMABUF di WebKitGTK (`WEBKIT_DISABLE_DMABUF_RENDERER=1`,
  se non è già impostata): senza accelerazione grafica la finestra restava bianca.
- Workflow di rilascio: PyGObject sotto la 3.51 e i typelib GIRepository e AyatanaAppIndicator
  per la build Linux (con PyGObject recente l'hook di PyInstaller non trova GIRepository 2.0).
- La finestra usa l'icona di Iudex (la stessa dei collegamenti) anche avviata dai sorgenti:
  prima mostrava l'icona di serie di Windows (quella di `pythonw.exe`). Su Windows pywebview
  riceve il `.ico`, su Linux il PNG. Vale anche per Praeco, che usa la stessa finestra.
- Lista delle prove degli installer su macchina virtuale: `docs/prova-installazione.md`.

### App autonoma
- `Guscio(nascosto=True)`: la finestra parte nascosta, solo come icona nell'area di notifica
  (avvio con il sistema, usato da Praeco).

### Correzioni
- L'eseguibile senza console si fermava all'avvio del server ("Unable to configure formatter
  'default'": uvicorn chiama `sys.stdout.isatty()` e senza console `sys.stdout` è `None`):
  stdout e stderr vanno su `os.devnull`, i log restano nel file.

## 0.7.0 — 2026-10-26

### App autonoma
- Installer per Windows (PyInstaller in una cartella + Inno Setup: per l'utente, senza
  amministratore, collegamenti, disinstallazione che lascia i dati) e AppImage per Linux
  (server e browser predefinito); workflow `Rilascio` sui soli tag `v*` che costruisce i
  pacchetti, calcola gli sha256 e pubblica `latest.json` nella release.
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
