"""Server locale di Iudex: API JSON per l'interfaccia e pagine statiche."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, export, preferenze
from .autonoma import aggiornamenti, backup
from .autonoma.cartelle import congelata
from .autonoma.server import aggiungi_health
from .cache import Archivio
from .client import ClientSentenzeWeb, ErroreRemoto
from .config import URL_AGGIORNAMENTI, impostazioni
from .impronte import CODICI
from .query import (
    CAMPI_FACET,
    ETICHETTE_SEGNALI,
    ORDINAMENTI,
    SEGNALI,
    costruisci_query,
    formatta_riferimenti,
    normalizza_documento,
    normalizza_facet,
    normalizza_segnali,
    parametri_dettaglio,
    parametri_ricerca,
)

log = logging.getLogger("iudex.app")
STATICA = Path(__file__).resolve().parent / "static"
SECONDI_GIORNO = 86400
HEADER_INTERFACCIA = "x-iudex"
PAGINE_STATICHE = {"guida", "faq", "versioni", "software-simili", "licenza"}
# I valori di "materia" contengono spazi e virgole: nel permalink usano un separatore diverso.
SEPARATORI = {"materia": ";"}


HEADERS_HOST_VALIDI = {"127.0.0.1", "localhost", "testserver"}


async def _controlla_aggiornamenti(app: FastAPI) -> None:
    try:
        app.state.aggiornamento = await aggiornamenti.controlla(URL_AGGIORNAMENTI, __version__)
        if app.state.aggiornamento["disponibile"]:
            log.info("disponibile Iudex %s", app.state.aggiornamento["versione"])
    except aggiornamenti.ErroreAggiornamento as exc:
        log.info("controllo degli aggiornamenti non riuscito: %s", exc)


@asynccontextmanager
async def ciclo_vita(app: FastAPI):
    app.state.archivio = Archivio(impostazioni.percorso_db)
    app.state.client = ClientSentenzeWeb(impostazioni)
    app.state.sigle = None
    # Le voci di cache scadute non servono più: si tolgono all'avvio (diario e sentenze
    # consultate restano).
    rimosse = app.state.archivio.pulisci_scadute(
        impostazioni.ttl_ricerche, impostazioni.ttl_estremi_giorni * SECONDI_GIORNO
    )
    if rimosse:
        log.info("cache: %d voci scadute rimosse", rimosse)
    # Copia di sicurezza settimanale in backup/ (le ultime otto).
    try:
        backup.se_serve(
            app.state.archivio.copia_di_sicurezza, impostazioni.cartella_dati / "backup", "iudex"
        )
    except Exception as exc:  # noqa: BLE001 - un backup mancato non ferma l'avvio
        log.warning("copia di sicurezza non riuscita: %s", exc)
    app.state.aggiornamento = None
    controlla = impostazioni.aggiornamenti == "1" or (
        impostazioni.aggiornamenti != "0" and congelata()
    )
    if controlla:
        app.state.controllo_aggiornamenti = asyncio.create_task(_controlla_aggiornamenti(app))
    # Un valore sbagliato di IUDEX_IMPRONTA ferma l'avvio con il messaggio dei codici ammessi.
    log.info("identità dichiarata oggi: %s", app.state.client.impronta_corrente().nome)
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
aggiungi_health(app, "iudex", __version__)


@app.middleware("http")
async def solo_interfaccia(request: Request, call_next):
    """Le API rispondono solo alla pagina di Iudex.

    L'header personalizzato obbliga i browser al preflight CORS, che il server non
    autorizza; il controllo sull'Host impedisce anche il DNS rebinding.
    """
    host = (request.headers.get("host") or "").split(":")[0].lower()
    host_consentiti = HEADERS_HOST_VALIDI | {impostazioni.host.lower()}
    if host and host not in host_consentiti:
        return JSONResponse(status_code=403, content={"errore": "host non autorizzato"})
    if request.url.path.startswith("/api/") and request.headers.get(HEADER_INTERFACCIA) != "1":
        return JSONResponse(
            status_code=403,
            content={"errore": "richiesta non proveniente dall'interfaccia di Iudex"},
        )
    return await call_next(request)


@app.exception_handler(ErroreRemoto)
async def _errore_remoto(_: Request, exc: ErroreRemoto) -> JSONResponse:
    stato = 503 if exc.stato in (403, 429) else 502
    return JSONResponse(status_code=stato, content={"errore": str(exc), "stato_remoto": exc.stato})


@app.exception_handler(RequestValidationError)
async def _richiesta_non_valida(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Solo campo e messaggio: la documentazione di FastAPI sconsiglia di restituire str(exc).
    dettagli = "; ".join(
        f"{'.'.join(str(p) for p in e.get('loc', ()) if p != 'body') or 'corpo'}: {e.get('msg')}"
        for e in exc.errors()
    )
    return JSONResponse(status_code=422, content={"errore": f"dati non validi ({dettagli})"})


@app.exception_handler(Exception)
async def _errore_interno(_: Request, exc: Exception) -> JSONResponse:
    # Gestito da ServerErrorMiddleware: la risposta arriva alla pagina in JSON e Starlette
    # rilancia comunque l'eccezione al server, che ne scrive la traccia nel registro.
    return JSONResponse(
        status_code=500, content={"errore": f"errore interno di Iudex ({type(exc).__name__})"}
    )


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


def _filtri(kind, tipoprov, szdec, anno, ssz, materia, segnale=None) -> dict[str, list[str]]:
    """Filtri della ricerca; ``segnale`` (contrasto/conformita) viaggia con loro, così finisce
    nel permalink, nella cronologia e nel diario come ogni altro filtro."""
    grezzi = {
        "kind": kind,
        "tipoprov": tipoprov,
        "szdec": szdec,
        "anno": anno,
        "ssz": ssz,
        "materia": materia,
    }
    filtri = {
        campo: _lista(campo, grezzi[campo]) for campo in CAMPI_FACET if _lista(campo, grezzi[campo])
    }
    if segnale in SEGNALI:
        filtri["segnale"] = [segnale]
    return filtri


def _permalink(testo, rif, filtri, ordina, righe, pagina) -> str:
    coppie: list[tuple[str, str]] = []
    if testo:
        coppie.append(("testo", testo))
    if rif:
        coppie.append(("rif", rif))
    for campo in CAMPI_FACET:
        if filtri.get(campo):
            coppie.append((campo, SEPARATORI.get(campo, ",").join(filtri[campo])))
    if filtri.get("segnale"):
        coppie.append(("segnale", filtri["segnale"][0]))
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
            p.get("segnale"),
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
        if campo == "segnale":
            parti.append(ETICHETTE_SEGNALI.get(valori[0], valori[0]))
        else:
            parti.append(f"{campo}={','.join(valori)}")
    return " · ".join(parti) or "tutte le sentenze"


def _descrivi_permalink(permalink: str) -> str:
    p = _da_permalink(permalink)
    return _descrizione(p["testo"], p["rif"], p["filtri"])


def _arricchisci(archivio: Archivio, documenti: list[dict]) -> None:
    """Aggiunge a ogni documento ``consultazione`` (None se mai aperta) per il badge "già
    vista": quante volte, l'ultima, da quali ricerche è stata aperta e in quali è uscita."""
    ids = [d["id"] for d in documenti if d.get("id")]
    consultate = archivio.consultazioni(ids)
    provenienze = archivio.provenienze(list(consultate))
    for doc in documenti:
        c = consultate.get(doc.get("id"))
        if c is None:
            doc["consultazione"] = None
            continue
        doc["consultazione"] = {
            "volte": c["volte"],
            "prima": c["prima"],
            "ultima": c["ultima"],
            "pdf": c["pdf"],
            "aperta_da": [
                {"descrizione": _descrivi_permalink(a["permalink"]), **a} for a in c["aperture"][:5]
            ],
            "uscita_in": provenienze.get(doc["id"], [])[:5],
        }


