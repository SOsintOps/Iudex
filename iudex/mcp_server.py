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
from typing import Annotated, Literal

import httpx
from pydantic import Field

from . import __version__
from .config import impostazioni

try:  # mcp 2.x (MCPServer, ToolError, ToolAnnotations con nomi snake_case)
    from mcp.server import MCPServer as FastMCP
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.types import ToolAnnotations
except ImportError as exc:  # pragma: no cover - extra non installato o mcp 1.x
    raise SystemExit("Installa l'extra MCP aggiornato: pip install -e .[mcp]") from exc

BASE = os.environ.get("IUDEX_URL", f"http://{impostazioni.host}:{impostazioni.porta}")
HEADER = {"X-Iudex": "1"}
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
        "Non cercare per nome di persona."
    ),
)


def _chiama(percorso: str, parametri: dict) -> dict:
    try:
        r = httpx.get(BASE + percorso, params=parametri, headers=HEADER, timeout=90)
    except httpx.TransportError as exc:
        raise ToolError(
            f"Iudex non risponde su {BASE}: va avviato con 'python -m iudex' ({exc})"
        ) from exc
    if r.status_code >= 400:
        try:
            corpo = r.json()
            dettaglio = corpo.get("errore") or corpo.get("detail")
        except ValueError:
            dettaglio = r.text[:200]
        raise ToolError(f"Iudex ha risposto {r.status_code}: {dettaglio}")
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
    return (
        f"{d['trovati']} provvedimenti per «{d['descrizione']}»{_segnali(d)}\n"
        + "\n".join(righe_testo)
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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    print(f"Iudex MCP {__version__}")  # noqa: T201
    main()
