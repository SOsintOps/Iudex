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


def formatta_riferimenti(rnc: dict) -> list[dict]:
    """Trasforma le liste parallele ``rnc-*`` di un provvedimento in riferimenti leggibili.

    Ogni indice descrive un riferimento: ``sp`` tipo di atto, ``num`` numero, ``dat`` anno,
    ``art`` articolo ("0001 00"), ``com`` comma. Restituisce voci con il testo da mostrare e
    il testo da usare nel campo "Riferimento normativo".
    """
    if not rnc:
        return []
    liste = {k: (v if isinstance(v, list) else [v]) for k, v in rnc.items()}
    quanti = max((len(v) for v in liste.values()), default=0)

    def voce(campo: str, i: int) -> str:
        lista = liste.get(campo, [])
        return str(lista[i]).strip() if i < len(lista) and lista[i] is not None else ""

    risultato: list[dict] = []
    visti: set[str] = set()
    for i in range(quanti):
        codice = voce("sp", i).upper()
        tipo = TIPI_ATTO.get(codice, codice.lower() if codice else "")
        numero = _senza_zeri(voce("num", i)) if voce("num", i) else ""
        anno = voce("dat", i)
        articolo_grezzo = voce("art", i).split()
        articolo = _senza_zeri(articolo_grezzo[0]) if articolo_grezzo else ""
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
