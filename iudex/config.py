"""Impostazioni di Iudex: indirizzi del servizio remoto, limiti di cortesia, percorsi locali.

Tutti i valori possono essere modificati con variabili d'ambiente ``IUDEX_*``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent

BASE = "https://www.italgiure.giustizia.it"
URL_SNCASS = f"{BASE}/sncass/"
URL_SOLR = f"{BASE}/sncass/isapi/hc.dll/sn.solr/sn-collection/select"
URL_ESTREMI = f"{BASE}/sncass/isapi/hc.dll/sn/estremi"
URL_PDF = f"{BASE}/xway/application/nif/clean/hc.dll"
URL_TELEMETRIA = f"{BASE}/xway/application/nif/isapishare/hc.dll"

def _env_int(nome: str, predefinito: int) -> int:
    valore = os.environ.get(nome)
    return int(valore) if valore and valore.isdigit() else predefinito


def _env_float(nome: str, predefinito: float) -> float:
    valore = os.environ.get(nome)
    try:
        return float(valore) if valore else predefinito
    except ValueError:
        return predefinito


@dataclass(frozen=True)
class Impostazioni:
    host: str = os.environ.get("IUDEX_HOST", "127.0.0.1")
    porta: int = _env_int("IUDEX_PORTA", 8765)
    cartella_dati: Path = field(
        default_factory=lambda: Path(os.environ.get("IUDEX_DATI", RADICE / "dati"))
    )
    # Limiti di cortesia verso il server della Corte.
    intervallo_minimo: float = _env_float("IUDEX_INTERVALLO", 2.0)
    timeout: float = _env_float("IUDEX_TIMEOUT", 30.0)
    righe_massime: int = 50
    righe_predefinite: int = 10
    # Cache delle risposte di ricerca (secondi) e della lista degli estremi (giorni).
    ttl_ricerche: int = _env_int("IUDEX_TTL_RICERCHE", 3600)
    ttl_estremi_giorni: int = 30
    # Per impostazione predefinita Iudex non replica le chiamate di telemetria "xway" del sito.
    replica_telemetria: bool = os.environ.get("IUDEX_TELEMETRIA", "0") == "1"
    # Identità dichiarata: per impostazione predefinita il browser del giorno fra quelli di
    # ``impronte.py``; un codice (chrome, edge, firefox) la fissa.
    impronta: str | None = os.environ.get("IUDEX_IMPRONTA") or None

    @property
    def percorso_db(self) -> Path:
        return self.cartella_dati / "iudex.sqlite"

    @property
    def certificato_intermedio(self) -> Path:
        return RADICE / "iudex" / "certs" / "ti_trust_ov_ca.pem"


impostazioni = Impostazioni()
