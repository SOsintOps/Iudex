"""Server MCP che espone Iudex a un assistente (Claude, LM Studio, altri client MCP).

Gli strumenti chiamano l'API HTTP locale di Iudex, che deve essere in esecuzione
(``python -m iudex``): così passano dalla cache e dai limiti di cortesia già scritti.
Richiede il pacchetto ``mcp`` (``pip install -e .[mcp]``). Avvio: ``python -m iudex.mcp_server``.
"""

from __future__ import annotations

import os

import httpx

from . import __version__
from .config import impostazioni

try:  # mcp 2.x
    from mcp.server import MCPServer as FastMCP
except ImportError:  # pragma: no cover - mcp 1.x
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit("Installa l'extra MCP: pip install -e .[mcp]") from exc

BASE = os.environ.get("IUDEX_URL", f"http://{impostazioni.host}:{impostazioni.porta}")
HEADER = {"X-Iudex": "1"}
RIGHE_MASSIME = 20

mcp = FastMCP(
    "Iudex",
    instructions=(
        "Ricerca nelle sentenze civili e penali della Corte di Cassazione (SentenzeWeb) "
        "tramite Iudex. Usa cerca_sentenze per parole o estremi, cerca_per_norma per un "
        "riferimento normativo, leggi_sentenza per il testo integrale. Ogni ricerca costa una "
        "richiesta al server della Corte: non ripetere ricerche identiche e non scorrere molte "
        "pagine. Non cercare per nome di persona."
    ),
)


def _chiama(percorso: str, parametri: dict) -> dict:
    try:
        r = httpx.get(BASE + percorso, params=parametri, headers=HEADER, timeout=90)
    except httpx.TransportError as exc:
        raise RuntimeError(
            f"Iudex non risponde su {BASE}: avvialo con 'python -m iudex' ({exc})"
        ) from exc
    if r.status_code >= 400:
        try:
            dettaglio = r.json().get("errore") or r.json().get("detail")
        except ValueError:
            dettaglio = r.text[:200]
        raise RuntimeError(f"Iudex ha risposto {r.status_code}: {dettaglio}")
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


@mcp.tool()
def cerca_sentenze(
    testo: str,
    archivio: str = "",
    anno: str = "",
    sezione: str = "",
    tipo: str = "",
    righe: int = 10,
    pagina: int = 1,
) -> str:
    """Cerca sentenze della Cassazione per parole, frase ("..."), troncamento (*) o estremi
    (12345/2024). archivio: "snciv" (civile) o "snpen" (penale); anno: "2026" oppure
    "2025,2026"; sezione: codice (1-7, F, L, U); tipo: Sentenza, Ordinanza, Decreto."""
    parametri = {
        "testo": testo,
        "righe": max(1, min(righe, RIGHE_MASSIME)),
        "pagina": max(1, pagina),
    }
    if archivio:
        parametri["kind"] = archivio
    if anno:
        parametri["anno"] = anno
    if sezione:
        parametri["szdec"] = sezione
    if tipo:
        parametri["tipoprov"] = tipo
    d = _chiama("/api/cerca", parametri)
    righe_testo = [_riga(doc) for doc in d["documenti"]]
    intestazione = (
        f"{d['trovati']} provvedimenti per «{d['descrizione']}» "
        f"(pagina {d['pagina']}, {len(righe_testo)} mostrati)"
    )
    return intestazione + "\n" + "\n".join(righe_testo)


@mcp.tool()
def cerca_per_norma(riferimento: str, testo: str = "", archivio: str = "", righe: int = 10) -> str:
    """Cerca le sentenze che citano un riferimento normativo scritto come in una citazione
    (es. "art. 18 legge 300/1970", "art. 2043 c.c."), con parole facoltative nel testo."""
    parametri = {"rif": riferimento, "righe": max(1, min(righe, RIGHE_MASSIME))}
    if testo:
        parametri["testo"] = testo
    if archivio:
        parametri["kind"] = archivio
    d = _chiama("/api/cerca", parametri)
    righe_testo = [_riga(doc) for doc in d["documenti"]]
    return f"{d['trovati']} provvedimenti per «{d['descrizione']}»\n" + "\n".join(righe_testo)


@mcp.tool()
def leggi_sentenza(id_sentenza: str, da_carattere: int = 0, quanti: int = 12000) -> str:
    """Restituisce estremi, dispositivo, riferimenti normativi e testo integrale di una sentenza
    dato il suo id (es. snciv2026L26495S). Il testo è restituito a finestre: usa da_carattere
    per leggere oltre i primi caratteri."""
    d = _chiama(f"/api/sentenza/{id_sentenza}", {})
    doc = d["documento"]
    testo = d.get("testo") or ""
    finestra = testo[da_carattere : da_carattere + max(500, min(quanti, 30000))]
    riferimenti = "; ".join(r["testo"] for r in doc.get("riferimenti_normativi", [])[:20])
    intestazione = (
        f"{doc.get('archivio')}, Sez. {doc.get('sezione')}, {doc.get('tipo')} n. "
        f"{doc.get('numero')}/{doc.get('anno')} · udienza {doc.get('data_decisione')} · "
        f"deposito {doc.get('data_deposito')} · {doc.get('ecli') or ''}\n"
        f"PDF ufficiale: {doc.get('pdf')}\n"
        f"Materia: {', '.join(doc.get('materia') or []) or '-'}\n"
        f"Riferimenti normativi: {riferimenti or '-'}\n"
        f"Dispositivo: {doc.get('massima') or '-'}\n"
        f"Testo ({len(testo)} caratteri, da {da_carattere}):\n"
    )
    return intestazione + finestra


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    print(f"Iudex MCP {__version__}")  # noqa: T201
    main()