def _scelte(request: Request) -> dict:
    """Le impostazioni effettive (scheda Impostazioni e variabili d'ambiente)."""
    return preferenze.effettive(request.app.state.archivio.impostazioni(), impostazioni)


def _conserva_storico(request: Request) -> bool:
    """Spento nella scheda Impostazioni: Iudex non registra niente di ciò che si consulta."""
    return bool(_scelte(request)["conserva_storico"])


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
    segnale = (filtri.get("segnale") or [None])[0]
    q, hl_q = costruisci_query(testo, rif_norm, filtri, segnale)
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
            "segnali": normalizza_segnali(dati.get("facet_counts", {}).get("facet_queries")),
            "tempo_solr_ms": dati.get("responseHeader", {}).get("QTime"),
        }
        if _conserva_storico(request):
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
    risposta["documenti"] = [dict(doc) for doc in risposta["documenti"]]
    for doc in risposta["documenti"]:
        doc["preferito"] = doc["id"] in preferiti
    _arricchisci(archivio, risposta["documenti"])
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
    segnale: str | None = Query(None, pattern="^(contrasto|conformita)$"),
    ordina: str = "pubblicazione",
    pagina: int = Query(1, ge=1),
    righe: int = Query(impostazioni.righe_predefinite, ge=1, le=impostazioni.righe_massime),
) -> dict:
    filtri = _filtri(kind, tipoprov, szdec, anno, ssz, materia, segnale)
    risposta = await _esegui_ricerca(request, testo, rif, filtri, ordina, pagina, righe)
    if not _conserva_storico(request):
        return risposta
    archivio: Archivio = request.app.state.archivio
    if pagina == 1:
        archivio.registra_ricerca(
            testo=testo,
            riferimenti=rif,
            filtri=filtri,
            ordinamento=risposta["ordinamento"],
            righe=risposta["righe"],
            trovati=risposta["trovati"],
            permalink=_ricerca_di(risposta),
        )
    _annota_ricerca(archivio, risposta)
    return risposta


