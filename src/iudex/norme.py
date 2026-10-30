"""Testo delle norme dall'API Open Data di Normattiva (dati IPZS in CC BY 4.0).

Iudex legge un articolo alla volta, su richiesta dell'utente, e solo dall'API
(``api.normattiva.it``): mai dal sito ``www.normattiva.it``, che resta un link da aprire nel
browser. Regole di cortesia come per la Corte, ma con un lock e un intervallo propri (una
lettura di Normattiva non fa aspettare una ricerca di sentenze e viceversa): una richiesta
alla volta, almeno ``intervallo_minimo`` secondi fra due richieste (2 s,
``IUDEX_INTERVALLO_NORMATTIVA``), nessuna ripetizione su 409/429, che impongono una pausa
locale secondo ``Retry-After``, un solo nuovo tentativo su errore di rete, 5xx o
``code "1000"`` (guasto temporaneo della fonte). Un 404 dei servizi di dettaglio vuol dire che
Normattiva non ha quell'articolo con quei parametri (``NormaNonTrovata``); quando la fonte non
risponde il messaggio lo dice, e non dà mai la norma per inesistente.

Le forme delle richieste e delle risposte sono quelle misurate con la sonda del 30/10/2026
(specifica "API Normattiva Open Data", rev. 10): ``idArticolo`` è il numero dell'articolo,
``sottoArticolo`` il suffisso (1 = nessuno, 2 = bis...), gli articoli dei codici stanno
nell'allegato dell'atto d'origine e si leggono via URN.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import time
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlencode

import httpx

from . import __version__
from .client import (
    PAUSA_MASSIMA_S,
    PAUSA_PREDEFINITA_S,
    ErroreRemoto,
    Statistiche,
    VoceRegistro,
    secondi_retry_after,
)
from .config import impostazioni
from .query import SUFFISSI

log = logging.getLogger("iudex.normattiva")

URL_API = "https://api.normattiva.it/t/normattiva.api/bff-opendata/v1/api/v1"
URL_SITO = "https://www.normattiva.it"
FONTE = "Normattiva (IPZS), CC BY 4.0"
USER_AGENT = f"Iudex/{__version__} (+https://github.com/SOsintOps/Iudex)"
TIMEOUT_S = 30.0
NON_DISPONIBILE = "Normattiva: fonte temporaneamente non disponibile"

__all__ = [
    "FONTE",
    "SUFFISSI",
    "URL_API",
    "Articolo",
    "Atto",
    "ClientNormattiva",
    "NormaNonTrovata",
    "articolo_da_html",
    "dividi_articolo",
    "url_normattiva",
]


class NormaNonTrovata(Exception):
    """Normattiva ha risposto che l'atto o l'articolo non c'è (404 o ricerca vuota)."""


@dataclass(frozen=True)
class Atto:
    """Un atto di Normattiva.

    ``codice_redazionale`` e ``data_gu`` valgono None per i codici, letti via URN; le date
    sono ``YYYY-MM-DD``; ``urn`` è senza articolo e, per i codici, con l'allegato (vuoto se il
    prefisso URN del tipo di atto non è noto: allora il link usa il codice redazionale).
    """

    codice_redazionale: str | None
    data_gu: str | None
    data_emanazione: str
    titolo: str
    urn: str


@dataclass(frozen=True)
class Articolo:
    """Un articolo letto da Normattiva; vigenze ``YYYY-MM-DD`` o None (non indicata/aperta)."""

    numero: str
    rubrica: str | None
    testo: str
    note: str | None
    inizio_vigenza: str | None
    fine_vigenza: str | None
    vigenza_richiesta: str | None
    titolo_atto: str
    url: str
    fonte: str = FONTE


