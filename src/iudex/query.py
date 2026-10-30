"""Costruzione delle query Solr per SentenzeWeb.

Implementazione indipendente della sintassi di ricerca del sito, descritta in
``docs/analisi-sito.md`` (sezione "Sintassi del campo"). Il modulo non contiene né traduce
codice del sito: riproduce il formato delle richieste e il comportamento osservabile, così
che una ricerca fatta con Iudex restituisca gli stessi risultati della ricerca fatta sul
sito, e corregge i casi in cui quella sintassi tradisce l'intenzione di chi scrive (per
esempio ``NOT`` dentro una frase).
"""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlencode

from .config import URL_PDF

QUERY_INIZIALE = '(kind:"snciv" OR kind:"snpen")'

# Campi richiesti per la pagina dei risultati (gli stessi che chiede il sito).
CAMPI_RISULTATO = (
    "id,filename,szdec,kind,ssz,tipoprov,numcard,numdec,numdep,datdep,ecli,anno,datdec,"
    "presidente,relatore,requisitoria,testoocr,ocr"
)

ORDINAMENTI = {
    "pubblicazione": "pd desc,numdec desc",
    "udienza": "datdec desc,pd desc,numdec desc",
    "rilevanza": "",
}

CAMPI_FACET = ("kind", "tipoprov", "szdec", "anno", "ssz", "materia")

# Frasi con cui un provvedimento dichiara nel testo un contrasto o la conformità a un
# orientamento. Sono un segnale testuale, non una classificazione della giurisprudenza.
# "discostarsi" è escluso di proposito: compare soprattutto in "non vi sono ragioni per
# discostarsi", che dichiara conformità (misura riportata da mcp-legal-it, Apache-2.0).
SEGNALI = {
    "contrasto": ("contrasto giurisprudenziale", "difforme orientamento"),
    "conformita": ("orientamento consolidato", "in senso conforme"),
}
ETICHETTE_SEGNALI = {
    "contrasto": "segnalano un contrasto",
    "conformita": "richiamano un orientamento consolidato",
}

# Tipi di atto nei campi "rnc-sp" dei provvedimenti (codici del CED, parziali).
TIPI_ATTO = {
    "LS": "legge",
    "DLG": "d.lgs.",
    "DL": "d.l.",
    "DPR": "d.P.R.",
    "DM": "d.m.",
    "DPCM": "d.P.C.M.",
    "RD": "r.d.",
    "RDL": "r.d.l.",
    "LR": "legge reg.",
    "CC": "c.c.",
    "CPC": "c.p.c.",
    "CP": "c.p.",
    "CPP": "c.p.p.",
    "COST": "Cost.",
    "CEDU": "CEDU",
    "TUE": "TUE",
    "TFUE": "TFUE",
    "REG": "reg. UE",
    "DIR": "dir. UE",
}
CODICI_SENZA_ESTREMI = {"CC", "CPC", "CP", "CPP", "COST", "CEDU", "TUE", "TFUE"}
# Il CED indica i codici con "rnc-sp" = "COD" e il codice in "rnc-gen" (per le leggi "rnc-gen"
# vale "LS"). "CR" per la Costituzione è dedotto dagli articoli citati, non documentato.
CODICI_CED = {"CC": "CC", "CP": "CP", "PC": "CPC", "PV": "CPP", "CR": "COST"}
# Suffissi degli articoli nell'ordine del CED ("0380 02" = 380-bis) e di Normattiva
# (sottoArticolo 2 = bis): indice + 1 = codice numerico, "" = articolo semplice.
SUFFISSI = (
    "",
    "bis",
    "ter",
    "quater",
    "quinquies",
    "sexies",
    "septies",
    "octies",
    "novies",
    "decies",
    "undecies",
    "duodecies",
    "terdecies",
    "quaterdecies",
    "quinquiesdecies",
    "sexiesdecies",
    "septiesdecies",
    "octiesdecies",
)

ARCHIVI = {"snciv": "Civile", "snpen": "Penale"}
SEZIONI = {
    "1": "Prima",
    "2": "Seconda",
    "3": "Terza",
    "4": "Quarta",
    "5": "Quinta",
    "6": "Sesta",
    "7": "Settima",
    "F": "Feriale",
    "L": "Lavoro",
    "U": "Unite",
}
SOTTOSEZIONI = {"0": "nessuna", "5": "Tributaria", "L": "Lavoro"}

