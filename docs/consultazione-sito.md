# Come viene consultato il sito

Il portale ufficiale **SentenzeWeb** della Corte Suprema di Cassazione, per una singola
interrogazione giurisprudenziale, invia al server circa venti richieste HTTP: una per ogni
carattere digitato (suggerimenti automatici), la query di ricerca vera e propria, quattro
chiamate separate per i conteggi dei filtri (*facet*) e una chiamata di telemetria.
Iudex ne invia **una sola**, poiché richiede i conteggi statistici dei filtri nella medesima
interrogazione della ricerca principale. Inoltre rispetta rigorosi criteri di parsimonia:

| Regola | Valore |
|--------|--------|
| Richieste in parallelo | 1 |
| Intervallo minimo fra due richieste | 2 secondi (`IUDEX_INTERVALLO`) |
| Nuovi tentativi | 1 solo, su errore di rete o 5xx; nessuno su 403/429 |
| Suggerimenti durante la digitazione | nessuna richiesta al server: l'elenco delle sigle normative del CED è scaricato una sola volta e conservato per 30 giorni |
| Risposte di ricerca | in cache locale per un'ora: ripetere o ricaricare un'interrogazione non contatta il server |
| Provvedimenti aperti | conservati in locale: riaprire il testo integrale di una pronuncia non contatta il server |
| Controllo novità delle ricerche salvate | esclusivamente su richiesta dell'utente (clic), una chiamata per ricerca |
| Esportazioni | pagina corrente: nessuna richiesta; primi 50 provvedimenti: al più una; primi 100: al più due |
| Copie ufficiali in PDF | una richiesta alla prima apertura del provvedimento (con la medesima cadenza delle altre chiamate), poi lettura dalla copia locale; mai acquisizione massiva |
| Telemetria del sito (`xway`) | non replicata (`IUDEX_TELEMETRIA=1` per abilitarla) |
| Identità dichiarata | User-Agent e intestazioni HTTP di un browser standard: per impostazione predefinita Chrome, Edge o Firefox su Windows scelto in base al giorno; nelle Impostazioni è possibile selezionare un'impronta predefinita fissa, una personalizzata (sottoposta a verifica di coerenza) o più impronte personalizzate a rotazione; la variabile `IUDEX_IMPRONTA` le fissa tutte. Variano esclusivamente gli header HTTP: l'impronta TLS rimane quella dell'interprete Python |
| Accesso locale | pagine, API e documenti PDF rispondono esclusivamente alla finestra nativa di Iudex (tramite token custodito nella cartella dei dati); un browser esterno o un sito di terzi non possono accedervi |

Non è prevista alcuna funzione di estrazione massiva (*scraping*) o di scansione sistematica
dell'archivio, né dovrà essere introdotta: la banca dati appartiene alla Corte Suprema di
Cassazione, che la rende pubblica per finalità di consultazione giurisprudenziale.

## Vedi anche

- [Pagina principale (README)](../README.md)
- [Analisi tecnica di SentenzeWeb](analisi-sito.md)
- [Guida all'utilizzo](guida.md)
- [Domande frequenti (FAQ)](faq.md)
- [Software simili](software-simili.md)
