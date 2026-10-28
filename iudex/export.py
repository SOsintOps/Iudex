"""Esportazione di risultati, sentenze, diario e sentenze consultate."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
import zipfile

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


# --- diario e sentenze consultate ----------------------------------------------------------

COLONNE_DIARIO = (
    "id",
    "quando",
    "giorno",
    "tipo",
    "testo",
    "riferimenti",
    "filtri",
    "ordinamento",
    "pagina",
    "trovati",
    "permalink",
    "id_sentenza",
    "estremi",
)


def _ora_locale(quando: float | None) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(quando)) if quando else ""


def _estremi_voce(voce: dict) -> str:
    doc = voce.get("documento")
    return estremi_brevi(doc) if doc else ""


def diario_jsonl(voci: list[dict]) -> str:
    """Una riga JSON per voce, dalla più vecchia alla più recente."""
    righe = []
    for voce in reversed(voci):
        d = {k: v for k, v in voce.items() if k != "documento"}
        d["quando_locale"] = _ora_locale(voce.get("quando"))
        d["estremi"] = _estremi_voce(voce) or None
        righe.append(json.dumps(d, ensure_ascii=False))
    return "\n".join(righe) + ("\n" if righe else "")


def diario_csv(voci: list[dict]) -> str:
    buffer = io.StringIO()
    scrittore = csv.writer(buffer, delimiter=";", lineterminator="\n")
    scrittore.writerow(COLONNE_DIARIO)
    for voce in reversed(voci):
        riga = dict(voce)
        riga["quando"] = _ora_locale(voce.get("quando"))
        riga["filtri"] = json.dumps(voce.get("filtri") or {}, ensure_ascii=False)
        riga["estremi"] = _estremi_voce(voce)
        scrittore.writerow(["" if riga.get(c) is None else riga.get(c) for c in COLONNE_DIARIO])
    return buffer.getvalue()


def _testo_grezzo(grezzo: dict) -> str:
    valore = grezzo.get("ocrfull") or grezzo.get("testoocr") or grezzo.get("ocr") or ""
    if isinstance(valore, list):
        valore = "\n".join(str(v) for v in valore)
    return paragrafa(_senza_tag(str(valore)))[0]


# --- FollowTheMoney ------------------------------------------------------------------------

# Prefisso degli id, come ``make_entity_id(*parti, key_prefix=...)`` di followthemoney: SHA-1
# del prefisso e delle parti. Lo stesso magistrato ha lo stesso id in tutte le sentenze.
PREFISSO_FTM = "iudex"
EDITORE = "Corte Suprema di Cassazione, SentenzeWeb"
ARCHIVI_FTM = {"snciv": "civile", "snpen": "penale"}


def id_ftm(*parti: str) -> str:
    digest = hashlib.sha1(PREFISSO_FTM.encode("utf-8"))  # noqa: S324 - id, non sicurezza
    for parte in parti:
        digest.update(str(parte).encode("utf-8"))
    return digest.hexdigest()


def _entita(id_: str, schema: str, proprieta: dict) -> dict:
    """Un'entità FtM: id, schema e proprietà sempre in liste, senza valori vuoti."""
    pulite = {}
    for nome, valori in proprieta.items():
        if not isinstance(valori, list | tuple):
            valori = [valori]
        valori = [str(v) for v in valori if v not in (None, "")]
        if valori:
            pulite[nome] = list(dict.fromkeys(valori))
    return {"id": id_, "schema": schema, "properties": pulite}


