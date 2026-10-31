"""Server MCP che espone Iudex a un assistente (Claude, LM Studio, altri client MCP).

Gli strumenti chiamano l'API HTTP locale di Iudex, che deve essere in esecuzione
(``python -m iudex``): così passano dalla cache e dalla limitazione della frequenza delle
richieste già scritte, e le sentenze lette finiscono nel diario come quelle aperte dalla
pagina. Gli errori che il modello può correggere (Iudex spento, parametri sbagliati,
pausa chiesta dal server) sono ``ToolError``: il modello legge il messaggio invece di un
errore generico. Richiede il pacchetto ``mcp`` (``pip install -e .[mcp]``).
Avvio: ``python -m iudex.mcp_server``.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import date
from typing import Annotated, Literal

import httpx
from pydantic import Field

from . import __version__, accesso
from .config import impostazioni
from .query import SEZIONI, SUFFISSI, analizza_citazione

try:  # mcp 2.x (MCPServer, ToolError, ToolAnnotations con nomi snake_case)
    from mcp.server import MCPServer as FastMCP
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.types import ToolAnnotations
except ImportError as exc:  # pragma: no cover - extra non installato o mcp 1.x
    raise SystemExit("Installa l'extra MCP aggiornato: pip install -e .[mcp]") from exc

BASE = os.environ.get("IUDEX_URL", f"http://{impostazioni.host}:{impostazioni.porta}")
HEADER = {"X-Iudex": "1"}


def _header() -> dict:
    """Header delle chiamate: il token si rilegge ogni volta dal file della cartella dei dati
    (``IUDEX_TOKEN`` lo sostituisce), così vale anche dopo una rigenerazione."""
    token = os.environ.get("IUDEX_TOKEN") or accesso.leggi(impostazioni.cartella_dati)
    return {**HEADER, "X-Iudex-Token": token} if token else dict(HEADER)


RIGHE_MASSIME = 20
CARATTERI_MASSIMI = 30000
# Strumenti in sola lettura per chi li chiama (Iudex aggiorna solo cache e diario locali),
# ma su un mondo aperto: interrogano il server della Corte.
LETTURA = ToolAnnotations(read_only_hint=True, open_world_hint=True)

mcp = FastMCP(
    "Iudex",
    instructions=(
        "Ricerca nelle sentenze civili e penali della Corte di Cassazione (SentenzeWeb) "
        "tramite Iudex. Usa cerca_sentenze per parole o estremi, cerca_per_norma per un "
        "riferimento normativo, leggi_sentenza per il testo integrale (la prima lettura "
        "mostra inizio e fine, dove sta il dispositivo). Ogni ricerca costa una richiesta al "
        "server della Corte: non ripetere ricerche identiche e non scorrere molte pagine. "
        "Per un nome di persona o di società usa la frase esatta fra virgolette; molti nomi "
        "nelle sentenze sono oscurati e lo stesso nome può essere di persone diverse. "
        "leggi_norma restituisce il testo di un articolo da Normattiva (vigente o a una "
        "data), con la vigenza e il link: costa al più una richiesta a Normattiva, nessuna "
        "se l'articolo è già nella cache. verifica_citazioni controlla fino a 10 citazioni "
        "di sentenze della Cassazione per chiamata: prima le sentenze già consultate su "
        "questo computer, poi una sola richiesta alla Corte per citazione, in sequenza, con "
        "almeno 2 secondi fra una richiesta e l'altra. «non trovata» vuol dire che gli "
        "estremi non sono nell'archivio online di SentenzeWeb, non che la sentenza sia "
        "inesistente: può mancare dall'archivio pubblico o la citazione può avere un "
        "numero, un anno o un archivio sbagliati. «fonte non raggiungibile» vuol dire che "
        "la verifica non è stata fatta: riprova più tardi, senza trarne conclusioni."
    ),
)


def _richiesta(percorso: str, parametri: dict) -> httpx.Response:
    """Una chiamata all'API locale; ``ToolError`` solo se Iudex non risponde."""
    try:
        return httpx.get(BASE + percorso, params=parametri, headers=_header(), timeout=90)
    except httpx.TransportError as exc:
        raise ToolError(f"Iudex non risponde su {BASE}: va aperto Iudex ({exc})") from exc


