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

## Chiamate e pagine del sito che Iudex non usa

Rilettura completa di `index.js` (versione `?v1.2`, 75 KB, esportato con REA il 21 ottobre
2026) alla ricerca di ogni `$.ajax` e di ogni URL. Oltre a quanto sopra, il sito conosce:

| Chiamata o pagina | Che cosa fa | Iudex |
|-------------------|-------------|-------|
| `GET /sncass/detail.html?numdec:<n>+AND+anno:<a>+AND+kind:<snciv\|snpen>` | pagina che mostra un solo provvedimento, usata come **permalink** (verificata: `detail.html?numdec:26495+AND+anno:2026+AND+kind:snciv` apre la sentenza). Variante `detail.html?nmas:<Rv.>+AND+kind:…` per numero di massima | non usato: il collegamento a un provvedimento è sempre il PDF; da valutare un collegamento "pagina sul sito" |
| `GET /xway/application/nif/isapishare/hc.dll?app.document=<url del PDF>` | **telemetria** all'apertura di un PDF ("document tracking"), risposta ignorata | non replicata (come la telemetria `app.query`) |
| `POST …/select?app.suggester` con `q={!boost b=score}kind:"key" AND key:<testo>*`, `rows=16`, `fl=key` | i suggerimenti mentre si digita: le sigle sono **documenti con `kind:"key"` nella stessa collezione** Solr | non usato: Iudex non fa richieste mentre si digita |
| `POST …/select?app.facet` con `facet.prefix`, `facet.offset`, `facet.limit`, `facet.sort`, `fl=name` | la lista completa di un filtro, a pagine e filtrabile per prefisso (il "+" accanto ai filtri) | non usato: Iudex chiede fino a 257 valori per filtro nella ricerca stessa |
| campo `requisitoria` + secondo `filename` | per i provvedimenti penali con requisitoria, il PDF della **requisitoria del Procuratore generale** (`verbo=attach&db=snpen&id=<secondo filename .clean.pdf>`) | campo richiesto ma non mostrato; da valutare |
| campi `ved-numdec`/`ved-an`/`ved-nmas`, `con-*`, `dif-*`, `sic-ved-*` | **precedenti collegati** dal CED (vedi, conformi, difformi), resi come collegamenti a `detail.html` | non richiesti né mostrati; da valutare |
| campi `ocrfull`, `nmas`, `origin`, `numdep` | testo completo nella pagina di dettaglio; numero di massima; archivio di origine; per `kind:"penale"` (archivio storico) il numero è `numdep` | `numdep` è richiesto; gli altri no |
| testo "in fase di oscuramento" / "in fase di valutazione oscuramento" nel campo `ocr` | il sito **non apre il PDF** dei provvedimenti in corso di oscuramento | Iudex nasconde il collegamento al PDF quando il testo indica l'oscuramento |
| `GET /sncass/accessibilita.html` | note di accessibilità del CED | pagina statica, nessuna API |

Ordinamenti offerti dal sito: `pd desc,numdec desc` (pubblicazione), `datdec desc,pd desc,numdec desc`
(udienza), nessun `sort` (rilevanza); il predefinito interno di `index.js` è
`pd desc,datdec desc,anno desc,numdec desc`. Iudex usa i tre del menu.

Non è stata fatta nessuna prova di endpoint diversi da quelli che il sito stesso chiama
(nessun `/admin`, `/terms`, `/suggest` di Solr): l'analisi è in sola lettura del codice
pubblico e di una pagina di dettaglio.

Nota: l'intestazione di `index.js` dichiara la licenza **GPL versione 3**
(`http://www.maas.ccr.it/z.licence`, "This file is part of Z"). Iudex non contiene né
traduce quel codice: `iudex/query.py` è scritto dalla specifica della sezione "Sintassi del
campo" qui sotto e riproduce solo il formato delle richieste, che è un'interfaccia.

## Sintassi del campo "Parole o Numero/Anno sentenza"

Questa sezione è la **specifica** da cui è scritto `iudex/query.py`: descrive che cosa il
sito fa con il testo digitato (comportamento osservato provando le ricerche e leggendo le
richieste inviate), non come lo fa. Iudex riproduce le stesse clausole e, nei tre casi
segnati, fa di meglio.

### Estremi di un provvedimento

Se il testo è fatto di un numero (al più 5 cifre) e di un anno (2 o 4 cifre) separati da
`/`, da `del` o da un trattino, con davanti facoltativamente `n.`/`num.` e un tipo
(`sent…`, `ord…`, `dec…`), la ricerca diventa:

```
anno:"2024" AND numdec:"12345"[ AND tipoprov:"Sentenza"]
```

con il numero riempito di zeri a 5 cifre (`numdec:"00099"`), l'anno a due cifre completato a
`20xx`, `ord` che vale `tipoprov:"Ordinanza" OR tipoprov:"Ordinanza Interlocutoria"` e `dec`
`tipoprov:"Decreto"`. Il sito accetta solo anni negli ultimi sette; Iudex accetta dal 2000
all'anno corrente (l'archivio copre circa cinque anni, quindi i risultati coincidono) e in
più ignora un prefisso `Cass.`/`Cass. civ.` e accetta il tipo anche in fondo
(`n. 99 del 2025 sent.`). Per gli estremi non si chiede l'evidenziazione (`hl.q` resta
`nomatch`).

### Parole

| Testo digitato | Clausola inviata | Note |
|----------------|------------------|------|
| `licenziamento` | `licenziamento` | una parola: caratteri speciali di Solr protetti con `\` |
| `giusta causa` | `"giusta causa"~7` | più parole: frase con distanza massima 7 fra i termini |
| `"giusta causa"` | `"giusta causa"` | virgolette: frase esatta, passata com'è |
| `licenz*` | `licenz*` | troncamento, passato com'è |
| `a AND b`, `a OR b` | `a AND b`, `a OR b` | operatori in maiuscolo, passati com'è |
| `demansionamento NOT mobbing` | sito: `"demansionamento -mobbing"~7` · Iudex: `demansionamento -mobbing` | il sito chiude tutto in una frase e Solr ignora il `-`: *non* esclude. Iudex esclude davvero |
| `NOT mobbing` | sito: ` \-mobbing` · Iudex: `*:* -mobbing` | il sito protegge il meno; Iudex antepone `*:*` perché una query solo negativa abbia una base |
| `a:b OR c` | sito: `a:b OR c` · Iudex: `a\:b OR c` | con gli operatori il sito non protegge i caratteri speciali e la query può fallire |

Regola generale di Iudex: il testo è scomposto in token (frasi fra virgolette, parentesi,
`AND`/`OR`/`NOT`, parole con eventuale `-` davanti o `*` dentro). Senza frasi, operatori,
parentesi, esclusioni o troncamenti vale la riga "una parola" o "più parole"; altrimenti
ogni token è reso nella sintassi di Solr (`NOT x` e `-x` diventano `-x`, le parole sono
protette tranne il `*`) e i token sono uniti da spazi. L'evidenziazione (`hl.q`) usa i soli
termini positivi.

### Riferimento normativo

Vedi sopra: forma canonica chiesta al server, ogni variante come frase con distanza 8.

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
