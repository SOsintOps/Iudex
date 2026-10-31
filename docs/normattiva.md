# Normattiva

Dalla versione 0.9 Iudex consente di consultare direttamente il testo delle disposizioni
normative richiamate nelle pronunce della Corte, attingendo a **Normattiva**, il portale
istituzionale della normativa vigente edita dalla Repubblica Italiana. La fonte utilizzata è
l'**API Open Data** di Normattiva (`api.normattiva.it`), non il portale web
`www.normattiva.it`, che rimane accessibile tramite collegamento esterno nel browser.

- **Bottone Testo**: accanto a ciascun riferimento normativo indicizzato nella pronuncia,
  consente di aprire in calce il testo della disposizione: intitolazione ed estremi dell'atto
  normativo, numero e rubrica dell'articolo, testo dell'articolato suddiviso in commi, note
  redazionali e di modifica richiudibili, estremi di vigenza e collegamento **Apri su
  Normattiva**. Il pulsante viene mostrato esclusivamente quando il riferimento normativo
  presenta estremi univoci: per la Costituzione e i codici fondamentali (`c.c.`, `c.p.`,
  `c.p.c.`, `c.p.p.`) è sufficiente il numero dell'articolo; per le leggi ordinarie e gli atti
  aventi forza di legge (decreti-legge, decreti legislativi) e regolamentari occorrono anche
  numero e anno di promulgazione o emanazione. Le fonti regionali (leggi regionali) e la CEDU
  non presentano il pulsante.
- **Strumento MCP `leggi_norma`**: mette a disposizione il medesimo testo normativo per un
  assistente o modello linguistico locale, a partire da una citazione testuale standard
  (`"art. 2043 c.c."`) oppure dai singoli parametri strutturati, con indicazione facoltativa
  della data di vigenza per la consultazione in multivigenza (vedi [Installazione e server MCP](installazione.md#con-un-assistente-o-un-llm-locale-mcp)).
- **API locale** `GET /api/norma?tipo=&numero=&anno=&articolo=&vigenza=`, impiegata sia
  dall'interfaccia grafica sia dal server MCP.
- **EUR-Lex**: per le fonti del diritto dell'Unione europea — Trattato sull'Unione europea
  (TUE), Trattato sul funzionamento dell'Unione europea (TFUE), regolamenti e direttive UE —
  al posto del pulsante di lettura viene esposto un collegamento diretto che apre l'atto in
  lingua italiana su **EUR-Lex** nel browser (tramite identificatore CELEX); Iudex non effettua
  alcuna richiesta di rete verso EUR-Lex.

## Fonte, valore legale e licenza

I testi normativi sono messi a disposizione dall'Istituto Poligrafico e Zecca dello Stato
(IPZS) e pubblicati su Normattiva con licenza **Creative Commons Attribuzione 4.0
Internazionale (CC BY 4.0)**. Iudex li espone corredati dell'attribuzione
«Fonte: Normattiva (IPZS), CC BY 4.0» e del collegamento diretto all'atto; chiunque riutilizzi
i testi normativi estratti tramite Iudex è tenuto a conservare la medesima indicazione di
provenienza. Si ricorda che i testi presenti nella banca dati Normattiva hanno carattere
meramente informativo e conoscitivo: ai sensi di legge, l'unico testo ufficiale che fa fede è
quello pubblicato nella **Gazzetta Ufficiale della Repubblica Italiana**.

| Regola | Valore |
|--------|--------|
| Richieste | una per ciascun clic su **Testo** (o per invocazione di `leggi_norma`), mai in automatico all'apertura della sentenza, senza precaricamento (*prefetching*); alla prima consultazione di un atto normativo vengono effettuate due chiamate (risoluzione dell'atto e lettura dell'articolo), per le successive una sola |
| Intervallo minimo fra due richieste | 2 secondi (`IUDEX_INTERVALLO_NORMATTIVA`), gestito con un limitatore di frequenza autonomo e separato rispetto a quello verso la Corte di Cassazione |
| Nuovi tentativi | 1 solo qualora la fonte non risponda; sospensione temporanea qualora Normattiva richieda un rallentamento (HTTP 409/429); in caso di errore il pannello non ripete automaticamente il tentativo |
| Cache locale | il testo vigente alla data corrente è conservato in locale per 30 giorni; il testo richiesto con una specifica data di vigenza storica è conservato stabilmente; la riapertura del medesimo articolo non genera traffico di rete |
| Fonte non raggiungibile | l'avviso segnala espressamente l'indisponibilità temporanea di Normattiva, senza mai indurre a ritenere inesistente o abrogata la disposizione cercata |

## Limiti

Iudex acquisisce e mostra un singolo articolo per volta: gli allegati tecnici e le tabelle
annesse agli atti normativi non vengono riprodotti nel pannello (per la loro consultazione è
disponibile il collegamento **Apri su Normattiva**). La banca dati di Normattiva non comprende
la legislazione regionale, gli atti dell'Unione europea e la Convenzione europea dei diritti
dell'uomo (CEDU): per tali fonti l'endpoint `/api/norma` restituisce lo stato HTTP `422`. Il
contenuto testuale viene inserito nella pagina esclusivamente come testo puro, mai come codice
HTML eseguibile.

**Connessione tramite VPN.** Come il server della Corte, anche i server di Normattiva non
rispondono agli indirizzi di uscita delle VPN commerciali: chi utilizza una VPN deve includere
nello *split tunneling* per indirizzo IP anche `147.78.212.26` (`api.normattiva.it`) e
`147.78.212.12` (`www.normattiva.it`), oltre a `81.126.56.168` (`www.italgiure.giustizia.it`).
Vedi [Installazione — Da dietro una VPN](installazione.md#da-dietro-una-vpn).

## Vedi anche

- [Pagina principale (README)](../README.md)
- [Installazione e configurazione MCP](installazione.md)
- [Guida all'utilizzo](guida.md)
- [Domande frequenti (FAQ)](faq.md)
