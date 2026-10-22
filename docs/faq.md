# Domande frequenti

La stessa pagina è nell'app, nel menu **Help → Domande frequenti**.

## I dati

**Che cosa contiene SentenzeWeb?** Le sentenze, le ordinanze e i decreti civili e penali
della Corte di Cassazione pubblicati negli ultimi anni: al 21 ottobre 2026 circa 422.000
provvedimenti dal 2021. È una finestra scorrevole di circa cinque anni. Non contiene le
massime ufficiali né i provvedimenti anteriori: quelli sono in ItalgiureWeb, riservato agli
operatori.

**Iudex copia la banca dati?** No. Ogni ricerca interroga il server della Corte nel momento
in cui la fai. In locale restano le risposte recenti (un'ora), i testi che hai aperto e il
diario delle tue consultazioni.

**Di chi sono i testi?** Della Corte Suprema di Cassazione, che li pubblica per la
consultazione. Il PDF si apre sempre dal sito ufficiale.

**Perché non cercare per nome di persona?** Le sentenze contengono dati personali e talvolta
categorie particolari di dati; nel 2024 il Garante per la protezione dei dati personali ha
ammonito la Corte per la presenza di dati relativi alla salute e a vittime di reati nei testi
pubblicati. Iudex non costruisce indici nominativi.

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

**Quante?** Una per ricerca, una per il testo di una sentenza mai aperta, una per un
riferimento normativo nuovo, una al mese per la lista delle sigle. Il sito ne fa circa venti
per ricerca.

**Limiti:** una richiesta alla volta, almeno due secondi di distanza, un solo nuovo tentativo
su errore di rete, nessuna insistenza su 403/429. Nessuna funzione di scaricamento massivo.

**Novità delle ricerche salvate:** solo su richiesta, una chiamata per ricerca. Il primo
controllo registra il punto di partenza.

**Esportazioni:** pagina corrente = nessuna richiesta; primi 50 = al più una; primi 100 = al
più due.

**Identità:** gli stessi header del browser Chrome che usa il sito ufficiale.

## I dati locali

Tutto in `dati/iudex.sqlite` (percorso nella scheda Stato); preferenze di aspetto nel
browser. Svuotamento dalla scheda Stato; per azzerare, chiudi Iudex ed elimina il file.

**Iudex salva le mie ricerche?** Sì, nel Diario: ogni ricerca (parole, filtri, risultati) e
ogni sentenza aperta, con la ricerca di provenienza. Delle sentenze aperte conserva la
risposta intera del server, testo compreso; dei risultati non aperti solo il conteggio. Il
diario non si svuota con i pulsanti della cache; si esporta in JSONL, CSV, zip o
FollowTheMoney (`.ftm`), e *Copia di sicurezza* salva il database intero.

**Colonne:** trascina le linee fra i pannelli o fra le intestazioni delle tabelle; doppio
clic ripristina; da tastiera, focus sulla maniglia e frecce.

## Problemi

- **HTTP 403/429:** il server limita le richieste. Iudex non ne manda altre per il tempo
  indicato da `Retry-After` (un minuto se manca) e risponde subito «riprova fra N s»; la
  scheda Stato mostra quanto manca; dopo un 403 riapre la sessione. Alza `IUDEX_INTERVALLO`
  se succede spesso.
- **Errore di certificato:** il server invia una catena incompleta; Iudex include
  l'intermedio in `iudex/certs/`. Se il messaggio compare, reinstalla o apri una segnalazione.
- **"Richiesta non proveniente dall'interfaccia di Iudex":** le API accettano solo le
  chiamate della pagina (header `X-Iudex: 1`).
- **La ricerca non risponde:** il server locale non è avviato (`scripts\avvia.cmd` o
  `python -m iudex --apri`). Porta occupata da un altro programma: cambia `IUDEX_PORTA`; se
  è già aperto un altro Iudex, l'avvio apre quello.
- **"Errore interno di Iudex":** errore imprevisto (per esempio disco pieno); la traccia è
  nella finestra del server.

## Oltre il browser

- **Finestra nativa:** `scripts\avvia-finestra.cmd` (extra `desktop`, pywebview su WebView2).
- **Assistenti e LLM locali:** `python -m iudex.mcp_server` (extra `mcp`) espone tre
  strumenti che passano dall'API locale; serve un client MCP e Iudex in esecuzione.
