"""Impronte browser che Iudex dichiara al server della Corte.

Ogni impronta è l'insieme coerente di header (``User-Agent``, ``Accept-Language``, client
hints ``sec-ch-ua*`` e ``Accept`` della pagina) di un browser installato su Windows. Il
profilo del giorno si ricava dalla data del calendario, così resta lo stesso per tutta la
giornata, anche riavviando Iudex, e cambia a mezzanotte; ``IUDEX_IMPRONTA`` ne fissa uno.

Cambiano solo gli header: l'impronta TLS e HTTP resta quella di ``httpx``/Python.

Le versioni sono quelle installate sul computer di sviluppo il 25 ottobre 2026 (Chrome 155,
Edge 157, Firefox 158): vanno aggiornate ogni tanto. I client hints di Chromium si ricavano
dalla versione maggiore con lo stesso algoritmo del browser (il marchio "greased" e l'ordine
dei tre marchi dipendono solo dal numero di versione), verificato sulla cattura di Chrome 155
in ``docs/analisi/cattura-cdp-2026-10-21.json``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

ACCEPT_PAGINA_CHROMIUM = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
)
ACCEPT_PAGINA_FIREFOX = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8"
)

_SEC_FETCH_PAGINA = {
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# Algoritmo GREASE di Chromium (components/embedder_support/user_agent_utils.cc).
_CARATTERI_GREASE = (" ", "(", ":", "-", ".", "/", ")", ";", "=", "?", "_")
_VERSIONI_GREASE = ("8", "99", "24")
_ORDINI = (
    ("grease", "chromium", "marchio"),
    ("grease", "marchio", "chromium"),
    ("chromium", "grease", "marchio"),
    ("marchio", "grease", "chromium"),
    ("chromium", "marchio", "grease"),
    ("marchio", "chromium", "grease"),
)


def sec_ch_ua_chromium(versione: int, marchio: str) -> str:
    """Valore di ``sec-ch-ua`` di un browser Chromium con quel marchio e quella versione."""
    n = len(_CARATTERI_GREASE)
    grease = f"Not{_CARATTERI_GREASE[versione % n]}A{_CARATTERI_GREASE[(versione + 1) % n]}Brand"
    valori = {
        "grease": (grease, _VERSIONI_GREASE[versione % len(_VERSIONI_GREASE)]),
        "chromium": ("Chromium", str(versione)),
        "marchio": (marchio, str(versione)),
    }
    return ", ".join(f'"{valori[k][0]}";v="{valori[k][1]}"' for k in _ORDINI[versione % 6])


@dataclass(frozen=True)
class Impronta:
    codice: str
    nome: str
    user_agent: str
    accept_language: str
    accept_pagina: str
    client_hints: dict[str, str] = field(default_factory=dict)

    def header_comuni(self) -> dict[str, str]:
        """Header presenti in ogni richiesta (impostati sul client HTTP)."""
        return {
            "User-Agent": self.user_agent,
            "Accept-Language": self.accept_language,
            **self.client_hints,
        }

    def header_pagina(self) -> dict[str, str]:
        """Header del ``GET`` iniziale della pagina del sito (apertura della sessione)."""
        return {"Accept": self.accept_pagina, **_SEC_FETCH_PAGINA}


def _chromium(codice: str, nome: str, versione: int, marchio: str, suffisso: str = "") -> Impronta:
    return Impronta(
        codice=codice,
        nome=f"{nome} {versione} su Windows",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{versione}.0.0.0 Safari/537.36{suffisso}"
        ),
        accept_language="it-IT,it;q=0.9,en;q=0.8",
        accept_pagina=ACCEPT_PAGINA_CHROMIUM,
        client_hints={
            "sec-ch-ua": sec_ch_ua_chromium(versione, marchio),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
    )


def _firefox(versione: int) -> Impronta:
    return Impronta(
        codice="firefox",
        nome=f"Firefox {versione} su Windows",
        user_agent=(
            f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{versione}.0) "
            f"Gecko/20100101 Firefox/{versione}.0"
        ),
        accept_language="it-IT,it;q=0.8,en-US;q=0.5,en;q=0.3",
        accept_pagina=ACCEPT_PAGINA_FIREFOX,
    )


IMPRONTE: tuple[Impronta, ...] = (
    _chromium("chrome", "Chrome", 155, "Google Chrome"),
    _chromium("edge", "Edge", 157, "Microsoft Edge", suffisso=" Edg/157.0.0.0"),
    _firefox(158),
)
CODICI = tuple(i.codice for i in IMPRONTE)


def impronta_del_giorno(giorno: date, scelta: str | None = None) -> Impronta:
    """L'impronta di quel giorno, oppure quella fissata da ``scelta`` (un codice)."""
    if scelta:
        for impronta in IMPRONTE:
            if impronta.codice == scelta.strip().lower():
                return impronta
        raise ValueError(f"impronta sconosciuta {scelta!r}: valori ammessi {', '.join(CODICI)}")
    return IMPRONTE[giorno.toordinal() % len(IMPRONTE)]
