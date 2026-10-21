"""Costruzione delle query Solr nello stesso modo del JavaScript ufficiale di SentenzeWeb.

Le regole sono una trascrizione di ``index.js`` del sito (funzioni ``freeTextQuery``,
``checkEstremi``, ``escapeSolrValue``, ``buildQuery``, ``buildHlQuery`` e il costruttore
delle frasi per i riferimenti normativi), così che una ricerca fatta con Iudex restituisca
gli stessi risultati della ricerca fatta sul sito.
"""

from __future__ import annotations

import itertools
import re
from datetime import date
from urllib.parse import urlencode

from .config import URL_PDF

QUERY_INIZIALE = '(kind:"snciv" OR kind:"snpen")'

# Elenco dei campi richiesti dal sito per la pagina dei risultati (copiato dalla cattura).
CAMPI_RISULTATO = (
    "id,filename,szdec,kind,ssz,tipoprov,numcard,numdec,numdep,datdep,ecli,anno,datdec,"
    "presidente,relatore,requisitoria,testoocr,ocr"
)

ORDINAMENTI = {
    "pubblicazione": "pd desc,numdec desc",
    "udienza": "datdec desc,pd desc,numdec desc",
    "rilevanza": "",
}

CAMPI_FACET = ("kind", "tipoprov", "szdec", "anno", "ssz")

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

_SOLR_DA_ESCAPARE = set('/\\+-&|!(){}[]^~*?:"')
_SOLO_CIFRE = re.compile(r"^\d+$")


def escape_solr(valore: str) -> str:
    """Antepone una barra rovesciata ai caratteri speciali di Solr (``escapeSolrValue``)."""
    return "".join(("\\" + c) if c in _SOLR_DA_ESCAPARE else c for c in valore)


def controlla_estremi(testo: str, anno_corrente: int | None = None) -> str | None:
    """Riconosce "numero/anno" o "sent. n. 123 del 2024" e lo traduce in clausole Solr.

    Trascrizione di ``checkEstremi``: numero di al più 5 cifre (riempito con zeri),
    anno a 2 o 4 cifre negli ultimi 7 anni, tipo di provvedimento facoltativo.
    """
    anno_corrente = anno_corrente or date.today().year
    val = testo.replace("/", " / ").replace(".", " ")
    val = re.sub(r"\s+", " ", val).strip().lower()
    token = val.split(" ")
    if len(token) < 3 or len(token) > 6:
        return None
    anno = num = tipo = None
    for j, tkn in enumerate(token):
        if not tipo:
            if tkn.startswith("dec"):
                tipo = 'tipoprov:"Decreto"'
            elif tkn.startswith("ord"):
                tipo = 'tipoprov:"Ordinanza" OR tipoprov:"Ordinanza Interlocutoria"'
            elif tkn.startswith("sent"):
                tipo = 'tipoprov:"Sentenza"'
        if not _SOLO_CIFRE.match(tkn):
            continue
        precede_barra = j > 1 and token[j - 1] == "/"
        segue_barra = j + 2 < len(token) and token[j + 1] == "/"
        if not num:
            precede_n = j > 0 and token[j - 1] in ("n", "num")
            if len(tkn) < 6 and (precede_n or precede_barra or segue_barra):
                num = f'numdec:"{tkn.zfill(5)}"'
                continue
        if not anno:
            precede_del = j > 0 and token[j - 1] == "del"
            if precede_del or precede_barra or segue_barra:
                trovato = None
                if len(tkn) == 2:
                    candidato = int(str(anno_corrente)[:2] + tkn)
                    trovato = candidato if candidato <= anno_corrente else int("19" + tkn)
                elif len(tkn) == 4:
                    y = int(tkn)
                    if anno_corrente - 7 <= y <= anno_corrente:
                        trovato = y
                if trovato:
                    anno = f'anno:"{trovato}"'
                    continue
    if anno and num:
        return anno + " AND " + num + (" AND " + tipo if tipo else "")
    return None


def _ha_esclusione(val: str) -> bool:
    return " NOT " in val[1:] or val.startswith("NOT ")


def _normalizza_not(val: str) -> str:
    val = re.sub(r"^NOT +", " -", val)
    return re.sub(r" NOT +", " -", val)


def _ha_sintassi(val: str) -> bool:
    return "*" in val or '"' in val or " AND " in val or " OR " in val


