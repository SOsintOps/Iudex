# Domande frequenti

La stessa pagina è nell'app, nel menu **Help → Domande frequenti**.

## I dati

**Che cosa contiene SentenzeWeb?** Le sentenze, le ordinanze e i decreti civili e penali
della Corte di Cassazione pubblicati negli ultimi anni: al 21 ottobre 2026 circa 422.000
provvedimenti dal 2021. È una finestra scorrevole di circa cinque anni. Non contiene le
massime ufficiali né i provvedimenti anteriori: quelli sono in ItalgiureWeb, riservato agli
operatori.

**Iudex copia la banca dati?** No. Ogni ricerca interroga il server della Corte nel momento
in cui la fai. In locale restano le risposte recenti (un'ora), i testi e i PDF che hai aperto
e la memoria delle tue ricerche e consultazioni.

**Di chi sono i testi?** Della Corte Suprema di Cassazione, che li pubblica per la
consultazione. Iudex salva il PDF ufficiale di una sentenza solo quando lo apri, una volta, e
non scarica mai in blocco.

**Si può cercare un nome di persona o di società?** Sì. Sulla Corte la ricerca usa lo stesso
motore del sito: un nome fra virgolette trova le sentenze che lo contengono nel testo, una
richiesta alla volta come ogni altra ricerca. Fra le sentenze già salvate su questo computer
Iudex cerca con un indice locale, senza nessuna richiesta alla Corte: l'indice sta nel database
di Iudex e non viene mai inviato. Usa i risultati con cautela: molti nomi nelle sentenze sono
oscurati, e lo stesso nome può appartenere a persone diverse. Le sentenze contengono dati
personali e talvolta categorie particolari di dati; nel 2024 il Garante per la protezione dei
dati personali ha ammonito la Corte per la presenza di dati relativi alla salute e a vittime di
reati nei testi pubblicati: quello che trovi va trattato con la stessa riservatezza.

## La ricerca

**I risultati sono gli stessi del sito?** Sì, a parità di parole e filtri: Iudex segue la
stessa sintassi del sito (frasi, troncamenti, estremi, riferimenti normativi, descritta in
[analisi-sito.md](analisi-sito.md)) e manda la query allo stesso motore. In tre casi fa
meglio: `NOT parola` esclude davvero (sul sito finisce dentro una frase e non esclude), i
caratteri speciali sono protetti anche con gli operatori, gli estremi accettano anche
`Cass. civ.` e il tipo in fondo.

**Estremi:** `12345/2024`, `n. 123 del 2025`, `sent. 99/24`, `ord. 5/2023` (ultimi sette anni).

**Frasi e troncamenti:** più parole = distanza massima sette termini; `"giusta causa"` = frase
esatta; `licenz*` = troncamento; `AND`, `OR`, `NOT`.

**Norma:** nel campo "Riferimento normativo" scrivi la citazione (`art. 18 legge 300/1970`,
`art. 2043 c.c.`): il server della Corte la normalizza nelle varianti usate dalle sentenze.
I riferimenti indicizzati di una sentenza aperta sono cliccabili.

**Materia:** classificazione per argomento del CED; Iudex mostra i valori più frequenti fra
i risultati. Il sito non ha questo filtro.

**"Dalla cache locale":** la stessa ricerca era stata fatta da meno di un'ora.

**Paragrafi:** il testo OCR arriva senza a capo; Iudex ricostruisce intestazioni e punti
numerati, ma non separa le parole che l'OCR ha unito.

## Le richieste al server

**Quante?** Una per ricerca, una per il testo di una sentenza mai aperta, una per il PDF di
una sentenza alla prima apertura, una per un riferimento normativo nuovo, una al mese per la
lista delle sigle. Il sito ne fa circa venti per ricerca.

**Limiti:** una richiesta alla volta, almeno due secondi di distanza, un solo nuovo tentativo
su errore di rete, nessuna insistenza su 403/429. Nessuna funzione di scaricamento massivo.

**Novità delle ricerche salvate:** solo su richiesta, una chiamata per ricerca. Il primo
controllo registra il punto di partenza.

**Esportazioni:** pagina corrente = nessuna richiesta; primi 50 = al più una; primi 100 = al
più due.

**Identità:** gli header di un browser. Per impostazione predefinita Chrome, Edge o Firefox su
Windows, scelto dal giorno del calendario: lo stesso per tutta la giornata, un altro il giorno
dopo, quando Iudex riapre anche la sessione. Nelle Impostazioni si può fissare una predefinita,
usarne una personalizzata (controllata perché sia coerente) o far ruotare le personalizzate;
`IUDEX_IMPRONTA` le fissa tutte; la scheda Stato mostra quella in uso. Cambiano solo gli
header: l'impronta TLS resta quella di Python.

## I dati locali

Tutto nella cartella dei dati di Iudex: il database `iudex.sqlite` (percorso nella scheda
Stato), il token di accesso e, salvo scelta diversa, la cartella `pdf`. Svuotamento della
cache dalla scheda Stato; per azzerare, chiudi Iudex ed elimina la cartella.

**Iudex salva le mie ricerche?** Sì, per sempre (salvo che tu spenga lo storico nelle
Impostazioni): ogni ricerca, ogni pagina di risultati vista con le sentenze mostrate, ogni
sentenza aperta (testo o PDF) con la ricerca di provenienza, e su quale computer. Delle
sentenze aperte conserva la risposta intera del server, testo compreso. Il badge *già vista*
nei risultati lo mostra al passaggio del mouse. Lo storico non si svuota con i pulsanti della
cache; si esporta dalla Cronologia (CSV per Excel, JSONL, pacchetto ZIP con i PDF) e dal Diario
(JSONL, CSV, zip, FollowTheMoney), e *Copia di sicurezza* salva il database intero.

**Posso portare lo storico su un altro computer?** Sì: esporta il pacchetto ZIP dalla
Cronologia e importalo nell'altro Iudex (Impostazioni, *Importa uno storico*). L'importazione
unisce senza duplicati, anche più volte e da più computer; accetta anche il JSONL o una copia
del database.

**Dove sono i PDF?** Nella cartella scelta nell'installer o nelle Impostazioni (la scheda
Stato la mostra), uno per sentenza con il nome `<id>.pdf`. Cambiando cartella, Iudex sposta
quelli già salvati.

