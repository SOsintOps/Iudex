# Iudex 0.8: memoria permanente di ricerche, PDF e consultazioni; impostazioni; solo finestra

Piano deciso con l'utente il 28 ottobre 2026. Stato dei lavori in [PROGRESS.md](../PROGRESS.md):
per riprendere il lavoro da un'altra sessione o da un altro PC basta `git pull`, leggere questo
file e il primo passo non spuntato di PROGRESS.md.

## Contesto

L'analista vuole che Iudex ricordi in modo permanente ogni ricerca fatta, quali sentenze sono
uscite da quale ricerca e quali sentenze ha consultato (testo e PDF), con i PDF salvati in una
cartella e il tutto esportabile. Vuole inoltre una scheda Impostazioni per decidere se
conservare lo storico, quale impronta del browser dichiarare e dove aprire i PDF, e
un'architettura come Voicebox: Iudex vive solo nella sua finestra, non più nel browser.
Fasi successive, solo progettate qui: estrazione delle entità e dialogo con altre app (Praeco)
per fare meno richieste al server della Corte.

Stato di partenza (Iudex 0.7.0, `main` a `b37d211`):

- `iudex/cache.py` (`Archivio`): `ricerche` (solo pagina 1, cancellabile), `diario` (ricerche
  e aperture, permanente), `consultate` (sentenze aperte con il documento grezzo zlib),
  `salvate.ultimi_id`, `preferiti`, cache `sentenze`, `risposte` (1 h, l'unico posto con gli
  id dei risultati, svuotata all'avvio), `estremi`. Migrazioni solo con `COLONNE_AGGIUNTE`
  (ADD COLUMN), `user_version` 0; il backup "prima delle migrazioni" citato in
  `autonoma/backup.py` non è implementato.
- PDF: solo il link diretto alla Corte (`query.url_pdf`, `app.js`); `/api/pdf/{id}` è un
  redirect 307 che l'interfaccia non usa; `client.py` non scarica file binari.
- Export (`iudex/export.py`): risultati, singola sentenza, diario (troncato a 5000 righe),
  consultate (zip, ftm), copia del database. Manca l'export delle ricerche con i loro risultati.
- Impronta (`impronte.py`): Chrome, Edge o Firefox su Windows a rotazione per giorno;
  `IUDEX_IMPRONTA` ne fissa una. Nessuna scheda Impostazioni: tutto da variabili d'ambiente.
- Architettura: finestra pywebview con icona
  nell'area di notifica, server FastAPI nello stesso processo, `/health`, argomenti
  `--data-dir/--port/--parent-pid`, installer Inno Setup. Restano la modalità browser
  (`--apri`, `scripts/avvia.cmd`, AppImage che apre il browser) e le API raggiungibili da
  qualsiasi browser su 127.0.0.1 (protette solo dall'header `X-Iudex`).

## Decisioni dell'utente (28 ottobre 2026)

1. Provenienza: si registrano solo i risultati **effettivamente visti** (ogni pagina caricata,
   anche se servita dalla cache); nessuna richiesta in più per sfogliare le altre pagine.
2. Il PDF si salva **quando lo apro**: il pulsante PDF passa da Iudex, la prima volta lo scarica
   e lo salva, poi apre sempre la copia locale.
3. La cartella dei PDF si **indica in fase di installazione** e si può cambiare in seguito.
4. Consultata = testo aperto **e** PDF aperto; **badge "già vista"** nei risultati con tooltip
   al passaggio del mouse: data dell'ultima consultazione e voce della/e ricerca/e.
5. Cancellazione dello storico: **cancella davvero** (con conferma), come oggi.
6. Export: **CSV/Excel, JSONL/JSON, pacchetto ZIP con i PDF**.
7. Piano nel repository su GitHub (`docs/plan/` e `docs/PROGRESS.md`), pushato a ogni passo.
8. Commit: autore Ramingo, niente trailer AI, un commit pushato per passo dopo
   `ruff format`, `ruff check iudex tests` e `pytest` verdi; CHANGELOG ("Da rilasciare") e
   `iudex/static/versioni.html` aggiornati.
9. Impostazioni: interruttore **conservazione dello storico**; spento = **non si registra
   proprio niente** (ricerche, risultati, diario, consultate, testi in cache, PDF: il PDF si
   apre ma non si salva).
10. Impronta: **rotazione giornaliera**, **fissa fra le predefinite**, **personalizzata**,
    **più personalizzate in rotazione** (insieme alle predefinite o al loro posto).
11. Architettura come Voicebox, **solo finestra, subito**: niente più modalità browser; resta
    pywebview (una shell Tauri non è prevista ora).
12. Apertura del PDF **a scelta nelle Impostazioni**: dentro la finestra di Iudex oppure con
    il programma PDF predefinito del PC.
13. Accesso alle API locali con un **token condiviso nella cartella dei dati**, letto dalla
    finestra, dal server MCP e in futuro da altre app.
14. **Importazione** (chiesta durante il passo 8): **unisce** ai dati presenti, con il
    controllo dei duplicati, un **pacchetto ZIP**, un **JSONL** o una **copia del database**
    di Iudex; copia di sicurezza prima.
15. Ogni ricerca, esecuzione e voce del diario registra la **macchina** su cui è stata fatta
    (id stabile e nome del computer, rinominabile).
16. Id stabili (`uid`) di esecuzioni e voci del diario, per riconoscere i duplicati fra
    archivi di macchine diverse.

## Passi

Un commit pushato per passo, con la spunta in PROGRESS.md nello stesso commit.

### 1. Piano nel repository

Questo file e `docs/PROGRESS.md`. Prima: `git pull`.

### 2. Versionamento dello schema

In `cache.py`: `PRAGMA user_version` con migrazioni numerate (`_migra_N`); copia di sicurezza
con `backup.esegui` prima di ogni migrazione di un database esistente (quanto già promesso in
`backup.py`); le `COLONNE_AGGIUNTE` attuali diventano la migrazione 1. Nuova tabella
`impostazioni(chiave PK, valore JSON)`. Test: migrazione di un database con lo schema 0.7.0,
dati conservati.

### 3. Impostazioni (API e scheda)

`GET/PUT /api/impostazioni` e una scheda "Impostazioni" in `index.html`/`app.js` nello stile
esistente. Chiavi: `conserva_storico` (vero), `cartella_pdf`, `pdf_apertura`
(`finestra`|`programma`), `impronta_modo` (`giorno`|`fissa`|`personalizzata`|`rotazione`),
`impronta_fissa`, `impronte_personalizzate` (elenco di {nome, user_agent, accept_language,
client_hints}), `rotazione_include_predefinite`. Precedenza: una variabile d'ambiente, se
presente, vince e la scheda mostra il campo bloccato.

### 3b. Solo finestra, API con token

Come Voicebox, il backend locale serve solo la propria finestra.

- `cartelle.prepara` crea `token` nella cartella dei dati (32 byte casuali, rigenerabile dalla
  scheda Impostazioni).
- Middleware in `app.py`, accanto ai controlli di `Host` e `X-Iudex`: le pagine e ogni `/api/*`
  richiedono il cookie di sessione o l'header `X-Iudex-Token`; `/health` resta libero.
- La finestra (`autonoma/finestra.py`, `desktop.py`) apre `/accesso?codice=<token>`, che
  imposta un cookie HttpOnly SameSite=Strict e reindirizza a `/`. Un browser qualsiasi su
  127.0.0.1 vede solo l'invito ad aprire Iudex dalla sua finestra.
- `mcp_server.py` legge il token e manda l'header.
- Tolti `--apri`, `scripts/avvia.cmd` e l'apertura del browser in `__main__.py`;
  `python -m iudex` resta come backend "sidecar" per chi lo integra, con il token.
- I link esterni (sito della Corte, GitHub) si aprono nel browser di sistema con l'API JS di
  pywebview.
- AppImage per Linux: finestra pywebview con WebKitGTK di sistema (dipendenza documentata),
  non più il browser.
- Test: richieste senza token rifiutate, con cookie o header accettate, `/health` libero; MCP
  con il token.

### 4. Impronte personalizzate

`impronte.py`: `Impronta.personalizzata(...)` con controllo di coerenza (User-Agent Chromium ⇒
`sec-ch-ua` con la stessa versione maggiore, generabile con `sec_ch_ua_chromium`; User-Agent
Firefox ⇒ niente client hints; Accept-Language non vuoto) e `impronta_attiva(giorno,
impostazioni)` per le quattro modalità. Resta invariata la firma `impronta_del_giorno(giorno,
scelta)`, usata dalle app che importano Iudex. Il client applica la nuova impronta ricreando la sessione (stesso
percorso del reset dopo un 403). Il pulsante "Prova" mostra gli header che verrebbero inviati,
senza contattare la Corte.

### 5. Memoria delle ricerche e provenienza

Nuove tabelle `esecuzioni(id, permalink, quando, pagina, righe, trovati, dalla_cache)` e
`risultati(id_esecuzione, id_sentenza, posizione)` con indice su `id_sentenza`; `ricerche`
registra ogni ricerca distinta (permalink senza pagina) con `ultima_volta` e `volte`. Si scrive
in `_esegui_ricerca`/`/api/cerca` per ogni pagina vista, anche dalla cache, e in "Controlla
novità" delle ricerche salvate. Cancellare una ricerca (con conferma) elimina anche esecuzioni
e risultati. Con `conserva_storico` spento nessuna scrittura, né qui né in diario, consultate
o sentenze.

### 6. Consultazioni e badge "già vista"

Diario: nuovo tipo `pdf` accanto a `sentenza`, con il permalink di provenienza. `/api/cerca`
aggiunge a ogni documento `consultazione {ultima, volte, ricerche: [{descrizione, quando}]}`,
calcolato in locale senza richieste. Interfaccia: badge "già vista" nei risultati, nei
preferiti e nelle salvate, con tooltip (data e voci delle ricerche); nel pannello di lettura
l'elenco "uscita in N ricerche". Una consultata senza testo in cache si riapre da
`consultate.grezzo` (una richiesta in meno).

### 7. PDF salvati

- `client.py`: download binario dentro lo stesso lock e lo stesso intervallo, con controllo
  del content-type o dell'intestazione `%PDF`.
- `/api/pdf/{id}`: la copia locale se c'è, altrimenti scarica, salva `cartella_pdf/<id>.pdf`
  (nome stabile, utile per la fase C) e registra
  `pdf(id_sentenza PK, quando, percorso relativo alla cartella, byte, sha256)`. Sentenza in
  fase di oscuramento ⇒ messaggio chiaro. I link dell'interfaccia passano da `/api/pdf/{id}`.
- Cartella: predefinita `pdf/` nella cartella dei dati; l'installer (`packaging/iudex.iss`)
  aggiunge la pagina "Cartella dei PDF" e scrive `installazione.ini` nella cartella dei dati,
  letto al primo avvio per impostare `cartella_pdf`; si cambia dalla scheda Impostazioni con
  "sposta i PDF esistenti".
- Linux: l'AppImage non ha una fase di installazione, quindi al primo avvio la finestra chiede
  la cartella dei PDF (predefinita `~/.local/share/iudex/pdf`); lo stesso dialogo appare su
  Windows se `installazione.ini` manca (avvio dai sorgenti o installazione vecchia).
- `pdf_apertura`: `finestra` (visore WebView2 nel pannello di lettura, dalla copia locale) o
  `programma` (`os.startfile` sul file salvato; `xdg-open` su Linux).
- Storico spento ⇒ PDF non salvato: in finestra è solo inoltrato; con "programma" va in un
  file temporaneo cancellato alla chiusura di Iudex.

### 8. Export del database delle ricerche

`/api/export/ricerche?formato=csv|jsonl|zip` in `export.py`, con gli helper CSV esistenti
(`;` e BOM UTF-8 per Excel, nessuna dipendenza nuova): `ricerche.csv`, `esecuzioni.csv`,
`risultati.csv` (ricerca→sentenza con estremi e data di consultazione), `consultazioni.csv`;
JSONL con un record per riga e il campo `tipo`; ZIP con CSV, JSONL, `pdf/` e `testi/`. Export
del diario in streaming, senza il tetto di 5000 righe. Pulsanti nelle schede Diario e
Impostazioni.

### 8c. Importazione con unione e controllo dei duplicati

`POST /api/importa` (file caricato dalla scheda Impostazioni): pacchetto ZIP o JSONL
dell'export del passo 8, oppure un `.sqlite` di Iudex (letto in sola lettura, convertito con
`Archivio.dati_ricerche`). Prima una copia di sicurezza. Regole di unione:

- macchine: aggiunte se nuove (il nome locale non cambia);
- ricerche: per permalink; `prima_volta` la minima, `quando` la massima, `volte` la massima
  fra quella locale e le esecuzioni di pagina 1;
- esecuzioni e voci del diario: per `uid`, mai duplicate; i risultati seguono la loro
  esecuzione;
- consultate: per id della sentenza; si aggiunge la risposta intera se manca, `prima_volta`
  la minima, `ultima_volta` la massima, `volte` dal diario;
- PDF: per id; il file si copia se manca, controllando lo sha256 dichiarato; se c'è già con
  uno sha256 diverso resta quello locale e lo si segnala.

Il riepilogo dice quanti record sono stati aggiunti e quanti erano già presenti. Test: doppia
importazione dello stesso pacchetto senza duplicati, unione di due archivi con macchine
diverse, `.sqlite` di una 0.7.0.

### 8b. Installazione su Windows e su Linux

Le procedure esistono dalla 0.7.0 (workflow `rilascio.yml` sui tag `v*`): vanno adattate e
provate.

- **Windows** (`packaging/iudex.iss`, PyInstaller `--onedir`): installazione per l'utente in
  `%LOCALAPPDATA%\Programs\Iudex` senza diritti di amministratore; nuova pagina "Cartella dei
  PDF"; collegamenti nel menu Start e sul Desktop che aprono solo la finestra; avvio
  facoltativo all'accesso come icona nell'area di notifica; la disinstallazione non tocca dati
  e PDF. Requisito WebView2 (presente in Windows 11; su Windows 10 l'installer controlla e
  rimanda al download di Microsoft).
- **Linux** (`packaging/appimage/`, `costruisci_appimage.sh`): AppImage che apre la finestra
  pywebview con WebKitGTK di sistema; voce di menu `.desktop` e icona installate al primo avvio
  in `~/.local/share/applications` (facoltativo); se WebKitGTK manca, messaggio con il comando
  per installarlo (Debian/Ubuntu `gir1.2-webkit2-4.1`, Fedora `webkit2gtk4.1`), senza ripiego
  sul browser.
- **Dai sorgenti** (sviluppo, entrambi i sistemi): `python -m iudex.desktop` nel venv; README
  con i passi per Windows (uv) e per Linux (venv con le librerie GTK di sistema).
- **Prova**: gli installer si provano su macchina virtuale (Windows 11 e Debian 13, per esempio
  la VM `london` già presente), seguendo una lista scritta in `docs/prova-installazione.md`:
  installazione, scelta della cartella, ricerca, PDF, aggiornamento sopra la 0.7.0 con i dati
  conservati, disinstallazione.

### 9. Documentazione e versione 0.8.0

README (togliere "Iudex non scarica i PDF" e la modalità browser), `docs/guida.md`,
`docs/faq.md` e le pagine `static/*.html`, CHANGELOG, `versioni.html`. Il tag `v0.8.0`, che avvia il
workflow di rilascio, solo su conferma dell'utente. La 0.8.0 comprende anche quanto già in
"Da rilasciare" (avvio nascosto, `flussi_sicuri`), prima previsto come 0.7.1.

## Fasi successive (progettate, da sviluppare dopo)

- **B. Entità.** Piano in [2026-10-28-entita.md](2026-10-28-entita.md).
- **C. Dialogo con altre app (Praeco).** Chiave comune: l'id SentenzeWeb; prima di chiedere un
  testo o un PDF alla Corte, Iudex guarda nel proprio archivio e in quello dell'altra app. Da
  progettare.
- Vincolo: non cambiare le API pubbliche di Iudex senza verificare le app che le usano.

## Verifica

- Ogni passo: `ruff format`, `ruff check iudex tests`, `pytest` (test senza rete; `respx` per
  il download del PDF e la sessione; migrazione da una copia dello schema 0.7.0).
- Prova dal vivo, con lo split tunneling di Proton attivo verso 81.126.56.168 e dopo una
  copia di `dati/iudex.sqlite`:
  - ricerca e pagina 2 → righe in `esecuzioni` e `risultati`;
  - testo e PDF aperti → diario, file nella cartella, seconda apertura servita in locale
    (nessuna nuova voce nel registro di `/api/stato`);
  - badge e tooltip nei risultati;
  - storico spento → nessuna riga nuova e PDF non salvato;
  - impronta personalizzata visibile in `/api/stato`;
  - Chrome su http://127.0.0.1:8765 non vede né l'interfaccia né le API, la finestra sì,
    MCP funziona;
  - PDF aperto nella finestra e, cambiata l'impostazione, nel lettore di Windows;
  - export ZIP aperto e controllato;
  - le ricerche e le consultate già presenti (37 e 3 il 28 ottobre) ancora al loro posto.
