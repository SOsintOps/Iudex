"""Controllo degli aggiornamenti da ``latest.json`` della release più recente su GitHub.

All'avvio (una volta per avvio, disattivabile) si legge ``latest.json``; se la versione è più
recente l'interfaccia lo dice. L'installer si scarica e si avvia solo su richiesta
dell'utente, dopo aver controllato lo sha256 pubblicato nello stesso file: niente
aggiornamenti silenziosi. Formato di ``latest.json`` (scritto dal workflow dei rilasci)::

    {"versione": "0.7.0", "data": "2026-10-26", "note": "…",
     "windows": {"url": "…/Iudex-0.7.0-setup.exe", "sha256": "…", "byte": 123},
     "linux": {"url": "…/Iudex-0.7.0-x86_64.AppImage", "sha256": "…", "byte": 456},
     "linux-deb": {"url": "…/iudex_amd64.deb", "sha256": "…", "byte": 789}}

Su Windows l'installer scaricato si avvia e chiude Iudex. Su Linux Iudex non si sostituisce da
solo: il .deb chiede i permessi di amministratore e l'AppImage in uso non si può cambiare
mentre gira. ``prepara_su_linux`` mette il file nuovo al suo posto e dice all'utente come
completare l'aggiornamento.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

log = logging.getLogger("iudex.autonoma")


class ErroreAggiornamento(Exception):
    """latest.json illeggibile, installer non scaricato o con sha256 diverso."""


def tupla_versione(versione: str) -> tuple[int, ...]:
    """``"v0.7.0"`` → ``(0, 7, 0)``; i suffissi (``-beta``) non contano."""
    return tuple(int(n) for n in re.findall(r"\d+", versione.split("-")[0].lstrip("vV"))[:3])


def piattaforma() -> str:
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


def chiave_pacchetto(confezione: str | None = None) -> str:
    """La chiave di latest.json per questa installazione: ``linux-deb`` per il .deb, altrimenti
    il sistema (``windows``, ``linux`` per l'AppImage)."""
    return "linux-deb" if confezione == "deb" else piattaforma()


async def controlla(
    url: str, versione: str, client: httpx.AsyncClient | None = None, chiave: str | None = None
) -> dict:
    """``{"disponibile", "versione", "note", "data", "pacchetto", "chiave"}``; ``disponibile``
    è falso anche quando la release non ha un pacchetto per questo sistema. ``chiave`` sceglie
    il pacchetto (predefinita: il sistema)."""
    proprio = client or httpx.AsyncClient(follow_redirects=True, timeout=10)
    try:
        r = await proprio.get(url)
        r.raise_for_status()
        dati = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ErroreAggiornamento(f"latest.json non leggibile: {exc}") from exc
    finally:
        if client is None:
            await proprio.aclose()
    nuova = str(dati.get("versione") or "")
    chiave = chiave or piattaforma()
    pacchetto = dati.get(chiave)
    return {
        "disponibile": bool(nuova)
        and bool(pacchetto)
        and tupla_versione(nuova) > tupla_versione(versione),
        "versione": nuova,
        "attuale": versione,
        "note": dati.get("note") or "",
        "data": dati.get("data") or "",
        "pacchetto": pacchetto,
        "chiave": chiave,
    }


async def scarica(pacchetto: dict, cartella: Path, client: httpx.AsyncClient | None = None) -> Path:
    """Scarica l'installer in ``cartella`` e ne controlla lo sha256 prima di restituirlo."""
    url, atteso = pacchetto.get("url"), str(pacchetto.get("sha256") or "").lower()
    if not url or len(atteso) != 64:
        raise ErroreAggiornamento("latest.json senza url o sha256 dell'installer")
    cartella.mkdir(parents=True, exist_ok=True)
    destinazione = cartella / url.rsplit("/", 1)[1]
    parziale = destinazione.with_name(destinazione.name + ".incomplete")
    proprio = client or httpx.AsyncClient(follow_redirects=True, timeout=60)
    h = hashlib.sha256()
    try:
        async with proprio.stream("GET", url) as r:
            r.raise_for_status()
            with open(parziale, "wb") as f:
                async for blocco in r.aiter_bytes():
                    f.write(blocco)
                    h.update(blocco)
    except httpx.HTTPError as exc:
        parziale.unlink(missing_ok=True)
        raise ErroreAggiornamento(f"installer non scaricato: {exc}") from exc
    finally:
        if client is None:
            await proprio.aclose()
    if h.hexdigest() != atteso:
        parziale.unlink(missing_ok=True)
        raise ErroreAggiornamento("sha256 dell'installer diverso da quello di latest.json")
    os.replace(parziale, destinazione)
    return destinazione


def avvia_installer(percorso: Path) -> None:
    """Avvia l'installer scaricato (l'installer chiude l'app in esecuzione)."""
    if sys.platform == "win32":
        os.startfile(str(percorso))  # noqa: S606 - file verificato con lo sha256
    else:
        percorso.chmod(0o755)
        subprocess.Popen([str(percorso)], start_new_session=True)  # noqa: S603


def prepara_su_linux(percorso: Path, confezione: str | None, appimage: str | None = None) -> dict:
    """Su Linux: mette il file nuovo al suo posto e restituisce le istruzioni per l'utente,
    ``{"modo", "testo", "comando", "file"}``. Non avvia nulla.

    - ``.deb``: il comando ``sudo apt install`` da copiare.
    - AppImage (``appimage`` = percorso del file in uso, variabile ``APPIMAGE``): il file nuovo
      va accanto a quello in uso, eseguibile; se la cartella non è scrivibile resta dov'è.
    """
    if confezione == "deb":
        return {
            "modo": "deb",
            "testo": "Chiudi Iudex, esegui il comando nel terminale, poi riapri Iudex.",
            "comando": f'sudo apt install "{percorso}"',
            "file": str(percorso),
        }
    destinazione = percorso
    if appimage:
        accanto = Path(appimage).parent / percorso.name
        if accanto != percorso and accanto != Path(appimage):
            # Copia su un nome provvisorio e poi rinomina: un errore a metà (disco pieno) non
            # lascia un file troncato con il nome della versione nuova.
            parziale = accanto.with_name(accanto.name + ".incomplete")
            try:
                shutil.copyfile(percorso, parziale)
                os.replace(parziale, accanto)
                percorso.unlink(missing_ok=True)
                destinazione = accanto
            except OSError:
                parziale.unlink(missing_ok=True)
                log.info(
                    "cartella dell'AppImage non scrivibile: il file nuovo resta in %s", percorso
                )
    try:
        destinazione.chmod(0o755)
    except OSError:  # dischi senza permessi Unix (exFAT, FAT): il file resta com'è
        log.info("permessi non cambiati su %s", destinazione)
    testo = f"Chiudi Iudex e apri il file nuovo: {destinazione}."
    if appimage and Path(appimage) != destinazione:
        testo += f" Poi puoi cancellare il file vecchio: {appimage}."
    return {"modo": "appimage", "testo": testo, "comando": "", "file": str(destinazione)}