# Codici: atto d'origine fisso, nessuna richiesta per risolverlo. URN misurati il 30/10/2026:
# c.c. nell'allegato 2 del R.D. 262/1942 (art. 2043), c.p. e c.p.c. nell'allegato 1 dei R.D.
# 1398/1930 e 1443/1940 (artt. 575 e 99), c.p.p. nel d.P.R. 447/1988 senza allegato (art. 1),
# Costituzione (art. 3).
CODICI: dict[str, Atto] = {
    "CC": Atto(
        None,
        None,
        "1942-03-16",
        "Codice civile (R.D. 16 marzo 1942, n. 262)",
        "urn:nir:stato:regio.decreto:1942-03-16;262:2",
    ),
    "CP": Atto(
        None,
        None,
        "1930-10-19",
        "Codice penale (R.D. 19 ottobre 1930, n. 1398)",
        "urn:nir:stato:regio.decreto:1930-10-19;1398:1",
    ),
    "CPC": Atto(
        None,
        None,
        "1940-10-28",
        "Codice di procedura civile (R.D. 28 ottobre 1940, n. 1443)",
        "urn:nir:stato:regio.decreto:1940-10-28;1443:1",
    ),
    "CPP": Atto(
        None,
        None,
        "1988-09-22",
        "Codice di procedura penale (d.P.R. 22 settembre 1988, n. 447)",
        "urn:nir:stato:decreto.del.presidente.della.repubblica:1988-09-22;447",
    ),
    "COST": Atto(
        None,
        None,
        "1947-12-27",
        "Costituzione della Repubblica italiana",
        "urn:nir:stato:costituzione:1947-12-27",
    ),
}

# Tipi di Iudex (``query.TIPI_ATTO``) -> denominazioni di ``ricerca/avanzata``, provate in
# ordine. Trappola: la sigla "RDL" dell'API è il regio decreto legislativo, il "RDL" di Iudex è
# il regio decreto-legge.
DENOMINAZIONI: dict[str, tuple[str, ...]] = {
    "LS": ("LEGGE",),
    "DLG": ("DECRETO LEGISLATIVO",),
    "DL": ("DECRETO-LEGGE",),
    "DPR": ("DECRETO DEL PRESIDENTE DELLA REPUBBLICA",),
    "DPCM": ("DECRETO DEL PRESIDENTE DEL CONSIGLIO DEI MINISTRI",),
    "DM": ("DECRETO", "DECRETO MINISTERIALE"),
    "RD": ("REGIO DECRETO",),
    "RDL": ("REGIO DECRETO-LEGGE",),
}

# Prefissi URN per il link al sito (visti nei rinvii delle risposte, salvo DPCM e RDL).
PREFISSI_URN: dict[str, str] = {
    "LS": "stato:legge",
    "DLG": "stato:decreto.legislativo",
    "DL": "stato:decreto.legge",
    "DPR": "presidente.repubblica:decreto",
    "DPCM": "presidente.consiglio.ministri:decreto",
    "RD": "stato:regio.decreto",
    "RDL": "stato:regio.decreto.legge",
}

_ARTICOLO = re.compile(r"^\s*(?:art(?:icolo)?\.?\s*)?0*(\d{1,4})\s*-?\s*([a-z]*)\s*\.?\s*$", re.I)
_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def dividi_articolo(articolo: str) -> tuple[int, int]:
    """``idArticolo`` e ``sottoArticolo`` di un articolo: "2-bis" -> (2, 2), "2043" -> (2043, 1).

    Accetta anche "art. 2 bis" e "2bis"; un suffisso sconosciuto o un numero non valido danno
    ``ValueError``.
    """
    trovato = _ARTICOLO.match(articolo or "")
    if not trovato or int(trovato.group(1)) == 0:
        raise ValueError(f"articolo non valido: {articolo!r}")
    suffisso = trovato.group(2).lower()
    if suffisso not in SUFFISSI:
        raise ValueError(f"suffisso dell'articolo non riconosciuto: {articolo!r}")
    return int(trovato.group(1)), SUFFISSI.index(suffisso) + 1


def _etichetta(numero: int, sotto: int) -> str:
    return f"{numero}-{SUFFISSI[sotto - 1]}" if sotto > 1 else str(numero)


def url_normattiva(atto: Atto, articolo: str) -> str:
    """Il link all'articolo sul sito, da aprire nel browser dell'utente (Iudex non lo chiede).

    Con l'URN: ``/uri-res/N2Ls?<urn>~art<n><suffisso>`` (forma dei rinvii nelle risposte);
    senza, la pagina dell'atto per codice redazionale e data della Gazzetta.
    """
    numero, sotto = dividi_articolo(articolo)
    if atto.urn:
        return f"{URL_SITO}/uri-res/N2Ls?{atto.urn}~art{numero}{SUFFISSI[sotto - 1]}"
    parametri = urlencode(
        {
            "atto.dataPubblicazioneGazzetta": atto.data_gu or "",
            "atto.codiceRedazionale": atto.codice_redazionale or "",
        }
    )
    return f"{URL_SITO}/atto/caricaDettaglioAtto?{parametri}"