# Caratteri con significato speciale nella sintassi di Solr (documentazione Solr,
# "Escaping Special Characters"). ``*`` resta fuori dal secondo insieme perché nel modo
# avanzato è il troncamento voluto dall'utente.
_SPECIALI_SOLR = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')
_SPECIALI_SENZA_JOLLY = re.compile(r'([+\-&|!(){}\[\]^"~?:\\/])')


def escape_solr(valore: str) -> str:
    """Protegge con una barra rovesciata ogni carattere speciale di Solr."""
    return _SPECIALI_SOLR.sub(r"\\\1", valore)


# ---------- estremi di un provvedimento ----------

_CLAUSOLE_TIPO = {
    "sent": 'tipoprov:"Sentenza"',
    "ord": '(tipoprov:"Ordinanza" OR tipoprov:"Ordinanza Interlocutoria")',
    "dec": 'tipoprov:"Decreto"',
}

# Grammatica degli estremi: [Cass. [civ.|pen.]] [tipo] [n.] NUMERO (/ | - | del) ANNO [tipo]
_ESTREMI = re.compile(
    r"""^\s*
    (?:cass(?:azione)?\.?\s*(?:civ(?:ile)?\.?|pen(?:ale)?\.?)?\s*)?
    (?:(?P<tipo1>sent|ord|dec)[a-z]*\.?\s*)?
    (?:n(?:um(?:ero)?)?\.?\s*)?
    (?P<numero>\d{1,5})\s*
    (?:/|-|del)\s*
    (?P<anno>\d{4}|\d{2})
    (?:\s*(?P<tipo2>sent|ord|dec)[a-z]*\.?)?
    \s*$""",
    re.IGNORECASE | re.VERBOSE,
)


def _anno_valido(cifre: str, anno_corrente: int) -> int | None:
    anno = int(cifre) if len(cifre) == 4 else 2000 + int(cifre)
    return anno if 2000 <= anno <= anno_corrente else None


def controlla_estremi(testo: str, anno_corrente: int | None = None) -> str | None:
    """Clausola Solr per gli estremi di un provvedimento, oppure ``None``.

    Riconosce ``12345/2024``, ``123 / 24``, ``n. 99 del 2025``, ``sent. 99/24``,
    ``ord. 5-2023``, ``Cass. civ. n. 99 del 2025 sent.``: numero di al più 5 cifre, anno a
    due o quattro cifre dal 2000 all'anno corrente, tipo di provvedimento facoltativo prima o
    dopo. Il numero è riempito di zeri a 5 cifre, come indicizzato dal CED.
    """
    m = _ESTREMI.match(testo)
    if not m:
        return None
    anno = _anno_valido(m.group("anno"), anno_corrente or date.today().year)
    if anno is None:
        return None
    clausola = f'anno:"{anno}" AND numdec:"{m.group("numero").zfill(5)}"'
    tipo = (m.group("tipo1") or m.group("tipo2") or "").lower()
    if tipo:
        clausola += " AND " + _CLAUSOLE_TIPO[tipo]
    return clausola


# ---------- parole, frasi, operatori ----------

_TOKEN = re.compile(
    r"""
    "(?P<frase>[^"]*)"?                 # frase fra virgolette (anche non chiusa)
  | (?P<par>[()])                       # parentesi di raggruppamento
  | (?P<op>AND|OR|NOT)(?=\s|$|[()])     # operatori, solo in maiuscolo
  | -(?P<neg>[^\s()"]+)                 # esclusione con il meno
  | (?P<parola>[^\s()"]+)               # parola, eventualmente con * di troncamento
    """,
    re.VERBOSE,
)


