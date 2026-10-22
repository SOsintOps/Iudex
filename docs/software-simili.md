# Software simili

Progetti che accedono alla stessa banca dati o a dati vicini, osservati il 21 ottobre 2026
leggendo codice e documentazione. Nessuno offre un'interfaccia grafica locale. La stessa
pagina è nell'app (`/software-simili.html`).

## SentenzeWeb e ItalgiureWeb (Corte di Cassazione)

SentenzeWeb (<https://www.italgiure.giustizia.it/sncass/>) è la fonte di Iudex: pagina jQuery
su Apache Solr, ricerca gratuita sulle sentenze civili e penali degli ultimi anni. La sua
interfaccia manda una richiesta per ogni lettera digitata e quattro per i conteggi dei
filtri; non ha cronologia, export, permalink né filtro per materia. ItalgiureWeb è il
sistema completo del CED, riservato agli operatori; dal 1° ottobre 2026 solo nel nuovo
front end. Iudex non lo usa.

## it-eli-mcp (matematicsolutions, Python, MIT)

Server MCP per la legislazione con un modulo Cassazione. Stesso Solr, richieste GET, query
costruita a mano (`ocr:"termine" AND kind:snciv AND anno:2024`), User-Agent proprio. Ha
individuato il difetto della catena TLS e include il certificato intermedio corretto
(ripreso da Iudex). Niente facet, ordinamento, riferimenti normativi, limiti o cache.
`DISCOVERY.md` documenta la verifica degli endpoint.

## BetterCallClaudeMCP_Italy (gattonim, TypeScript, AGPL-3)

Suite di server MCP. Il modulo Cassazione fa POST come il sito ma chiede un cookie di
ItalgiureWeb (inutile per SentenzeWeb) e senza cookie restituisce link di ripiego. Verifica
TLS disattivata. Una richiesta ogni due secondi, una connessione: ritmo adottato da Iudex.

## mcp-legal-it (capazme, Python, Apache-2.0)

Server MCP con oltre duecento strumenti per il diritto italiano. Per la Cassazione usa lo
stesso Solr con il parser edismax, pesi sui campi, `fq` separati e facet; rilassa o
restringe da solo la query; stima gli orientamenti contando frasi segnale. Risultati non
coincidenti con il sito. Verifica TLS disattivata, nessun intervallo fra richieste, fonti
in parallelo. Iudex ne riprende l'idea dei **segnali di orientamento** (stesse frasi, una
sola OR per gruppo, «discostarsi» escluso) come `facet.query` nella ricerca, senza
cambiarne i risultati.

## giurisprudenza-db (Synthos-Logic, CC BY 4.0 / MIT)

Dataset Markdown dei provvedimenti segnalati dal Massimario e delle rassegne mensili,
raccolti dal sito istituzionale della Corte. Non interroga SentenzeWeb.

## Confronto

| Progetto | Tipo | Accesso | Stessi risultati del sito | Limiti | TLS |
|---|---|---|---|---|---|
| Iudex | interfaccia locale + MCP | Solr, 1 richiesta per ricerca | sì | 1 alla volta, 2 s, cache | verificato, intermedio incluso |
| it-eli-mcp | MCP | Solr, GET | no | nessuno | verificato, intermedio incluso |
| BetterCallClaudeMCP_Italy | MCP | Solr, POST, cookie | no | 1 alla volta, 2 s | disattivata |
| mcp-legal-it | MCP | Solr, edismax | no | nessuno | disattivata |
| giurisprudenza-db | dataset | sito istituzionale | — | periodico | — |