def _ricerca_di(risposta: dict) -> str:
    """Il permalink della pagina 1: identifica la ricerca in cronologia ed esecuzioni."""
    return _permalink(
        risposta["testo"],
        risposta["riferimenti"],
        risposta["filtri"],
        risposta["ordinamento"],
        risposta["righe"],
        1,
    )


def _annota_ricerca(archivio: Archivio, risposta: dict, origine: str = "ricerca") -> None:
    """Ogni esecuzione di una ricerca è una voce del diario, anche se servita dalla cache, e
    un'esecuzione con le sentenze mostrate (la provenienza di ciascuna)."""
    archivio.registra_esecuzione(
        ricerca=_ricerca_di(risposta),
        permalink=risposta["permalink"],
        descrizione=risposta["descrizione"],
        pagina=risposta["pagina"],
        righe=risposta["righe"],
        trovati=risposta["trovati"],
        dalla_cache=risposta["dalla_cache"],
        origine=origine,
        documenti=risposta["documenti"],
        inizio=risposta["inizio"],
    )
    archivio.annota_ricerca(
        testo=risposta["testo"],
        riferimenti=risposta["riferimenti"],
        filtri=risposta["filtri"],
        ordinamento=risposta["ordinamento"],
        pagina=risposta["pagina"],
        permalink=risposta["permalink"],
        trovati=risposta["trovati"],
    )


# --- sentenza ------------------------------------------------------------------------------


def _testo_unito(valore) -> str | None:
    if isinstance(valore, list):
        return "\n".join(str(v) for v in valore) or None
    return valore


def _da_grezzo(grezzo: dict) -> tuple[dict, str | None]:
    """Documento normalizzato e testo dalla risposta intera del server per una sentenza."""
    documento = normalizza_documento(grezzo)
    testo = _testo_unito(grezzo.get("ocrfull") or grezzo.get("testoocr") or grezzo.get("ocr"))
    documento["materia"] = grezzo.get("materia")
    documento["massima"] = _testo_unito(grezzo.get("ocrdis"))
    # Campi "rnc-*": riferimenti normativi citati nel provvedimento (indicizzati dal CED).
    rnc = {chiave[4:]: valore for chiave, valore in grezzo.items() if chiave.startswith("rnc-")}
    documento["riferimenti_normativi"] = formatta_riferimenti(rnc)
    return documento, testo