def _token(testo: str) -> list[tuple[str, str]]:
    """Scompone il testo in token ``(tipo, valore)``; ``NOT`` nega il termine che segue."""
    risultato: list[tuple[str, str]] = []
    nega = False
    for m in _TOKEN.finditer(testo):
        tipo = m.lastgroup or "parola"
        valore = m.group(tipo) or ""
        if tipo == "op" and valore == "NOT":
            nega = True
            continue
        if tipo in ("frase", "parola") and nega:
            tipo = "neg_frase" if tipo == "frase" else "neg"
        nega = False
        if tipo == "frase" and not valore.strip():
            continue
        risultato.append((tipo, valore))
    return risultato


def _modo_avanzato(token: list[tuple[str, str]]) -> bool:
    return any(t != "parola" or "*" in v for t, v in token)


def _rendi(tipo: str, valore: str) -> str:
    if tipo == "frase":
        return f'"{valore}"'
    if tipo == "neg_frase":
        return f'-"{valore}"'
    if tipo == "neg":
        return "-" + _SPECIALI_SENZA_JOLLY.sub(r"\\\1", valore)
    if tipo == "parola":
        return _SPECIALI_SENZA_JOLLY.sub(r"\\\1", valore)
    return valore  # operatori e parentesi


def query_testo_libero(testo: str | None) -> str | None:
    """Clausola Solr per il campo "Parole o estremi".

    - estremi di un provvedimento → clausola su ``anno``, ``numdec`` e ``tipoprov``;
    - una parola sola → la parola, con i caratteri speciali protetti;
    - più parole senza operatori → frase con distanza massima 7 fra i termini;
    - altrimenti (frasi fra virgolette, ``AND``/``OR``/``NOT``, parentesi, troncamento
      ``*``) → i termini nella sintassi di Solr; ``NOT x`` e ``-x`` escludono ``x``; se
      restano solo esclusioni si antepone ``*:*`` perché la query abbia una base.
    """
    if not testo or not testo.strip():
        return None
    estremi = controlla_estremi(testo)
    if estremi:
        return estremi
    token = _token(testo)
    if not token:
        return None
    if not _modo_avanzato(token):
        parole = [v for _, v in token]
        if len(parole) == 1:
            return escape_solr(parole[0])
        return '"' + " ".join(parole) + '"~7'
    positivi = any(t in ("frase", "parola") for t, _ in token)
    negativi = any(t in ("neg", "neg_frase") for t, _ in token)
    clausola = " ".join(_rendi(t, v) for t, v in token)
    if negativi and not positivi:
        clausola = "*:* " + clausola
    return clausola


def query_evidenziazione(testo: str | None) -> str | None:
    """Clausola per ``hl.q``: i soli termini positivi, così da evidenziarli nel testo."""
    if not testo or not testo.strip():
        return None
    termini = []
    for tipo, valore in _token(testo):
        if tipo == "frase":
            termini.append(f'"{valore}"')
        elif tipo == "parola":
            termini.append(_SPECIALI_SENZA_JOLLY.sub(r"\\\1", valore))
    return " ".join(termini) or None


# ---------- riferimenti normativi ----------

_GRAFFA = re.compile(r"\{([^{}]*)\}")


def _espandi_graffe(frase: str) -> list[str]:
    """``a {b,c} d`` → ``["a b d", "a c d"]``: ogni gruppo fra graffe è un'alternativa."""
    m = _GRAFFA.search(frase)
    if not m:
        return [frase]
    risultato: list[str] = []
    for alternativa in m.group(1).split(","):
        risultato.extend(_espandi_graffe(frase[: m.start()] + alternativa + frase[m.end() :]))
    return risultato


def query_riferimenti(normalizzato: str | None) -> str | None:
    """Clausola per i riferimenti normativi a partire dalla risposta di ``estremi?wat=``.

    Il server restituisce la forma canonica del riferimento come alternative separate da
    `` OR ``, con varianti fra graffe; ogni variante diventa una frase con distanza 8.
    """
    if not normalizzato or not normalizzato.strip():
        return None
    frasi: list[str] = []
    for alternativa in normalizzato.split(" OR "):
        frasi.extend(_espandi_graffe(alternativa))
    return " OR ".join(f'"{f}"~8' for f in frasi)


# ---------- query completa e parametri delle richieste ----------