def _dettaglio(r: httpx.Response) -> str:
    try:
        corpo = r.json()
        return str(corpo.get("errore") or corpo.get("detail"))
    except (ValueError, AttributeError):
        return r.text[:200]


def _chiama(percorso: str, parametri: dict) -> dict:
    r = _richiesta(percorso, parametri)
    if r.status_code >= 400:
        raise ToolError(f"Iudex ha risposto {r.status_code}: {_dettaglio(r)}")
    return r.json()


def _riga(doc: dict) -> str:
    estremi = (
        f"{doc.get('archivio')}, Sez. {doc.get('sezione')}, {doc.get('tipo')} "
        f"n. {doc.get('numero')}/{doc.get('anno')}"
    )
    frammenti = " | ".join(
        f.replace('<em class="hit">', "«").replace("</em>", "»")
        for f in doc.get("frammenti", [])[:2]
    )
    return (
        f"- id: {doc.get('id')} · {estremi} · dep. {doc.get('data_deposito')} · "
        f"{doc.get('ecli') or ''}\n  {frammenti}"
    )


def _segnali(d: dict) -> str:
    s = d.get("segnali") or {}
    if not s:
        return ""
    return (
        f"\nSegnali nel testo: {s.get('contrasto', 0)} segnalano un contrasto, "
        f"{s.get('conformita', 0)} richiamano un orientamento consolidato "
        "(conteggio di frasi, non una classificazione)."
    )


def finestra(testo: str, da_carattere: int, quanti: int, posizione_pqm: int | None = None) -> str:
    """La parte di testo da restituire.

    Con ``da_carattere`` a zero e un testo più lungo di ``quanti``: i primi due terzi di
    ``quanti`` e l'ultimo terzo a partire dal P.Q.M. (o dalla fine), con l'indicazione dei
    caratteri omessi, perché l'esito della decisione sta in fondo. Altrimenti la finestra
    da ``da_carattere``.
    """
    quanti = max(500, min(quanti, CARATTERI_MASSIMI))
    da_carattere = max(0, da_carattere)
    if da_carattere or len(testo) <= quanti:
        return testo[da_carattere : da_carattere + quanti]
    testa = quanti * 2 // 3
    coda = quanti - testa
    inizio_coda = len(testo) - coda
    if posizione_pqm is not None and testa < posizione_pqm < inizio_coda:
        inizio_coda = posizione_pqm
    return (
        testo[:testa]
        + f"\n[… caratteri {testa}–{inizio_coda} omessi: leggili con da_carattere={testa} …]\n"
        + testo[inizio_coda : inizio_coda + coda]
    )


Archivio = Literal["", "snciv", "snpen"]
Segnale = Literal["", "contrasto", "conformita"]


@mcp.tool(title="Cerca sentenze della Cassazione", annotations=LETTURA)
def cerca_sentenze(
    testo: str,
    archivio: Annotated[Archivio, Field(description="snciv = civile, snpen = penale")] = "",
    anno: Annotated[str, Field(description='"2026" oppure "2025,2026"')] = "",
    sezione: Annotated[str, Field(description="codice: 1-7, F, L, U")] = "",
    tipo: Annotated[str, Field(description="Sentenza, Ordinanza, Decreto")] = "",
    segnale: Annotated[
        Segnale, Field(description="solo i provvedimenti che dichiarano contrasto o conformità")
    ] = "",
    righe: Annotated[int, Field(ge=1, le=RIGHE_MASSIME)] = 10,
    pagina: Annotated[int, Field(ge=1)] = 1,
) -> str:
    """Cerca sentenze della Cassazione per parole, frase ("..."), troncamento (*) o estremi
    (12345/2024)."""
    parametri: dict = {"testo": testo, "righe": righe, "pagina": pagina}
    for chiave, valore in (
        ("kind", archivio),
        ("anno", anno),
        ("szdec", sezione),
        ("tipoprov", tipo),
        ("segnale", segnale),
    ):
        if valore:
            parametri[chiave] = valore
    d = _chiama("/api/cerca", parametri)
    righe_testo = [_riga(doc) for doc in d["documenti"]]
    intestazione = (
        f"{d['trovati']} provvedimenti per «{d['descrizione']}» "
        f"(pagina {d['pagina']}, {len(righe_testo)} mostrati){_segnali(d)}"
    )
    return intestazione + "\n" + "\n".join(righe_testo)


