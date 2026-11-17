"""Controlla il pacchetto Linux costruito da PyInstaller e scrive le dipendenze del .deb.

Uso (solo su Linux, richiede ``readelf``)::

    python packaging/controlla_pacchetto.py build/dist/Iudex

Fallisce (codice 1) se:

- un file del pacchetto chiede una libreria che non è nel pacchetto e non è in ``SISTEMA``;
- ci sono ancora dati di GTK (``share/``, ``gio_modules/``, ``lib/gdk-pixbuf/``…);
- manca uno dei typelib richiesti;
- c'è un collegamento simbolico rotto.

Scrive ``dipendenze.txt`` accanto alla cartella del pacchetto (il campo ``Depends``).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from librerie_linux import DATI_ESCLUSI, TYPELIB_RICHIESTI, dipendenze  # noqa: E402

ELF = b"\x7fELF"


def librerie_richieste(file: Path) -> set[str]:
    """I nomi delle librerie richieste (voci NEEDED) da un file ELF."""
    uscita = subprocess.run(
        ["readelf", "-d", str(file)], capture_output=True, text=True, check=True
    ).stdout
    nomi = set()
    for riga in uscita.splitlines():
        if "(NEEDED)" in riga and "[" in riga:
            nomi.add(riga.split("[", 1)[1].split("]", 1)[0])
    return nomi


def controlla(cartella: Path) -> tuple[list[str], set[str]]:
    """Gli errori trovati e le librerie che il pacchetto chiede al sistema."""
    errori: list[str] = []
    interna = cartella / "_internal"
    for dato in DATI_ESCLUSI:
        if (interna / dato).exists():
            errori.append(f"dati di GTK nel pacchetto: _internal/{dato}")
    for nome in TYPELIB_RICHIESTI:
        if not (interna / "gi_typelibs" / f"{nome}.typelib").is_file():
            errori.append(f"typelib mancante: {nome}")
    presenti: set[str] = set()
    elf: list[Path] = []
    for f in sorted(cartella.rglob("*")):
        if f.is_symlink() and not f.exists():
            errori.append(f"collegamento rotto: {f.relative_to(cartella)}")
            continue
        if not f.is_file():
            continue
        presenti.add(f.name)
        with f.open("rb") as d:
            if d.read(4) == ELF:
                elf.append(f)
    richieste: set[str] = set()
    for f in elf:
        richieste |= librerie_richieste(f)
    dal_sistema = richieste - presenti
    try:
        dipendenze(dal_sistema)
    except KeyError as exc:
        errori.append(str(exc.args[0]))
    return errori, dal_sistema


def main(argv: list[str]) -> int:
    cartella = Path(argv[1] if len(argv) > 1 else "build/dist/Iudex")
    errori, dal_sistema = controlla(cartella)
    print("librerie dal sistema:", ", ".join(sorted(dal_sistema)))
    if errori:
        for e in errori:
            print("ERRORE:", e)
        return 1
    campo = dipendenze(dal_sistema)
    (cartella.parent / "dipendenze.txt").write_text(campo + "\n", encoding="utf-8")
    print("Depends:", campo)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