async def _carica_sentenza(
    request: Request,
    id_sentenza: str,
    hl_q: str | None = None,
    *,
    consultazione: str | None = None,
    annota: bool = False,
) -> tuple[dict, str | None, str | None, bool]:
    """Restituisce (documento, testo, testo evidenziato dal server o None, dalla cache).

    Con ``annota`` l'apertura finisce nel diario (``consultazione`` è il permalink della
    ricerca di provenienza) e la sentenza fra le consultate: la prima volta serve la risposta
    intera del server, quindi la chiamata di dettaglio si fa anche se il testo è già in cache.
    """
    archivio: Archivio = request.app.state.archivio
    chiave_hl = json.dumps(["hl", id_sentenza, hl_q]) if hl_q else None
    gia_consultata = True
    conserva = _conserva_storico(request)
    annota = annota and conserva
    if annota:
        archivio.annota_sentenza(id_sentenza, consultazione)
        gia_consultata = archivio.tocca_consultata(id_sentenza)
    salvata = archivio.leggi_sentenza(id_sentenza)
    if not salvata and gia_consultata:
        # Testo tolto dalla cache ma sentenza già consultata: si ricostruisce dalla risposta
        # intera conservata, senza chiedere di nuovo al server.
        grezzo = archivio.grezzo_consultata(id_sentenza)
        if grezzo is not None:
            documento, testo = _da_grezzo(grezzo)
            if conserva:
                archivio.scrivi_sentenza(id_sentenza, documento, testo)
            salvata = {"documento": documento, "testo": testo}
    if salvata and gia_consultata:
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
    documento, testo = _da_grezzo(grezzo)
    if conserva:
        archivio.scrivi_sentenza(id_sentenza, documento, testo)
    if annota and not gia_consultata:
        archivio.scrivi_consultata(id_sentenza, documento, grezzo)
    marcato = None
    if chiave_hl:
        marcato = _testo_unito(dati.get("highlighting", {}).get(id_sentenza, {}).get("ocr"))
        if marcato and conserva:
            archivio.scrivi_risposta(chiave_hl, {"testo": marcato})
    return documento, testo, marcato, False


@app.get("/api/sentenza/{id_sentenza}")
async def sentenza(
    request: Request, id_sentenza: str, evidenzia: str | None = None, da: str | None = None
) -> dict:
    """``da`` è il permalink della ricerca da cui la sentenza viene aperta (per il diario)."""
    archivio: Archivio = request.app.state.archivio
    documento, testo, marcato, dalla_cache = await _carica_sentenza(
        request, id_sentenza, evidenzia or None, consultazione=da or None, annota=True
    )
    documento = dict(documento)
    documento["preferito"] = id_sentenza in archivio.id_preferiti()
    # Le sentenze salvate dalla 0.1.0 hanno i riferimenti ancora come liste grezze.
    if isinstance(documento.get("riferimenti_normativi"), dict):
        documento["riferimenti_normativi"] = formatta_riferimenti(
            documento["riferimenti_normativi"]
        )
    testo_paragrafato, posizione = export.paragrafa(testo)
    marcato_paragrafato = export.paragrafa(marcato)[0] if marcato else None
    consultata = archivio.consultata(id_sentenza) or {}
    return {
        "documento": documento,
        "testo": testo_paragrafato,
        "testo_evidenziato": marcato_paragrafato,
        "posizione_pqm": posizione,
        "dalla_cache": dalla_cache,
        "consultazione": {
            "volte": consultata.get("volte", 0),
            "prima_volta": consultata.get("prima_volta"),
            "ultima_volta": consultata.get("ultima_volta"),
            "aperture": [
                {k: v for k, v in voce.items() if k != "documento"}
                for voce in archivio.diario(id_sentenza=id_sentenza, limite=100)
            ],
            # Le ricerche in cui la sentenza è uscita fra i risultati visti.
            "uscita_in": archivio.provenienze([id_sentenza]).get(id_sentenza, []),
        },
    }


@app.get("/api/pdf/{id_sentenza}")
async def pdf(request: Request, id_sentenza: str) -> RedirectResponse:
    documento, _, _, _ = await _carica_sentenza(request, id_sentenza)
    if not documento.get("pdf"):
        raise HTTPException(404, "PDF non disponibile")
    return RedirectResponse(documento["pdf"], status_code=307)


# --- riferimenti normativi (suggerimenti locali) --------------------------------------------


async def _lista_sigle(request: Request) -> list[tuple[str, str]]:
    if getattr(request.app.state, "sigle", None) is not None:
        return request.app.state.sigle
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
    request.app.state.sigle = coppie
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


