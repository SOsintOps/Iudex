# Registro delle modifiche

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
