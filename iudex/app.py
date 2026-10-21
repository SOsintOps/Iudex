"""Server locale di Iudex: API JSON per l'interfaccia e pagine statiche."""

from __future__ import annotations

import json
import logging
import math
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__, export
from .cache import Archivio
from .client import ClientSentenzeWeb, ErroreRemoto
from .config import impostazioni
from .query import (
    CAMPI_FACET,
    ORDINAMENTI,
    costruisci_query,
    formatta_riferimenti,
    normalizza_documento,
    normalizza_facet,
    parametri_dettaglio,
    parametri_ricerca,
)

log = logging.getLogger("iudex.app")
STATICA = Path(__file__).resolve().parent / "static"
SECONDI_GIORNO = 86400
HEADER_INTERFACCIA = "x-iudex"
PAGINE_STATICHE = {"versioni", "faq", "software-simili"}
# I valori di "materia" contengono spazi e virgole: nel permalink usano un separatore diverso.
SEPARATORI = {"materia": ";"}


@asynccontextmanager
async def ciclo_vita(app: FastAPI):
    app.state.archivio = Archivio(impostazioni.percorso_db)
    app.state.client = ClientSentenzeWeb(impostazioni)
    log.info(
        "Iudex %s in ascolto su http://%s:%s/", __version__, impostazioni.host, impostazioni.porta
    )
    yield
    await app.state.client.chiudi()
    app.state.archivio.chiudi()


app = FastAPI(
    title="Iudex", version=__version__, lifespan=ciclo_vita, docs_url=None, redoc_url=None
)
app.mount("/static", StaticFiles(directory=str(STATICA)), name="static")


@app.middleware("http")
async def solo_interfaccia(request: Request, call_next):
    """Le API rispondono solo alla pagina di Iudex.

    L'header personalizzato obbliga i browser al preflight CORS, che il server non
    autorizza: una pagina di un altro sito non può usare Iudex per interrogare la Corte.
    """
    if request.url.path.startswith("/api/") and request.headers.get(HEADER_INTERFACCIA) != "1":
        return JSONResponse(
            status_code=403,
            content={"errore": "richiesta non proveniente dall'interfaccia di Iudex"},
        )
    return await call_next(request)


@app.exception_handler(ErroreRemoto)
async def _errore_remoto(_: Request, exc: ErroreRemoto) -> JSONResponse:
    return JSONResponse(status_code=502, content={"errore": str(exc), "stato_remoto": exc.stato})


@app.get("/", include_in_schema=False)
async def pagina() -> FileResponse:
    return FileResponse(STATICA / "index.html")


@app.get("/{nome}.html", include_in_schema=False)
async def pagina_statica(nome: str) -> FileResponse:
    if nome not in PAGINE_STATICHE:
        raise HTTPException(404)
    return FileResponse(STATICA / f"{nome}.html")


# --- funzioni di servizio ------------------------------------------------------------------


def _lista(campo: str, valore: str | None) -> list[str]:
    sep = SEPARATORI.get(campo, ",")
    return [v.strip() for v in (valore or "").split(sep) if v.strip()]


def _filtri(kind, tipoprov, szdec, anno, ssz, materia) -> dict[str, list[str]]:
    grezzi = {
        "kind": kind,
        "tipoprov": tipoprov,
        "szdec": szdec,
        "anno": anno,
        "ssz": ssz,
        "materia": materia,
    }
    return {
        campo: _lista(campo, grezzi[campo]) for campo in CAMPI_FACET if _lista(campo, grezzi[campo])
    }


def _permalink(testo, rif, filtri, ordina, righe, pagina) -> str:
    coppie: list[tuple[str, str]] = []
    if testo:
        coppie.append(("testo", testo))
    if rif:
        coppie.append(("rif", rif))
    for campo in CAMPI_FACET:
        if filtri.get(campo):
            coppie.append((campo, SEPARATORI.get(campo, ",").join(filtri[campo])))
    if ordina != "pubblicazione":
        coppie.append(("ordina", ordina))
    if righe != impostazioni.righe_predefinite:
        coppie.append(("righe", str(righe)))
    if pagina > 1:
        coppie.append(("pagina", str(pagina)))
    return urlencode(coppie)


