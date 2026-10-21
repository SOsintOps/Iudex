"""Genera dal logo originale tutte le immagini usate dal progetto.

Legge ``iudex-logo-originale.jpg`` (sfondo bianco) e scrive:

- ``docs/immagini/logo.png`` e ``logo-scuro.png``: logo intero con sfondo trasparente,
  linee scure per il tema chiaro e linee chiare per il tema scuro (README);
- ``iudex/static/marchio.png`` e ``marchio-scuro.png``: bilancia con corona, 128 px,
  per la barra di navigazione;
- ``iudex/static/favicon.ico`` (16, 32, 48, 64 px) e ``favicon.png`` (256 px): tratti
  bianchi su quadrato blu ``#0066ff``; a 16 e 32 px solo la bilancia, senza corona.

Dipendenze: Pillow, numpy, scipy (non servono all'app: ``pip install pillow numpy scipy``).
Uso: ``python assets/logo/genera_logo.py`` dalla radice del repository.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

QUI = Path(__file__).resolve().parent
RADICE = QUI.parent.parent
ORIGINALE = QUI / "iudex-logo-originale.jpg"
IMMAGINI = RADICE / "docs" / "immagini"
STATICA = RADICE / "iudex" / "static"

BLU = (0, 102, 255)
# Centro e raggio del cerchio tratteggiato nell'originale (2048 px): le componenti con
# raggio massimo sotto 700 px sono bilancia, corona e circuiti; la scritta sta sotto y=1500.
CENTRO = (1036, 980)
RAGGIO_INTERNO = 700
SOTTO_SCRITTA = 1500
SOPRA_CORONA = 600  # la bilancia senza corona inizia sotto questa y


def colore_ad_alfa(img: Image.Image) -> np.ndarray:
    """Bianco → trasparente; colore non premoltiplicato (RGBA float 0..255)."""
    rgb = np.asarray(img.convert("RGB")).astype(float)
    alfa = 255.0 - rgb.min(axis=2)
    alfa[alfa < 12] = 0  # rumore JPEG
    sicuro = np.where(alfa > 0, alfa, 1.0)
    col = np.clip(255.0 - (255.0 - rgb) * 255.0 / sicuro[..., None], 0, 255)
    col[alfa == 0] = 0
    return np.dstack([col, alfa])


def variante_scura(rgba: np.ndarray) -> np.ndarray:
    """Linee blu notte → avorio, linee blu → blu chiaro; alfa invariata."""
    r, _g, b, a = (rgba[..., i] for i in range(4))
    t = np.clip((b - r - 36.0) / (162.0 - 36.0), 0, 1)[..., None]
    col = np.array([240.0, 242.0, 248.0]) * (1 - t) + np.array([127.0, 143.0, 255.0]) * t
    out = rgba.copy()
    out[..., :3] = np.where(a[..., None] > 0, col, 0)
    return out


def immagine(rgba: np.ndarray) -> Image.Image:
    return Image.fromarray(np.round(rgba).astype(np.uint8))


def ritaglia(rgba: np.ndarray, margine: float = 0.0) -> np.ndarray:
    ys, xs = np.where(rgba[..., 3] > 0)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    m = int(max(x1 - x0, y1 - y0) * margine)
    h, w = rgba.shape[:2]
    return rgba[max(0, y0 - m) : min(h, y1 + m), max(0, x0 - m) : min(w, x1 + m)]


def quadra(img: Image.Image, margine: float = 0.0) -> Image.Image:
    w, h = img.size
    lato = int(max(w, h) * (1 + 2 * margine))
    q = Image.new("RGBA", (lato, lato), (0, 0, 0, 0))
    q.paste(img, ((lato - w) // 2, (lato - h) // 2))
    return q


def componenti(rgba: np.ndarray) -> tuple[np.ndarray, list[int], list[int]]:
    """Etichette delle componenti connesse e indici di (bilancia+corona) e (sola bilancia)."""
    etichette, n = ndimage.label(rgba[..., 3] > 40, structure=np.ones((3, 3)))
    yy, xx = np.mgrid[: etichette.shape[0], : etichette.shape[1]]
    raggio = np.sqrt((xx - CENTRO[0]) ** 2 + (yy - CENTRO[1]) ** 2)
    indici = np.arange(1, n + 1)
    r_max = ndimage.maximum(raggio, etichette, index=indici)
    y_max = ndimage.maximum(yy, etichette, index=indici)
    y_min = ndimage.minimum(yy, etichette, index=indici)
    tutto = [i + 1 for i in range(n) if r_max[i] < RAGGIO_INTERNO and y_max[i] < SOTTO_SCRITTA]
    bilancia = [i for i in tutto if y_min[i - 1] > SOPRA_CORONA]
    return etichette, tutto, bilancia


def estrai(rgba: np.ndarray, etichette: np.ndarray, indici: list[int], bianco: bool) -> Image.Image:
    maschera = ndimage.binary_dilation(np.isin(etichette, indici), iterations=4)
    out = rgba.copy()
    out[~maschera] = 0
    if bianco:
        out[..., :3] = 255
    return immagine(ritaglia(out))


def icona(tratti: Image.Image, lato: int, spessore: int, occupazione: float = 0.82) -> Image.Image:
    grande = 1024
    alfa = tratti.getchannel("A")
    if spessore > 1:
        alfa = alfa.filter(ImageFilter.MaxFilter(spessore))
    disegno = Image.merge("RGBA", (*Image.new("RGB", tratti.size, (255, 255, 255)).split(), alfa))
    interno = int(grande * occupazione)
    disegno = quadra(disegno).resize((interno, interno), Image.LANCZOS)
    sfondo = Image.new("RGBA", (grande, grande), (0, 0, 0, 0))
    ImageDraw.Draw(sfondo).rounded_rectangle((0, 0, grande - 1, grande - 1), radius=int(grande * 0.2), fill=BLU + (255,))
    sfondo.alpha_composite(disegno, ((grande - interno) // 2, (grande - interno) // 2))
    return sfondo.resize((lato, lato), Image.LANCZOS)


def main() -> None:
    originale = Image.open(ORIGINALE)
    rgba = colore_ad_alfa(originale)

    # Logo intero per il README.
    intero = ritaglia(rgba, 0.02)
    for nome, arr in (("logo.png", intero), ("logo-scuro.png", variante_scura(intero))):
        img = immagine(arr)
        img.thumbnail((1024, 1024), Image.LANCZOS)
        img.save(IMMAGINI / nome, optimize=True)
        print(nome, img.size)

    etichette, tutto, bilancia = componenti(rgba)

    # Marchio della barra di navigazione (colori originali e variante chiara).
    marchio = estrai(rgba, etichette, tutto, bianco=False)
    for nome, img in (("marchio.png", marchio), ("marchio-scuro.png", immagine(variante_scura(np.asarray(marchio).astype(float))))):
        q = quadra(img, 0.02).resize((128, 128), Image.LANCZOS)
        q.save(STATICA / nome, optimize=True)
        print(nome, q.size)

    # Favicon: tratti bianchi su quadrato blu.
    completa = estrai(rgba, etichette, tutto, bianco=True)
    sola = estrai(rgba, etichette, bilancia, bianco=True)
    taglie = {
        16: icona(sola, 16, 45, 0.86),
        32: icona(sola, 32, 25, 0.84),
        48: icona(completa, 48, 19),
        64: icona(completa, 64, 13),
        256: icona(completa, 256, 5),
    }
    taglie[256].save(STATICA / "favicon.png", optimize=True)
    lista = [taglie[s] for s in (64, 48, 32, 16)]
    lista[0].save(STATICA / "favicon.ico", format="ICO", append_images=lista[1:], sizes=[(64, 64), (48, 48), (32, 32), (16, 16)])
    print("favicon.ico", [i.size for i in lista], "favicon.png", taglie[256].size)


if __name__ == "__main__":
    main()