def entita_ftm(id_sentenza: str, doc: dict, grezzo: dict, nota: str | None = None) -> list[dict]:
    """Le entità FollowTheMoney di una sentenza consultata.

    - ``CourtCase``: il provvedimento (estremi, archivio, sezione, ECLI come nome alternativo,
      materia e norme citate come parole chiave, dispositivo come sintesi);
    - ``Document``: il testo integrale con le date di decisione e di deposito, collegato al
      ``CourtCase`` con la proprietà ``proof``;
    - ``Person`` e ``CourtCaseParty`` per presidente e relatore (campi strutturati del CED).

    Le parti del giudizio non vengono estratte: stanno solo nel testo, in forma non
    uniforme, e sono dati personali; restano leggibili nel ``bodyText``.
    """
    id_caso = id_ftm("caso", id_sentenza)
    id_documento = id_ftm("documento", id_sentenza)
    estremi = estremi_brevi(doc)
    sezione = doc.get("sezione")
    corte = "Corte Suprema di Cassazione" + (f", Sezione {sezione}" if sezione else "")
    riferimenti = [r.get("testo") for r in doc.get("riferimenti_normativi") or [] if r.get("testo")]
    entita = [
        _entita(
            id_documento,
            "Document",
            {
                "fileName": (doc.get("filename") or f"{id_sentenza}.txt").rsplit("/", 1)[-1],
                "title": estremi,
                "bodyText": _testo_grezzo(grezzo),
                "authoredAt": doc.get("data_decisione"),
                "publishedAt": doc.get("data_deposito"),
                "date": doc.get("data_deposito"),
                "language": "ita",
                "publisher": EDITORE,
                "sourceUrl": doc.get("pdf"),
            },
        ),
        _entita(
            id_caso,
            "CourtCase",
            {
                "name": estremi,
                "caseNumber": f"{doc.get('numero')}/{doc.get('anno')}",
                "court": corte,
                "category": ARCHIVI_FTM.get(grezzo.get("kind"), doc.get("archivio")),
                "type": doc.get("tipo"),
                "alias": doc.get("ecli"),
                "keywords": [*(doc.get("materia") or []), *riferimenti],
                "summary": doc.get("massima"),
                "notes": nota,
                "country": "it",
                "publisher": EDITORE,
                "sourceUrl": doc.get("pdf"),
                "proof": id_documento,
            },
        ),
    ]
    for ruolo, nome in (("presidente", doc.get("presidente")), ("relatore", doc.get("relatore"))):
        if not nome:
            continue
        id_persona = id_ftm("persona", nome.strip().upper())
        entita.append(_entita(id_persona, "Person", {"name": nome.strip()}))
        entita.append(
            _entita(
                id_ftm("parte", id_sentenza, ruolo, id_persona),
                "CourtCaseParty",
                {"party": id_persona, "case": id_caso, "role": ruolo},
            )
        )
    return entita


def consultate_ftm(voci) -> str:
    """Entità di tutte le sentenze consultate in JSON a righe (formato ``.ftm`` di ``ftm``).

    ``voci``: tuple ``(id_sentenza, documento, grezzo, nota)``. Le persone comuni a più
    sentenze compaiono una volta sola.
    """
    viste: set[str] = set()
    righe = []
    for id_sentenza, doc, grezzo, nota in voci:
        for e in entita_ftm(id_sentenza, doc, grezzo, nota):
            if e["id"] in viste:
                continue
            viste.add(e["id"])
            righe.append(json.dumps(e, ensure_ascii=False))
    return "\n".join(righe) + ("\n" if righe else "")


