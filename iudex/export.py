"""Esportazione di risultati e sentenze in CSV, JSON e Markdown."""

from __future__ import annotations

import csv
import io
import json
import re

COLONNE = (
    "id",
    "archivio",
    "sezione",
    "sottosezione",
    "tipo",
    "numero",
    "anno",
    "data_decisione",
    "data_deposito",
    "ecli",
    "presidente",
    "relatore",
    "pdf",
)


def _senza_tag(testo: str | None) -> str:
    return re.sub(r"<[^>]+>", "", testo or "")


INTESTAZIONI = (
    "FATTI DI CAUSA",
    "RAGIONI DELLA DECISIONE",
    "RITENUTO IN FATTO",
    "CONSIDERATO IN DIRITTO",
    "MOTIVI DELLA DECISIONE",
    "SVOLGIMENTO DEL PROCESSO",
    "FATTO E DIRITTO",
    "RILEVATO CHE",
    "CONSIDERATO CHE",
    "RITENUTO CHE",
    "OSSERVA",
)
_RE_PQM = re.compile(r"\s*P\.\s?Q\.\s?M\.?\s*")
_RE_INTESTAZIONI = re.compile(r"\s*(" + "|".join(re.escape(i) for i in INTESTAZIONI) + r")\s*")
_RE_PUNTI = re.compile(r"(?<=[.;:])\s*(\d{1,2}(?:\.\d{1,2}){0,3}\.)\s+(?=[A-ZÈÀÌÒÙ])")
_RE_PARTI = re.compile(r"\s*(-\s?(?:contro)?ricorrent[ei]\s?-|-\s?intimat[oi]\s?-)\s*")


def paragrafa(testo: str | None) -> tuple[str, int | None]:
    """Ricostruisce i paragrafi di un testo OCR privo di a capo.

    Inserisce un a capo doppio prima delle intestazioni classiche dei provvedimenti, dei
    punti numerati ("2.", "2.1.") che seguono un segno di punteggiatura e delle parti
    processuali; "P.Q.M." diventa un'intestazione. Restituisce il testo e la posizione del
    dispositivo (indice di "P.Q.M."), se presente.
    """
    if not testo:
        return "", None
    t = testo
    if "\n" not in t:
        t = _RE_INTESTAZIONI.sub(lambda m: f"\n\n{m.group(1)}\n\n", t)
        t = _RE_PARTI.sub(lambda m: f"\n{m.group(1)}\n", t)
        t = _RE_PUNTI.sub(lambda m: f"\n\n{m.group(1)} ", t)
    t = _RE_PQM.sub("\n\nP.Q.M.\n\n", t)
    t = re.sub(r"[ \t]*\n[ \t]*", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    posizione = t.find("P.Q.M.")
    return t, (posizione if posizione >= 0 else None)


def estremi_brevi(doc: dict) -> str:
    """``Cass. civ., Sez. Lavoro, Ordinanza n. 26349/2026``."""
    archivio = "civ." if doc.get("kind") == "snciv" else "pen."
    sezione = doc.get("sezione") or ""
    sezione = f"Sez. {sezione}, " if sezione else ""
    tipo = doc.get("tipo") or ""
    return f"Cass. {archivio}, {sezione}{tipo} n. {doc.get('numero')}/{doc.get('anno')}"


def risultati_csv(documenti: list[dict]) -> str:
    buffer = io.StringIO()
    scrittore = csv.writer(buffer, delimiter=";", lineterminator="\n")
    scrittore.writerow([*COLONNE, "frammenti"])
    for doc in documenti:
        scrittore.writerow(
            [doc.get(c, "") or "" for c in COLONNE]
            + [" | ".join(_senza_tag(f) for f in doc.get("frammenti", []))]
        )
    return buffer.getvalue()


def risultati_json(risposta: dict) -> str:
    return json.dumps(risposta, ensure_ascii=False, indent=1)


def risultati_markdown(risposta: dict) -> str:
    righe = [
        f"# Ricerca SentenzeWeb: {risposta.get('descrizione') or risposta.get('query')}",
        "",
        f"Risultati: {risposta.get('trovati')} (pagina {risposta.get('pagina')}, "
        f"{len(risposta.get('documenti', []))} mostrati). Fonte: Corte Suprema di Cassazione, "
        "SentenzeWeb.",
        "",
    ]
    for doc in risposta.get("documenti", []):
        righe.append(f"## {estremi_brevi(doc)}" + (f" ({doc['ecli']})" if doc.get("ecli") else ""))
        righe.append(
            f"Udienza {doc.get('data_decisione') or '?'}, "
            f"deposito {doc.get('data_deposito') or '?'}. "
            f"Presidente {doc.get('presidente') or '?'}, relatore {doc.get('relatore') or '?'}."
        )
        if doc.get("pdf"):
            righe.append(f"PDF: {doc['pdf']}")
        for frammento in doc.get("frammenti", []):
            righe.append(f"> … {_senza_tag(frammento).strip()} …")
        righe.append("")
    return "\n".join(righe)


def sentenza_markdown(doc: dict, testo: str | None) -> str:
    righe = [
        f"# {estremi_brevi(doc)}",
        "",
        f"- ECLI: {doc.get('ecli') or '-'}",
        f"- Udienza: {doc.get('data_decisione') or '-'}",
        f"- Deposito: {doc.get('data_deposito') or '-'}",
        f"- Presidente: {doc.get('presidente') or '-'}",
        f"- Relatore: {doc.get('relatore') or '-'}",
        f"- PDF: {doc.get('pdf') or '-'}",
        "",
        "Fonte: Corte Suprema di Cassazione, SentenzeWeb (www.italgiure.giustizia.it/sncass).",
        "",
        "---",
        "",
        paragrafa(_senza_tag(testo))[0] if testo else "(testo non disponibile)",
    ]
    return "\n".join(righe)


def sentenza_json(doc: dict, testo: str | None) -> str:
    dati = {**doc, "testo": _senza_tag(testo) if testo else None}
    return json.dumps(dati, ensure_ascii=False, indent=1)