def _clausola_filtro(campo: str, valori: list[str]) -> str:
    valori_puliti = [v for v in valori if v]
    if not valori_puliti:
        return ""
    termini = [f'{campo}:"{escape_solr(v)}"' for v in valori_puliti]
    return termini[0] if len(termini) == 1 else "(" + " OR ".join(termini) + ")"


def clausola_segnale(gruppo: str) -> str:
    """``ocr:("frase 1" OR "frase 2")``: un'unica clausola per gruppo, così una decisione che
    usa entrambe le frasi è contata una volta sola."""
    frasi = SEGNALI[gruppo]
    return "ocr:(" + " OR ".join(f'"{f}"' for f in frasi) + ")"


def normalizza_segnali(facet_queries: dict | None) -> dict[str, int]:
    """Da ``facet_counts.facet_queries`` (chiave = la query) ai conteggi per gruppo."""
    facet_queries = facet_queries or {}
    return {
        gruppo: int(facet_queries[clausola_segnale(gruppo)])
        for gruppo in SEGNALI
        if clausola_segnale(gruppo) in facet_queries
    }


def costruisci_query(
    testo: str | None,
    riferimenti_normalizzati: str | None,
    filtri: dict[str, list[str]] | None = None,
    segnale: str | None = None,
) -> tuple[str, str]:
    """Restituisce ``(q, hl.q)`` nel formato che il server si aspetta.

    ``q`` = testo, riferimenti, archivi e filtri uniti da ``AND``; ``hl.q`` = ``nomatch``
    più le stesse parti tranne gli estremi, che non vanno evidenziati. ``segnale``
    (``contrasto`` o ``conformita``) restringe ai provvedimenti che usano quelle frasi e le
    evidenzia; senza segnale la query è identica a quella del sito.
    """
    filtri = filtri or {}
    parti: list[str] = []
    testo_q = query_testo_libero(testo)
    if testo_q:
        parti.append(f"({testo_q})")
    rif_q = query_riferimenti(riferimenti_normalizzati)
    if rif_q:
        parti.append(f"({rif_q})")
    parti.append(f"({QUERY_INIZIALE})")
    clausole_filtri = [_clausola_filtro(campo, filtri.get(campo, [])) for campo in CAMPI_FACET]
    parti.extend(c for c in clausole_filtri if c)
    clausola_s = clausola_segnale(segnale) if segnale in SEGNALI else ""
    if clausola_s:
        parti.append(clausola_s)
    q = " AND ".join(parti)

    parti_hl: list[str] = ["nomatch"]
    hl_testo = query_evidenziazione(testo)
    if hl_testo and not controlla_estremi(testo or ""):
        parti_hl.append(f"({hl_testo})")
    if rif_q:
        parti_hl.append(f"({rif_q})")
    parti_hl.extend(c for c in clausole_filtri if c)
    if clausola_s:
        parti_hl.append(clausola_s)
    return q, " AND ".join(parti_hl)


def parametri_ricerca(
    q: str, hl_q: str, inizio: int, righe: int, ordinamento: str, con_facet: bool = True
) -> list[tuple[str, str]]:
    """Corpo della POST di ricerca (parametri del sito, più i facet nella stessa chiamata)."""
    parametri: list[tuple[str, str]] = [
        ("start", str(inizio)),
        ("rows", str(righe)),
        ("q", q),
        ("wt", "json"),
        ("indent", "off"),
    ]
    sort = ORDINAMENTI.get(ordinamento, ORDINAMENTI["pubblicazione"])
    if sort:
        parametri.append(("sort", sort))
    parametri += [
        ("fl", CAMPI_RISULTATO),
        ("hl", "true"),
        ("hl.snippets", "4"),
        ("hl.fragsize", "100"),
        ("hl.fl", "ocr"),
        ("hl.q", hl_q),
        ("hl.maxAnalyzedChars", "1000000"),
        ("hl.simple.pre", '<em class="hit">'),
        ("hl.simple.post", "</em>"),
    ]
    if con_facet:
        parametri += [
            ("facet", "true"),
            ("facet.method", "enum"),
            ("facet.mincount", "1"),
            ("facet.limit", "257"),
            ("facet.sort", "false"),
            # La materia ha migliaia di valori: solo i più frequenti, ordinati per conteggio.
            ("f.materia.facet.limit", "60"),
            ("f.materia.facet.sort", "count"),
        ]
        parametri += [("facet.field", campo) for campo in CAMPI_FACET]
        # Conteggi dei segnali nella stessa risposta (facet_counts.facet_queries): nessuna
        # richiesta in più e nessun effetto su risultati e ordinamento.
        parametri += [("facet.query", clausola_segnale(gruppo)) for gruppo in SEGNALI]
    return parametri


