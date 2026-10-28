# Iudex: avanzamento dei lavori

Un passo per riga: `[ ]` da fare, `[~]` in corso, `[x]` fatto con l'hash del commit dopo il
trattino lungo. Il file si aggiorna nello stesso commit del lavoro. Piano in corso:
[plan/2026-10-28-memoria-permanente.md](plan/2026-10-28-memoria-permanente.md).

## Passi (0.8.0)

- [x] 1. Piano nel repository (`docs/plan/2026-10-28-memoria-permanente.md`) e questo file
  — `57082ee`
- [x] 2. Versionamento dello schema (`user_version`, migrazioni numerate, backup prima) e
  tabella `impostazioni` — `75145cc`
- [x] 3. Impostazioni: API `GET/PUT /api/impostazioni` e scheda nell'interfaccia
  (`iudex/preferenze.py`); l'editor delle impronte personalizzate arriva con il passo 4
- [ ] 3b. Solo finestra: API e pagine con token (cookie per la finestra, header per MCP),
  niente più modalità browser
- [ ] 4. Impronte: fissa, personalizzata, più personalizzate in rotazione
- [ ] 5. Memoria delle ricerche e provenienza (`esecuzioni`, `risultati`)
- [ ] 6. Consultazioni (testo e PDF) e badge "già vista" con tooltip
- [ ] 7. PDF salvati nella cartella scelta (installer e Impostazioni), aperti in finestra o
  con il programma del PC
- [ ] 8. Export del database delle ricerche: CSV/Excel, JSONL, ZIP con i PDF
- [ ] 8b. Installazione su Windows (Inno Setup) e Linux (AppImage) adattata e provata su VM
- [ ] 9. Documentazione e versione 0.8.0 (tag solo su conferma)

## Fasi successive

- [ ] B. Estrazione delle entità come in Praeco (dopo il passo 30 di Praeco)
- [ ] C. Dialogo Iudex↔Praeco per ridurre le richieste alla Corte

## Diario

- 2026-10-28: Iudex aggiornato a 0.7.0 sul PC (`b37d211`), Praeco locale a `16cd3ab`. Piano
  deciso con l'utente (13 decisioni, vedi il piano). Prossimo: passo 2.
- 2026-10-28: passo 2 (schema versione 2). `iudex/static/versioni.html` riporta solo le
  versioni rilasciate: si aggiorna al passo 9 insieme alla 0.8.0. `ruff format` (0.17.3)
  riformatta anche `client.py` e `mcp_server.py` già su main: lasciati com'erano, fuori dai
  passi. Prossimo: passo 3.
- 2026-10-28: passo 3. La voce del passo 2 nel CHANGELOG entra con questo commit.
  `tests/test_client.py::test_prima_la_pagina_poi_la_query_con_intervallo` è instabile su
  Windows (0,594 s misurati contro 0,6 attesi, risoluzione del timer): passa ripetuto, da
  sistemare a parte. Interfaccia non ancora provata dal vivo (niente Node per `--check`):
  prova nella finestra prevista dopo i passi dell'interfaccia. Prossimo: passo 3b.