def _data_vigenza(valore) -> str | None:
    """``YYYYMMDD`` -> ``YYYY-MM-DD``; "0", vuota o ``99999999`` (vigenza aperta) -> None."""
    testo = str(valore or "").strip()
    if len(testo) != 8 or not testo.isdigit() or testo == "99999999" or testo == "00000000":
        return None
    return f"{testo[:4]}-{testo[4:6]}-{testo[6:]}"


def _pulisci(testo: str) -> str:
    """Spazi compressi riga per riga, righe vuote multiple ridotte a una, bordi tolti."""
    righe = [re.sub(r"\s+", " ", riga).strip() for riga in testo.replace("\xa0", " ").split("\n")]
    risultato: list[str] = []
    for riga in righe:
        if riga or (risultato and risultato[-1]):
            risultato.append(riga)
    return "\n".join(risultato).strip()


def _togli_parentesi_spuria(testo: str) -> str:
    testo = testo.strip()
    if testo.count(")") > testo.count("("):
        posizione = testo.rfind(")")
        testo = testo[:posizione] + testo[posizione + 1 :]
    return testo.strip()


def _rubrica(testo: str) -> str | None:
    testo = _togli_parentesi_spuria(re.sub(r"\s+", " ", testo)).rstrip(". ").strip()
    if testo.startswith("(") and testo.endswith(")"):
        testo = testo[1:-1].strip().rstrip(".").strip()
    return testo or None


def _numero(testo: str) -> str | None:
    trovato = re.match(r"^\s*art(?:icolo)?\.?\s*(.+?)\s*\.?\s*$", testo, re.I)
    numero = (trovato.group(1) if trovato else testo).strip().rstrip(".").strip()
    return numero or None


# Classi dell'articoloHtml -> zona del testo. Le altre classi ereditano la zona del contenitore.
_ZONE = {
    "article-num-akn": "numero",
    "article-heading-akn": "rubrica",
    "art_aggiornamento-akn": "note",
    "art_aggiornamento_separator-akn": "salta",
    "attachment-just-text": "allegato",
    "preamble-title-akn": "salta",
    "preamble-end-akn": "salta",
}
_BLOCCHI = {"div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul", "ol", "tr", "table"}
_VUOTI = {"br", "hr", "img", "input", "meta", "link", "wbr", "col", "area", "base"}
_PARAGRAFI = {"art-comma-div-akn", "art_aggiornamento_testo-akn", "art_aggiornamento_title-akn"}


