# Guida all'utilizzo

La stessa guida è nell'app, nel menu **Help → Guida all'utilizzo**.

Iudex è un'interfaccia locale per SentenzeWeb, la banca dati pubblica delle sentenze civili
e penali della Corte Suprema di Cassazione. Non duplica la banca dati: ogni ricerca interroga il
server della Corte nel momento in cui la esegui. In locale restano la memoria di ciò che hai
fatto (ricerche, sentenze uscite da ciascuna, consultazioni), i testi e i PDF aperti, le
ricerche salvate e i preferiti. Iudex si usa dalla sua finestra (collegamento nel menu Start o
sul Desktop; su Linux l'AppImage).

## Il flusso di lavoro

1. **Cerca**: parole, estremi o riferimento normativo nel riquadro in alto, poi *Cerca*
   (o Invio). Parte una sola richiesta al server.
2. **Restringi** con i filtri a sinistra (archivio, tipo, sezione, anno, sottosezione,
   materia): i conteggi arrivano con la stessa risposta della ricerca.
3. **Leggi**: *Apri testo* mostra il provvedimento in paragrafi accanto ai risultati, con
   le occorrenze evidenziate, il salto al P.Q.M. e i riferimenti normativi cliccabili. *PDF*
   apre il PDF ufficiale: la prima volta Iudex lo scarica e lo salva, poi lo riapre dalla
   copia locale.
4. **Riconosci**: il badge **già vista** segna le sentenze che hai già consultato; al
   passaggio del mouse dice quando e da quali ricerche.
5. **Conserva**: *Preferisci* mette il provvedimento fra i preferiti (con una nota);
   *Salva ricerca* salva i criteri di ricerca per ripeterla e controllare le novità.
6. **Esporta**: pagina di risultati o primi 50/100 in CSV, JSON o Markdown; singola
   sentenza in Markdown o JSON; citazione pronta da incollare; tutto lo storico dalla
   *Cronologia*.
7. **Ritrova**: tutto è nella *Cronologia* e nel *Diario*; ogni ricerca ha un collegamento
   diretto (permalink).

## La barra di navigazione

| Voce | Che cosa fa |
|------|-------------|
| Logo e nome | tornano alla pagina iniziale |
| Ricerca | riquadro di ricerca, filtri, risultati, pannello di lettura |
| Cronologia | le ricerche fatte, quante volte, con il collegamento per rifarle; export dello storico |
| Diario | l'archivio personale permanente: per giorno, le ricerche e le sentenze aperte da ciascuna (testo e PDF), con il testo conservato |
| Ricerche salvate | le interrogazioni conservate, con il controllo delle novità su richiesta |
| Preferiti | i singoli provvedimenti segnati, con le note |
| Stato | versione, richieste fatte al server, identità dichiarata, cache, PDF salvati, registro delle chiamate |
| Impostazioni | storico, PDF, impronta del browser, orari del tema scuro, nome del computer, importazione di uno storico |
| Help | guida, domande frequenti, versioni, software simili, licenza |
| Compatta | una riga per risultato (estremi, date, presidente, relatore, ECLI); un secondo clic torna alla vista con i frammenti |
| Sole e luna | tema chiaro o scuro; un secondo clic sull'icona attiva torna all'automatico per orario (19-7 per impostazione predefinita, orari nelle Impostazioni) |

## La ricerca

- **Parole o estremi**: più parole cercano la frase con distanza fino a 7 termini;
  `"giusta causa"` cerca la frase esatta; `licenz*` tronca; `AND`, `OR` combinano;
  `NOT mobbing` o `-mobbing` esclude la parola. Estremi: `12345/2024`, `n. 123 del 2025`, `sent. 99/24`, `ord. 5/2023`.
  La sintassi è quella del sito ufficiale, quindi i risultati coincidono.
- **Riferimento normativo**: `art. 2043 c.c.`, `art. 18 legge 300/1970`, `art. 640 c.p.`.
  Il server della Corte lo normalizza nelle forme con cui le sentenze lo citano; Iudex
  conserva le normalizzazioni per 30 giorni. Si combina con le parole.
- **Ordina per**: data di pubblicazione, data di udienza, rilevanza.
- **Per pagina**: 10, 25 o 50. Ogni pagina nuova è una richiesta; quelle viste restano in
  cache per un'ora.
- **Sintassi**: promemoria della sintassi e delle scorciatoie sotto il riquadro.

Mentre scrivi non parte nessuna richiesta: Iudex non ha suggerimenti automatici.

## I filtri

Per ogni filtro, i valori presenti nei risultati con conteggio e barra proporzionale.
Più valori dello stesso filtro si sommano (civile *o* penale), filtri diversi si
incrociano (sezione Lavoro *e* anno 2026). Ogni filtro attivo compare come etichetta
sopra i risultati; la crocetta lo toglie, *Azzera* li toglie tutti.

**Segnali nel testo**, in cima alla colonna: quanti provvedimenti fra i risultati dichiarano
un contrasto («contrasto giurisprudenziale», «difforme orientamento») o richiamano un
orientamento consolidato («orientamento consolidato», «in senso conforme»). La spunta
mostra solo quei provvedimenti, con le frasi evidenziate. Conteggi nella stessa risposta
della ricerca, nessuna richiesta in più; senza spunta i risultati coincidono con il sito. È
un segnale testuale, non una classificazione. Idea ed elenco delle frasi da
[mcp-legal-it](https://github.com/capazme/mcp-legal-it).

Filtri: archivio (civile/penale), tipo di provvedimento, sezione, anno di decisione,
sottosezione, materia (classificazione del CED; nell'indirizzo i valori sono separati da
punto e virgola).

La maniglia fra filtri e risultati si trascina per cambiare la larghezza; doppio clic per
ripristinare; frecce da tastiera con il focus sulla maniglia.

## I risultati

Ogni risultato mostra archivio e sezione, tipo e numero, date di udienza e deposito,
presidente, relatore, ECLI e (vista normale) i frammenti con le parole evidenziate.

- **Già vista**: compare accanto agli estremi delle sentenze già consultate (testo o PDF).
  Il passaggio del mouse mostra quante volte e l'ultima volta, da quali ricerche l'hai
  aperta e in quali ricerche precedenti è uscita.
- **Apri testo**: testo integrale nel pannello di lettura (una richiesta la prima volta,
  poi dalla cache). Anche il clic sugli estremi lo apre.
- **PDF**: il PDF ufficiale. La prima volta Iudex lo scarica (una richiesta) e lo salva nella
  cartella dei PDF come `<id>.pdf`; poi lo apre sempre dalla copia locale, nel pannello di
  lettura o con il programma PDF del computer (scelta nelle Impostazioni). Le sentenze in
  fase di oscuramento non hanno ancora il PDF.
- **Preferisci**: aggiunge o toglie dai preferiti.
- **Salva ricerca**: salva i criteri di ricerca correnti con un nome a tua scelta.
- **Esporta**: *pagina corrente* (nessuna richiesta), *primi 50* (al più una), *primi 100*
  (al più due); formati CSV, JSON, Markdown.
- **Collegamento diretto (permalink)**: ogni ricerca ha un indirizzo con tutti i parametri
  (`#testo=licenziamento&kind=snciv&anno=2026`); riaprendolo Iudex ripete la stessa ricerca.

## Il pannello di lettura

Testo in paragrafi con le intestazioni riconosciute (Fatti di causa, Ragioni della
decisione, P.Q.M.); in alto estremi, date, magistrati, ECLI e materia, quante volte l'hai
aperta, da quali ricerche e in quali ricerche è uscita.

- **PDF**, **Aggiungi ai preferiti**: come nell'elenco. Il PDF mostrato nel pannello ha
  *Torna al testo*.
- **Copia citazione**: negli appunti, nel formato `Cass. civ., Sez. Lavoro, Sentenza n.
  26495/2026, dep. 09/10/2026 (ECLI:IT:CASS:2026:26495CIV)`.
- **Markdown**, **JSON**: scaricano il singolo provvedimento, testo compreso.
- **P.Q.M.**: salta al dispositivo.
- **A−**, **A+**: carattere del testo (memorizzato).
- **‹ 1 / 4 ›**: occorrenze delle parole cercate (anche `n` e `p`).
- **Riferimenti normativi**: in fondo al testo, cliccabili (cercano le sentenze che citano
  la stessa norma). Accanto a quelli che Iudex legge con certezza c'è **Testo** (vedi sotto).
- **Chiudi** (anche `Esc`); `Alt+→` / `Alt+←` passano al provvedimento successivo o
  precedente senza chiudere.

## Testo della norma

Accanto a un riferimento normativo il bottone **Testo** apre, sotto i riferimenti, l'articolo
letto da Normattiva: titolo dell'atto, numero e rubrica dell'articolo, testo diviso in commi,
note e aggiornamenti in un blocco richiudibile, vigenza ("In vigore dal ..."), il link
**Apri su Normattiva** e la fonte "Normattiva (IPZS), CC BY 4.0". I segni `(( ))` sono quelli
di Normattiva e racchiudono il testo inserito o modificato da leggi successive.

- Il bottone compare solo quando il riferimento ha tutti i dati certi: per i codici (c.c.,
  c.p., c.p.c., c.p.p., Costituzione) basta l'articolo, per leggi e decreti servono anche
  numero e anno. Leggi regionali e CEDU non hanno il bottone; regolamenti e direttive UE
  avranno il link **EUR-Lex**.
- Una sola richiesta a Normattiva per clic, mai prima: aprire una sentenza non chiede nulla.
  Un secondo clic su **Testo** richiude il pannello senza nuove richieste.
- Il testo letto resta nella cache locale per 30 giorni: riaprirlo non chiede nulla a
  Normattiva (il pannello lo dice con "dalla cache locale").
- Allegati e tabelle degli atti non sono mostrati: per quelli c'è **Apri su Normattiva**.
- Se Normattiva non ha l'articolo, chiede una pausa ("Normattiva: attendere N s") o non
  risponde, il pannello lo dice; Iudex non ritenta da solo.

## Diario

L'archivio personale, che nessun pulsante della cache svuota. Per giorno: le ricerche (ora,
parole, filtri, provvedimenti, pagina) e sotto ciascuna le sentenze aperte da quei risultati,
testo e PDF. La stessa sentenza aperta in giorni diversi da ricerche diverse compare sotto
ognuna.

- Delle ricerche resta la traccia e l'elenco delle sentenze mostrate in ogni pagina vista;
  delle sentenze **aperte** la risposta intera del server, testo compreso, una volta sola
  per sentenza: si riaprono anche senza rete e anche dopo che il provvedimento è uscito
  dall'archivio pubblico.
- Export: *Diario JSONL*, *Diario CSV* (tutte le voci); *Sentenze consultate (zip)* con
  `<id>.json` (risposta del server, tutti i campi) e `<id>.txt` (solo testo in paragrafi);
  *FollowTheMoney*: file `.ftm` (JSON a righe, il formato di Aleph e di `ftm`) con un
  `CourtCase` e un `Document` per sentenza e presidente e relatore come `Person` collegati
  da `CourtCaseParty`. Le parti del giudizio non vengono estratte.
- I testi contengono nomi, date di nascita e fatti di causa in chiaro: restano nella cartella
  dei dati di Iudex e da nessun'altra parte. Vanno custoditi con la stessa riservatezza di un
  fascicolo di studio.

## Cronologia, ricerche salvate, preferiti

- **Cronologia**: data e ora, testo e filtri, risultati, ordinamento, per pagina; *Apri*
  rifà la ricerca, *Elimina* toglie la voce (con le sentenze uscite da quella ricerca),
  *Svuota* cancella tutto.
- **Esporta lo storico** (nella barra della Cronologia): *Excel (CSV)* con una riga per ogni
  sentenza uscita in ogni ricerca, la data di consultazione e se il PDF è salvato; *JSONL*
  con tutto lo storico; *Pacchetto ZIP con i PDF* con i CSV di ricerche, esecuzioni,
  risultati e consultazioni, il JSONL, la risposta intera e il testo delle sentenze consultate
  e i PDF salvati. Ogni riga dice anche su quale computer è stata fatta.
- **Ricerche salvate**: un'*interrogazione* da ripetere. *Controlla novità* rifà la
  ricerca (una richiesta) e confronta con l'ultimo controllo; nessun controllo automatico.
- **Preferiti**: un *singolo provvedimento* con nota e badge *già vista*; *PDF* apre il PDF
  come nell'elenco, *Rimuovi* lo toglie.

## Impostazioni

- **Conserva lo storico**: spento, Iudex non registra niente (ricerche, sentenze uscite,
  diario, consultazioni, testi, PDF: il PDF si apre da un file provvisorio cancellato alla
  chiusura). Quello già registrato resta.
- **PDF delle sentenze**: la cartella (scelta anche nell'installer; cambiandola, i PDF già
  salvati si spostano) e dove aprirli: nella finestra di Iudex o con il programma PDF del
  computer.
- **Identità dichiarata al server della Corte**: una delle impronte predefinite (Chrome, Edge
  o Firefox su Windows) a rotazione ogni giorno, sempre la stessa, una personalizzata o le
  personalizzate a rotazione (con o senza le predefinite). Un'impronta personalizzata è il
  nome, lo User-Agent e le lingue di un browser vero; Iudex controlla che sia coerente e per
  Chrome ed Edge ricava `sec-ch-ua`. *Prova* mostra gli header senza contattare la Corte.
  `IUDEX_IMPRONTA`, se impostata, vince e il campo resta bloccato.
- **Aspetto**: le ore di inizio e di fine del tema scuro automatico (ora del computer); valgono
  subito.
- **Questo computer**: il nome che compare accanto a ricerche e consultazioni negli export.
- **Importa uno storico**: unisce allo storico di questo computer il pacchetto ZIP, il JSONL
  o una copia del database (`.sqlite`) di un altro Iudex. Niente viene duplicato né
  cancellato; prima Iudex fa una copia di sicurezza; il riepilogo dice che cosa è stato
  aggiunto e che cosa c'era già.

## Stato

Richieste fatte al server e intervallo minimo (2 s); identità dichiarata ora; testi e risposte
in cache, voci del diario, sentenze consultate, pagine di risultati ricordate, PDF salvati e
la loro cartella, percorso dell'archivio, con *Svuota cache ricerche* e *Svuota testi in
cache* (preferiti, diario e storico restano) e *Copia di sicurezza* (copia pulita del
database nella cartella dei dati); registro delle ultime chiamate con esito e durata.
Per Normattiva: richieste fatte, intervallo minimo, eventuale pausa e articoli in cache.

## Tastiera

| Tasto | Effetto |
|-------|---------|
| `/` | cursore nel campo di ricerca |
| `Invio` | avvia la ricerca; su un risultato lo apre |
| `j` / `k` | risultato successivo / precedente |
| `n` / `p` | occorrenza successiva / precedente nel testo |
| `Alt+→` / `Alt+←` | provvedimento successivo / precedente, con il pannello aperto |
| `Esc` | chiude il pannello di lettura |
| `←` / `→` su una maniglia | allarga o stringe la colonna; doppio clic per ripristinare |

## Con un assistente

Il server MCP incluso espone tre strumenti a un assistente o LLM locale, con il token della
cartella dei dati. Dettagli nelle [domande frequenti](faq.md). In ogni caso Iudex fa una
richiesta alla volta al server della Corte, con almeno due secondi di distanza, e non ha
funzioni di scaricamento massivo.