def consultate_zip(coppie) -> bytes:
    """Archivio zip con, per ogni sentenza consultata, ``<id>.json`` (risposta intera del
    server) e ``<id>.txt`` (solo il testo, con i paragrafi ricostruiti)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for id_sentenza, grezzo in coppie:
            zf.writestr(f"{id_sentenza}.json", json.dumps(grezzo, ensure_ascii=False, indent=1))
            zf.writestr(f"{id_sentenza}.txt", _testo_grezzo(grezzo))
    return buffer.getvalue()


# --- database delle ricerche -----------------------------------------------------------------

# Il BOM fa riconoscere a Excel la codifica UTF-8 (accenti) aprendo il CSV con un doppio clic.
BOM = "\ufeff"
# Versione del formato del pacchetto, letta dall'importazione.
FORMATO_PACCHETTO = 1

COLONNE_RICERCHE = (
    "id",
    "prima_volta",
    "ultima_volta",
    "volte",
    "descrizione",
    "testo",
    "riferimenti",
    "filtri",
    "ordinamento",
    "righe",
    "trovati",
    "macchina",
    "permalink",
)
COLONNE_ESECUZIONI = (
    "id",
    "quando",
    "macchina",
    "origine",
    "descrizione",
    "pagina",
    "righe",
    "trovati",
    "dalla_cache",
    "ricerca",
    "permalink",
    "uid",
)
COLONNE_RISULTATI = (
    "id_esecuzione",
    "quando",
    "macchina",
    "descrizione",
    "pagina",
    "posizione",
    "id_sentenza",
    "estremi",
    "data_deposito",
    "ecli",
    "consultata",
    "ultima_consultazione",
    "pdf_salvato",
    "ricerca",
)
COLONNE_CONSULTAZIONI = (
    "id",
    "quando",
    "macchina",
    "tipo",
    "id_sentenza",
    "estremi",
    "da_ricerca",
    "uid",
)


def _csv(colonne: tuple[str, ...], righe: list[dict]) -> str:
    buffer = io.StringIO()
    scrittore = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    scrittore.writerow(colonne)
    for riga in righe:
        scrittore.writerow(["" if riga.get(c) is None else riga.get(c) for c in colonne])
    return BOM + buffer.getvalue()


def _tabelle_ricerche(dati: dict, descrivi) -> dict[str, list[dict]]:
    """Le righe dei quattro CSV, con date leggibili, estremi per esteso e il nome della
    macchina. ``descrivi`` trasforma un permalink nella descrizione della ricerca."""
    nomi = {k: v["nome"] for k, v in dati["macchine"].items()}
    esecuzione_macchina = {e["id"]: e.get("macchina") for e in dati["esecuzioni"]}
    pdf_salvati = {p["id_sentenza"] for p in dati["pdf"]}
    ultime: dict[str, float] = {}
    for c in dati["consultazioni"]:
        ultime[c["id_sentenza"]] = c["quando"]
    ricerche = [
        {
            **r,
            "prima_volta": _ora_locale(r.get("prima_volta")),
            "ultima_volta": _ora_locale(r.get("quando")),
            "descrizione": descrivi(r["permalink"]),
            "filtri": json.dumps(r.get("filtri") or {}, ensure_ascii=False),
            "macchina": nomi.get(r.get("macchina"), r.get("macchina")),
        }
        for r in dati["ricerche"]
    ]
    esecuzioni = [
        {
            **e,
            "quando": _ora_locale(e["quando"]),
            "dalla_cache": "sì" if e["dalla_cache"] else "no",
            "macchina": nomi.get(e.get("macchina"), e.get("macchina")),
        }
        for e in dati["esecuzioni"]
    ]
    risultati = [
        {
            **r,
            "quando": _ora_locale(r["quando"]),
            "macchina": nomi.get(esecuzione_macchina.get(r["id_esecuzione"]), ""),
            "estremi": estremi_brevi(r["estremi"]),
            "data_deposito": r["estremi"].get("data_deposito"),
            "ecli": r["estremi"].get("ecli"),
            "consultata": "sì" if r["id_sentenza"] in ultime else "no",
            "ultima_consultazione": _ora_locale(ultime.get(r["id_sentenza"])),
            "pdf_salvato": "sì" if r["id_sentenza"] in pdf_salvati else "no",
        }
        for r in dati["risultati"]
    ]
    consultazioni = [
        {
            "id": c["id"],
            "uid": c.get("uid"),
            "quando": _ora_locale(c["quando"]),
            "macchina": nomi.get(c.get("macchina"), c.get("macchina")),
            "tipo": "testo" if c["tipo"] == "sentenza" else "pdf",
            "id_sentenza": c["id_sentenza"],
            "estremi": estremi_brevi(c["documento"]) if c.get("documento") else "",
            "da_ricerca": descrivi(c["permalink"]) if c.get("permalink") else "",
        }
        for c in dati["consultazioni"]
    ]
    return {
        "ricerche": ricerche,
        "esecuzioni": esecuzioni,
        "risultati": risultati,
        "consultazioni": consultazioni,
    }


def ricerche_csv(dati: dict, descrivi) -> dict[str, str]:
    """``{nome del file: contenuto}`` dei quattro CSV, apribili in Excel."""
    t = _tabelle_ricerche(dati, descrivi)
    return {
        "ricerche.csv": _csv(COLONNE_RICERCHE, t["ricerche"]),
        "esecuzioni.csv": _csv(COLONNE_ESECUZIONI, t["esecuzioni"]),
        "risultati.csv": _csv(COLONNE_RISULTATI, t["risultati"]),
        "consultazioni.csv": _csv(COLONNE_CONSULTAZIONI, t["consultazioni"]),
    }


# Record del JSONL, nell'ordine in cui l'importazione li legge: le macchine e le ricerche prima
# delle esecuzioni, le esecuzioni prima dei loro risultati.
TIPI_JSONL = (
    ("macchina", "macchine"),
    ("ricerca", "ricerche"),
    ("esecuzione", "esecuzioni"),
    ("risultato", "risultati"),
    ("diario", "diario"),
    ("consultata", "consultate"),
    ("pdf", "pdf"),
)


def ricerche_jsonl(dati: dict, descrivi) -> str:
    """Un record JSON per riga con il campo ``record`` (macchina, ricerca, esecuzione,
    risultato, diario, consultata, pdf); date in secondi (``quando``) e locali
    (``quando_locale``). La prima riga descrive il pacchetto."""
    righe = [
        json.dumps(
            {"record": "pacchetto", "app": "iudex", "formato": FORMATO_PACCHETTO},
            ensure_ascii=False,
        )
    ]
    for tipo, chiave in TIPI_JSONL:
        voci = dati[chiave]
        if tipo == "macchina":
            voci = [{"id": k, "nome": v["nome"]} for k, v in voci.items()]
        for voce in voci:
            record = {"record": tipo, **voce}
            if tipo == "ricerca":
                record["descrizione"] = descrivi(voce["permalink"])
            if "quando" in voce:
                record["quando_locale"] = _ora_locale(voce.get("quando"))
            righe.append(json.dumps(record, ensure_ascii=False))
    return "\n".join(righe) + "\n"


LEGGIMI_RICERCHE = """Iudex: database delle ricerche

