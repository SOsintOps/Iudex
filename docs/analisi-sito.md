# Come funziona SentenzeWeb (analisi del 21 ottobre 2026)

Questa nota descrive ciò che Iudex ha bisogno di sapere del sito ufficiale
<https://www.italgiure.giustizia.it/sncass/> per interrogarlo nello stesso modo di un
browser. Tutto quello che segue è stato osservato in sola lettura: una ricerca manuale dal
browser, la lettura del JavaScript pubblico della pagina (`index.js`, 75 KB) e una sessione
di osservazione passiva con il Chrome DevTools Protocol (cattura in
`analisi/cattura-cdp-2026-10-21.json`, evidenze in `analisi/rea-2026-10-21.json`).

## Architettura

- Pagina statica (`index.html`, jQuery 1.4.2, jQuery UI 1.8.5, `index.js`) servita da IIS 7.5.
- Motore di ricerca **Apache Solr**, esposto da un modulo ISAPI:
  `https://www.italgiure.giustizia.it/sncass/isapi/hc.dll/sn.solr/sn-collection/select`.
- Nessuna autenticazione. Il server imposta un cookie di sessione (`cookiesession1`) alla
  prima pagina; il browser lo rimanda nelle richieste successive.
- Nessun `robots.txt` leggibile (risponde 401) e nessuna pagina di condizioni d'uso sul sito.
- Catena TLS incompleta: il server invia un certificato intermedio sbagliato (TI Trust DV al
  posto di OV). I browser lo risolvono da soli; i client Python no, per questo Iudex include
  l'intermedio corretto in `iudex/certs/ti_trust_ov_ca.pem`.

## Chiamate che il sito fa per una ricerca

Per la parola "licenziamento" digitata nel campo di ricerca e un clic su Cerca il browser
invia **19 richieste** al server:

| # | Richiesta | Scopo |
|---|-----------|-------|
| 1-13 | `POST …/select?app.suggester` | una per ogni lettera digitata (suggerimenti), senza debounce |
| 14 | `POST …/select?app.query` | la ricerca vera e propria |
| 15 | `GET /xway/application/nif/isapishare/hc.dll?app.query&q=…` | telemetria (risposta ignorata dal sito) |
| 16-19 | `POST …/select?app.facet` | quattro chiamate separate per i conteggi di archivio, tipo, sezione, anno |

Iudex ne fa **una**: la ricerca con i facet nella stessa richiesta (Solr lo consente e il
modulo ISAPI lo lascia passare; i conteggi sono identici a quelli del sito).

### Corpo della ricerca (`app.query`)

`POST`, `Content-Type: application/x-www-form-urlencoded; charset=UTF-8`:

```
start=0&rows=10
&q=(licenziamento) AND ((kind:"snciv" OR kind:"snpen"))
&wt=json&indent=off
&sort=pd desc,numdec desc
&fl=id,filename,szdec,kind,ssz,tipoprov,numcard,numdec,numdep,datdep,ecli,anno,datdec,presidente,relatore,requisitoria,testoocr,ocr
&hl=true&hl.snippets=4&hl.fragsize=100&hl.fl=ocr
&hl.q=nomatch AND (licenziamento)
&hl.maxAnalyzedChars=1000000&hl.simple.pre=<em class="hit">&hl.simple.post=</em>
```

Quando è selezionato un solo archivio il sito aggiunge il suffisso all'URL
(`?app.query=snciv`); Iudex fa lo stesso.

### Facet (`app.facet`)

```
facet=true&facet.method=enum&facet.mincount=1&facet.limit=257&facet.sort=false
&facet.field=kind      (snciv | snpen)
&facet.field=tipoprov  (Decreto | Ordinanza | Ordinanza Interlocutoria | Sentenza)
&facet.field=szdec     (1..7, F = feriale, L = lavoro, U = unite)
&facet.field=anno
&facet.field=ssz       (sottosezione: 5 = tributaria, L = lavoro)
```

