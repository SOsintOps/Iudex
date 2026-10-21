"""Genera l'immagine di anteprima per i social (GitHub → Settings → Social preview).

Scrive ``docs/immagini/anteprima-social.png``, 1280 × 640 px (rapporto 2:1 richiesto da
GitHub), sfondo del tema scuro dell'app, logo a sinistra e testo a destra, con un margine
di 40 px che GitHub non ritaglia.

Dipendenze: Pillow (non serve all'app). Font: Segoe UI di Windows; su altri sistemi
impostare ``FONT_DIR``. Uso: ``python assets/logo/genera_anteprima.py`` dalla radice.
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

QUI = Path(__file__).resolve().parent
RADICE = QUI.parent.parent
IMMAGINI = RADICE / "docs" / "immagini"
FONT_DIR = Path(os.environ.get("FONT_DIR", r"C:\Windows\Fonts"))

LARGHEZZA, ALTEZZA = 1280, 640
SFONDO = (22, 22, 22)
TESTO = (238, 238, 238)
GRIGIO = (160, 160, 160)
BLU = (0, 102, 255)
BLU_CHIARO = (122, 154, 255)


def font(nome: str, corpo: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / nome), corpo)


def main() -> None:
    img = Image.new("RGB", (LARGHEZZA, ALTEZZA), SFONDO)
    d = ImageDraw.Draw(img)

    # Fascia blu in alto, come la scheda attiva della barra di navigazione.
    d.rectangle([0, 0, LARGHEZZA, 8], fill=BLU)

    logo = Image.open(IMMAGINI / "logo-scuro.png").convert("RGBA")
    altezza_logo = 440
    logo = logo.resize((round(logo.width * altezza_logo / logo.height), altezza_logo), Image.LANCZOS)
    img.paste(logo, (70, (ALTEZZA - altezza_logo) // 2 + 4), logo)

    x = 70 + logo.width + 70
    y = 150
    d.text((x, y), "Iudex", font=font("segoeuib.ttf", 104), fill=TESTO, anchor="ls")
    y += 52
    d.text(
        (x, y),
        "Interfaccia locale per SentenzeWeb",
        font=font("segoeui.ttf", 36),
        fill=BLU_CHIARO,
        anchor="ls",
    )
    y += 42
    d.text(
        (x, y),
        "Corte Suprema di Cassazione",
        font=font("segoeui.ttf", 30),
        fill=GRIGIO,
        anchor="ls",
    )

    punti = [
        "Stessa sintassi e stessi risultati del sito ufficiale",
        "Una richiesta per ricerca, filtri e materia inclusi",
        "Testo in paragrafi, P.Q.M., riferimenti normativi",
        "Diario delle consultazioni, export, server MCP",
    ]
    corpo = font("segoeui.ttf", 27)
    y += 70
    for punto in punti:
        d.ellipse([x, y - 15, x + 10, y - 5], fill=BLU)
        d.text((x + 26, y), punto, font=corpo, fill=TESTO, anchor="ls")
        y += 44

    d.text(
        (LARGHEZZA - 48, ALTEZZA - 40),
        "github.com/SOsintOps/Iudex · MIT",
        font=font("segoeui.ttf", 22),
        fill=GRIGIO,
        anchor="rs",
    )

    destinazione = IMMAGINI / "anteprima-social.png"
    img.save(destinazione, optimize=True)
    print(destinazione, img.size, destinazione.stat().st_size, "byte")


if __name__ == "__main__":
    main()
