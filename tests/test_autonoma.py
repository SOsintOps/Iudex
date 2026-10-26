"""App autonoma: cartelle per sistema, /health, scelta della porta, sorveglianza del genitore.

Nessuna finestra nei test: pywebview e pystray non vengono importati.
"""

import os
import socket
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import iudex.__main__ as avvio
from iudex.autonoma import cartelle, server


def test_cartelle_per_sistema(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert cartelle.cartella_utente("iudex", "win32") == tmp_path / "Roaming" / "Iudex"
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    assert cartelle.cartella_utente("praeco", "linux") == tmp_path / "share" / "praeco"
    assert cartelle.cartella_utente("iudex", "darwin") == (
        Path.home() / "Library" / "Application Support" / "Iudex"
    )
    # Dai sorgenti dati/ del repository, da un eseguibile la cartella dell'utente.
    assert cartelle.cartella_predefinita("iudex", tmp_path) == tmp_path / "dati"
    monkeypatch.setattr(cartelle.sys, "frozen", True, raising=False)
    assert cartelle.cartella_predefinita("iudex", tmp_path) == cartelle.cartella_utente("iudex")
    cartelle.prepara(tmp_path / "app", ("modelli",))
    assert {p.name for p in (tmp_path / "app").iterdir()} == {"backup", "log", "modelli"}


def test_health_riconoscibile():
    app = FastAPI()
    server.aggiungi_health(app, "iudex", "9.9.9")
    with TestClient(app) as c:
        assert c.get("/health").json() == {"app": "iudex", "versione": "9.9.9", "pid": os.getpid()}


def test_scelta_della_porta(monkeypatch):
    with socket.socket() as occupata:
        occupata.bind(("127.0.0.1", 0))
        occupata.listen()
        porta = occupata.getsockname()[1]
        # Occupata da un altro programma: si passa alla successiva.
        monkeypatch.setattr(server, "leggi_health", lambda h, p, timeout=1.5: None)
        scelta, gia = server.scegli_porta("127.0.0.1", porta, "iudex")
        assert scelta > porta and not gia
        # Occupata dalla stessa app: si riusa.
        monkeypatch.setattr(server, "leggi_health", lambda h, p, timeout=1.5: {"app": "iudex"})
        assert server.scegli_porta("127.0.0.1", porta, "iudex") == (porta, True)
        # Occupata da un'altra app nostra: non si riusa.
        monkeypatch.setattr(server, "leggi_health", lambda h, p, timeout=1.5: {"app": "praeco"})
        assert server.scegli_porta("127.0.0.1", porta, "iudex")[0] != porta


def test_sorveglianza_del_genitore():
    assert server.processo_vivo(os.getpid())
    assert not server.processo_vivo(0)
    chiuso = threading.Event()
    # Un PID che non esiste: il server si chiude subito.
    server.sorveglia_genitore(2**22 + 12345, chiuso.set, intervallo=0.05)
    assert chiuso.wait(2)


def test_argomenti_del_backend(monkeypatch, tmp_path):
    chiamate = []
    monkeypatch.setattr(avvio, "_porta_occupata", lambda: False)
    monkeypatch.setattr(avvio.uvicorn, "run", lambda *a, **k: chiamate.append(k))
    monkeypatch.setattr(avvio, "log_su_file", lambda cartella, nome: None)
    prima = avvio.config.impostazioni
    try:
        assert avvio.main(["--data-dir", str(tmp_path), "--port", "18765"]) == 0
        assert chiamate[0]["port"] == 18765
        assert avvio.config.impostazioni.cartella_dati == tmp_path.resolve()
        assert (tmp_path / "backup").is_dir() and (tmp_path / "log").is_dir()
    finally:
        monkeypatch.delenv("IUDEX_DATI", raising=False)
        monkeypatch.delenv("IUDEX_PORTA", raising=False)
        avvio.config.impostazioni = avvio.impostazioni = prima