def _da_permalink(permalink: str) -> dict:
    """Riporta un permalink ai parametri di ricerca (usato per le ricerche salvate)."""
    p = {k: v[0] for k, v in parse_qs(permalink, keep_blank_values=True).items()}
    return {
        "testo": p.get("testo") or None,
        "rif": p.get("rif") or None,
        "filtri": _filtri(
            p.get("kind"),
            p.get("tipoprov"),
            p.get("szdec"),
            p.get("anno"),
            p.get("ssz"),
            p.get("materia"),
        ),
        "ordina": p.get("ordina", "pubblicazione"),
    }


def _descrizione(testo, rif, filtri) -> str:
    parti = []
    if testo:
        parti.append(testo)
    if rif:
        parti.append(f"rif. {rif}")
    for campo, valori in filtri.items():
        parti.append(f"{campo}={','.join(valori)}")
    return " · ".join(parti) or "tutte le sentenze"


async def _riferimento_normalizzato(request: Request, rif: str | None) -> str | None:
    if not rif or not rif.strip():
        return None
    chiave = "rif:" + " ".join(rif.lower().split())
    archivio: Archivio = request.app.state.archivio
    salvato = archivio.leggi_estremi(chiave, impostazioni.ttl_estremi_giorni * SECONDI_GIORNO)
    if salvato is not None:
        return salvato
    client: ClientSentenzeWeb = request.app.state.client
    normalizzato = await client.normalizza_riferimento(rif.strip())
    archivio.scrivi_estremi(chiave, normalizzato)
    return normalizzato


async def _esegui_ricerca(request: Request, testo, rif, filtri, ordina, pagina, righe) -> dict:
    archivio: Archivio = request.app.state.archivio
    client: ClientSentenzeWeb = request.app.state.client
    righe = max(1, min(righe, impostazioni.righe_massime))
    pagina = max(1, pagina)
    if ordina not in ORDINAMENTI:
        ordina = "pubblicazione"
    inizio = (pagina - 1) * righe
    rif_norm = await _riferimento_normalizzato(request, rif)
    q, hl_q = costruisci_query(testo, rif_norm, filtri)
    chiave = json.dumps([q, hl_q, inizio, righe, ordina])
    risposta = archivio.leggi_risposta(chiave, impostazioni.ttl_ricerche)
    dalla_cache = risposta is not None
    if risposta is None:
        # Il sito indica l'archivio nel suffisso dell'URL quando è selezionato uno solo.
        kind = filtri["kind"][0] if len(filtri.get("kind", [])) == 1 else None
        dati = await client.cerca(parametri_ricerca(q, hl_q, inizio, righe, ordina), kind)
        evidenziazioni = dati.get("highlighting", {})
        documenti = [normalizza_documento(d, evidenziazioni) for d in dati["response"]["docs"]]
        risposta = {
            "query": q,
            "evidenzia": hl_q,
            "trovati": dati["response"]["numFound"],
            "documenti": documenti,
            "facet": normalizza_facet(dati.get("facet_counts", {}).get("facet_fields", {})),
            "tempo_solr_ms": dati.get("responseHeader", {}).get("QTime"),
        }
        archivio.scrivi_risposta(chiave, risposta)
    risposta = dict(risposta)
    risposta.update(
        {
            "pagina": pagina,
            "righe": righe,
            "inizio": inizio,
            "ordinamento": ordina,
            "testo": testo,
            "riferimenti": rif,
            "riferimenti_normalizzati": rif_norm,
            "filtri": filtri,
            "descrizione": _descrizione(testo, rif, filtri),
            "permalink": _permalink(testo, rif, filtri, ordina, righe, pagina),
            "dalla_cache": dalla_cache,
        }
    )
    preferiti = archivio.id_preferiti()
    for doc in risposta["documenti"]:
        doc["preferito"] = doc["id"] in preferiti
    return risposta


# --- ricerca -------------------------------------------------------------------------------


@app.get("/api/cerca")
async def cerca(
    request: Request,
    testo: str | None = None,
    rif: str | None = None,
    kind: str | None = None,
    tipoprov: str | None = None,
    szdec: str | None = None,
    anno: str | None = None,
    ssz: str | None = None,
    materia: str | None = None,
    ordina: str = "pubblicazione",
    pagina: int = Query(1, ge=1),
    righe: int = Query(impostazioni.righe_predefinite, ge=1, le=impostazioni.righe_massime),
) -> dict:
    filtri = _filtri(kind, tipoprov, szdec, anno, ssz, materia)
    risposta = await _esegui_ricerca(request, testo, rif, filtri, ordina, pagina, righe)
    if pagina == 1:
        request.app.state.archivio.registra_ricerca(
            testo=testo,
            riferimenti=rif,
            filtri=filtri,
            ordinamento=risposta["ordinamento"],
            righe=risposta["righe"],
            trovati=risposta["trovati"],
            permalink=_permalink(testo, rif, filtri, risposta["ordinamento"], risposta["righe"], 1),
        )
    return risposta