### Testo integrale

Stesso endpoint con `rows=1&q=id:"<id>"&fl=&hl=true&hl.fl=*&hl.fragsize=0`. Il testo è nel
campo `ocr`; `ocrdis` contiene il dispositivo/massima; i campi `rnc-*` elencano i
riferimenti normativi indicizzati dal CED.

### PDF

`https://www.italgiure.giustizia.it/xway/application/nif/clean/hc.dll?verbo=attach&db=<kind>&id=<filename>`
dove `filename` è quello del documento con `.pdf` sostituito da `.clean.pdf`
(es. `./20261014/snpen@s60@a2026@n36099@tS.pdf`). Iudex non scarica i PDF: il collegamento
apre il documento sul sito ufficiale.

### Riferimenti normativi

Il campo "Riferimenti normativi" non è una query diretta: il sito chiede al server la forma
canonica (`GET …/isapi/hc.dll/sn/estremi?wat=<testo>`), che risponde con alternative
separate da ` OR ` e varianti fra graffe, per esempio per `art. 18 legge 300/1970`:

```
(18 300 {1970,70}) OR ({st,stat,statuto} {lav,lavoratori} 18) OR art. 18 legge 300/1970
```

Ogni variante diventa una frase con distanza 8 (`"(18 300 1970)"~8 OR …`). Iudex ripete lo
stesso procedimento e conserva in locale sia la lista delle sigle (`?wat=list`, ~130 KB) sia
le normalizzazioni già chieste, per 30 giorni.

## Sintassi del campo "Parole o Numero/Anno sentenza"

Trascritta in `iudex/query.py` dalle funzioni `freeTextQuery`, `checkEstremi` ed
`escapeSolrValue` del sito:

- `12345/2024`, `n. 123 del 2025`, `sent. 99/24` → `anno:"…" AND numdec:"…"` (numero riempito
  a 5 cifre, anno negli ultimi 7 anni, tipo facoltativo);
- più parole → frase con distanza 7 (`"giusta causa"~7`);
- `"…"`, `*`, `AND`, `OR` → passati a Solr così come sono;
- `NOT x` → ` -x`;
- una parola sola → caratteri speciali di Solr protetti con `\`.

## Campi del documento

`id`, `kind`, `numdec`, `anno`, `tipoprov`, `szdec`, `ssz`, `materia`, `presidente`,
`relatore`, `datdec` (udienza), `datdep`/`pd` (deposito/pubblicazione), `ocr`, `ocrdis`,
`sicId`, `filename`, `rnc-*`. L'ECLI mostrato dal sito è composto lato client:
`ECLI:IT:CASS:<anno>:<numdec>CIV|PEN`.

## Header che il browser invia

`User-Agent` di Chrome, `Accept: */*`, `Origin` e `Referer` del sito,
`X-Requested-With: XMLHttpRequest`, `Sec-Fetch-Dest: empty`, `Sec-Fetch-Mode: cors`,
`Sec-Fetch-Site: same-origin`, `sec-ch-ua*`, `Accept-Language`, cookie di sessione.
Iudex invia gli stessi header.

## Dimensioni dell'archivio (21 ottobre 2026)

422.168 provvedimenti: 184.904 civili e 237.264 penali, anni 2021-2026.

## Progetti esistenti consultati

- `matematicsolutions/it-eli-mcp`: server MCP in Python che interroga lo stesso Solr
  (documenta la verifica in `DISCOVERY.md` e include il certificato intermedio).
- `gattonim/BetterCallClaudeMCP_Italy`: server MCP in TypeScript, stesso endpoint con
  `rejectUnauthorized:false`; limita a una richiesta ogni 2 s.
- `capazme/mcp-legal-it`: raccolta di strumenti giuridici con ricerca in Cassazione.
- `Synthos-Logic/giurisprudenza-db`: dataset in Markdown dal sito della Corte, non da SentenzeWeb.

Nessuno dei quattro ha un'interfaccia grafica locale.