def _senza_zeri(valore: str) -> str:
    v = valore.strip().lstrip("0")
    return v or "0"


def _anno_ced(valore: str) -> str:
    """L'anno di ``rnc-dat``, che a volte porta la data intera ("1989 07 28")."""
    trovato = re.match(r"\s*(\d{4})", valore)
    return trovato.group(1) if trovato else ""


def _articolo_ced(valore: str) -> str:
    """Il numero di articolo da ``rnc-art``: "0001 00" -> "1", "0380 02" -> "380-bis".

    Un suffisso numerico fuori dalla tabella dà una stringa vuota: meglio nessun articolo
    che l'articolo sbagliato.
    """
    parti = valore.split()
    if not parti or not parti[0].isdigit():
        return ""
    numero = _senza_zeri(parti[0])
    if len(parti) > 1 and parti[1].isdigit():
        indice = int(parti[1])
        if indice > len(SUFFISSI):
            return ""
        if indice >= 2:
            numero += "-" + SUFFISSI[indice - 1]
    return numero


def _allinea_estremi(valori: list[str], codici: list[bool]) -> list[str]:
    """Numeri (o anni) di ciascun riferimento.

    Il CED compatta ``rnc-num`` e ``rnc-dat``: contengono solo i valori presenti, cioè quelli
    degli atti che non sono codici. Se la lista è lunga quanto quei riferimenti si allinea a
    loro, se è lunga quanto l'elenco intero (dati non compattati) si allinea per indice;
    altrimenti non si sa a chi appartiene ogni valore e nessuno ne riceve uno.
    """
    altri = [i for i, codice in enumerate(codici) if not codice]
    risultato = [""] * len(codici)
    if len(valori) == len(altri):
        for i, valore in zip(altri, valori, strict=True):
            risultato[i] = valore
    elif len(valori) == len(codici):
        risultato = list(valori)
    return risultato


def _allinea_articoli(valori: list[str], codici: list[bool]) -> list[str]:
    """Articolo di ciascun riferimento, solo dove l'allineamento è certo.

    Anche ``rnc-art`` è compattata: mancano gli articoli degli atti citati per intero. Un
    codice si cita sempre con un articolo, quindi i valori mancanti appartengono ad atti che
    non sono codici. Per un codice preceduto da ``prima`` di quegli atti e seguito da ``dopo``,
    i mancanti prima di lui sono almeno ``mancanti - dopo`` e al massimo ``min(mancanti,
    prima)``: l'articolo è certo solo quando i due limiti coincidono. Per gli altri atti
    l'articolo è certo solo se nessuno manca (lista completa) o se mancano tutti.
    """
    if len(valori) == len(codici):
        return list(valori)
    risultato = [""] * len(codici)
    mancanti = len(codici) - len(valori)
    altri_totali = sum(1 for codice in codici if not codice)
    if mancanti < 0 or mancanti > altri_totali:
        return risultato
    prima = 0
    for i, codice in enumerate(codici):
        if not codice:
            prima += 1
            continue
        dopo = altri_totali - prima
        minimo, massimo = max(0, mancanti - dopo), min(mancanti, prima)
        if minimo == massimo:
            risultato[i] = valori[i - minimo]
    return risultato