# --- sentenza ------------------------------------------------------------------------------


def _testo_unito(valore) -> str | None:
    if isinstance(valore, list):
        return "\n".join(str(v) for v in valore) or None
    return valore


async def _carica_sentenza(
    request: Request, id_sentenza: str, hl_q: str | None = None
) -> tuple[dict, str | None, str | None, bool]:
    """Restituisce (documento, testo, testo evidenziato dal server o None, dalla cache)."""
    archivio: Archivio = request.app.state.archivio
    chiave_hl = json.dumps(["hl", id_sentenza, hl_q]) if hl_q else None
    salvata = archivio.leggi_sentenza(id_sentenza)
    if salvata:
        marcato = None
        if chiave_hl:
            voce = archivio.leggi_risposta(chiave_hl, impostazioni.ttl_ricerche)
            marcato = voce.get("testo") if voce else None
        return salvata["documento"], salvata["testo"], marcato, True
    client: ClientSentenzeWeb = request.app.state.client
    dati = await client.dettaglio(parametri_dettaglio(id_sentenza, hl_q))
    docs = dati.get("response", {}).get("docs", [])
    if not docs:
        raise HTTPException(404, "sentenza non trovata")
    grezzo = docs[0]
    documento = normalizza_documento(grezzo)
    testo = _testo_unito(grezzo.get("ocrfull") or grezzo.get("testoocr") or grezzo.get("ocr"))
    documento["materia"] = grezzo.get("materia")
    documento["massima"] = _testo_unito(grezzo.get("ocrdis"))
    # Campi "rnc-*": riferimenti normativi citati nel provvedimento (indicizzati dal CED).
    rnc = {chiave[4:]: valore for chiave, valore in grezzo.items() if chiave.startswith("rnc-")}
    documento["riferimenti_normativi"] = formatta_riferimenti(rnc)
    archivio.scrivi_sentenza(id_sentenza, documento, testo)
    marcato = None
    if chiave_hl:
        marcato = _testo_unito(dati.get("highlighting", {}).get(id_sentenza, {}).get("ocr"))
        if marcato:
            archivio.scrivi_risposta(chiave_hl, {"testo": marcato})
    return documento, testo, marcato, False


@app.get("/api/sentenza/{id_sentenza}")
async def sentenza(request: Request, id_sentenza: str, evidenzia: str | None = None) -> dict:
    documento, testo, marcato, dalla_cache = await _carica_sentenza(
        request, id_sentenza, evidenzia or None
    )
    documento = dict(documento)
    documento["preferito"] = id_sentenza in request.app.state.archivio.id_preferiti()
    # Le sentenze salvate dalla 0.1.0 hanno i riferimenti ancora come liste grezze.
    if isinstance(documento.get("riferimenti_normativi"), dict):
        documento["riferimenti_normativi"] = formatta_riferimenti(
            documento["riferimenti_normativi"]
        )
    testo_paragrafato, posizione = export.paragrafa(testo)
    marcato_paragrafato = export.paragrafa(marcato)[0] if marcato else None
    return {
        "documento": documento,
        "testo": testo_paragrafato,
        "testo_evidenziato": marcato_paragrafato,
        "posizione_pqm": posizione,
        "dalla_cache": dalla_cache,
    }


@app.get("/api/pdf/{id_sentenza}")
async def pdf(request: Request, id_sentenza: str) -> RedirectResponse:
    documento, _, _, _ = await _carica_sentenza(request, id_sentenza)
    if not documento.get("pdf"):
        raise HTTPException(404, "PDF non disponibile")
    return RedirectResponse(documento["pdf"], status_code=307)


# --- riferimenti normativi (suggerimenti locali) --------------------------------------------