@mcp.tool(title="Cerca le sentenze che citano una norma", annotations=LETTURA)
def cerca_per_norma(
    riferimento: str,
    testo: str = "",
    archivio: Annotated[Archivio, Field(description="snciv = civile, snpen = penale")] = "",
    righe: Annotated[int, Field(ge=1, le=RIGHE_MASSIME)] = 10,
) -> str:
    """Cerca le sentenze che citano un riferimento normativo scritto come in una citazione
    (es. "art. 18 legge 300/1970", "art. 2043 c.c."), con parole facoltative nel testo."""
    parametri: dict = {"rif": riferimento, "righe": righe}
    if testo:
        parametri["testo"] = testo
    if archivio:
        parametri["kind"] = archivio
    d = _chiama("/api/cerca", parametri)
    righe_testo = [_riga(doc) for doc in d["documenti"]]
    return f"{d['trovati']} provvedimenti per «{d['descrizione']}»{_segnali(d)}\n" + "\n".join(
        righe_testo
    )


@mcp.tool(title="Leggi una sentenza", annotations=LETTURA)
def leggi_sentenza(
    id_sentenza: Annotated[str, Field(description="es. snciv2026L26495S")],
    da_carattere: Annotated[int, Field(ge=0)] = 0,
    quanti: Annotated[int, Field(ge=500, le=CARATTERI_MASSIMI)] = 12000,
) -> str:
    """Restituisce estremi, dispositivo, riferimenti normativi e testo integrale di una
    sentenza. Con da_carattere=0 un testo lungo arriva come inizio + fine (dal P.Q.M.), con
    l'indicazione dei caratteri omessi; da_carattere legge una finestra qualsiasi."""
    d = _chiama(f"/api/sentenza/{id_sentenza}", {})
    doc = d["documento"]
    testo = d.get("testo") or ""
    riferimenti = "; ".join(r["testo"] for r in doc.get("riferimenti_normativi", [])[:20])
    intestazione = (
        f"{doc.get('archivio')}, Sez. {doc.get('sezione')}, {doc.get('tipo')} n. "
        f"{doc.get('numero')}/{doc.get('anno')} · udienza {doc.get('data_decisione')} · "
        f"deposito {doc.get('data_deposito')} · {doc.get('ecli') or ''}\n"
        f"PDF ufficiale: {doc.get('pdf') or '-'}\n"
        f"Materia: {', '.join(doc.get('materia') or []) or '-'}\n"
        f"Riferimenti normativi: {riferimenti or '-'}\n"
        f"Dispositivo: {doc.get('massima') or '-'}\n"
        f"Testo ({len(testo)} caratteri, da {da_carattere}):\n"
    )
    return intestazione + finestra(testo, da_carattere, quanti, d.get("posizione_pqm"))


# --- norme -----------------------------------------------------------------------------------