class _LettoreArticolo(HTMLParser):
    """Parser tollerante dell'articoloHtml: i tag non chiusi si chiudono con il contenitore."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pila: list[tuple[str, str]] = []
        self.zone: dict[str, list[str]] = {
            "numero": [],
            "rubrica": [],
            "testo": [],
            "note": [],
            "allegato": [],
        }

    def _zona(self) -> str:
        for _tag, zona in reversed(self.pila):
            if zona:
                return zona
        return "testo"

    def _scrivi(self, testo: str, zona: str | None = None) -> None:
        zona = zona or self._zona()
        if zona in self.zone:
            self.zone[zona].append(testo)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classi = (dict(attrs).get("class") or "").split()
        if tag in _VUOTI:
            if tag == "br":
                self._scrivi("\n")
            return
        zona = next((_ZONE[c] for c in classi if c in _ZONE), "")
        self.pila.append((tag, zona))
        if any(c in _PARAGRAFI for c in classi):
            self._scrivi("\n\n")
        elif tag in _BLOCCHI:
            self._scrivi("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self._scrivi("\n")

    def handle_endtag(self, tag: str) -> None:
        if not any(t == tag for t, _zona in self.pila):
            return
        while self.pila:
            aperto, _zona = self.pila[-1]
            zona = self._zona()
            self.pila.pop()
            if aperto in _BLOCCHI:
                self._scrivi("\n", zona)
            if aperto == tag:
                break

    def handle_data(self, data: str) -> None:
        self._scrivi(data)


def articolo_da_html(html: str) -> tuple[str | None, str | None, str, str | None]:
    """Numero, rubrica, testo e note di un ``articoloHtml`` di Normattiva.

    Atto normale: numero in ``h2.article-num-akn``, rubrica in ``div.article-heading-akn``,
    commi e lettere un paragrafo ciascuno; il testo modificato fra ``((`` e ``))`` resta (è la
    marcatura ufficiale delle modifiche), gli aggiornamenti vanno nelle note. Allegato (i
    codici): righe separate da ``<br>``, "Art. 2043." / "(Rubrica)." / testo. Dei rinvii resta
    il testo; ``&nbsp;`` diventa uno spazio.
    """
    lettore = _LettoreArticolo()
    lettore.feed(html or "")
    lettore.close()
    zone = {nome: _pulisci("".join(parti)) for nome, parti in lettore.zone.items()}
    numero = _numero(zone["numero"]) if zone["numero"] else None
    rubrica = _rubrica(zone["rubrica"]) if zone["rubrica"] else None
    testo = zone["testo"]
    if zone["allegato"]:
        righe = zone["allegato"].split("\n")
        while righe and not righe[0]:
            righe.pop(0)
        if righe and re.match(r"^art(?:icolo)?\.?\s*\d", righe[0], re.I):
            numero = numero or _numero(righe.pop(0))
            while righe and not righe[0]:
                righe.pop(0)
            if righe and re.match(r"^\(.*\)\.?$", righe[0]):
                rubrica = rubrica or _rubrica(righe.pop(0))
        testo = _pulisci("\n".join([testo, "\n".join(righe)]))
    return numero, rubrica, testo, zone["note"] or None


async def _dormi(secondi: float) -> None:
    await asyncio.sleep(secondi)


def _orologio() -> float:
    return time.monotonic()


class ClientNormattiva:
    """Client dell'API Open Data di Normattiva, con lock, intervallo e statistiche propri."""

    def __init__(
        self,
        intervallo_minimo: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.intervallo_minimo = (
            impostazioni.intervallo_normattiva if intervallo_minimo is None else intervallo_minimo
        )
        self._transport = transport
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None
        self._pausa_fino: float = 0.0
        self.stat = Statistiche()

    def pausa_residua(self) -> int:
        """Secondi che mancano alla fine della pausa chiesta da Normattiva (0 se nessuna)."""
        return max(0, math.ceil(self._pausa_fino - _orologio()))

    def _imponi_pausa(self, risposta: httpx.Response) -> int:
        secondi = secondi_retry_after(risposta.headers.get("retry-after"))
        secondi = PAUSA_PREDEFINITA_S if secondi is None else min(secondi, PAUSA_MASSIMA_S)
        self._pausa_fino = _orologio() + secondi
        return secondi

    def _assicura_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=httpx.Timeout(TIMEOUT_S, connect=10.0),
                transport=self._transport,
                limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            )
        return self._client

    async def chiudi(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _attendi_turno(self) -> None:
        ultima = self.stat.ultima_chiamata
        if ultima is not None:
            attesa = self.intervallo_minimo - (_orologio() - ultima)
            if attesa > 0:
                await _dormi(attesa)

    def _registra(self, tipo: str, stato: int | None, inizio: float, dettaglio: str = "") -> None:
        durata = int((_orologio() - inizio) * 1000)
        self.stat.registro.append(VoceRegistro(time.time(), tipo, stato, durata, dettaglio))
        log.info("Normattiva %s -> %s in %d ms", tipo, stato, durata)

    async def _invia(self, percorso: str, corpo: dict | None, *, tipo: str) -> dict | list:
        client = self._assicura_client()
        # Le GET partono senza corpo e senza Content-Type (con il Content-Type il server
        # risponde 409); le POST con JSON.
        metodo = "GET" if corpo is None else "POST"
        headers = None if corpo is None else {"Content-Type": "application/json"}
        contenuto = None if corpo is None else json.dumps(corpo, ensure_ascii=False).encode()
        dettaglio_404 = percorso.startswith("/atto/")
        tentativi = 0
        while True:
            tentativi += 1
            await self._attendi_turno()
            inizio = _orologio()
            self.stat.ultima_chiamata = inizio
            self.stat.chiamate += 1
            try:
                risposta = await client.request(
                    metodo, URL_API + percorso, headers=headers, content=contenuto
                )
            except httpx.TransportError as exc:
                self._registra(tipo, None, inizio, str(exc))
                if tentativi >= 2:
                    raise ErroreRemoto(f"{NON_DISPONIBILE} (errore di rete)") from exc
                continue
            stato = risposta.status_code
            self._registra(tipo, stato, inizio)
            if stato in (409, 429):
                # Nessuna ripetizione: pausa locale secondo Retry-After, come per la Corte.
                secondi = self._imponi_pausa(risposta)
                raise ErroreRemoto(
                    f"Normattiva ha rifiutato la richiesta (HTTP {stato}): "
                    f"Iudex riproverà fra {secondi} s",
                    stato,
                )
            try:
                dati = risposta.json()
            except ValueError:
                dati = None
            guasto = stato >= 500 or (isinstance(dati, dict) and str(dati.get("code")) == "1000")
            if guasto:
                if tentativi < 2:
                    continue
                raise ErroreRemoto(NON_DISPONIBILE, stato)
            if stato == 404 and dettaglio_404:
                messaggio = dati.get("message") if isinstance(dati, dict) else None
                raise NormaNonTrovata(
                    "Normattiva non ha questo articolo" + (f" ({messaggio})" if messaggio else "")
                )
            if stato >= 400:
                raise ErroreRemoto(f"Normattiva: richiesta non accettata (HTTP {stato})", stato)
            if not isinstance(dati, dict | list):
                raise ErroreRemoto("Normattiva: risposta non in formato JSON")
            return dati

    async def _richiesta(self, percorso: str, corpo: dict | None, *, tipo: str) -> dict | list:
        """Una richiesta all'API (POST con ``corpo``, GET senza), con lock, pausa e intervallo."""
        async with self._lock:
            residua = self.pausa_residua()
            if residua:
                raise ErroreRemoto(f"Normattiva ha chiesto una pausa: riprova fra {residua} s", 429)
            return await self._invia(percorso, corpo, tipo=tipo)

    async def denominazioni(self) -> list[dict]:
        """Le denominazioni degli atti (``label``/``value``) usate da ``ricerca/avanzata``."""
        dati = await self._richiesta("/tipologiche/denominazione-atto", None, tipo="denominazioni")
        if not isinstance(dati, list):
            raise ErroreRemoto("Normattiva: risposta inattesa per le denominazioni")
        return dati

    async def risolvi_atto(self, tipo: str, numero: str, anno: str) -> Atto:
        """L'atto di un riferimento: costante per i codici, ``ricerca/avanzata`` per gli altri.

        ``ValueError`` per i tipi che Normattiva non ha (leggi regionali, CEDU, trattati e atti
        dell'Unione); ``NormaNonTrovata`` se la ricerca non trova l'atto; ``ErroreRemoto`` se
        trova più atti con lo stesso numero e anno (nessuna scelta a caso).
        """
        tipo = (tipo or "").upper()
        if tipo in CODICI:
            return CODICI[tipo]
        if tipo not in DENOMINAZIONI:
            raise ValueError(f"tipo non leggibile da Normattiva: {tipo or '(vuoto)'}")
        numero, anno = str(numero or "").strip().lstrip("0"), str(anno or "").strip()
        if not numero.isdigit() or not re.fullmatch(r"\d{4}", anno):
            raise ValueError("numero e anno dell'atto sono obbligatori")
        for denominazione in DENOMINAZIONI[tipo]:
            corpo = {
                "denominazioneAtto": denominazione,
                "numeroProvvedimento": numero,
                "annoProvvedimento": anno,
                "orderType": "recente",
                "paginazione": {"paginaCorrente": 1, "numeroElementiPerPagina": 10},
            }
            dati = await self._richiesta("/ricerca/avanzata", corpo, tipo="ricerca")
            lista = dati.get("listaAtti") if isinstance(dati, dict) else None
            candidati = [
                a
                for a in (lista or [])
                if isinstance(a, dict)
                and str(a.get("numeroProvvedimento", "")).lstrip("0") == numero
                and str(a.get("annoProvvedimento", "")) == anno
            ]
            if len(candidati) > 1:
                titoli = "; ".join(str(a.get("descrizioneAtto") or "") for a in candidati[:5])
                raise ErroreRemoto(f"Normattiva: atto ambiguo, più risultati ({titoli})")
            if candidati:
                return self._atto(tipo, numero, candidati[0])
        raise NormaNonTrovata(f"Normattiva non ha trovato l'atto {tipo} {numero}/{anno}")

    @staticmethod
    def _atto(tipo: str, numero: str, dati: dict) -> Atto:
        emanazione = str(dati.get("dataEmanazione") or "")[:10]
        titolo = str(dati.get("descrizioneAtto") or "").strip()
        if not titolo:
            titolo = re.sub(r"\s+", " ", str(dati.get("titoloAtto") or "")).strip(" []")
        prefisso = PREFISSI_URN.get(tipo)
        urn = f"urn:nir:{prefisso}:{emanazione};{numero}" if prefisso and emanazione else ""
        return Atto(
            codice_redazionale=str(dati.get("codiceRedazionale") or "") or None,
            data_gu=str(dati.get("dataGU") or "")[:10] or None,
            data_emanazione=emanazione,
            titolo=titolo,
            urn=urn,
        )

    async def leggi_articolo(
        self, atto: Atto, articolo: str, vigenza: str | None = None
    ) -> Articolo:
        """Un articolo dell'atto, vigente oggi o alla data ``vigenza`` (``YYYY-MM-DD``).

        Atti risolti con la ricerca: ``dettaglio-atto`` con ``idArticolo`` e ``sottoArticolo``;
        codici: ``dettaglio-atto-urn`` con ``~art<n><suffisso>`` e ``!vig=`` se c'è una data.
        """
        numero, sotto = dividi_articolo(articolo)
        if vigenza is not None and not _DATA.match(vigenza):
            raise ValueError(f"data di vigenza non valida: {vigenza!r}")
        if atto.codice_redazionale and atto.data_gu:
            percorso = "/atto/dettaglio-atto"
            corpo: dict = {
                "dataGU": atto.data_gu,
                "codiceRedazionale": atto.codice_redazionale,
                "idArticolo": numero,
                "sottoArticolo": sotto,
                "sottoArticolo1": 0,
                "flagTipoArticolo": 0,
                "dataVigenza": vigenza or date.today().isoformat(),
            }
        elif atto.urn:
            percorso = "/atto/dettaglio-atto-urn"
            urn = f"{atto.urn}~art{numero}{SUFFISSI[sotto - 1]}"
            corpo = {"urn": urn + (f"!vig={vigenza}" if vigenza else "")}
        else:
            raise ValueError("atto senza codice redazionale né URN")
        dati = await self._richiesta(percorso, corpo, tipo="articolo")
        contenuto = dati.get("data") if isinstance(dati, dict) else None
        contenuto = contenuto if isinstance(contenuto, dict) else {}
        letto = contenuto.get("atto")
        if not isinstance(letto, dict):
            if contenuto.get("lista"):
                raise ErroreRemoto("Normattiva: riferimento ambiguo, più atti corrispondono")
            raise ErroreRemoto("Normattiva: risposta senza l'articolo richiesto")
        _numero_letto, rubrica, testo, note = articolo_da_html(str(letto.get("articoloHtml") or ""))
        if not testo:
            raise ErroreRemoto("Normattiva: risposta senza il testo dell'articolo")
        return Articolo(
            numero=_etichetta(numero, sotto),
            rubrica=rubrica,
            testo=testo,
            note=note,
            inizio_vigenza=_data_vigenza(letto.get("articoloDataInizioVigenza")),
            fine_vigenza=_data_vigenza(letto.get("articoloDataFineVigenza")),
            vigenza_richiesta=vigenza,
            titolo_atto=str(letto.get("titolo") or atto.titolo),
            url=url_normattiva(atto, articolo),
        )