def query_testo_libero(testo: str | None) -> str | None:
    """Clausola Solr per il campo "Parole o Numero/Anno sentenza" (``freeTextQuery``)."""
    if not testo or not testo.strip():
        return None
    val = testo.strip()
    estremi = controlla_estremi(val)
    if estremi:
        return estremi
    if _ha_esclusione(val):
        val = _normalizza_not(val)
    if _ha_sintassi(val):
        return val
    # Come nel sito: conta solo uno spazio non in prima posizione (dopo la riscrittura di NOT).
    if val.find(" ") > 0:
        return '"' + val.replace('"', "") + '"~7'
    return escape_solr(val.replace('"', ""))


def query_evidenziazione(testo: str | None) -> str | None:
    """Clausola usata per ``hl.q`` (``freeTextQuery`` con ``hl`` attivo)."""
    if not testo or not testo.strip():
        return None
    return escape_solr(testo.strip().replace('"', ""))


def _espandi_graffe(frase: str) -> list[str]:
    """``a {b,c} d`` → ``["a b d", "a c d"]`` (stessa combinatoria del sito)."""
    segmenti: list[list[str]] = []
    pos = 0
    while True:
        apre = frase.find("{", pos)
        if apre < 0:
            if pos < len(frase):
                segmenti.append([frase[pos:]])
            break
        if apre != pos:
            segmenti.append([frase[pos:apre]])
        chiude = frase.find("}", apre)
        if chiude < 0:
            segmenti.append([frase[apre:]])
            break
        segmenti.append(frase[apre + 1 : chiude].split(","))
        pos = chiude + 1
    if not segmenti:
        return [frase]
    return ["".join(c) for c in itertools.product(*segmenti)]


def query_riferimenti(normalizzato: str | None) -> str | None:
    """Clausola per i riferimenti normativi a partire dalla risposta di ``estremi?wat=``.

    Il sito chiede al server la forma canonica del riferimento (alternative separate da
    `` OR `` e varianti fra graffe) e cerca ciascuna variante come frase con distanza 8.
    """
    if not normalizzato or not normalizzato.strip():
        return None
    frasi: list[str] = []
    for alternativa in normalizzato.split(" OR "):
        frasi.extend(_espandi_graffe(alternativa))
    return " OR ".join(f'"{f}"~8' for f in frasi)


def _clausola_filtro(campo: str, valori: list[str]) -> str:
    valori_puliti = [v for v in valori if v]
    if not valori_puliti:
        return ""
    termini = [f'{campo}:"{escape_solr(v)}"' for v in valori_puliti]
    return termini[0] if len(termini) == 1 else "(" + " OR ".join(termini) + ")"


def costruisci_query(
    testo: str | None,
    riferimenti_normalizzati: str | None,
    filtri: dict[str, list[str]] | None = None,
) -> tuple[str, str]:
    """Restituisce ``(q, hl.q)`` come ``Y.buildQuery`` e ``Y.buildHlQuery`` del sito."""
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
    q = " AND ".join(parti)

    parti_hl: list[str] = ["nomatch"]
    hl_testo = query_evidenziazione(testo)
    if hl_testo and not controlla_estremi(testo or ""):
        parti_hl.append(f"({hl_testo})")
    if rif_q:
        parti_hl.append(f"({rif_q})")
    parti_hl.extend(c for c in clausole_filtri if c)
    return q, " AND ".join(parti_hl)


def parametri_ricerca(
    q: str, hl_q: str, inizio: int, righe: int, ordinamento: str, con_facet: bool = True
) -> list[tuple[str, str]]:
    """Corpo della POST ``app.query`` (parametri del sito, più i facet nella stessa chiamata)."""
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
        ]
        parametri += [("facet.field", campo) for campo in CAMPI_FACET]
    return parametri


def parametri_dettaglio(id_sentenza: str, hl_q: str | None) -> list[tuple[str, str]]:
    """Corpo della POST per il testo integrale di una sentenza (``openDetail`` del sito)."""
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
    """URL del PDF "pulito" come lo costruisce il sito a partire dal campo ``filename``."""
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


def normalizza_documento(doc: dict, evidenziazioni: dict | None = None) -> dict:
    """Trasforma un documento Solr nel formato usato dall'interfaccia di Iudex."""
    kind = doc.get("kind", "")
    filename = _primo(doc.get("filename"))
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
        "pdf": url_pdf(kind, filename) if filename and kind else None,
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
