# Registro delle modifiche

## 0.4.0 — 2026-10-21

### Interfaccia
- Il menu **Informazioni** si chiama **Help** e contiene due pagine nuove: la **Guida
  all'utilizzo** (flusso di lavoro e funzione di ogni voce) e la **Licenza** (MIT, testi
  della Corte, componenti di terzi).
- **Logo** nella barra di navigazione, a sinistra del nome, con variante per il tema scuro.
- Il piè di pagina mostra solo la versione; il conteggio delle richieste e della cache
  resta nella scheda Stato.

### Repository
- Riordino secondo le convenzioni di GitHub: avviatori in `scripts/`, logo originale e
  script di generazione in `assets/logo/`, `CONTRIBUTING.md`, `SECURITY.md`,
  `.editorconfig`, `.gitattributes`, integrazione continua (ruff + pytest su Python 3.11 e
  3.13), Dependabot mensile e modelli per segnalazioni e pull request in `.github/`.
- `docs/analisi-sito.md`: sezione sulle chiamate e pagine del sito che Iudex non usa
  (permalink `detail.html`, telemetria `app.document`, requisitoria, precedenti collegati,
  liste dei filtri con `facet.prefix`, suggerimenti con `kind:"key"`, provvedimenti in
  fase di oscuramento).

### Ricerca
- Costruttore delle query riscritto **dalla specifica della sintassi** (`docs/analisi-sito.md`),
  senza codice derivato dal JavaScript del sito (che è GPL-3). Stesse clausole del sito e tre
  miglioramenti: `NOT parola` e `-parola` **escludono davvero** (sul sito finivano dentro una
  frase); i caratteri speciali sono protetti anche con gli operatori (`a:b OR c`); gli
  estremi accettano `Cass. civ.` davanti, il tipo in fondo (`n. 99 del 2025 sent.`) e il
  trattino (`123-2024`).

## 0.3.1 — 2026-10-21

### Grafica
- **Logo** di Iudex (bilancia con corona d'alloro e circuiti) nel README, con sfondo
  trasparente e variante per il tema scuro di GitHub.
- **Favicon** ricavata dal logo: tratti bianchi su quadrato blu, leggibile anche a 16 px,
  al posto della "I" provvisoria.
- La voce Informazioni della barra ha la stessa grandezza delle altre voci (era rimasta
  più piccola).
- Schermate del README rifatte con la barra attuale (icone sole e luna).
- Tolto l'avviso sul Garante dalla pagina iniziale; la risposta sui dati personali resta
  nelle domande frequenti.

## 0.3.0 — 2026-10-21

### Grafica
- Interfaccia allineata a **Exploratores**: stesse variabili di colore (`#0066ff`, `#333`,
  `#888`, `#f9f9f9`), font Inter ospitato in locale, barra di navigazione fissa con
  sottomenu, riquadro di ricerca, pulsanti bianchi con passaggio in blu, tabelle con righe
  alternate, piè di pagina fisso. Sparisce il carattere Palatino e la palette porpora.
- **Tema scuro** con scelta **automatica in base all'orario**: per impostazione predefinita
  scuro dalle 19 alle 7 (ora del computer), orari modificabili nella scheda Stato; il
  tema si sceglie con le icone sole e luna nella barra; un secondo clic su quella attiva
  torna all'automatico.
- Le voci Cronologia, Ricerche salvate, Preferiti e Stato stanno nella barra di navigazione;
  le pagine informative sono nel sottomenu Informazioni. Indirizzi `#cronologia`,
  `#salvate`, `#preferiti`, `#stato` per aprire direttamente una scheda.

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
