"""Impostazioni di Iudex: indirizzi del servizio remoto, limiti di cortesia, percorsi locali.

Tutti i valori possono essere modificati con variabili d'ambiente ``IUDEX_*``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .autonoma.cartelle import cartella_predefinita

PACCHETTO = Path(__file__).resolve().parent
# Radice dei sorgenti (dove sta ``dati/``): con il layout ``src/`` è due livelli sopra.
RADICE = PACCHETTO.parent.parent if PACCHETTO.parent.name == "src" else PACCHETTO.parent

BASE = "https://www.italgiure.giustizia.it"
URL_SNCASS = f"{BASE}/sncass/"
URL_SOLR = f"{BASE}/sncass/isapi/hc.dll/sn.solr/sn-collection/select"
URL_ESTREMI = f"{BASE}/sncass/isapi/hc.dll/sn/estremi"
URL_PDF = f"{BASE}/xway/application/nif/clean/hc.dll"
URL_TELEMETRIA = f"{BASE}/xway/application/nif/isapishare/hc.dll"
# Aggiornamenti dell'app installata: latest.json della release più recente.
URL_AGGIORNAMENTI = "https://github.com/SOsintOps/Iudex/releases/latest/download/latest.json"


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
        default_factory=lambda: Path(
            os.environ.get("IUDEX_DATI") or cartella_predefinita("iudex", RADICE)
        )
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
    # Controllo degli aggiornamenti all'avvio: per impostazione predefinita solo nell'app
    # installata (dai sorgenti si aggiorna con git); IUDEX_AGGIORNAMENTI=0 lo spegne, =1 lo
    # accende anche dai sorgenti.
    aggiornamenti: str = os.environ.get("IUDEX_AGGIORNAMENTI", "")
    # Limite di cortesia verso l'API Open Data di Normattiva (testo delle norme): secondi
    # minimi fra due richieste, con un lock separato da quello della Corte. Si cambia con
    # IUDEX_INTERVALLO_NORMATTIVA (per esempio 3.5).
    intervallo_normattiva: float = _env_float("IUDEX_INTERVALLO_NORMATTIVA", 2.0)

    @property
    def percorso_db(self) -> Path:
        return self.cartella_dati / "iudex.sqlite"

    @property
    def certificato_intermedio(self) -> Path:
        return PACCHETTO / "certs" / "ti_trust_ov_ca.pem"


impostazioni = Impostazioni()