def formatta_riferimenti(rnc: dict) -> list[dict]:
    """Trasforma le liste parallele ``rnc-*`` di un provvedimento in riferimenti leggibili.

    ``sp`` è il tipo di atto (``COD`` per i codici, con il codice in ``gen``: CC, CP, PC =
    c.p.c., PV = c.p.p., CR = Costituzione), ``num`` il numero, ``dat`` l'anno, ``art``
    l'articolo ("0001 00", "0380 02" = 380-bis), ``com`` il comma. ``sp`` e ``gen`` hanno un
    valore per riferimento; ``num``, ``dat`` e ``art`` sono compattate dal CED (solo i valori
    presenti) e vengono riallineate dove l'allineamento è certo, altrimenti il valore si lascia
    vuoto. Restituisce voci con il testo da mostrare e il testo da usare nel campo
    "Riferimento normativo".
    """
    if not rnc:
        return []
    liste = {k: (v if isinstance(v, list) else [v]) for k, v in rnc.items() if v is not None}

    def lista(campo: str) -> list[str]:
        return ["" if v is None else str(v).strip() for v in liste.get(campo, [])]

    sp, gen = lista("sp"), lista("gen")
    quanti = max(len(sp), len(gen))
    if not quanti:
        # Senza tipi di atto: un riferimento per indice, come per i dati più vecchi.
        quanti = max((len(v) for v in liste.values()), default=0)
    sp += [""] * (quanti - len(sp))
    gen += [""] * (quanti - len(gen))
    codici = [voce.upper() == "COD" for voce in sp]
    numeri = _allinea_estremi(lista("num"), codici)
    anni = _allinea_estremi(lista("dat"), codici)
    articoli = _allinea_articoli(lista("art"), codici)

    risultato: list[dict] = []
    visti: set[str] = set()
    for i in range(quanti):
        if codici[i]:
            codice = CODICI_CED.get(gen[i].upper(), gen[i].upper())
            numero, anno = "", ""
        else:
            codice = sp[i].upper()
            numero = _senza_zeri(numeri[i]) if numeri[i] else ""
            anno = _anno_ced(anni[i])
        tipo = TIPI_ATTO.get(codice, codice.lower() if codice else "")
        articolo = _articolo_ced(articoli[i])
        # Il campo "com" (comma) non risulta allineato agli altri nei dati osservati:
        # non viene mostrato per non attribuire commi sbagliati.
        parti_atto = [tipo]
        if codice not in CODICI_SENZA_ESTREMI and numero and anno:
            parti_atto.append(f"{numero}/{anno}")
        atto = " ".join(p for p in parti_atto if p).strip()
        if not atto and not articolo:
            continue
        testo = ((f"art. {articolo} " if articolo else "") + atto).strip()
        if testo in visti:
            continue
        visti.add(testo)
        risultato.append(
            {
                "tipo": tipo,
                "numero": numero,
                "anno": anno,
                "articolo": articolo,
                "testo": testo,
                "ricerca": testo,
            }
        )
    return risultato


def parametri_dettaglio(id_sentenza: str, hl_q: str | None) -> list[tuple[str, str]]:
    """Corpo della POST per il testo integrale di un provvedimento (un solo documento)."""
    parametri: list[tuple[str, str]] = [
        ("start", "0"),
        ("rows", "1"),
        ("q", f'id:"{escape_solr(id_sentenza)}"'),
    ]
    if hl_q:
        parametri.append(("hl.q", hl_q))
    parametri += [
        ("wt", "json"),
        ("indent", "off"),
        ("fl", ""),
        ("hl", "true"),
        ("hl.fl", "*"),
        ("hl.fragsize", "0"),
        ("hl.maxAnalyzedChars", "1000000"),
        ("hl.simple.pre", '<em class="hit">'),
        ("hl.simple.post", "</em>"),
    ]
    return parametri


def codifica_corpo(parametri: list[tuple[str, str]]) -> str:
    return urlencode(parametri)


def url_pdf(kind: str, filename: str) -> str:
    """URL del PDF "pulito" a partire dal campo ``filename`` del documento."""
    nome = filename
    if ".clean." not in nome:
        nome = nome.replace(".pdf", ".clean.pdf")
    return URL_PDF + "?" + urlencode({"verbo": "attach", "db": kind, "id": nome})


def _primo(valore):
    if isinstance(valore, list):
        return valore[0] if valore else None
    return valore


def _data_iso(valore) -> str | None:
    v = _primo(valore)
    if not v or len(str(v)) != 8:
        return None
    v = str(v)
    return f"{v[0:4]}-{v[4:6]}-{v[6:8]}"