# Sigle degli atti come si scrivono nelle citazioni, senza punti e spazi -> codice di Iudex.
_SIGLE_ATTI = {
    "cc": "CC",
    "codicecivile": "CC",
    "cp": "CP",
    "codicepenale": "CP",
    "cpc": "CPC",
    "codicediproceduracivile": "CPC",
    "cpp": "CPP",
    "codicediprocedurapenale": "CPP",
    "cost": "COST",
    "costituzione": "COST",
    "l": "LS",
    "legge": "LS",
    "dlgs": "DLG",
    "decretolegislativo": "DLG",
    "dl": "DL",
    "decretolegge": "DL",
    "dpr": "DPR",
    "dpcm": "DPCM",
    "dm": "DM",
    "rd": "RD",
    "regiodecreto": "RD",
    "rdl": "RDL",
}
_CODICI = {"CC", "CP", "CPC", "CPP", "COST"}
_SUFFISSO = "|".join(sorted((s for s in SUFFISSI if s), key=len, reverse=True))
_RIFERIMENTO = re.compile(
    rf"""^\s*art(?:icolo|t?\.)?\s*(?P<numero>\d{{1,4}})\s*(?:-?\s*(?P<suffisso>{_SUFFISSO})\b)?
    \s*,?\s*(?:del(?:la|l')?\s*)?(?P<atto>.+?)\s*$""",
    re.IGNORECASE | re.VERBOSE,
)
_ESTREMI_ATTO = re.compile(
    r"""^(?P<sigla>[a-z.\s'-]+?)\s*(?:n\.?\s*)?(?P<numero>\d{1,6})\s*(?:/|,|del\s)\s*
    (?P<anno>\d{4})$""",
    re.IGNORECASE | re.VERBOSE,
)


def _sigla(testo: str) -> str:
    return re.sub(r"[\s.'-]", "", testo.lower())


def leggi_riferimento(testo: str) -> dict | None:
    """Campi di /api/norma da un riferimento scritto come in una citazione, oppure ``None``.

    "art. 2043 c.c." -> CC, articolo 2043; "art. 13 d.lgs. 196/2003" -> DLG 196/2003, articolo
    13; "art. 2-bis l. 241/1990" -> LS 241/1990, articolo 2-bis. Nessuna deduzione: un atto
    che non si riconosce dà ``None``.
    """
    m = _RIFERIMENTO.match(testo or "")
    if not m:
        return None
    articolo = m.group("numero").lstrip("0") or "0"
    if m.group("suffisso"):
        articolo += "-" + m.group("suffisso").lower()
    atto = m.group("atto").strip()
    if _SIGLE_ATTI.get(_sigla(atto)) in _CODICI:
        return {"tipo": _SIGLE_ATTI[_sigla(atto)], "numero": "", "anno": "", "articolo": articolo}
    estremi = _ESTREMI_ATTO.match(atto)
    if not estremi:
        return None
    tipo = _SIGLE_ATTI.get(_sigla(estremi.group("sigla")))
    if not tipo or tipo in _CODICI:
        return None
    return {
        "tipo": tipo,
        "numero": estremi.group("numero"),
        "anno": estremi.group("anno"),
        "articolo": articolo,
    }


def _testo_norma(d: dict, da_carattere: int) -> str:
    atto, art, vig = d.get("atto") or {}, d.get("articolo") or {}, d.get("vigenza") or {}
    testo = art.get("testo") or ""
    rubrica = f" - {art['rubrica']}" if art.get("rubrica") else ""
    fine = f" al {vig['fine']}" if vig.get("fine") else ""
    alla_data = (
        f" (testo alla data {vig['richiesta']})" if vig.get("richiesta") else " (testo vigente)"
    )
    cache = " (dalla cache di Iudex)" if d.get("da_cache") else ""
    corpo = testo[da_carattere : da_carattere + CARATTERI_MASSIMI]
    if art.get("note") and da_carattere + CARATTERI_MASSIMI >= len(testo):
        corpo += f"\n\nNote: {art['note']}"
    return (
        f"{atto.get('titolo') or '-'}\n"
        f"Art. {art.get('numero')}{rubrica}\n"
        f"Vigenza: dal {vig.get('inizio') or '?'}{fine}{alla_data}\n"
        f"Link: {d.get('url') or '-'}\n"
        f"Fonte: {d.get('fonte') or 'Normattiva'}{cache}\n"
        f"Testo ({len(testo)} caratteri, da {da_carattere}):\n{corpo}"
    )


