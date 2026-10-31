<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/immagini/logo-scuro.png">
    <img src="docs/immagini/logo.png" alt="Iudex" width="320">
  </picture>
</p>

# Iudex

[![CI](https://github.com/SOsintOps/Iudex/actions/workflows/ci.yml/badge.svg)](https://github.com/SOsintOps/Iudex/actions/workflows/ci.yml)

Interfaccia locale per interrogare **SentenzeWeb**, la banca dati pubblica dei provvedimenti
giurisdizionali (sentenze, ordinanze e decreti) civili e penali della Corte Suprema di
Cassazione (<https://www.italgiure.giustizia.it/sncass/>), curata dal **CED** (Centro
Elettronico di Documentazione).

Iudex è un progetto indipendente (non è uno strumento ufficiale né è affiliato alla Corte
Suprema di Cassazione, al Ministero della Giustizia o a IPZS/Normattiva), non è un archivio
autonomo e non duplica la banca dati: ogni interrogazione interpella
in tempo reale il server della Corte come farebbe il browser, ma all'interno di una finestra
dedicata, con un'interfaccia studiata per la lettura e il raffronto delle pronunce e con una
memoria permanente delle ricerche e delle consultazioni effettuate (interrogazioni,
provvedimenti estratti da ciascuna, motivazioni integrali e copie ufficiali in PDF aperte,
esportabili e trasferibili su un altro computer).

![Iudex 0.8: risultati in vista compatta con il filtro "Civile" attivo, i segnali di orientamento giurisprudenziale e i filtri con i conteggi](docs/immagini/risultati.png)

## Indice

- [Che cosa fa](#che-cosa-fa)
- [Schermate](#schermate)
- [Approfondimenti](#approfondimenti)
- [Licenza](#licenza)

## Che cosa fa

- **Ricerca giurisprudenziale** per termini, frase esatta, troncamento, operatori booleani
  (`AND`/`OR`/`NOT`), **estremi del provvedimento** (`12345/2024`, `sent. n. 99 del 2025`) e
  **riferimento normativo** (`art. 18 legge 300/1970`), con la medesima sintassi e gli stessi
  risultati del portale ufficiale (con la differenza che l'operatore `NOT`, inefficace sul sito,
  qui esclude realmente i termini indesiderati).
- **Filtri** per settore/archivio (civile o penale), natura del provvedimento (sentenza,
  ordinanza, ordinanza interlocutoria, decreto), sezione (Sezioni Unite e sezioni semplici),
  anno di pubblicazione, sottosezione e **materia** (secondo la classificazione del CED),
  corredati dei relativi conteggi e utilizzabili in selezione multipla.
- **Motivazione integrale e dispositivo** in un pannello di lettura affiancato ai risultati,
  ricostruiti in paragrafi (*Fatti di causa* / *Svolgimento del processo*, *Ragioni della
  decisione* / *Motivi della decisione*, *P.Q.M.*), con evidenziazione e navigazione delle
  occorrenze (`n`/`p`), salto rapido al dispositivo (`P.Q.M.`), estrazione in sintesi del
  dispositivo, **riferimenti normativi** indicizzati dal CED (cliccabili per ricercare le
  ulteriori pronunce che richiamano la medesima disposizione) e **copia ufficiale in PDF**,
  salvata in locale alla prima apertura e consultabile nella finestra di Iudex o con il lettore
  PDF di sistema.
- **Testo delle disposizioni normative**: accanto ai riferimenti normativi indicizzati nella
  pronuncia, il pulsante **Testo** apre l'articolo vigente acquisito da **Normattiva** (fonte
  istituzionale, dati IPZS con licenza CC BY 4.0), completo di estremi di vigenza e
  collegamento all'atto; i regolamenti e le direttive dell'Unione europea, il TUE e il TFUE
  espongono il collegamento diretto a **EUR-Lex**. Vedi la pagina dedicata
  [Normattiva](docs/normattiva.md).
- **Memoria permanente**: registra ogni interrogazione e ogni pagina di risultati esaminata,
  con i provvedimenti restituiti, la postazione utilizzata e l'orario; un indicatore **"già
  vista"** segnala nei risultati le pronunce già consultate e, al passaggio del cursore, mostra
  quando il provvedimento è stato aperto e da quali ricerche è emerso. La funzione è
  disattivabile nelle Impostazioni.
- **Cronologia**, **ricerche salvate** con **verifica delle sopravvenienze giurisprudenziali
  (novità)** su richiesta, **provvedimenti preferiti corredati di note di studio**; ogni
  interrogazione dispone di un collegamento diretto (*permalink*, es.
  `#testo=…&kind=snciv&anno=2026`).
- **Diario di consultazione**: registro cronologico permanente, articolato per giornata, delle
  ricerche effettuate e delle pronunce aperte da ciascuna (motivazione testuale e PDF); per i
  provvedimenti aperti conserva l'intera risposta del server, inclusa la motivazione integrale,
  consentendone la consultazione anche in assenza di connessione di rete.
- **Esportazione dello storico** in formato CSV per fogli di calcolo (Excel), JSONL o pacchetto
  ZIP comprensivo dei documenti PDF, e **importazione** in un'altra installazione di Iudex
  (fusione senza duplicazioni, anche a partire da una copia del database SQLite); creazione
  automatica di una copia di sicurezza prima di ogni migrazione dello schema e di ogni
  importazione.
- **Impostazioni**: gestione della conservazione dello storico, percorso di archiviazione e
  modalità di apertura dei PDF, profilo del browser dichiarato al server della Corte (a
  rotazione giornaliera, fisso, personalizzato o personalizzati a rotazione), identificativo
  della postazione di lavoro.
- **Esportazione dei risultati** (pagina corrente oppure primi 50/100 provvedimenti) in CSV,
  JSON o Markdown, nonché della singola pronuncia in Markdown o JSON, con **citazione
  giurisprudenziale** formattata e pronta per l'inserimento negli atti o negli scritti
  difensivi.
- **Colonne ridimensionabili** mediante trascinamento (pannelli e tabelle), tema chiaro e
  scuro, vista a righe compatte, corpo del carattere regolabile, scorciatoie da tastiera,
  totale assenza di dipendenze esterne nell'interfaccia.
- Menu **Help** integrato con **guida all'utilizzo**, **domande frequenti**, **registro delle
  versioni**, **software simili** e **licenza**.
- Veste grafica coordinata con [Exploratores](https://github.com/SOsintOps/Exploratores)
  (medesima tavolozza cromatica, carattere Inter in locale, stessa barra di navigazione), con
  un **tema scuro** ad attivazione oraria automatica (dalle ore 19:00 alle 07:00, con fascia
  oraria personalizzabile).

## Schermate

L'indicatore **già vista** contraddistingue le pronunce già esaminate; al passaggio del cursore
indica la data dell'ultima consultazione, la ricerca da cui il provvedimento è stato aperto e
le ulteriori interrogazioni in cui è comparso.

![Iudex: badge "già vista" su una pronuncia dei risultati, con il riquadro che indica l'ultima consultazione, la ricerca da cui è stata aperta e le ricerche in cui è uscita](docs/immagini/gia-vista.png)

Nell'intestazione del pannello di lettura, sopra la motivazione, sono riepilogati il numero di
consultazioni della pronuncia, le ricerche da cui è stata aperta e quelle in cui è figurata tra
i risultati.

![Iudex: intestazione del pannello di lettura con prima apertura, ricerca di provenienza e ricerche in cui la pronuncia è uscita](docs/immagini/lettura.png)

Vista compatta con tema scuro ad attivazione serale automatica: sono esposti unicamente gli
estremi del provvedimento, la data di deliberazione (udienza o camera di consiglio) e la data
di pubblicazione (deposito in cancelleria), il presidente del collegio, il consigliere relatore
e il codice ECLI (*European Case Law Identifier*); nella colonna di sinistra figurano i segnali
di orientamento giurisprudenziale (qui è attivo il filtro «Orientamento consolidato») e i
filtri con barre proporzionali.

![Iudex: tema scuro, righe compatte, filtro sui provvedimenti che richiamano un orientamento giurisprudenziale consolidato](docs/immagini/tema-scuro.png)

La scheda Cronologia conserva stabilmente le interrogazioni eseguite e consente di esportare lo
storico in CSV per Excel, JSONL o in un pacchetto ZIP comprensivo dei PDF ufficiali,
importabile in un'altra installazione di Iudex.

![Iudex: scheda Cronologia con le ricerche effettuate e i pulsanti di esportazione dello storico](docs/immagini/cronologia.png)

Il Diario raccoglie, giorno per giorno, le ricerche svolte e le pronunce aperte all'interno di
ciascuna, conservandone il testo integrale; da questa vista è possibile esportare i dati in
JSONL, CSV, archivio ZIP o formato FollowTheMoney.

![Iudex: scheda Diario con le ricerche di una giornata e la pronuncia aperta da una di esse](docs/immagini/diario.png)

La scheda Impostazioni permette di configurare la conservazione dello storico, la cartella di
salvataggio e la modalità di apertura dei PDF, l'impronta del browser dichiarata al server
della Corte, la fascia oraria del tema scuro e il nome del computer.

![Iudex: scheda Impostazioni con storico, cartella dei PDF e impronta del browser](docs/immagini/impostazioni.png)

Le pagine informative integrate (domande frequenti, registro delle versioni, software simili)
adottano la medesima veste grafica e sono consultabili dal menu Help della barra di
navigazione.

![Iudex: pagina delle domande frequenti](docs/immagini/domande-frequenti.png)

Le schermate riproducono interrogazioni reali eseguite dalla finestra di Iudex 0.8 su un
archivio di prova; nel rispetto della disciplina sulla protezione dei dati personali e
dell'oscuramento delle generalità delle parti (art. 52 d.lgs. 30 giugno 2003, n. 196), sono
state selezionate viste prive di dati identificativi delle parti del giudizio.

## Approfondimenti

La documentazione tecnica, le istruzioni di installazione e le regole di interrogazione delle
fonti ufficiali sono raccolte nelle seguenti pagine dedicate:

- [**Come viene consultato il sito**](docs/consultazione-sito.md) — Criteri di parsimonia nelle
  richieste al server di SentenzeWeb, limiti di frequenza (*rate limiting*), gestione della
  cache locale, identità dichiarata e tutela dell'infrastruttura pubblica della Corte.
- [**Normattiva ed EUR-Lex**](docs/normattiva.md) — Consultazione del testo delle disposizioni
  normative tramite l'API Open Data di Normattiva, collegamenti CELEX a EUR-Lex per le fonti
  dell'Unione europea, licenza CC BY 4.0 (IPZS), valore legale della Gazzetta Ufficiale e
  limiti tecnici.
- [**Installazione, finestra nativa e server MCP**](docs/installazione.md) — Installazione
  tramite pacchetto precompilato (Windows e Linux) o dai sorgenti, configurazione delle
  variabili d'ambiente, integrazione con assistenti e LLM locali tramite protocollo MCP
  (`cerca_sentenze`, `cerca_per_norma`, `leggi_sentenza`, `leggi_norma`, `verifica_citazioni`),
  catena di certificati TLS e accesso tramite VPN (*split tunneling*).
- [**Sviluppo e architettura**](docs/sviluppo.md) — Esecuzione dei controlli di qualità e della
  suite di test offline, architettura dei moduli Python e linee guida per contribuire al
  progetto.
- [**Guida all'utilizzo**](docs/guida.md) — Manuale operativo completo delle funzioni di
  ricerca, lettura, annotazione, esportazione e scorciatoie da tastiera.
- [**Domande frequenti (FAQ)**](docs/faq.md) — Risposte ai quesiti più comuni su contenuto
  della banca dati, sintassi di ricerca, dati locali e risoluzione dei problemi.
- [**Analisi tecnica di SentenzeWeb**](docs/analisi-sito.md) — Documentazione degli endpoint
  Apache Solr/ISAPI, dei parametri di interrogazione e della struttura dei campi del CED.
- [**Software simili**](docs/software-simili.md) — Confronto con altri strumenti e progetti che
  interagiscono con le banche dati giurisprudenziali e normative italiane.

## Licenza

Il codice sorgente di Iudex è distribuito con licenza **MIT** ([LICENSE](LICENSE)).

I testi dei provvedimenti giurisdizionali appartengono alla **Corte Suprema di Cassazione** e
restano soggetti alle condizioni d'uso e alle prescrizioni in materia di protezione dei dati
personali con cui la Corte li rende pubblici. I testi degli atti normativi sono elaborati
dall'**Istituto Poligrafico e Zecca dello Stato (IPZS)** e pubblicati tramite **Normattiva** con
licenza **Creative Commons Attribuzione 4.0 Internazionale (CC BY 4.0)** (fonte: Normattiva,
IPZS); si ricorda che l'unico testo normativo che fa fede a fini legali è quello pubblicato
nella **Gazzetta Ufficiale della Repubblica Italiana**.
