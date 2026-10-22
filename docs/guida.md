# Guida all'utilizzo

La stessa guida è nell'app, nel menu **Help → Guida all'utilizzo**.

Iudex è un'interfaccia locale per SentenzeWeb, la banca dati pubblica delle sentenze civili
e penali della Corte Suprema di Cassazione. Non duplica la banca dati: ogni ricerca interroga il
server della Corte nel momento in cui la esegui; in locale restano cronologia, diario, ricerche
salvate, preferiti e una cache dei testi già aperti.

## Il flusso di lavoro

1. **Cerca**: parole, estremi o riferimento normativo nel riquadro in alto, poi *Cerca*
   (o Invio). Parte una sola richiesta al server.
2. **Restringi** con i filtri a sinistra (archivio, tipo, sezione, anno, sottosezione,
   materia): i conteggi arrivano con la stessa risposta della ricerca.
3. **Leggi**: *Apri testo* mostra il provvedimento in paragrafi accanto ai risultati, con
   le occorrenze evidenziate, il salto al P.Q.M. e i riferimenti normativi cliccabili. Il
   PDF ufficiale si apre sempre dal sito della Corte.
4. **Conserva**: *Preferisci* mette il provvedimento fra i preferiti (con una nota);
   *Salva ricerca* salva i criteri di ricerca per ripeterla e controllare le novità.
5. **Esporta**: pagina di risultati o primi 50/100 in CSV, JSON o Markdown; singola
   sentenza in Markdown o JSON; citazione pronta da incollare.
6. **Ritrova**: tutto è nella *Cronologia* e nel *Diario*; ogni ricerca ha un collegamento diretto (permalink).

## La barra di navigazione

| Voce | Che cosa fa |
|------|-------------|
| Logo e nome | tornano alla pagina iniziale |
| Ricerca | riquadro di ricerca, filtri, risultati, pannello di lettura |
| Cronologia | le ricerche fatte, con il numero di risultati e il collegamento per rifarle |
| Diario | l'archivio personale permanente: per giorno, le ricerche e le sentenze aperte da ciascuna, con il testo conservato |
| Ricerche salvate | le interrogazioni conservate, con il controllo delle novità su richiesta |
| Preferiti | i singoli provvedimenti segnati, con le note |
| Stato | versione, richieste fatte al server, cache, orari del tema scuro, registro delle chiamate |
| Help | guida, domande frequenti, versioni, software simili, licenza |
| Compatta | una riga per risultato (estremi, date, presidente, relatore, ECLI); un secondo clic torna alla vista con i frammenti |
| Sole e luna | tema chiaro o scuro; un secondo clic sull'icona attiva torna all'automatico per orario (19-7 per impostazione predefinita) |

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

- **Apri testo**: testo integrale nel pannello di lettura (una richiesta la prima volta,
  poi dalla cache). Anche il clic sugli estremi lo apre.
- **PDF ufficiale**: apre il documento sul sito della Corte. Iudex non scarica i PDF.
- **Preferisci**: aggiunge o toglie dai preferiti.
- **Salva ricerca**: salva i criteri di ricerca correnti con un nome a tua scelta.
- **Esporta**: *pagina corrente* (nessuna richiesta), *primi 50* (al più una), *primi 100*
  (al più due); formati CSV, JSON, Markdown.
- **Collegamento diretto (permalink)**: dopo ogni ricerca la barra degli indirizzi del browser contiene tutti i
  parametri (`#testo=licenziamento&kind=snciv&anno=2026`); riaprendolo Iudex ripete la
  stessa ricerca.

## Il pannello di lettura

Testo in paragrafi con le intestazioni riconosciute (Fatti di causa, Ragioni della
decisione, P.Q.M.); in alto estremi, date, magistrati, ECLI e materia.

- **PDF ufficiale**, **Aggiungi ai preferiti**: come nell'elenco.
- **Copia citazione**: negli appunti, nel formato `Cass. civ., Sez. Lavoro, Sentenza n.
  26495/2026, dep. 09/10/2026 (ECLI:IT:CASS:2026:26495CIV)`.
- **Markdown**, **JSON**: scaricano il singolo provvedimento, testo compreso.
- **P.Q.M.**: salta al dispositivo.
- **A−**, **A+**: carattere del testo (memorizzato).
- **‹ 1 / 4 ›**: occorrenze delle parole cercate (anche `n` e `p`).
- **Riferimenti normativi**: in fondo al testo, cliccabili (cercano le sentenze che citano
  la stessa norma).
- **Chiudi** (anche `Esc`); `Alt+→` / `Alt+←` passano al provvedimento successivo o
  precedente senza chiudere.

## Diario

L'archivio personale, che nessun pulsante svuota. Per giorno: le ricerche (ora, parole,
filtri, provvedimenti, pagina) e sotto ciascuna le sentenze aperte da quei risultati. La
stessa sentenza aperta in giorni diversi da ricerche diverse compare sotto ognuna.

- Delle ricerche resta solo la traccia; delle sentenze **aperte** la risposta intera del
  server, testo compreso, una volta sola per sentenza: si riaprono dal diario anche senza
  rete e anche dopo che il provvedimento è uscito dall'archivio pubblico.
- Nel pannello di lettura: «Aperta *N* volte», data della prima apertura, ricerche di
  provenienza cliccabili.
- Export: *Diario JSONL*, *Diario CSV* (tutte le voci); *Sentenze consultate (zip)* con
  `<id>.json` (risposta del server, tutti i campi) e `<id>.txt` (solo testo in paragrafi);
  *FollowTheMoney*: file `.ftm` (JSON a righe, il formato di Aleph e di `ftm`) con un
  `CourtCase` e un `Document` per sentenza e presidente e relatore come `Person` collegati
  da `CourtCaseParty`. Le parti del giudizio non vengono estratte.
- I testi contengono nomi, date di nascita e fatti di causa in chiaro: restano in
  `dati/iudex.sqlite` e da nessun'altra parte. Va custodito con la stessa riservatezza di un fascicolo di studio.

## Cronologia, ricerche salvate, preferiti

- **Cronologia**: data e ora, testo e filtri, risultati, ordinamento, per pagina; *Apri*
  rifà la ricerca, *Elimina* toglie la voce, *Svuota* cancella tutto.
- **Ricerche salvate**: un'*interrogazione* da ripetere. *Controlla novità* rifà la
  ricerca (una richiesta) e confronta con l'ultimo controllo; nessun controllo automatico.
- **Preferiti**: un *singolo provvedimento* con nota; *PDF* apre il documento sul sito,
  *Rimuovi* lo toglie.

## Stato

Richieste fatte al server e intervallo minimo (2 s); testi e risposte in cache, voci del
diario e sentenze consultate, percorso dell'archivio, con *Svuota cache ricerche* e *Svuota
testi in cache* (preferiti e diario restano) e *Copia di sicurezza* (copia pulita del
database in `dati/iudex-AAAAMMGG-HHMMSS.sqlite`); orari del tema scuro automatico; registro
delle ultime chiamate con esito e durata.

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

## Oltre il browser

`scripts\avvia-finestra.cmd` apre Iudex in una finestra propria; il server MCP incluso
espone tre strumenti a un assistente o LLM locale. Dettagli nelle [domande
frequenti](faq.md). In ogni caso Iudex fa una richiesta alla volta al server della Corte,
con almeno due secondi di distanza, e non ha funzioni di scaricamento massivo.