def ecli(doc: dict) -> str | None:
    if doc.get("ecli"):
        return _primo(doc["ecli"])
    anno, numdec, kind = doc.get("anno"), doc.get("numdec"), doc.get("kind")
    if not (anno and numdec and kind in ARCHIVI):
        return None
    suffisso = "CIV" if kind == "snciv" else "PEN"
    return f"ECLI:IT:CASS:{anno}:{numdec}{suffisso}"


def _in_oscuramento(doc: dict) -> bool:
    testo = str(_primo(doc.get("ocr") or doc.get("testoocr")) or "").lower()
    return "in fase di oscuramento" in testo or "in fase di valutazione oscuramento" in testo


def normalizza_documento(doc: dict, evidenziazioni: dict | None = None) -> dict:
    """Trasforma un documento Solr nel formato usato dall'interfaccia di Iudex."""
    kind = doc.get("kind", "")
    filename = _primo(doc.get("filename"))
    oscuramento = _in_oscuramento(doc)
    frammenti = []
    if evidenziazioni:
        frammenti = evidenziazioni.get(doc.get("id", ""), {}).get("ocr", []) or []
    sezione_codice = str(doc.get("szdec", "") or "")
    sottosezione_codice = str(doc.get("ssz", "") or "")
    return {
        "id": doc.get("id"),
        "archivio": ARCHIVI.get(kind, kind),
        "kind": kind,
        "tipo": doc.get("tipoprov"),
        "numero": doc.get("numdec"),
        "anno": doc.get("anno"),
        "sezione_codice": sezione_codice,
        "sezione": SEZIONI.get(sezione_codice, sezione_codice),
        "sottosezione": SOTTOSEZIONI.get(sottosezione_codice, sottosezione_codice),
        "data_decisione": _data_iso(doc.get("datdec")),
        "data_deposito": _data_iso(doc.get("datdep")),
        "presidente": _primo(doc.get("presidente")),
        "relatore": _primo(doc.get("relatore")),
        "ecli": ecli(doc),
        "frammenti": frammenti,
        "pdf": url_pdf(kind, filename) if filename and kind and not oscuramento else None,
        "filename": filename,
    }


def normalizza_facet(facet_fields: dict) -> dict[str, list[dict]]:
    """``{"kind": ["snciv", 3658, "snpen", 367]}`` → liste di ``{codice, etichetta, conteggio}``."""
    etichette = {"kind": ARCHIVI, "szdec": SEZIONI, "ssz": SOTTOSEZIONI}
    risultato: dict[str, list[dict]] = {}
    for campo, coppie in (facet_fields or {}).items():
        voci = []
        for codice, conteggio in zip(coppie[0::2], coppie[1::2], strict=False):
            etichetta = etichette.get(campo, {}).get(str(codice), str(codice))
            voci.append({"codice": str(codice), "etichetta": etichetta, "conteggio": conteggio})
        if campo == "anno":
            voci.sort(key=lambda v: v["codice"], reverse=True)
        risultato[campo] = voci
    return risultato


# ---------- citazioni di sentenze della Cassazione ----------

_MESI = (
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)
_CITAZIONE_INIZIO = re.compile(
    r"^\s*(?:(?:la\s+)?corte\s+(?:suprema\s+)?di\s+)?cass(?:azione)?(?![a-z])\.?", re.IGNORECASE
)
_CITAZIONE_ARCHIVIO = re.compile(r"\b(?P<archivio>civ|pen)(?:ile|ale)?\b\.?", re.IGNORECASE)
_CITAZIONE_SEZIONE = re.compile(
    r"""\bsez(?:ione|\.)?\s*
    (?P<sezione>un(?:ite)?\b|lav(?:oro)?\b|trib(?:utaria)?\b|fer(?:iale)?\b|[ivx]+\b|[1-7]\b)
    |\b(?P<unite>ss\.?\s*uu|s\.\s*u)\b\.?""",
    re.IGNORECASE | re.VERBOSE,
)
_CITAZIONE_DATA = re.compile(
    r"""\b\d{1,2}\s*(?:[/.-]\s*\d{1,2}\s*[/.-]|°?\s+(?:"""
    + "|".join(_MESI)
    + r""")\s+)\s*(?P<anno>\d{4})\b""",
    re.IGNORECASE | re.VERBOSE,
)
# "n. 26972/2008", "n. 99 del 2025", "n. 26972" (anno dalla data); senza "n.": "16924/2025".
_CITAZIONE_NUMERO = re.compile(
    r"""\bn(?:um(?:ero)?)?\.?\s*(?P<numero>\d{1,5})
        (?:\s*(?:/|-|del(?:l'anno)?\s)\s*(?P<anno>\d{4}|\d{2})\b)?
    |\b(?P<numero2>\d{1,5})\s*(?:/|del\s)\s*(?P<anno2>\d{4}|\d{2})\b""",
    re.IGNORECASE | re.VERBOSE,
)
_ROMANI = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7"}
_SEZIONI_CITATE = {"un": "U", "lav": "L", "trib": "5", "fer": "F"}


