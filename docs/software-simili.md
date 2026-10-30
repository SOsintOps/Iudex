# Software simili

Progetti che accedono alla stessa banca dati o a dati vicini, osservati il 21 ottobre 2026
leggendo codice e documentazione; mcp-legal-it è stato anche provato in uso il 30 ottobre
2026. Nessuno offre un'interfaccia grafica locale. La stessa pagina è nell'app
(`/software-simili.html`).

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

**Prova del 30 ottobre 2026 (versione 2.17.1).** 228 strumenti. La normativa arriva dal sito
di Normattiva letto come pagina web (Iudex usa l'API Open Data): il testo del corpo degli
atti è completo, ma allegati e tabelle si perdono senza avviso. Alla Cassazione nessuna pausa
fra le richieste (Iudex: 2 s); la ricerca viene ridotta da sola a un risultato; le citazioni
scritte con le virgole ("Cass. civ., Sez. Un., 11 novembre 2008, n. 26972") non sono
riconosciute. Esito: utile per i calcoli e, con riserve, per la normativa; non adatto come
fonte per la Cassazione, per il ritmo delle richieste. La versione 3.0, in sviluppo, corregge
installazione, verifica TLS e allowlist.

**Differenze con Iudex.** Iudex fa meno cose e le fa una alla volta: una richiesta per
ricerca, 2 secondi fra due richieste alla Corte e altrettanti, con un limite proprio, fra due
richieste a Normattiva. Di Normattiva legge solo l'API Open Data, solo su richiesta
dell'utente e un articolo per volta, e dice che allegati e tabelle non sono mostrati. Le
citazioni con le virgole e la data sono riconosciute da `verifica_citazioni`, che prima
guarda le sentenze già consultate e non tratta mai come inesistente una sentenza quando la
Corte non risponde.

## giurisprudenza-db (Synthos-Logic, CC BY 4.0 / MIT)

Dataset Markdown dei provvedimenti segnalati dal Massimario e delle rassegne mensili,
raccolti dal sito istituzionale della Corte. Non interroga SentenzeWeb.

## Confronto

| Progetto | Tipo | Accesso | Stessi risultati del sito | Limiti | TLS |
|---|---|---|---|---|---|
| Iudex | interfaccia locale + MCP | Solr, 1 richiesta per ricerca | sì | 1 alla volta, 2 s, cache | verificato, intermedio incluso |
| it-eli-mcp | MCP | Solr, GET | no | nessuno | verificato, intermedio incluso |
| BetterCallClaudeMCP_Italy | MCP | Solr, POST, cookie | no | 1 alla volta, 2 s | disattivata |
| mcp-legal-it (2.17.1) | MCP | Solr, edismax; Normattiva dal sito | no | nessuno | disattivata (corretta nella 3.0 in sviluppo) |
| giurisprudenza-db | dataset | sito istituzionale | — | periodico | — |
