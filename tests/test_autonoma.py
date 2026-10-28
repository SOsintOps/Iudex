"""App autonoma: cartelle per sistema, /health, scelta della porta, sorveglianza del genitore.

Nessuna finestra nei test: pywebview e pystray non vengono importati.
"""

import os
import socket
import threading
from pathlib import Path

import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

import iudex.__main__ as avvio
from iudex.autonoma import cartelle, finestra, server


def test_identita_windows_dal_titolo():
    assert finestra.identita_windows("Iudex 0.8.1", installata=True) == "SOsintOps.Iudex"
    assert finestra.identita_windows("praeco", installata=True) == "SOsintOps.Praeco"
    # Dai sorgenti (i test girano così) l'identità è distinta da quella dell'app installata.
    assert finestra.identita_windows("Iudex 0.8.1") == "SOsintOps.Iudex.Sviluppo"


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


def test_flussi_sicuri_senza_console(monkeypatch):
    monkeypatch.setattr(server.sys, "stdout", None)
    monkeypatch.setattr(server.sys, "stderr", None)
    server.flussi_sicuri()
    assert server.sys.stdout is not None and server.sys.stderr is not None
    server.sys.stdout.isatty()  # quello che fa uvicorn: non deve sollevare eccezioni


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


def test_backup_settimanale_e_rotazione(tmp_path):
    import sqlite3
    import time as tempo

    from iudex.autonoma import backup

    db = tmp_path / "x.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE t (a)")
    con.execute("INSERT INTO t VALUES (1)")
    con.commit()

    def copia(destinazione):
        con.execute("VACUUM INTO ?", (str(destinazione),))

    cartella = tmp_path / "backup"
    prima = backup.se_serve(copia, cartella, "x")
    assert prima and sqlite3.connect(prima).execute("SELECT a FROM t").fetchone() == (1,)
    assert backup.se_serve(copia, cartella, "x") is None  # meno di sette giorni
    assert backup.serve(cartella, "x", adesso=tempo.time() + 8 * 86400)
    for _ in range(10):
        backup.esegui(copia, cartella, "x", conserva=8)
    assert len(backup.copie(cartella, "x")) == 8


@respx.mock
async def test_aggiornamenti(tmp_path):
    import hashlib

    import httpx
    import pytest

    from iudex.autonoma import aggiornamenti as agg

    assert agg.tupla_versione("v0.10.1-beta") == (0, 10, 1) > agg.tupla_versione("0.9.9")
    installer = b"installer finto"
    pacchetto = {
        "url": "https://esempio.test/Iudex-9.0.0-setup.exe",
        "sha256": hashlib.sha256(installer).hexdigest(),
    }
    respx.get("https://esempio.test/latest.json").mock(
        return_value=httpx.Response(
            200, json={"versione": "9.0.0", "note": "prova", agg.piattaforma(): pacchetto}
        )
    )
    info = await agg.controlla("https://esempio.test/latest.json", "0.7.0")
    assert info["disponibile"] and info["versione"] == "9.0.0"
    assert not (await agg.controlla("https://esempio.test/latest.json", "9.0.0"))["disponibile"]
    respx.get(pacchetto["url"]).mock(return_value=httpx.Response(200, content=installer))
    percorso = await agg.scarica(pacchetto, tmp_path)
    assert percorso.read_bytes() == installer
    with pytest.raises(agg.ErroreAggiornamento, match="sha256"):
        await agg.scarica({**pacchetto, "sha256": "0" * 64}, tmp_path / "altro")
    assert not any((tmp_path / "altro").iterdir())
    respx.get("https://esempio.test/rotto.json").mock(return_value=httpx.Response(404))
    with pytest.raises(agg.ErroreAggiornamento):
        await agg.controlla("https://esempio.test/rotto.json", "0.7.0")
