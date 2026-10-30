# Domande frequenti (FAQ)

Domande frequenti su Iudex: i dati, la ricerca, le richieste al server, i dati locali, i problemi, la finestra e gli assistenti, lo sviluppo.

La stessa pagina è nell'app, nel menu **Help → Domande frequenti**.

## Indice

* [Che cosa contiene SentenzeWeb?](#che-cosa-contiene-sentenzeweb)
* [Iudex copia la banca dati?](#iudex-copia-la-banca-dati)
* [Di chi sono i testi?](#di-chi-sono-i-testi)
* [Si può cercare un nome di persona o di società?](#si-può-cercare-un-nome-di-persona-o-di-società)
* [I risultati sono gli stessi del sito?](#i-risultati-sono-gli-stessi-del-sito)
* [Come si cerca per estremi?](#come-si-cerca-per-estremi)
* [Come si cerca una frase o un troncamento?](#come-si-cerca-una-frase-o-un-troncamento)
* [Come si cerca per norma?](#come-si-cerca-per-norma)
* [Che cos'è il filtro "materia"?](#che-cosè-il-filtro-materia)
* [Che cosa vuol dire "dalla cache locale"?](#che-cosa-vuol-dire-dalla-cache-locale)
* [Perché il testo ha i paragrafi e il sito no?](#perché-il-testo-ha-i-paragrafi-e-il-sito-no)
* [Che cosa fa il bottone "Testo"?](#che-cosa-fa-il-bottone-testo)
* [Da dove viene il testo delle norme e con quale licenza?](#da-dove-viene-il-testo-delle-norme-e-con-quale-licenza)
* [Perché mancano allegati e tabelle?](#perché-mancano-allegati-e-tabelle)
* [Quante richieste fa Iudex a Normattiva?](#quante-richieste-fa-iudex-a-normattiva)
* [Quante richieste fa Iudex?](#quante-richieste-fa-iudex)
* [Quali limiti rispetta?](#quali-limiti-rispetta)
* [Il controllo delle novità è automatico?](#il-controllo-delle-novità-è-automatico)
* [Quanto costa un'esportazione?](#quanto-costa-unesportazione)
* [Con che identità si presenta Iudex?](#con-che-identità-si-presenta-iudex)
* [Dove sono salvati cronologia, preferiti e cache?](#dove-sono-salvati-cronologia-preferiti-e-cache)
* [Iudex salva le mie ricerche?](#iudex-salva-le-mie-ricerche)
* [Posso portare lo storico su un altro computer?](#posso-portare-lo-storico-su-un-altro-computer)
* [Dove sono i PDF?](#dove-sono-i-pdf)
* [Come cancello tutto?](#come-cancello-tutto)
* [Posso cambiare la larghezza delle colonne?](#posso-cambiare-la-larghezza-delle-colonne)
* ["Il server ha rifiutato la richiesta (HTTP 403 o 429)"](#il-server-ha-rifiutato-la-richiesta-http-403-o-429)
* ["Errore di rete" o "certificate verify failed"](#errore-di-rete-o-certificate-verify-failed)
* ["Errore di rete" con la VPN attiva](#errore-di-rete-con-la-vpn-attiva)
* [Nel browser compare "Iudex si usa dalla sua finestra"](#nel-browser-compare-iudex-si-usa-dalla-sua-finestra)
* ["Ricerca non riuscita: richiesta non proveniente dall'interfaccia di Iudex"](#ricerca-non-riuscita-richiesta-non-proveniente-dallinterfaccia-di-iudex)
* [La finestra si apre ma la ricerca non risponde](#la-finestra-si-apre-ma-la-ricerca-non-risponde)
* [Su Linux la finestra non si apre](#su-linux-la-finestra-non-si-apre)
* ["Errore interno di Iudex"](#errore-interno-di-iudex)
* [Perché Iudex non si apre più nel browser?](#perché-iudex-non-si-apre-più-nel-browser)
* [Si può usare da un assistente o da un LLM locale?](#si-può-usare-da-un-assistente-o-da-un-llm-locale)
* [Iudex è stato sviluppato con l'intelligenza artificiale?](#iudex-è-stato-sviluppato-con-lintelligenza-artificiale)

## I dati

### Che cosa contiene SentenzeWeb?

Le sentenze, le ordinanze e i decreti civili e penali della Corte di Cassazione pubblicati
negli ultimi anni: al 21 ottobre 2026 circa 422.000 provvedimenti dal 2021. È una finestra
scorrevole di circa cinque anni. Non contiene le massime ufficiali né i provvedimenti
anteriori: quelli sono in ItalgiureWeb, riservato agli operatori.

### Iudex copia la banca dati?

No. Ogni ricerca interroga il server della Corte nel momento in cui la fai. In locale restano
le risposte recenti (un'ora), i testi e i PDF che hai aperto e la memoria delle tue ricerche e
consultazioni.

### Di chi sono i testi?

Della Corte Suprema di Cassazione, che li pubblica per la consultazione. Iudex salva il PDF
ufficiale di una sentenza solo quando lo apri, una volta, e non scarica mai in blocco.

### Si può cercare un nome di persona o di società?

Sì. Sulla Corte la ricerca usa lo stesso motore del sito: un nome fra virgolette trova le
sentenze che lo contengono nel testo, una richiesta alla volta come ogni altra ricerca. Fra le
sentenze già salvate su questo computer Iudex cerca con un indice locale, senza nessuna
richiesta alla Corte: l'indice sta nel database di Iudex e non viene mai inviato. Usa i
risultati con cautela: molti nomi nelle sentenze sono oscurati, e lo stesso nome può
appartenere a persone diverse. Le sentenze contengono dati personali e talvolta categorie
particolari di dati; nel 2024 il Garante per la protezione dei dati personali ha ammonito la
Corte per la presenza di dati relativi alla salute e a vittime di reati nei testi pubblicati:
quello che trovi va trattato con la stessa riservatezza.

## La ricerca

### I risultati sono gli stessi del sito?

Sì, a parità di parole e filtri: Iudex segue la stessa sintassi del sito (frasi, troncamenti,
estremi, riferimenti normativi, descritta in [analisi-sito.md](analisi-sito.md)) e manda la
query allo stesso motore. In tre casi fa meglio: `NOT parola` esclude davvero (sul sito
finisce dentro una frase e non esclude), i caratteri speciali sono protetti anche con gli
operatori, gli estremi accettano anche `Cass. civ.` e il tipo in fondo.

### Come si cerca per estremi?

`12345/2024`, `n. 123 del 2025`, `sent. 99/24`, `ord. 5/2023` (ultimi sette anni).

### Come si cerca una frase o un troncamento?

Più parole = distanza massima sette termini; `"giusta causa"` = frase esatta; `licenz*` =
troncamento; `AND`, `OR`, `NOT`.

### Come si cerca per norma?

Nel campo "Riferimento normativo" scrivi la citazione (`art. 18 legge 300/1970`,
`art. 2043 c.c.`): il server della Corte la normalizza nelle varianti usate dalle sentenze. I
riferimenti indicizzati di una sentenza aperta sono cliccabili.

### Che cos'è il filtro "materia"?

Classificazione per argomento del CED; Iudex mostra i valori più frequenti fra i risultati. Il
sito non ha questo filtro.

### Che cosa vuol dire "dalla cache locale"?

La stessa ricerca era stata fatta da meno di un'ora.

### Perché il testo ha i paragrafi e il sito no?

Il testo OCR arriva senza a capo; Iudex ricostruisce intestazioni e punti numerati, ma non
separa le parole che l'OCR ha unito.

## Il testo delle norme

### Che cosa fa il bottone "Testo"?

Nella sentenza aperta, accanto a un riferimento normativo, apre l'articolo citato: titolo
dell'atto, numero e rubrica, testo a commi, note richiudibili, vigenza e il link **Apri su
Normattiva**. Compare solo quando il riferimento ha tutti i dati certi (per leggi e decreti
numero e anno, per i codici basta l'articolo): meglio nessun bottone che l'articolo sbagliato.
I segni `(( ))` racchiudono il testo inserito o modificato da leggi successive.

### Da dove viene il testo delle norme e con quale licenza?

Dall'API Open Data di Normattiva, la banca dati ufficiale delle leggi dello Stato curata
dall'Istituto Poligrafico e Zecca dello Stato. I dati sono in licenza CC BY 4.0: Iudex mostra
accanto a ogni testo "Fonte: Normattiva (IPZS), CC BY 4.0" e il link all'atto sul sito. Fa fede
la Gazzetta Ufficiale. Leggi regionali, CEDU e atti dell'Unione europea non sono in Normattiva.

### Perché mancano allegati e tabelle?

Iudex mostra il testo dell'articolo; allegati e tabelle degli atti non sono mostrati. Si
aprono dal link **Apri su Normattiva**.

### Quante richieste fa Iudex a Normattiva?

Una per clic su **Testo**, mai prima: aprire una sentenza non chiede nulla a Normattiva, e
fra due richieste passano almeno 2 secondi. Il testo letto resta nella cache locale per 30
giorni, quindi riaprirlo non fa richieste; un secondo clic richiude il pannello. Se Normattiva
chiede una pausa il pannello mostra quanti secondi attendere e Iudex non ritenta da solo. Le
richieste fatte sono nella scheda Stato.

## Le richieste al server

### Quante richieste fa Iudex?

Una per ricerca, una per il testo di una sentenza mai aperta, una per il PDF di una sentenza
alla prima apertura, una per un riferimento normativo nuovo, una al mese per la lista delle
sigle. Il sito ne fa circa venti per ricerca.

### Quali limiti rispetta?

Una richiesta alla volta, almeno due secondi di distanza, un solo nuovo tentativo su errore di
rete, nessuna insistenza su 403/429. Nessuna funzione di scaricamento massivo.

### Il controllo delle novità è automatico?

No: le novità delle ricerche salvate si controllano solo su richiesta, una chiamata per
ricerca. Il primo controllo registra il punto di partenza.

### Quanto costa un'esportazione?

Pagina corrente = nessuna richiesta; primi 50 = al più una; primi 100 = al più due.

### Con che identità si presenta Iudex?

Con gli header di un browser. Per impostazione predefinita Chrome, Edge o Firefox su Windows,
scelto dal giorno del calendario: lo stesso per tutta la giornata, un altro il giorno dopo,
quando Iudex riapre anche la sessione. Nelle Impostazioni si può fissare una predefinita,
usarne una personalizzata (controllata perché sia coerente) o far ruotare le personalizzate;
`IUDEX_IMPRONTA` le fissa tutte; la scheda Stato mostra quella in uso. Cambiano solo gli
header: l'impronta TLS resta quella di Python.

## I dati locali

### Dove sono salvati cronologia, preferiti e cache?

Tutto nella cartella dei dati di Iudex: il database `iudex.sqlite` (percorso nella scheda
Stato), il token di accesso e, salvo scelta diversa, la cartella `pdf`.

### Iudex salva le mie ricerche?

Sì, per sempre (salvo che tu spenga lo storico nelle Impostazioni): ogni ricerca, ogni pagina
di risultati vista con le sentenze mostrate, ogni sentenza aperta (testo o PDF) con la ricerca
di provenienza, e su quale computer. Delle sentenze aperte conserva la risposta intera del
server, testo compreso. Il badge *già vista* nei risultati lo mostra al passaggio del mouse.
Lo storico non si svuota con i pulsanti della cache; si esporta dalla Cronologia (CSV per
Excel, JSONL, pacchetto ZIP con i PDF) e dal Diario (JSONL, CSV, zip, FollowTheMoney), e
*Copia di sicurezza* salva il database intero.

### Posso portare lo storico su un altro computer?

Sì: esporta il pacchetto ZIP dalla Cronologia e importalo nell'altro Iudex (Impostazioni,
*Importa uno storico*). L'importazione unisce senza duplicati, anche più volte e da più
computer; accetta anche il JSONL o una copia del database.

### Dove sono i PDF?

Nella cartella scelta nell'installer o nelle Impostazioni (la scheda Stato la mostra), uno per
sentenza con il nome `<id>.pdf`. Cambiando cartella, Iudex sposta quelli già salvati.

### Come cancello tutto?

Svuotamento della cache dalla scheda Stato; per azzerare, chiudi Iudex ed elimina la cartella
dei dati.

### Posso cambiare la larghezza delle colonne?

Sì: trascina le linee fra i pannelli o fra le intestazioni delle tabelle; doppio clic
ripristina; da tastiera, focus sulla maniglia e frecce.

## Problemi

### "Il server ha rifiutato la richiesta (HTTP 403 o 429)"

Il server limita le richieste. Iudex non ne manda altre per il tempo indicato da `Retry-After`
(un minuto se manca) e risponde subito «riprova fra N s»; la scheda Stato mostra quanto manca;
dopo un 403 riapre la sessione. Alza `IUDEX_INTERVALLO` se succede spesso.

### "Errore di rete" o "certificate verify failed"

Il server invia una catena incompleta; Iudex include l'intermedio in `src/iudex/certs/`. Se il
messaggio compare, reinstalla o apri una segnalazione.

### "Errore di rete" con la VPN attiva

Il server della Corte non risponde agli indirizzi di uscita delle VPN (il collegamento resta
senza risposta). Escludi dal tunnel l'indirizzo di `www.italgiure.giustizia.it` con
l'esclusione per IP della VPN (*split tunneling*); i dettagli nel README, sezione «Da dietro
una VPN».

### Nel browser compare "Iudex si usa dalla sua finestra"

È voluto. Pagine e API rispondono solo alla finestra di Iudex (e al server MCP), che hanno il
token della cartella dei dati: aprilo dal collegamento nel menu Start o sul Desktop.

### "Ricerca non riuscita: richiesta non proveniente dall'interfaccia di Iudex"

Le API accettano solo le chiamate della pagina (header `X-Iudex: 1`).

### La finestra si apre ma la ricerca non risponde

Iudex non è aperto. Porta occupata da un altro programma: Iudex passa alla successiva libera
(o cambia `IUDEX_PORTA`); se è già aperto un altro Iudex, l'avvio apre quello.

### Su Linux la finestra non si apre

Manca WebKitGTK; il messaggio dice il comando (Debian e Ubuntu:
`sudo apt install gir1.2-webkit2-4.1 python3-gi`).

### "Errore interno di Iudex"

Errore imprevisto (per esempio disco pieno); la traccia è in `log/iudex.log` nella cartella dei
dati.

## Finestra e assistenti

### Perché Iudex non si apre più nel browser?

Iudex si usa solo dalla sua finestra (pywebview su WebView2 in Windows, WebKitGTK in Linux),
come Voicebox; dai sorgenti `scripts\avvia-finestra.cmd` (extra `desktop`).

### Si può usare da un assistente o da un LLM locale?

Sì: `python -m iudex.mcp_server` (extra `mcp`) espone tre strumenti che passano dall'API
locale; serve un client MCP e Iudex aperto. Il token si legge dal file `token` della cartella
dei dati (o da `IUDEX_TOKEN`).

## Lo sviluppo

### Iudex è stato sviluppato con l'intelligenza artificiale?

Sì, se n'è fatto ampio uso: assistenti AI hanno scritto buona parte del codice, dei test e
della documentazione, sotto la guida e con la revisione di chi sviluppa il progetto, che ha
deciso funzioni, regole e priorità. Nessuna delle AI coinvolte ha mostrato sintomi di
maltrattamento.
