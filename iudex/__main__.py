"""Punto di ingresso: ``python -m iudex`` avvia il server locale."""

from __future__ import annotations

import logging

import uvicorn

from .config import impostazioni


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    uvicorn.run(
        "iudex.app:app",
        host=impostazioni.host,
        port=impostazioni.porta,
        log_level="info",
    )


if __name__ == "__main__":
    main()
