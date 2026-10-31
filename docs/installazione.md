# Installazione

## Indice

- [Con l'installer (consigliato)](#con-linstaller-consigliato)
- [Dai sorgenti](#dai-sorgenti)
- [Finestra nativa](#finestra-nativa)
- [Con un assistente o un LLM locale (MCP)](#con-un-assistente-o-un-llm-locale-mcp)
- [Certificato TLS](#certificato-tls)
- [Da dietro una VPN](#da-dietro-una-vpn)

## Con l'installer (consigliato)

Dalla pagina delle [release](https://github.com/SOsintOps/Iudex/releases/latest):

- **Windows**: `Iudex-X.Y.Z-setup.exe`. Si installa nel profilo dell'utente, senza necessità di
  privilegi di amministratore, nel percorso `%LOCALAPPDATA%\Programs\Iudex`, e consente di
  scegliere la cartella destinata alla conservazione delle copie ufficiali in PDF; avvia Iudex
  in una finestra propria (basata sul componente WebView2, nativamente integrato in Windows 11;
  su Windows 10 il programma di installazione avvisa qualora manchi) con un'icona nell'area di
  notifica. L'archivio locale risiede in `%APPDATA%\Iudex` e viene preservato anche in caso di
  disinstallazione. L'eseguibile di installazione non è sottoscritto con un certificato
  commerciale di firma del codice (*code signing*): Windows SmartScreen può pertanto richiedere
  conferma all'avvio («Ulteriori informazioni» → «Esegui comunque»); l'impronta crittografica
  `sha256` di ciascun file è pubblicata nel manifesto `latest.json` allegato alla release.
- **Linux**: `Iudex-X.Y.Z-x86_64.AppImage` (da rendere eseguibile con `chmod +x`): apre la
  finestra avvalendosi di WebKitGTK di sistema (`sudo apt install gir1.2-webkit2-4.1 python3-gi`
  su distribuzioni Debian e Ubuntu; in caso di assenza Iudex mostra le istruzioni necessarie) e
  al primo avvio richiede il percorso per il salvataggio dei PDF; i dati vengono archiviati in
  `~/.local/share/iudex`.

## Dai sorgenti

Richiede Python 3.11 o versione successiva.

```bat
git clone https://github.com/SOsintOps/Iudex.git
cd Iudex
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .[desktop]
scripts\avvia-finestra.cmd
```

Il comando `scripts\avvia-finestra.cmd` (oppure `python -m iudex.desktop`) apre la finestra di
Iudex; qualora un'istanza di Iudex sia già attiva, riporta in primo piano quella esistente
anziché avviarne una seconda. Su sistemi Linux: `.venv/bin/python -m iudex.desktop`, utilizzando
WebKitGTK e PyGObject di sistema (su Debian e Ubuntu:
`sudo apt install gir1.2-webkit2-4.1 python3-gi`, creando l'ambiente virtuale con l'opzione
`--system-site-packages`). Nell'esecuzione dai sorgenti i dati (cronologia delle ricerche,
diario di consultazione, esecuzioni, provvedimenti preferiti, impostazioni, cache e token)
sono custoditi in `dati/iudex.sqlite` e nella cartella `dati/`, mentre i PDF delle pronunce sono
salvati in `dati/pdf/` salvo diversa configurazione; le voci di cache scadute vengono rimosse
automaticamente a ogni avvio.

Il comando `python -m iudex` avvia unicamente il server locale, privo di finestra grafica, per
chi intenda integrare Iudex quale servizio di backend in un'altra applicazione (argomenti
`--data-dir`, `--port`, `--parent-pid`): le pagine e le API richiedono l'invio del token
contenuto nel file `token` della cartella dei dati tramite l'intestazione HTTP `X-Iudex-Token`.

Con cadenza settimanale all'avvio, nonché prima di ogni migrazione dello schema del database e
di ogni operazione di importazione, Iudex genera automaticamente una copia di sicurezza della
banca dati locale nella sottocartella `backup/` della cartella dei dati (tramite istruzione
`VACUUM INTO`, conservando le ultime otto copie). I documenti PDF non sono incorporati nel
database SQLite: per eseguirne il salvataggio esterno è possibile esportare il pacchetto ZIP
dalla scheda Cronologia. La versione installata verifica all'avvio l'eventuale disponibilità di
aggiornamenti (effettuando una singola richiesta verso GitHub per leggere il file `latest.json`
dell'ultima release pubblicata, senza trasmettere alcun dato dell'utente) e ne dà avviso nella
scheda Stato; il nuovo installer viene scaricato ed eseguito solo su esplicita richiesta
dell'utente («Scarica e installa»), previa verifica dell'impronta `sha256`. La variabile
d'ambiente `IUDEX_AGGIORNAMENTI=0` disattiva la verifica automatica.

Variabili d'ambiente supportate:
- `IUDEX_PORTA` (`8765`)
- `IUDEX_HOST` (`127.0.0.1`)
- `IUDEX_DATI` (percorso della cartella dei dati)
- `IUDEX_INTERVALLO` (secondi di attesa minima fra le richieste al server della Corte)
- `IUDEX_INTERVALLO_NORMATTIVA` (secondi di attesa minima fra le richieste a Normattiva)
- `IUDEX_TTL_RICERCHE` (durata di validità in secondi della cache delle ricerche)
- `IUDEX_TELEMETRIA` (`1` per replicare la chiamata di telemetria del sito ufficiale)
- `IUDEX_AGGIORNAMENTI` (`0` disattiva il controllo degli aggiornamenti, `1` lo attiva anche
  nell'esecuzione dai sorgenti)
- `IUDEX_IMPRONTA` (`chrome`, `edge` o `firefox` per imporre l'uso costante del medesimo
  profilo browser, indipendentemente dalle preferenze salvate; la scheda Stato indica il profilo
  attivo)
- `IUDEX_TOKEN` (per l'autenticazione del server MCP in alternativa alla lettura del file
  `token`).

Iudex è progettato per l'ascolto sull'interfaccia di loopback `127.0.0.1`: le API accettano
esclusivamente richieste recanti un'intestazione `Host` locale; pertanto l'eventuale impiego di
un indirizzo differente (ad esempio `0.0.0.0` in una rete locale di studio) deve essere
esplicitamente dichiarato tramite `IUDEX_HOST`. Il token protegge l'accesso alle API, ma il
transito avviene su protocollo HTTP in chiaro.

## Finestra nativa

```bat
.venv\Scripts\python.exe -m pip install -e .[desktop]
scripts\avvia-finestra.cmd
```

Costituisce la modalità d'uso ordinaria di Iudex: una finestra applicativa dedicata (basata su
WebView2 in ambiente Windows, WebKitGTK su Linux, WebKit su macOS), dotata di icona nell'area
di notifica (*Apri*, *Mantieni in esecuzione*, *Esci*), che arresta automaticamente il server
locale alla chiusura. La finestra si autentica mediante il token presente nella cartella dei
dati (`/accesso?codice=...`, cui segue l'impostazione di un cookie di sessione); qualora si
tenti di aprire l'indirizzo locale da un comune browser web, viene mostrato esclusivamente un
avviso che invita a utilizzare la finestra dedicata di Iudex. Se un'istanza di Iudex è già
attiva sulla porta configurata, il comando riporta in primo piano la finestra esistente anziché
avviarne una nuova; se invece la porta risulta occupata da un programma diverso, seleziona
automaticamente la prima porta libera successiva. Gli argomenti `--data-dir` e `--port`
consentono di specificare la cartella dei dati e la porta di ascolto.

Quando viene eseguito come componente di backend di un'altra applicazione, il comando
`python -m iudex --data-dir CARTELLA --port PORTA --parent-pid PID` avvia il solo server HTTP e
ne dispone la chiusura automatica alla terminazione del processo genitore `PID`; l'endpoint
`GET /health` restituisce `{"app": "iudex", "versione", "pid"}` senza richiedere il token,
consentendo al processo chiamante di riconoscere la propria istanza, mentre tutte le altre
chiamate richiedono l'intestazione `X-Iudex-Token` valorizzata con il contenuto del file
`token`. Il registro diagnostico viene scritto con rotazione automatica in `log/iudex.log`
all'interno della cartella dei dati.

## Con un assistente o un LLM locale (MCP)

```bat
.venv\Scripts\python.exe -m pip install -e .[mcp]
```

Con l'applicazione Iudex attiva, il comando `python -m iudex.mcp_server` espone cinque
strumenti conformi al protocollo **MCP (*Model Context Protocol*)**, tutti in sola lettura, i
quali operano attraverso l'API locale beneficiando così della cache e dei limiti di frequenza
delle richieste:

| Strumento | Funzione |
|-----------|----------|
| `cerca_sentenze` | ricerca pronunce della Corte di Cassazione per termini, frase esatta, troncamento o estremi del provvedimento, con filtri per settore/archivio (civile o penale), anno, sezione, natura del provvedimento e segnale di orientamento giurisprudenziale |
| `cerca_per_norma` | ricerca le pronunce che richiamano una specifica disposizione normativa (`"art. 18 legge 300/1970"`) |
| `leggi_sentenza` | restituisce gli estremi del provvedimento, il dispositivo, i riferimenti normativi indicizzati dal CED e la motivazione integrale della pronuncia |
| `leggi_norma` | restituisce il testo di un articolo da Normattiva, completo di estremi di vigenza, collegamento e indicazione della fonte ufficiale |
| `verifica_citazioni` | verifica l'esistenza e la correttezza degli estremi fino a 10 citazioni giurisprudenziali della Cassazione per singola chiamata |

Il server MCP acquisisce il token di autenticazione dal file `token` presente nella cartella
dei dati (la medesima utilizzata da Iudex, ovvero quella indicata in `IUDEX_DATI` se
personalizzata) oppure dalla variabile d'ambiente `IUDEX_TOKEN`. Di seguito un esempio di
configurazione per LM Studio (`mcp.json`) o Claude Desktop:

```json
{
  "mcpServers": {
    "iudex": {
      "command": "C:\\percorso\\di\\Iudex\\.venv\\Scripts\\python.exe",
      "args": ["-m", "iudex.mcp_server"]
    }
  }
}
```

È necessario un modello linguistico che supporti l'invocazione di strumenti (*tool calling*);
grazie al numero contenuto di strumenti esposti, anche modelli locali di dimensioni ridotte
riescono a gestirli correttamente. Le istruzioni di sistema fornite dal server invitano
l'assistente a non ripetere interrogazioni identiche e a non scorrere inutilmente molteplici
pagine di risultati. Lo strumento `cerca_sentenze` accetta il filtro `segnale` (contrasto
giurisprudenziale o conformità a orientamento consolidato) e restituisce i relativi conteggi;
`leggi_sentenza`, alla prima lettura di una motivazione particolarmente estesa, restituisce
l'epigrafe, la parte iniziale dello svolgimento del processo e dei motivi della decisione e la
parte conclusiva a partire dal dispositivo (`P.Q.M.`), indicando il numero di caratteri omessi.
Eventuali condizioni di errore (Iudex non avviato, pausa richiesta dal server remoto) vengono
restituite al modello come errori strutturati dello strumento con un messaggio esplicativo.
Richiede il pacchetto `mcp` versione 2.x.

Lo strumento `leggi_norma` restituisce il testo vigente o storico di un articolo da Normattiva
(fonte istituzionale, dati IPZS con licenza CC BY 4.0) corredato delle date di vigenza e del
collegamento all'atto: accetta sia una citazione normativa testuale (`"art. 2043 c.c."`,
`"art. 13 d.lgs. 196/2003"`, `"art. 2-bis l. 241/1990"`) sia i parametri strutturati `tipo`,
`numero`, `anno`, `articolo` e la data di `vigenza` facoltativa, inoltrando la richiesta a
`GET /api/norma` (al più una chiamata verso Normattiva, nessuna qualora la disposizione sia già
presente nella cache locale).

Lo strumento `verifica_citazioni` controlla fino a 10 citazioni di pronunce della Corte di
Cassazione per singola chiamata, riconoscendo anche la forma redazionale estesa comprensiva di
sezione e data:

```json
{"citazioni": ["Cass. civ., Sez. Un., 11 novembre 2008, n. 26972",
               "Cass. pen. sez. VI n. 1234/2020", "Cass. civ. n. 1234/2031"]}
```

Per ciascun riferimento giurisprudenziale lo strumento verifica anzitutto la presenza del
provvedimento fra quelli già consultati e salvati sul computer locale e, solo qualora non sia
presente, invia un'interrogazione al server della Corte (tramite `/api/cerca`, nel rispetto
dell'intervallo minimo di 2 secondi e delle eventuali pause), procedendo in sequenza con una
richiesta per citazione. Gli esiti possibili sono cinque:
- **esiste**: il provvedimento è stato individuato (vengono restituiti identificativo ed ECLI,
  con un avviso specifico qualora la sezione indicata nella citazione non coincida con quella
  effettiva del provvedimento);
- **non trovata**: gli estremi indicati non risultano presenti nell'archivio pubblico di
  SentenzeWeb (circostanza che non esclude di per sé l'esistenza storica della pronuncia,
  poiché SentenzeWeb copre una finestra temporale recente e non l'intero archivio storico del
  CED contenuto in ItalgiureWeb);
- **fonte non raggiungibile**: il server della Corte non ha risposto o ha richiesto una pausa
  temporanea (la verifica risulta pertanto **non effettuata**, mai negativa, e per le citazioni
  successive della medesima chiamata non vengono tentate ulteriori richieste);
- **fuori archivio**: anno futuro o anteriore al 2000, scartato preliminarmente senza inviare
  richieste di rete;
- **non interpretabile**: stringa priva degli elementi minimi necessari per individuare numero
  e anno del provvedimento.

## Certificato TLS

Il server di SentenzeWeb presenta una catena di certificati TLS incompleta, omettendo il
certificato dell'autorità di certificazione intermedia («TI Trust Technologies OV CA»). Mentre
i principali browser completano autonomamente la catena (*AIA fetching*), la libreria standard
di Python rifiuta la connessione: per garantire la sicurezza del canale senza disabilitare la
verifica crittografica dei certificati, Iudex include il certificato intermedio ufficiale in
`src/iudex/certs/ti_trust_ov_ca.pem` e lo integra nel contesto TLS.

## Da dietro una VPN

Sia il server della Corte Suprema di Cassazione sia i server di Normattiva non rispondono alle
connessioni provenienti dagli indirizzi IP di uscita dei principali fornitori di VPN
commerciali: il tentativo di connessione TCP sulla porta 443 va in scadenza (*timeout*) senza
risposta, e Iudex segnala «errore di rete» (o l'indisponibilità di Normattiva). Non si tratta di
un malfunzionamento di Iudex né di un blocco dovuto alla frequenza delle interrogazioni: il
medesimo comportamento si riscontra accedendo ai portali dal browser.

La soluzione consiste nell'escludere dal tunnel VPN (*split tunneling*) gli **indirizzi IP**
delle fonti istituzionali:

| Servizio | Dominio | Indirizzo IP da escludere (*split tunneling*) |
|----------|---------|-----------------------------------------------|
| Corte Suprema di Cassazione (SentenzeWeb e PDF) | `www.italgiure.giustizia.it` | `81.126.56.168` (rete Telecom Italia) |
| Normattiva — API Open Data (usata da Iudex per il bottone **Testo** e `leggi_norma`) | `api.normattiva.it` | `147.78.212.26` |
| Normattiva — Portale web (per i link **Apri su Normattiva** nel browser) | `www.normattiva.it` | `147.78.212.12` |

In tal modo l'intera navigazione rimane protetta dalla VPN, mentre le ricerche
giurisprudenziali, lo scaricamento dei PDF ufficiali e la lettura degli articoli da Normattiva
raggiungono direttamente i rispettivi server (che per tali richieste rileveranno l'indirizzo IP
reale dell'utenza). A partire dalla versione 0.8, per il funzionamento di Iudex è altresì
sufficiente configurare lo *split tunneling* per applicazione escludendo il solo eseguibile di
Iudex (mentre per aprire i link di `www.normattiva.it` nel browser resta utile l'esclusione
dell'IP `147.78.212.12`).

## Vedi anche

- [Pagina principale (README)](../README.md)
- [Normattiva](normattiva.md)
- [Come viene consultato il sito](consultazione-sito.md)
- [Sviluppo](sviluppo.md)
- [Domande frequenti (FAQ)](faq.md)
