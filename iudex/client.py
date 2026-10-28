"""Client HTTP verso SentenzeWeb con la limitazione delle richieste di Iudex.

Regole: una sola richiesta alla volta, almeno ``intervallo_minimo`` secondi fra due
richieste, un solo tentativo di ripetizione su errore di rete o 5xx, nessuna ripetizione
su 403/429, che impongono una pausa locale secondo ``Retry-After``. Una risposta HTML al
posto del JSON (o un 403) fa riaprire la sessione alla richiesta successiva. Gli header
sono quelli di uno dei browser di ``impronte.py``, scelto dal giorno del calendario (o fissato
con ``IUDEX_IMPRONTA``); quando il giorno cambia la sessione si riapre con l'impronta nuova.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import ssl
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, date
from email.utils import parsedate_to_datetime

import certifi
import httpx

from .config import URL_ESTREMI, URL_SNCASS, URL_SOLR, URL_TELEMETRIA, Impostazioni
from .impronte import Impronta, impronta_del_giorno
from .query import codifica_corpo

log = logging.getLogger("iudex.rete")


class ErroreRemoto(Exception):
    """Errore nel dialogo con il server della Corte."""

    def __init__(self, messaggio: str, stato: int | None = None):
        super().__init__(messaggio)
        self.stato = stato


def contesto_ssl(certificato_intermedio) -> ssl.SSLContext:
    """Contesto TLS con il certificato intermedio che il server omette dalla catena."""
    ctx = ssl.create_default_context(cafile=certifi.where())
    if certificato_intermedio and certificato_intermedio.exists():
        ctx.load_verify_locations(str(certificato_intermedio))
    return ctx


HEADER_XHR = {
    "Accept": "*/*",
    "Origin": "https://www.italgiure.giustizia.it",
    "Referer": URL_SNCASS,
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}
# Il PDF si apre dal sito come un documento (link in una nuova scheda), non come XHR.
HEADER_PDF = {
    "Accept": "application/pdf,text/html,application/xhtml+xml,*/*;q=0.8",
    "Referer": URL_SNCASS,
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

@dataclass
class VoceRegistro:
    quando: float
    tipo: str
    stato: int | None
    durata_ms: int
    dettaglio: str = ""


@dataclass
class Statistiche:
    chiamate: int = 0
    ultima_chiamata: float | None = None
    registro: deque[VoceRegistro] = field(default_factory=lambda: deque(maxlen=100))


# Dopo un 403 o un 429 senza Retry-After Iudex non chiede nulla per un minuto; un
# Retry-After più lungo di un'ora viene limitato a un'ora (RFC 9110, sezione 10.2.3).
PAUSA_PREDEFINITA_S = 60
PAUSA_MASSIMA_S = 3600


def secondi_retry_after(valore: str | None, adesso: float | None = None) -> int | None:
    """Secondi da attendere secondo ``Retry-After``: numero di secondi oppure data HTTP."""
    if not valore:
        return None
    valore = valore.strip()
    if valore.isdigit():
        return int(valore)
    try:
        quando = parsedate_to_datetime(valore)
    except (TypeError, ValueError):
        return None
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=UTC)
    adesso = time.time() if adesso is None else adesso
    return max(0, round(quando.timestamp() - adesso))


class ClientSentenzeWeb:
    def __init__(self, impostazioni: Impostazioni):
        self.imp = impostazioni
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None
        self._sessione_pronta = False
        self._pausa_fino: float = 0.0
        self._impronta: Impronta | None = None
        self.stat = Statistiche()

    def impronta_corrente(self) -> Impronta:
        """L'impronta browser da dichiarare oggi (o quella fissata nelle impostazioni)."""
        return impronta_del_giorno(date.today(), self.imp.impronta)

    def pausa_residua(self) -> int:
        """Secondi che mancano alla fine della pausa imposta dal server (0 se nessuna)."""
        return max(0, math.ceil(self._pausa_fino - time.monotonic()))

    def _imponi_pausa(self, risposta: httpx.Response) -> int:
        secondi = secondi_retry_after(risposta.headers.get("retry-after"))
        secondi = PAUSA_PREDEFINITA_S if secondi is None else min(secondi, PAUSA_MASSIMA_S)
        self._pausa_fino = time.monotonic() + secondi
        return secondi

    def _azzera_sessione(self) -> None:
        """La sessione va riaperta: la prossima richiesta ripassa dalla pagina del sito."""
        self._sessione_pronta = False

    def _assicura_client(self) -> httpx.AsyncClient:
        if self._impronta is None:
            self._impronta = self.impronta_corrente()
        if self._client is None:
            self._client = httpx.AsyncClient(
                verify=contesto_ssl(self.imp.certificato_intermedio),
                headers=self._impronta.header_comuni(),
                timeout=httpx.Timeout(self.imp.timeout, connect=10.0),
                follow_redirects=True,
                limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            )
        return self._client

    async def chiudi(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            self._sessione_pronta = False

    async def _attendi_turno(self) -> None:
        ultima = self.stat.ultima_chiamata
        if ultima is not None:
            attesa = self.imp.intervallo_minimo - (time.monotonic() - ultima)
            if attesa > 0:
                await asyncio.sleep(attesa)

    async def _invia(
        self,
        metodo: str,
        url: str,
        *,
        tipo: str,
        headers: dict | None = None,
        content: str | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        client = self._assicura_client()
        tentativi = 0
        while True:
            tentativi += 1
            await self._attendi_turno()
            inizio = time.monotonic()
            self.stat.ultima_chiamata = inizio
            self.stat.chiamate += 1
            try:
                risposta = await client.request(
                    metodo, url, headers=headers, content=content, params=params
                )
            except httpx.TransportError as exc:
                durata = int((time.monotonic() - inizio) * 1000)
                self.stat.registro.append(
                    VoceRegistro(time.time(), tipo, None, durata, str(exc))
                )
                log.warning("%s %s: errore di rete (%s)", metodo, tipo, exc)
                if tentativi >= 2:
                    raise ErroreRemoto(f"errore di rete: {exc}") from exc
                await asyncio.sleep(5)
                continue
            durata = int((time.monotonic() - inizio) * 1000)
            self.stat.registro.append(
                VoceRegistro(time.time(), tipo, risposta.status_code, durata, "")
            )
            log.info("%s %s -> %s in %d ms", metodo, tipo, risposta.status_code, durata)
            if risposta.status_code in (403, 429):
                # Nessuna ripetizione automatica (RFC 9110 15.5.4: non ripetere con le stesse
                # credenziali); pausa locale secondo Retry-After, facoltativo nel 429 (RFC 6585
                # 4), e per il 403 sessione da riaprire: la richiesta successiva dell'utente
                # parte con un cookie nuovo, come la RFC consente.
                secondi = self._imponi_pausa(risposta)
                if risposta.status_code == 403:
                    self._azzera_sessione()
                raise ErroreRemoto(
                    "il server ha rifiutato la richiesta "
                    f"(HTTP {risposta.status_code}): Iudex riproverà fra {secondi} s",
                    risposta.status_code,
                )
            if risposta.status_code >= 500 and tentativi < 2:
                await asyncio.sleep(5)
                continue
            if risposta.status_code >= 400:
                raise ErroreRemoto(f"HTTP {risposta.status_code}", risposta.status_code)
            return risposta

    async def _richiesta(
        self,
        metodo: str,
        url: str,
        *,
        tipo: str,
        headers: dict | None = None,
        content: str | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        """Esegue una richiesta rispettando il lock, la sessione e l'intervallo minimo."""
        async with self._lock:
            residua = self.pausa_residua()
            if residua:
                # Rifiuto locale: nessuna richiesta parte finché dura la pausa chiesta dal server.
                raise ErroreRemoto(
                    f"il server ha chiesto una pausa: riprova fra {residua} s", 429
                )
            impronta = self.impronta_corrente()
            if impronta != self._impronta:
                # Giorno nuovo, browser nuovo: cookie e header ripartono da zero.
                await self.chiudi()
                self._impronta = impronta
                log.info("impronta del giorno: %s", impronta.nome)
            if not self._sessione_pronta:
                await self._invia(
                    "GET", URL_SNCASS, tipo="pagina", headers=self._impronta.header_pagina()
                )
                self._sessione_pronta = True
            return await self._invia(
                metodo, url, tipo=tipo, headers=headers, content=content, params=params
            )

    async def _solr(self, parametri: list[tuple[str, str]], *, suffisso: str, tipo: str) -> dict:
        risposta = await self._richiesta(
            "POST",
            URL_SOLR + suffisso,
            tipo=tipo,
            headers={
                **HEADER_XHR,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            content=codifica_corpo(parametri),
        )
        try:
            dati = json.loads(risposta.text)
        except json.JSONDecodeError as exc:
            # Di solito è la pagina HTML del sito al posto del JSON: sessione scaduta.
            self._azzera_sessione()
            raise ErroreRemoto("risposta non in formato JSON") from exc
        if not isinstance(dati, dict):
            raise ErroreRemoto("risposta inattesa dal server")
        if "error" in dati:
            errore = dati["error"]
            messaggio = errore.get("msg", "errore") if isinstance(errore, dict) else str(errore)
            raise ErroreRemoto(f"Solr: {messaggio}")
        risposta_solr = dati.get("response")
        if not isinstance(risposta_solr, dict) or not isinstance(risposta_solr.get("docs"), list):
            raise ErroreRemoto("risposta inattesa dal server (manca l'elenco dei documenti)")
        return dati

    async def cerca(self, parametri: list[tuple[str, str]], kind: str | None = None) -> dict:
        suffisso = "?app.query" + (f"={kind}" if kind else "")
        dati = await self._solr(parametri, suffisso=suffisso, tipo="ricerca")
        if self.imp.replica_telemetria:
            q = dict(parametri).get("q", "")
            await self.telemetria("app.query", q, kind)
        return dati

    async def dettaglio(self, parametri: list[tuple[str, str]]) -> dict:
        return await self._solr(parametri, suffisso="", tipo="dettaglio")

    async def scarica_pdf(self, url: str) -> bytes:
        """Il PDF di una sentenza (URL di ``query.url_pdf``), con lock, sessione e intervallo
        minimo come ogni altra richiesta; una pagina al posto del PDF è un errore."""
        risposta = await self._richiesta("GET", url, tipo="pdf", headers=HEADER_PDF)
        tipo = risposta.headers.get("content-type", "")
        if "pdf" not in tipo and not risposta.content.startswith(b"%PDF"):
            raise ErroreRemoto("il server non ha restituito un PDF")
        return risposta.content

    def _testo_estremi(self, risposta: httpx.Response) -> str:
        """Il servizio estremi risponde in testo semplice; una pagina HTML è un errore
        (sessione scaduta) e non deve finire in cache né dentro una query."""
        testo = risposta.text.strip()
        tipo = risposta.headers.get("content-type", "")
        if "html" in tipo or testo.lstrip().lower().startswith(("<!doctype", "<html")):
            self._azzera_sessione()
            raise ErroreRemoto("il servizio dei riferimenti normativi ha risposto con una pagina")
        return testo

    async def lista_estremi(self) -> str:
        risposta = await self._richiesta(
            "GET", URL_ESTREMI, tipo="estremi-lista", headers=HEADER_XHR, params={"wat": "list"}
        )
        return self._testo_estremi(risposta)

    async def normalizza_riferimento(self, testo: str) -> str:
        risposta = await self._richiesta(
            "GET", URL_ESTREMI, tipo="estremi", headers=HEADER_XHR, params={"wat": testo}
        )
        return self._testo_estremi(risposta)

    async def telemetria(self, azione: str, valore: str, kind: str | None = None) -> None:
        """Replica facoltativa della chiamata di tracciamento del sito (disattiva di default)."""
        url = URL_TELEMETRIA + "?" + azione + (f"={kind}" if kind else "")
        try:
            await self._richiesta(
                "GET",
                url,
                tipo="telemetria",
                headers={k: v for k, v in HEADER_XHR.items() if k != "Origin"},
                params={"q": valore} if azione == "app.query" else {"app.document": valore},
            )
        except ErroreRemoto:
            log.info("telemetria non riuscita (ignorata)")
