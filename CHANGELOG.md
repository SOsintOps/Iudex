# Registro delle modifiche

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