@mcp.tool(title="Leggi il testo di una norma", annotations=LETTURA)
def leggi_norma(
    riferimento: Annotated[
        str, Field(description='es. "art. 2043 c.c.", "art. 13 d.lgs. 196/2003"')
    ] = "",
    tipo: Annotated[
        str, Field(description="CC, CP, CPC, CPP, COST, LS, DLG, DL, DPR, DPCM, DM, RD, RDL")
    ] = "",
    numero: Annotated[str, Field(description="numero dell'atto (vuoto per i codici)")] = "",
    anno: Annotated[str, Field(description="anno dell'atto (vuoto per i codici)")] = "",
    articolo: Annotated[str, Field(description='es. "2043" oppure "2-bis"')] = "",
    vigenza: Annotated[str, Field(description="AAAA-MM-GG; vuoto = testo vigente")] = "",
    da_carattere: Annotated[int, Field(ge=0)] = 0,
) -> str:
    """Testo di un articolo da Normattiva (fonte ufficiale), vigente o alla data di vigenza,
    con le date di vigenza e il link. Dai il riferimento come in una citazione oppure i campi
    tipo, numero, anno e articolo; i campi espliciti prevalgono su quelli del riferimento."""
    campi = {"tipo": "", "numero": "", "anno": "", "articolo": ""}
    if riferimento:
        letti = leggi_riferimento(riferimento)
        if letti is None and not (tipo and articolo):
            raise ToolError(
                f"riferimento non interpretabile: «{riferimento}». Scrivilo come "
                '"art. 2043 c.c." o "art. 13 d.lgs. 196/2003", oppure usa tipo, numero, '
                "anno e articolo"
            )
        campi.update(letti or {})
    espliciti = {"tipo": tipo, "numero": numero, "anno": anno, "articolo": articolo}
    campi.update({chiave: valore for chiave, valore in espliciti.items() if valore})
    if vigenza:
        campi["vigenza"] = vigenza
    return _testo_norma(_chiama("/api/norma", campi), da_carattere)


# --- citazioni -------------------------------------------------------------------------------

CITAZIONI_MASSIME = 10
ANNO_MINIMO_ARCHIVIO = 2000  # SentenzeWeb pubblica i provvedimenti dal 2000


def _corrisponde(doc: dict, estremi: dict) -> bool:
    numero = str(doc.get("numero") or "").lstrip("0")
    return (
        numero == estremi["numdec"]
        and str(doc.get("anno")) == estremi["anno"]
        and (estremi["kind"] is None or doc.get("kind") == estremi["kind"])
    )


def _descrivi(doc: dict) -> str:
    ecli = f" · {doc['ecli']}" if doc.get("ecli") else ""
    return (
        f"id {doc.get('id')} · {doc.get('archivio') or doc.get('kind')}, Sez. "
        f"{doc.get('sezione')}, {doc.get('tipo')} n. {doc.get('numero')}/{doc.get('anno')}{ecli}"
    )


def _trovata(documenti: list[dict], estremi: dict, dove: str) -> str:
    esito = f"esiste ({dove}): " + "; ".join(_descrivi(doc) for doc in documenti[:3])
    sezione = estremi["sezione"]
    if sezione in SEZIONI and all(doc.get("sezione_codice") != sezione for doc in documenti):
        esito += (
            f" — attenzione: la citazione indica la sezione {SEZIONI[sezione]}, l'archivio un'altra"
        )
    return esito


def _fuori_archivio(anno: int, anno_corrente: int) -> str | None:
    if anno > anno_corrente:
        return f"fuori archivio: anno {anno} non plausibile (futuro), nessuna richiesta"
    if anno < ANNO_MINIMO_ARCHIVIO:
        return (
            f"fuori archivio: SentenzeWeb pubblica i provvedimenti dal {ANNO_MINIMO_ARCHIVIO}, "
            f"l'anno {anno} non si può verificare qui, nessuna richiesta"
        )
    return None