def _sezione_citata(m: re.Match | None) -> str | None:
    """Codice della sezione come nei documenti di SentenzeWeb (``szdec``): 1-7, U, L, F."""
    if m is None:
        return None
    if m.group("unite"):
        return "U"
    valore = m.group("sezione").lower()
    for prefisso, codice in _SEZIONI_CITATE.items():
        if valore.startswith(prefisso):
            return codice
    return _ROMANI.get(valore) or (valore if valore.isdigit() else None)


def _anno_citato(cifre: str, anno_corrente: int) -> str:
    if len(cifre) == 4:
        return cifre
    anno = 2000 + int(cifre)
    return str(anno if anno <= anno_corrente else anno - 100)


def analizza_citazione(testo: str, anno_corrente: int | None = None) -> dict | None:
    """Estremi di una citazione di una sentenza della Cassazione, oppure ``None``.

    Restituisce ``{"kind", "numdec", "anno", "sezione"}``: ``kind`` è "snciv", "snpen" o
    ``None`` (archivio non indicato; le sezioni lavoro e tributaria sono solo civili),
    ``numdec`` il numero senza zeri iniziali, ``anno`` l'anno a quattro cifre, ``sezione`` il
    codice di SentenzeWeb (1-7, U, L, F) o ``None``. Forme riconosciute, senza distinzione di
    maiuscole e con spazi e punti liberi: "Cass. civ. sez. III n. 1234/2020", "Cass. pen. n.
    1234/2020", "Cass. 5821/2021", "Cassazione civile sezione lavoro 16924/2025" e la forma
    con le virgole e la data "Cass. civ., Sez. Un., 11 novembre 2008, n. 26972" o "Cass. pen.,
    Sez. III, 12/01/2022, n. 1234", dove l'anno viene dalla data se il numero non lo porta.
    Nessun controllo sull'anno: se sia plausibile o nell'archivio lo decide chi chiama.
    """
    inizio = _CITAZIONE_INIZIO.match(testo or "")
    if not inizio:
        return None
    resto = testo[inizio.end() :]
    anno_corrente = anno_corrente or date.today().year
    anno_data = None
    data = _CITAZIONE_DATA.search(resto)
    if data:
        anno_data = data.group("anno")
        resto = resto[: data.start()] + " " + resto[data.end() :]
    numero = _CITAZIONE_NUMERO.search(resto)
    if not numero:
        return None
    cifre = numero.group("numero") or numero.group("numero2")
    anno = numero.group("anno") or numero.group("anno2")
    anno = _anno_citato(anno, anno_corrente) if anno else anno_data
    if not anno or int(cifre) == 0:
        return None
    trovata = _CITAZIONE_SEZIONE.search(resto)
    sezione = _sezione_citata(trovata)
    # Lavoro e tributaria sono sezioni civili: l'archivio si ricava anche senza "civ.".
    solo_civile = bool(trovata and (trovata.group("sezione") or "")[:3].lower() in ("lav", "tri"))
    archivio = _CITAZIONE_ARCHIVIO.search(resto)
    if archivio:
        kind = "snciv" if archivio.group("archivio").lower() == "civ" else "snpen"
    else:
        kind = "snciv" if solo_civile else None
    return {"kind": kind, "numdec": str(int(cifre)), "anno": anno, "sezione": sezione}
