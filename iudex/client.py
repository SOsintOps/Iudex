"""Client HTTP verso SentenzeWeb con i limiti di cortesia di Iudex.

Regole: una sola richiesta alla volta, almeno ``intervallo_minimo`` secondi fra due
richieste, un solo tentativo di ripetizione su errore di rete o 5xx, nessuna ripetizione
su 403/429. Header identici a quelli che Chrome invia dal sito ufficiale.
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
import time
from collections import deque
from dataclasses import dataclass, field

import certifi
import httpx

from .config import (
    SEC_CH_UA,
    URL_ESTREMI,
    URL_SNCASS,
    URL_SOLR,
    URL_TELEMETRIA,
    USER_AGENT,
    Impostazioni,
)
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


HEADER_COMUNI = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "sec-ch-ua": SEC_CH_UA,
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

HEADER_XHR = {
    "Accept": "*/*",
    "Origin": "https://www.italgiure.giustizia.it",
    "Referer": URL_SNCASS,
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

HEADER_PAGINA = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
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


class ClientSentenzeWeb:
    def __init__(self, impostazioni: Impostazioni):
        self.imp = impostazioni
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None
        self._sessione_pronta = False
        self.stat = Statistiche()

    async def _sessione(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                verify=contesto_ssl(self.imp.certificato_intermedio),
                headers=HEADER_COMUNI,
                timeout=httpx.Timeout(self.imp.timeout, connect=10.0),
                follow_redirects=True,
                limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            )
        if not self._sessione_pronta:
            # Come un browser: prima la pagina (che imposta il cookie di sessione), poi le query.
            await self._richiesta("GET", URL_SNCASS, tipo="pagina", headers=HEADER_PAGINA)
            self._sessione_pronta = True
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
        """Esegue una richiesta rispettando il lock e l'intervallo minimo; un solo retry."""
        assert self._client is not None
        async with self._lock:
            tentativi = 0
            while True:
                tentativi += 1
                await self._attendi_turno()
                inizio = time.monotonic()
                self.stat.ultima_chiamata = inizio
                self.stat.chiamate += 1
                try:
                    risposta = await self._client.request(
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
                    raise ErroreRemoto(
                        "il server ha rifiutato la richiesta "
                        f"(HTTP {risposta.status_code}): attendi prima di riprovare",
                        risposta.status_code,
                    )
                if risposta.status_code >= 500 and tentativi < 2:
                    await asyncio.sleep(5)
                    continue
                if risposta.status_code >= 400:
                    raise ErroreRemoto(f"HTTP {risposta.status_code}", risposta.status_code)
                return risposta

    async def _solr(self, parametri: list[tuple[str, str]], *, suffisso: str, tipo: str) -> dict:
        await self._sessione()
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
            raise ErroreRemoto("risposta non in formato JSON") from exc
        if "error" in dati:
            raise ErroreRemoto(f"Solr: {dati['error'].get('msg', 'errore')}")
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

    async def lista_estremi(self) -> str:
        await self._sessione()
        risposta = await self._richiesta(
            "GET", URL_ESTREMI, tipo="estremi-lista", headers=HEADER_XHR, params={"wat": "list"}
        )
        return risposta.text

    async def normalizza_riferimento(self, testo: str) -> str:
        await self._sessione()
        risposta = await self._richiesta(
            "GET", URL_ESTREMI, tipo="estremi", headers=HEADER_XHR, params={"wat": testo}
        )
        return risposta.text.strip()

    async def telemetria(self, azione: str, valore: str, kind: str | None = None) -> None:
        """Replica facoltativa della chiamata di tracciamento del sito (disattiva per difetto)."""
        await self._sessione()
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