class _Verifica:
    """Stato di una chiamata a verifica_citazioni: cache locale letta una volta, richieste
    contate, sospese dopo la prima risposta di fonte non raggiungibile."""

    def __init__(self) -> None:
        self.locali: list[dict] | None = None
        self.sospesa: str | None = None
        self.richieste = 0

    def _consultate(self) -> list[dict]:
        if self.locali is None:
            r = _richiesta("/api/consultate", {})
            elenco = r.json() if r.status_code == 200 else []
            self.locali = [c.get("documento") or {} for c in elenco]
        return self.locali

    def esito(self, estremi: dict) -> str:
        locali = [doc for doc in self._consultate() if _corrisponde(doc, estremi)]
        if locali:
            return _trovata(locali, estremi, "fra le sentenze consultate su questo computer")
        if self.sospesa:
            return f"fonte non raggiungibile: richiesta non fatta ({self.sospesa})"
        parametri = {
            "testo": f"{estremi['numdec']}/{estremi['anno']}",
            "anno": estremi["anno"],
            "righe": 5,
        }
        if estremi["kind"]:
            parametri["kind"] = estremi["kind"]
        r = _richiesta("/api/cerca", parametri)
        self.richieste += 1
        if r.status_code in (401, 403):
            raise ToolError(f"Iudex ha risposto {r.status_code}: {_dettaglio(r)}")
        if r.status_code == 429 or r.status_code >= 500:
            self.sospesa = f"Iudex ha risposto {r.status_code}: {_dettaglio(r)}"
            return f"fonte non raggiungibile, verifica non fatta ({self.sospesa})"
        if r.status_code >= 400:
            return f"non verificata: Iudex ha risposto {r.status_code}: {_dettaglio(r)}"
        documenti = [d for d in r.json().get("documenti", []) if _corrisponde(d, estremi)]
        if documenti:
            return _trovata(documenti, estremi, "SentenzeWeb")
        return "non trovata nell'archivio online di SentenzeWeb"


@mcp.tool(title="Verifica citazioni di sentenze della Cassazione", annotations=LETTURA)
def verifica_citazioni(
    citazioni: Annotated[
        list[str],
        Field(
            description=(
                'al massimo 10, es. "Cass. civ., Sez. Un., 11 novembre 2008, n. 26972" o '
                '"Cass. pen. sez. VI n. 1234/2020"'
            )
        ),
    ],
) -> str:
    """Verifica se le sentenze della Cassazione citate sono nell'archivio di SentenzeWeb.

    Per ogni citazione: esiste (con id ed ECLI), non trovata (assente dall'archivio online,
    il che non prova che la sentenza non sia mai stata pronunciata), fonte non raggiungibile
    (verifica non fatta), fuori archivio (anno futuro o anteriore al 2000, nessuna richiesta)
    o non interpretabile. Prima le sentenze già consultate su questo computer, poi una sola
    richiesta alla Corte per citazione."""
    if len(citazioni) > CITAZIONI_MASSIME:
        raise ToolError(
            f"al massimo {CITAZIONI_MASSIME} citazioni per chiamata (ne sono arrivate "
            f"{len(citazioni)}): dividile in più chiamate"
        )
    if not citazioni:
        return "Nessuna citazione da verificare."
    anno_corrente = date.today().year
    verifica = _Verifica()
    gia_viste: dict[tuple, str] = {}
    righe = []
    for indice, citazione in enumerate(citazioni, start=1):
        estremi = analizza_citazione(citazione, anno_corrente)
        if estremi is None:
            esito = "non interpretabile: servono numero e anno, es. «Cass. civ. n. 26972/2008»"
        else:
            chiave = (estremi["kind"], estremi["numdec"], estremi["anno"])
            esito = _fuori_archivio(int(estremi["anno"]), anno_corrente) or gia_viste.get(chiave)
            if esito is None:
                esito = gia_viste[chiave] = verifica.esito(estremi)
        righe.append(f"{indice}. «{citazione}» -> {esito}")
    intestazione = (
        f"Verifica di {len(citazioni)} citazioni ({verifica.richieste} richieste alla Corte). "
        "«non trovata» = assente dall'archivio online, non prova che la sentenza non esista; "
        "«fonte non raggiungibile» = verifica non fatta."
    )
    return intestazione + "\n" + "\n".join(righe)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    print(f"Iudex MCP {__version__}", file=sys.stderr)  # noqa: T201
    main()