async def _lista_sigle(request: Request) -> list[tuple[str, str]]:
    archivio: Archivio = request.app.state.archivio
    ttl = impostazioni.ttl_estremi_giorni * SECONDI_GIORNO
    contenuto = archivio.leggi_estremi("lista", ttl)
    if contenuto is None:
        client: ClientSentenzeWeb = request.app.state.client
        contenuto = await client.lista_estremi()
        archivio.scrivi_estremi("lista", contenuto)
    coppie = []
    for riga in contenuto.splitlines():
        if "/" in riga:
            sigla, descrizione = riga.split("/", 1)
            coppie.append((sigla.strip(), descrizione.strip()))
    return coppie


@app.get("/api/estremi")
async def estremi(request: Request, q: str = Query("", max_length=80)) -> list[dict]:
    coppie = await _lista_sigle(request)
    chiave = q.strip().lower()
    if not chiave:
        return []
    trovate = [
        {"sigla": s, "descrizione": d}
        for s, d in coppie
        if chiave in s.lower() or chiave in d.lower()
    ]
    trovate.sort(key=lambda v: (not v["sigla"].lower().startswith(chiave), v["sigla"]))
    return trovate[:20]


# --- cronologia, ricerche salvate, preferiti --------------------------------------------------


@app.get("/api/cronologia")
async def cronologia(request: Request) -> list[dict]:
    return request.app.state.archivio.cronologia()


@app.delete("/api/cronologia")
async def svuota_cronologia(request: Request) -> dict:
    request.app.state.archivio.svuota_cronologia()
    return {"ok": True}


@app.delete("/api/cronologia/{id_ricerca}")
async def elimina_ricerca(request: Request, id_ricerca: int) -> dict:
    request.app.state.archivio.elimina_ricerca(id_ricerca)
    return {"ok": True}


@app.get("/api/salvate")
async def salvate(request: Request) -> list[dict]:
    return request.app.state.archivio.ricerche_salvate()


@app.post("/api/salvate")
async def salva(request: Request) -> dict:
    corpo = await request.json()
    nome = (corpo.get("nome") or "").strip()
    permalink = (corpo.get("permalink") or "").strip()
    if not nome or not permalink:
        raise HTTPException(400, "nome e permalink sono obbligatori")
    request.app.state.archivio.salva_ricerca(nome, permalink)
    return {"ok": True}


@app.delete("/api/salvate/{id_salvata}")
async def elimina_salvata(request: Request, id_salvata: int) -> dict:
    request.app.state.archivio.elimina_ricerca_salvata(id_salvata)
    return {"ok": True}


@app.post("/api/salvate/{id_salvata}/controlla")
async def controlla_salvata(request: Request, id_salvata: int) -> dict:
    """Riesegue una ricerca salvata (una richiesta) e segnala i provvedimenti nuovi."""
    archivio: Archivio = request.app.state.archivio
    salvata = archivio.ricerca_salvata(id_salvata)
    if not salvata:
        raise HTTPException(404, "ricerca salvata non trovata")
    p = _da_permalink(salvata["permalink"])
    risposta = await _esegui_ricerca(
        request, p["testo"], p["rif"], p["filtri"], "pubblicazione", 1, impostazioni.righe_massime
    )
    ids = [d["id"] for d in risposta["documenti"]]
    precedenti = salvata.get("ultimi_id")
    prima_volta = precedenti is None
    nuovi = [] if prima_volta else [d for d in risposta["documenti"] if d["id"] not in precedenti]
    archivio.aggiorna_controllo(id_salvata, risposta["trovati"], ids, len(nuovi))
    return {
        "prima_volta": prima_volta,
        "trovati": risposta["trovati"],
        "nuovi": nuovi,
        "dalla_cache": risposta["dalla_cache"],
    }


@app.get("/api/preferiti")
async def preferiti(request: Request) -> list[dict]:
    return request.app.state.archivio.preferiti()


@app.post("/api/preferiti")
async def aggiungi_preferito(request: Request) -> dict:
    corpo = await request.json()
    id_sentenza = corpo.get("id")
    estremi = corpo.get("estremi") or {}
    if not id_sentenza:
        raise HTTPException(400, "id mancante")
    request.app.state.archivio.aggiungi_preferito(id_sentenza, estremi, corpo.get("nota"))
    return {"ok": True}


@app.put("/api/preferiti/{id_sentenza}")
async def nota_preferito(request: Request, id_sentenza: str) -> dict:
    corpo = await request.json()
    nota = (corpo.get("nota") or "").strip() or None
    if not request.app.state.archivio.aggiorna_nota(id_sentenza, nota):
        raise HTTPException(404, "preferito non trovato")
    return {"ok": True, "nota": nota}


