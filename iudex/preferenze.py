"""Impostazioni scelte dall'utente nella scheda Impostazioni, salvate nell'archivio.

Ogni chiave ha un valore predefinito; quella salvata lo sostituisce. Una variabile
d'ambiente che riguarda la stessa scelta (oggi ``IUDEX_IMPRONTA``) vince su entrambi: la
scheda mostra il campo bloccato con il motivo.
"""

from __future__ import annotations

from .config import Impostazioni
from .impronte import CODICI, ImprontaNonCoerente, personalizzata

MODI_IMPRONTA = ("giorno", "fissa", "personalizzata", "rotazione")
APERTURE_PDF = ("finestra", "programma")

PREDEFINITE: dict = {
    # Spento: non si registra niente (ricerche, risultati, diario, consultate, testi, PDF).
    "conserva_storico": True,
    # None = la cartella ``pdf`` dentro la cartella dei dati.
    "cartella_pdf": None,
    "pdf_apertura": "finestra",
    "impronta_modo": "giorno",
    "impronta_fissa": CODICI[0],
    # Nome dell'impronta personalizzata usata nel modo "personalizzata".
    "impronta_personalizzata": None,
    # [{nome, user_agent, accept_language, client_hints}], controllate da impronte.py.
    "impronte_personalizzate": [],
    # Nel modo "rotazione": le predefinite ruotano insieme alle personalizzate.
    "rotazione_include_predefinite": True,
}

CAMPI_IMPRONTA = ("nome", "user_agent", "accept_language")


class ImpostazioneNonValida(ValueError):
    pass


def _testo_o_nulla(chiave: str, valore) -> str | None:
    if valore is None or (isinstance(valore, str) and not valore.strip()):
        return None
    if not isinstance(valore, str):
        raise ImpostazioneNonValida(f"{chiave}: atteso un testo")
    return valore.strip()


def _impronte(valore) -> list[dict]:
    if not isinstance(valore, list):
        raise ImpostazioneNonValida("impronte_personalizzate: attesa una lista")
    nomi: set[str] = set()
    pulite = []
    for i, voce in enumerate(valore, 1):
        if not isinstance(voce, dict):
            raise ImpostazioneNonValida(f"impronta {i}: attesi i campi {', '.join(CAMPI_IMPRONTA)}")
        for campo in CAMPI_IMPRONTA:
            if not isinstance(voce.get(campo), str) or not voce[campo].strip():
                raise ImpostazioneNonValida(f"impronta {i}: manca {campo}")
        nome = voce["nome"].strip()
        if nome.lower() in nomi:
            raise ImpostazioneNonValida(f"impronta {i}: il nome {nome!r} è già usato")
        nomi.add(nome.lower())
        suggerimenti = voce.get("client_hints") or {}
        if not isinstance(suggerimenti, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in suggerimenti.items()
        ):
            raise ImpostazioneNonValida(f"impronta {i}: client_hints deve essere testo: testo")
        pulita = {
            "nome": nome,
            "user_agent": voce["user_agent"].strip(),
            "accept_language": voce["accept_language"].strip(),
            "client_hints": {k.strip().lower(): v.strip() for k, v in suggerimenti.items()},
        }
        # Un'impronta non credibile non si salva: il client non deve mai trovarla.
        try:
            personalizzata(**pulita)
        except ImprontaNonCoerente as exc:
            raise ImpostazioneNonValida(str(exc)) from None
        pulite.append(pulita)
    return pulite


def valida(valori: dict) -> dict:
    """Controlla le chiavi da salvare e le restituisce pulite; ``None`` = torna al predefinito.

    Solleva ``ImpostazioneNonValida`` con un messaggio per l'utente.
    """
    pulite: dict = {}
    for chiave, valore in valori.items():
        if chiave not in PREDEFINITE:
            raise ImpostazioneNonValida(f"impostazione sconosciuta: {chiave}")
        if valore is None:
            pulite[chiave] = None
        elif chiave in ("conserva_storico", "rotazione_include_predefinite"):
            if not isinstance(valore, bool):
                raise ImpostazioneNonValida(f"{chiave}: atteso vero o falso")
            pulite[chiave] = valore
        elif chiave == "pdf_apertura":
            if valore not in APERTURE_PDF:
                raise ImpostazioneNonValida(
                    f"pdf_apertura: valori ammessi {', '.join(APERTURE_PDF)}"
                )
            pulite[chiave] = valore
        elif chiave == "impronta_modo":
            if valore not in MODI_IMPRONTA:
                raise ImpostazioneNonValida(
                    f"impronta_modo: valori ammessi {', '.join(MODI_IMPRONTA)}"
                )
            pulite[chiave] = valore
        elif chiave == "impronta_fissa":
            if valore not in CODICI:
                raise ImpostazioneNonValida(f"impronta_fissa: valori ammessi {', '.join(CODICI)}")
            pulite[chiave] = valore
        elif chiave == "impronte_personalizzate":
            pulite[chiave] = _impronte(valore)
        else:  # cartella_pdf, impronta_personalizzata
            pulite[chiave] = _testo_o_nulla(chiave, valore)
    return pulite


def controlla_insieme(valori: dict) -> None:
    """Controlli che riguardano più chiavi, sui valori effettivi dopo la modifica."""
    nomi = [i["nome"] for i in valori["impronte_personalizzate"]]
    if (
        valori["impronta_modo"] == "personalizzata"
        and valori["impronta_personalizzata"] not in nomi
    ):
        raise ImpostazioneNonValida("scegli quale impronta personalizzata usare")
    if valori["impronta_modo"] == "rotazione" and not (
        nomi or valori["rotazione_include_predefinite"]
    ):
        raise ImpostazioneNonValida(
            "la rotazione non ha impronte: aggiungine una o includi le predefinite"
        )


def bloccate(config: Impostazioni) -> dict[str, str]:
    """Le chiavi fissate da una variabile d'ambiente, con il motivo da mostrare."""
    if config.impronta:
        motivo = f"fissata dalla variabile d'ambiente IUDEX_IMPRONTA={config.impronta}"
        return {"impronta_modo": motivo, "impronta_fissa": motivo}
    return {}


def effettive(salvate: dict, config: Impostazioni) -> dict:
    """Predefinite, sostituite da quelle salvate, sostituite dalle variabili d'ambiente."""
    valori = {**PREDEFINITE, **{k: v for k, v in salvate.items() if k in PREDEFINITE}}
    if config.impronta:
        valori["impronta_modo"] = "fissa"
        valori["impronta_fissa"] = config.impronta.strip().lower()
    return valori