**Colonne:** trascina le linee fra i pannelli o fra le intestazioni delle tabelle; doppio
clic ripristina; da tastiera, focus sulla maniglia e frecce.

## Problemi

- **HTTP 403/429:** il server limita le richieste. Iudex non ne manda altre per il tempo
  indicato da `Retry-After` (un minuto se manca) e risponde subito «riprova fra N s»; la
  scheda Stato mostra quanto manca; dopo un 403 riapre la sessione. Alza `IUDEX_INTERVALLO`
  se succede spesso.
- **Errore di certificato:** il server invia una catena incompleta; Iudex include
  l'intermedio in `src/iudex/certs/`. Se il messaggio compare, reinstalla o apri una segnalazione.
- **"Errore di rete" con la VPN attiva:** il server della Corte non risponde agli indirizzi
  di uscita delle VPN (il collegamento resta senza risposta). Escludi dal tunnel l'indirizzo
  di `www.italgiure.giustizia.it` con l'esclusione per IP della VPN (*split tunneling*); i
  dettagli nel README, sezione «Da dietro una VPN».
- **"Iudex si usa dalla sua finestra" nel browser:** è voluto. Pagine e API rispondono solo
  alla finestra di Iudex (e al server MCP), che hanno il token della cartella dei dati: aprilo
  dal collegamento nel menu Start o sul Desktop.
- **"Richiesta non proveniente dall'interfaccia di Iudex":** le API accettano solo le
  chiamate della pagina (header `X-Iudex: 1`).
- **La ricerca non risponde:** Iudex non è aperto. Porta occupata da un altro programma:
  Iudex passa alla successiva libera (o cambia `IUDEX_PORTA`); se è già aperto un altro Iudex,
  l'avvio apre quello.
- **Su Linux la finestra non si apre:** manca WebKitGTK; il messaggio dice il comando
  (Debian e Ubuntu: `sudo apt install gir1.2-webkit2-4.1 python3-gi`).
- **"Errore interno di Iudex":** errore imprevisto (per esempio disco pieno); la traccia è
  in `log/iudex.log` nella cartella dei dati.

## Finestra e assistenti

- **Finestra:** Iudex si usa solo dalla sua finestra (pywebview su WebView2 in Windows,
  WebKitGTK in Linux), come Voicebox; dai sorgenti `scripts\avvia-finestra.cmd` (extra
  `desktop`).
- **Assistenti e LLM locali:** `python -m iudex.mcp_server` (extra `mcp`) espone tre
  strumenti che passano dall'API locale; serve un client MCP e Iudex aperto. Il token si
  legge dal file `token` della cartella dei dati (o da `IUDEX_TOKEN`).

## Lo sviluppo

**Iudex è stato sviluppato con l'intelligenza artificiale?** Sì, se n'è fatto ampio uso:
assistenti AI hanno scritto buona parte del codice, dei test e della documentazione, sotto la
guida e con la revisione di chi sviluppa il progetto, che ha deciso funzioni, regole e priorità.
Nessuna delle AI coinvolte ha mostrato sintomi di maltrattamento.