@app.delete("/api/preferiti/{id_sentenza}")
async def rimuovi_preferito(request: Request, id_sentenza: str) -> dict:
    request.app.state.archivio.rimuovi_preferito(id_sentenza)
    return {"ok": True}


# --- esportazione --------------------------------------------------------------------------


def _allegato(contenuto: str, nome: str, tipo: str) -> Response:
    return Response(
        content=contenuto.encode("utf-8"),
        media_type=f"{tipo}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@app.get("/api/export")
async def esporta(
    request: Request,
    formato: str = Query("csv", pattern="^(csv|json|md)$"),
    testo: str | None = None,
    rif: str | None = None,
    kind: str | None = None,
    tipoprov: str | None = None,
    szdec: str | None = None,
    anno: str | None = None,
    ssz: str | None = None,
    materia: str | None = None,
    ordina: str = "pubblicazione",
    pagina: int = Query(1, ge=1),
    righe: int = Query(impostazioni.righe_predefinite, ge=1, le=impostazioni.righe_massime),
    massimo: int | None = Query(None, ge=1, le=100),
) -> Response:
    """Esporta la pagina corrente oppure, con ``massimo``, i primi N risultati (al più 100)."""
    filtri = _filtri(kind, tipoprov, szdec, anno, ssz, materia)
    if massimo:
        per_pagina = min(impostazioni.righe_massime, massimo)
        risposta = None
        documenti: list[dict] = []
        for p in range(1, math.ceil(massimo / per_pagina) + 1):
            parziale = await _esegui_ricerca(request, testo, rif, filtri, ordina, p, per_pagina)
            risposta = risposta or parziale
            documenti.extend(parziale["documenti"])
            if len(documenti) >= parziale["trovati"] or len(documenti) >= massimo:
                break
        assert risposta is not None
        risposta = dict(risposta, documenti=documenti[:massimo], pagina=1, righe=len(documenti))
    else:
        risposta = await _esegui_ricerca(request, testo, rif, filtri, ordina, pagina, righe)
    marca = time.strftime("%Y%m%d-%H%M%S")
    if formato == "csv":
        return _allegato(
            export.risultati_csv(risposta["documenti"]), f"iudex-{marca}.csv", "text/csv"
        )
    if formato == "json":
        return _allegato(export.risultati_json(risposta), f"iudex-{marca}.json", "application/json")
    return _allegato(export.risultati_markdown(risposta), f"iudex-{marca}.md", "text/markdown")


@app.get("/api/export/sentenza/{id_sentenza}")
async def esporta_sentenza(
    request: Request, id_sentenza: str, formato: str = Query("md", pattern="^(json|md)$")
) -> Response:
    documento, testo, _, _ = await _carica_sentenza(request, id_sentenza)
    if formato == "json":
        return _allegato(
            export.sentenza_json(documento, testo), f"{id_sentenza}.json", "application/json"
        )
    return _allegato(
        export.sentenza_markdown(documento, testo), f"{id_sentenza}.md", "text/markdown"
    )


# --- cache e stato -------------------------------------------------------------------------


@app.delete("/api/cache")
async def svuota_cache(request: Request) -> dict:
    return {"ok": True, "rimosse": request.app.state.archivio.svuota_risposte()}


@app.delete("/api/cache/sentenze")
async def svuota_sentenze(request: Request) -> dict:
    return {"ok": True, "rimosse": request.app.state.archivio.svuota_sentenze()}


@app.get("/api/stato")
async def stato(request: Request) -> dict:
    client: ClientSentenzeWeb = request.app.state.client
    archivio: Archivio = request.app.state.archivio
    return {
        "versione": __version__,
        "chiamate_remote": client.stat.chiamate,
        "intervallo_minimo_s": impostazioni.intervallo_minimo,
        "sentenze_in_cache": archivio.conta_sentenze(),
        "risposte_in_cache": archivio.conta_risposte(),
        "percorso_dati": str(impostazioni.percorso_db),
        "registro": [
            {
                "quando": time.strftime("%H:%M:%S", time.localtime(v.quando)),
                "tipo": v.tipo,
                "stato": v.stato,
                "durata_ms": v.durata_ms,
                "dettaglio": v.dettaglio,
            }
            for v in list(client.stat.registro)[-20:]
        ],
    }