ricerche.csv       una riga per ricerca (quante volte, la prima e l'ultima, la macchina)
esecuzioni.csv     ogni pagina di risultati vista, anche dalla cache, con la macchina
risultati.csv      le sentenze mostrate in ogni esecuzione: da quale ricerca è uscita ognuna
consultazioni.csv  le aperture del testo e del PDF, con la ricerca di provenienza
ricerche.jsonl     tutto quanto sopra in JSON, un record per riga (campo "record")
consultate/        la risposta intera del server per ogni sentenza consultata, <id>.json
testi/             il testo delle sentenze consultate, <id>.txt
pdf/               i PDF salvati, <id>.pdf

I CSV usano il punto e virgola e la codifica UTF-8 con BOM: si aprono in Excel con un doppio
clic. Il pacchetto si importa in un altro Iudex (scheda Impostazioni, Importa): i dati si
uniscono a quelli presenti senza duplicati.
"""


def ricerche_zip(dati: dict, descrivi, pdf_files: dict[str, object], consultate) -> bytes:
    """Pacchetto con i CSV, il JSONL, i PDF salvati (``{id: percorso}``) e, per ogni
    sentenza consultata (tuple ``(id, documento, grezzo)``), la risposta intera e il testo."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("LEGGIMI.txt", LEGGIMI_RICERCHE)
        for nome, contenuto in ricerche_csv(dati, descrivi).items():
            zf.writestr(nome, contenuto)
        zf.writestr("ricerche.jsonl", ricerche_jsonl(dati, descrivi))
        for id_sentenza, documento, grezzo in consultate:
            zf.writestr(
                f"consultate/{id_sentenza}.json",
                json.dumps({"documento": documento, "grezzo": grezzo}, ensure_ascii=False),
            )
            zf.writestr(f"testi/{id_sentenza}.txt", _testo_grezzo(grezzo))
        for id_sentenza, percorso in pdf_files.items():
            # I PDF sono già compressi: si archiviano senza ricomprimerli.
            zf.write(percorso, f"pdf/{id_sentenza}.pdf", compress_type=zipfile.ZIP_STORED)
    return buffer.getvalue()