class NuovaSalvata(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    permalink: str = Field(min_length=1, max_length=4000)


class NuovoPreferito(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    estremi: dict = Field(default_factory=dict)
    nota: str | None = Field(default=None, max_length=2000)


class NotaPreferito(BaseModel):
    nota: str | None = Field(default=None, max_length=2000)


@app.post("/api/salvate")
async def salva(request: Request, corpo: NuovaSalvata) -> dict:
    nome = corpo.nome.strip()
    permalink = corpo.permalink.strip()
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
    if _conserva_storico(request):
        _annota_ricerca(archivio, risposta, origine="controllo")
    return {
        "prima_volta": prima_volta,
        "trovati": risposta["trovati"],
        "nuovi": nuovi,
        "dalla_cache": risposta["dalla_cache"],
    }


@app.get("/api/preferiti")
async def preferiti(request: Request) -> list[dict]:
    archivio: Archivio = request.app.state.archivio
    voci = [dict(v, id=v["id_sentenza"]) for v in archivio.preferiti()]
    _arricchisci(archivio, voci)
    return voci


@app.post("/api/preferiti")
async def aggiungi_preferito(request: Request, corpo: NuovoPreferito) -> dict:
    request.app.state.archivio.aggiungi_preferito(corpo.id, corpo.estremi, corpo.nota)
    return {"ok": True}


@app.put("/api/preferiti/{id_sentenza}")
async def nota_preferito(request: Request, id_sentenza: str, corpo: NotaPreferito) -> dict:
    nota = (corpo.nota or "").strip() or None
    if not request.app.state.archivio.aggiorna_nota(id_sentenza, nota):
        raise HTTPException(404, "preferito non trovato")
    return {"ok": True, "nota": nota}


@app.delete("/api/preferiti/{id_sentenza}")
async def rimuovi_preferito(request: Request, id_sentenza: str) -> dict:
    request.app.state.archivio.rimuovi_preferito(id_sentenza)
    return {"ok": True}


# --- diario e sentenze consultate -----------------------------------------------------------


@app.get("/api/diario")
async def diario(
    request: Request,
    giorno: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    sentenza: str | None = None,
    limite: int = Query(500, ge=1, le=5000),
) -> list[dict]:
    return request.app.state.archivio.diario(giorno, sentenza or None, limite)


@app.get("/api/diario/giorni")
async def giorni_diario(request: Request) -> list[dict]:
    return request.app.state.archivio.giorni_diario()


@app.get("/api/consultate")
async def consultate(request: Request) -> list[dict]:
    return request.app.state.archivio.consultate()


@app.get("/api/consultate/{id_sentenza}/grezzo")
async def grezzo_consultata(request: Request, id_sentenza: str) -> dict:
    grezzo = request.app.state.archivio.grezzo_consultata(id_sentenza)
    if grezzo is None:
        raise HTTPException(404, "sentenza non consultata")
    return grezzo


@app.post("/api/aggiornamento/installa")
async def installa_aggiornamento(request: Request) -> dict:
    """Scarica l'installer della versione nuova, ne controlla lo sha256 e lo avvia."""
    info = request.app.state.aggiornamento
    if not info or not info.get("disponibile"):
        raise HTTPException(409, "nessun aggiornamento disponibile")
    try:
        percorso = await aggiornamenti.scarica(
            info["pacchetto"], impostazioni.cartella_dati / "aggiornamenti"
        )
    except aggiornamenti.ErroreAggiornamento as exc:
        raise HTTPException(502, str(exc)) from exc
    aggiornamenti.avvia_installer(percorso)
    return {"ok": True, "percorso": str(percorso), "versione": info["versione"]}


@app.post("/api/backup")
async def copia_di_sicurezza(request: Request) -> dict:
    marca = time.strftime("%Y%m%d-%H%M%S")
    destinazione = impostazioni.cartella_dati / f"iudex-{marca}.sqlite"
    percorso = request.app.state.archivio.copia_di_sicurezza(destinazione)
    return {"ok": True, "percorso": str(percorso)}


# --- esportazione --------------------------------------------------------------------------


def _allegato(contenuto: str | bytes, nome: str, tipo: str) -> Response:
    if isinstance(contenuto, str):
        contenuto = contenuto.encode("utf-8")
        tipo = f"{tipo}; charset=utf-8"
    return Response(
        content=contenuto,
        media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@app.get("/api/export/diario")
async def esporta_diario(
    request: Request, formato: str = Query("jsonl", pattern="^(jsonl|csv)$")
) -> Response:
    voci = request.app.state.archivio.diario(limite=5000)
    marca = time.strftime("%Y%m%d-%H%M%S")
    if formato == "csv":
        return _allegato(export.diario_csv(voci), f"iudex-diario-{marca}.csv", "text/csv")
    return _allegato(export.diario_jsonl(voci), f"iudex-diario-{marca}.jsonl", "application/jsonl")


@app.get("/api/export/consultate")
async def esporta_consultate(
    request: Request, formato: str = Query("zip", pattern="^(zip|ftm)$")
) -> Response:
    """Zip con risposta e testo di ogni sentenza consultata, oppure entità FollowTheMoney
    in JSON a righe (``.ftm``), da caricare con ``ftm`` o in Aleph."""
    archivio: Archivio = request.app.state.archivio
    marca = time.strftime("%Y%m%d-%H%M%S")
    if formato == "ftm":
        note = {p["id_sentenza"]: p.get("nota") for p in archivio.preferiti()}
        documenti = {c["id_sentenza"]: c["documento"] for c in archivio.consultate()}
        voci = (
            (id_s, documenti.get(id_s, {}), grezzo, note.get(id_s))
            for id_s, grezzo in archivio.grezzi_consultate()
        )
        return _allegato(
            export.consultate_ftm(voci), f"iudex-consultate-{marca}.ftm", "application/x-ndjson"
        )
    return _allegato(
        export.consultate_zip(archivio.grezzi_consultate()),
        f"iudex-consultate-{marca}.zip",
        "application/zip",
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
    segnale: str | None = Query(None, pattern="^(contrasto|conformita)$"),
    ordina: str = "pubblicazione",
    pagina: int = Query(1, ge=1),
    righe: int = Query(impostazioni.righe_predefinite, ge=1, le=impostazioni.righe_massime),
    massimo: int | None = Query(None, ge=1, le=100),
) -> Response:
    """Esporta la pagina corrente oppure, con ``massimo``, i primi N risultati (al più 100)."""
    filtri = _filtri(kind, tipoprov, szdec, anno, ssz, materia, segnale)
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


def _impostazioni_attuali(archivio: Archivio) -> dict:
    return {
        "valori": preferenze.effettive(archivio.impostazioni(), impostazioni),
        "predefinite": preferenze.PREDEFINITE,
        "bloccate": preferenze.bloccate(impostazioni),
        "codici_impronta": list(CODICI),
        "cartella_pdf_predefinita": str(impostazioni.cartella_dati / "pdf"),
    }


@app.get("/api/impostazioni")
async def leggi_impostazioni(request: Request) -> dict:
    return _impostazioni_attuali(request.app.state.archivio)


@app.put("/api/impostazioni")
async def scrivi_impostazioni(request: Request) -> dict:
    """Salva le chiavi inviate (le altre restano); ``null`` riporta una chiave al predefinito."""
    archivio: Archivio = request.app.state.archivio
    try:
        corpo = await request.json()
    except ValueError:
        raise HTTPException(422, "corpo JSON non valido") from None
    if not isinstance(corpo, dict):
        raise HTTPException(422, "atteso un oggetto JSON")
    try:
        nuove = preferenze.valida(corpo)
        bloccate = preferenze.bloccate(impostazioni).keys() & nuove.keys()
        if bloccate:
            raise preferenze.ImpostazioneNonValida(
                f"{', '.join(sorted(bloccate))}: fissata da una variabile d'ambiente"
            )
        dopo = {**archivio.impostazioni(), **nuove}
        preferenze.controlla_insieme(
            preferenze.effettive({k: v for k, v in dopo.items() if v is not None}, impostazioni)
        )
    except preferenze.ImpostazioneNonValida as exc:
        raise HTTPException(422, str(exc)) from None
    archivio.scrivi_impostazioni(nuove)
    return _impostazioni_attuali(archivio)


@app.get("/api/stato")
async def stato(request: Request) -> dict:
    client: ClientSentenzeWeb = request.app.state.client
    archivio: Archivio = request.app.state.archivio
    return {
        "versione": __version__,
        "chiamate_remote": client.stat.chiamate,
        "intervallo_minimo_s": impostazioni.intervallo_minimo,
        "pausa_residua_s": client.pausa_residua(),
        "impronta": client.impronta_corrente().nome,
        "impronta_fissa": bool(impostazioni.impronta),
        "sentenze_in_cache": archivio.conta_sentenze(),
        "risposte_in_cache": archivio.conta_risposte(),
        "voci_diario": archivio.conta_diario(),
        "sentenze_consultate": archivio.conta_consultate(),
        "percorso_dati": str(impostazioni.percorso_db),
        "aggiornamento": getattr(request.app.state, "aggiornamento", None),
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
