"""Correzione dei testi delle sentenze con regole fisse, senza modelli e senza cambiare il senso.

Il testo della Corte e quello estratto dai PDF hanno difetti di forma: spazi dentro le parole
(«B erane»), sillabazione di fine riga («san-⏎zione»), parole e date incollate
(«il15/03/1963»), apostrofi e virgolette tipografiche, spazi doppi. Questo modulo li corregge con
poche regole, in ordine fisso.

Garanzie, controllate dal codice:

- **lettere e cifre uguali**: una regola cambia solo spazi, a capo, trattini di fine riga e tipo
  di virgolette. Se dopo le regole le lettere o le cifre non sono identiche all'originale, il
  testo resta l'originale e nessuna modifica vale;
- **ogni unione ha una prova** (``Modifica.prova``): il testo gemello della stessa sentenza, lo
  stesso testo, il vocabolario dell'archivio; senza prova la parola resta com'è;
- **stesso testo, stesso risultato**: nessun caso, nessun modello; una seconda applicazione non
  cambia più nulla;
- il testo originale non si tocca: ``correggi_testo`` restituisce una copia.

Il vocabolario non sta qui: lo passa chi chiama (``Prove``), per esempio contato dall'indice di
ricerca del proprio archivio (``fts5vocab``). Senza vocabolario valgono solo le regole che non
chiedono una prova (caratteri e date incollate) e le prove del testo gemello e dello stesso testo.

Solo libreria standard.
"""

from __future__ import annotations

import collections
import functools
import logging
import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

log = logging.getLogger("iudex.correzione")

VERSIONE_REGOLE = "1"

# Sentenze distinte in cui compare una parola: da qui è una parola vera (un pezzo che è una parola
# vera non si unisce senza prove forti).
SENTENZE_PAROLA_VERA = 3
# Da qui una forma intera è nota e il vocabolario vale come prova.
SENTENZE_FORMA_NOTA = 50
# Una forma che si divide in due parole entrambe 10 volte più frequenti è incollata: non prova.
RAPPORTO_INCOLLATA = 10
# Lettere di contesto prima e dopo il punto dubbio, per cercarlo nel testo gemello.
LETTERE_CONTESTO = 12

# Coppie che esistono sia staccate sia unite: non si uniscono mai da sole.
COPPIE_CHE_RESTANO = frozenset(
    {
        ("in", "fine"),
        ("in", "fatti"),
        ("in", "vece"),
        ("per", "altro"),
        ("non", "ostante"),
        ("per", "tanto"),
        ("in", "oltre"),
        ("di", "fatti"),
        ("in", "vero"),
        ("per", "ciò"),
        ("sopra", "tutto"),
        ("da", "capo"),
    }
)

RE_PAROLA = re.compile(r"[^\W\d_]+")
RE_CARATTERI = [
    (re.compile("[‘’‛`´]"), "'"),
    (re.compile("[“”„]"), '"'),
    (re.compile("[­​‌‍﻿]"), ""),
    (re.compile("[  -   　\t]"), " "),
    (re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]"), " "),
]
RE_SPAZI = re.compile(r" {2,}")
RE_SILL_PDF = re.compile(r"(?<![\w-])([A-Za-zÀ-ÿ]{2,})-[ \t]*\n[ \t]*([a-zà-ÿ]{2,})\b")
RE_SILL_SITO = re.compile(r"(?<![\w-])([A-Za-zÀ-ÿ]{2,})- ([a-zà-ÿ]{2,})\b")
RE_LETTERA = re.compile(r"(?<![\w.'\-/])([A-ZÀ-Ý]) ([a-zà-ÿ]{2,})\b")
RE_LETTERA_MAIUSC = re.compile(r"(?<![\w.'\-/])([A-ZÀ-Ý]) ([A-ZÀ-Ý]{2,})\b(?![.'])")
RE_COPPIA = re.compile(r"(?<![\w'\-])([A-Za-zÀ-ÿ][a-zà-ÿ]+) ([a-zà-ÿ]{2,})\b")
RE_DATA_DOPO = re.compile(r"(?<![\d/.])(\d{1,2}[/.]\d{1,2}[/.]\d{4})(?=[A-Za-zÀ-ÿ])")
RE_DATA_PRIMA = re.compile(r"(?<=[A-Za-zà-ÿ])(?=\d{1,2}[/.]\d{1,2}[/.]\d{4}(?!\d))")
# Una lettera dopo queste parole è una voce di elenco («lett. B ossia», «capo C della»).
MARCHE_LETTERA = re.compile(
    r"(?:lett(?:era|ere)?|cap[oi]|sub|punt[oi]|tabell[ae]|allegat[oi]|sez(?:ione|ioni)?|n|nn|art|"
    r"artt|comma|tipo|classe|categoria|fascia|gruppo|piano|scala|interno|lotto|mod(?:ello)?|serie|"
    r"zona|area|reparto|sigla|imputat[oi]|teste|testi|soggetto|tale|signor|sig)\.?\s*$",
    re.I,
)
VOCALI = "aeiouAEIOUàèéìòù"
FONTI = ("sito", "pdf")


@functools.lru_cache(maxsize=400_000)
def piega(parola: str) -> str:
    """La forma di confronto: senza accenti, minuscola (come FTS5 con remove_diacritics)."""
    scomposta = unicodedata.normalize("NFKD", parola)
    return "".join(c for c in scomposta if not unicodedata.combining(c)).casefold()


def lettere_e_cifre(testo: str) -> str:
    """Le sole lettere e cifre del testo, nell'ordine: devono restare identiche dopo le regole."""
    return "".join(c for c in testo if c.isalnum())


def normalizza_caratteri(testo: str) -> tuple[str, int]:
    """Virgolette e apostrofi dritti, spazi speciali in spazi, niente caratteri invisibili né
    spazi doppi. Gli a capo e le virgolette «a caporale» restano. Restituisce anche il numero di
    sostituzioni."""
    sostituzioni = 0
    for rx, nuovo in RE_CARATTERI:
        testo, k = rx.subn(nuovo, testo)
        sostituzioni += k
    testo, k = RE_SPAZI.subn(" ", testo)
    return testo, sostituzioni + k


@dataclass(frozen=True)
class Modifica:
    """Una modifica applicata: la regola, il testo prima e dopo, la prova."""

    regola: str  # sillabazione | lettera_staccata | spazio_nella_parola | data_incollata
    originale: str
    corretto: str
    prova: str  # gemello | stesso testo | vocabolario | forma
    posizione: int  # nel testo al momento della regola
    contesto: str
    parole_vere: bool = False  # i due pezzi uniti erano due parole vere

    @property
    def tipo(self) -> str:
        return "divisione" if self.regola == "data_incollata" else "unione"


@dataclass
class TestoCorretto:
    testo: str
    modifiche: list[Modifica] = field(default_factory=list)
    non_provate: list[tuple[str, str, int]] = field(default_factory=list)  # regola, forma, pos.
    caratteri: int = 0  # sostituzioni della regola dei caratteri


class Prove:
    """Le prove per correggere un testo.

    - ``vocabolario``: parola piegata (``piega``) → numero di sentenze in cui compare; vuoto se
      non c'è;
    - ``gemello``: l'altro testo della stessa sentenza, se c'è. Per un testo del sito il gemello
      è quello del PDF (che spezza le parole ma non le incolla: una sua parola intera è una
      prova); per un testo del PDF è quello del sito, e la prova si cerca per posizione;
    - ``unisci_parole_vere``: se falso, due pezzi che sono entrambi parole vere non si uniscono
      mai (la classe più rischiosa della regola dello spazio nella parola);
    - ``coppia_rara``: funzione facoltativa (pezzo, pezzo) → vero se la coppia scritta staccata
      è rara nell'archivio; se c'è, due parole vere si uniscono solo quando è vera.
    """

    def __init__(
        self,
        vocabolario: Mapping[str, int] | None = None,
        testo: str = "",
        gemello: str | None = None,
        fonte: str = "sito",
        *,
        unisci_parole_vere: bool = True,
        coppia_rara: Callable[[str, str], bool] | None = None,
    ):
        if fonte not in FONTI:
            raise ValueError(f"fonte sconosciuta: {fonte}")
        self.voc = vocabolario or {}
        self.fonte = fonte
        self.unisci_parole_vere = unisci_parole_vere
        self.coppia_rara = coppia_rara
        self.stesso = collections.Counter(piega(x) for x in RE_PAROLA.findall(testo or ""))
        self.parole_gemello: collections.Counter = collections.Counter()
        self.lettere_gemello, self.spazio_gemello = "", []
        if gemello:
            if fonte == "sito":
                self.parole_gemello.update(piega(x) for x in RE_PAROLA.findall(gemello))
            else:
                lettere, spazi, spazio = [], [], False
                for c in gemello:
                    if c.isalnum():
                        lettere.append(c.lower())
                        spazi.append(spazio)
                        spazio = False
                    elif c.isspace():
                        spazio = True
                self.lettere_gemello, self.spazio_gemello = "".join(lettere), spazi
        self._incollate: dict[str, bool] = {}

    @staticmethod
    def indice_lettere(testo: str) -> tuple[list[int], str]:
        """Per ogni posizione del testo quante lettere e cifre la precedono, e le sole lettere."""
        conta, n, lettere = [], 0, []
        for c in testo:
            conta.append(n)
            if c.isalnum():
                n += 1
                lettere.append(c.lower())
        conta.append(n)
        return conta, "".join(lettere)

    def gemello_per_posizione(self, indice: tuple[list[int], str], posizione: int) -> bool:
        """Vero se nel testo gemello, nello stesso punto, non c'è uno spazio. Il punto si cerca
        con ``LETTERE_CONTESTO`` lettere prima e dopo, e deve trovarsi una volta sola."""
        if not self.lettere_gemello:
            return False
        conta, lettere = indice
        i = conta[posizione]
        k = LETTERE_CONTESTO
        if i < k or i + k > len(lettere):
            return False
        chiave = lettere[i - k : i + k]
        j = self.lettere_gemello.find(chiave)
        if j < 0 or self.lettere_gemello.find(chiave, j + 1) >= 0:
            return False
        return not self.spazio_gemello[j + k]

    def sentenze(self, parola: str) -> int:
        return self.voc.get(piega(parola), 0)

    def incollata(self, forma: str) -> bool:
        """Vero se la forma si divide in due parole entrambe molto più frequenti di lei."""
        if forma not in self._incollate:
            d = self.voc.get(forma, 0)
            self._incollate[forma] = any(
                self.voc.get(forma[:i], 0) >= RAPPORTO_INCOLLATA * d
                and self.voc.get(forma[i:], 0) >= RAPPORTO_INCOLLATA * d
                for i in range(2, len(forma) - 1)
            )
        return self._incollate[forma]

    def nota(self, forma: str) -> bool:
        piegata = piega(forma)
        return self.voc.get(piegata, 0) >= SENTENZE_FORMA_NOTA and not self.incollata(piegata)

    def frammento(self, pezzo: str, intera: str) -> bool:
        d = self.sentenze(pezzo)
        return d < SENTENZE_PAROLA_VERA or d * 100 <= self.sentenze(intera)

    def prova(self, intera: str, a: str, b: str) -> str | None:
        """La prova per unire ``a`` e ``b`` senza il gemello per posizione, o ``None``."""
        piegata = piega(intera)
        if self.parole_gemello.get(piegata, 0) >= 1:
            return "gemello"
        if self.nota(intera):
            return "vocabolario"
        if self.stesso.get(piegata, 0) >= 1:
            if self.fonte == "pdf":
                return "stesso testo"
            # Nel testo del sito le forme incollate esistono: vale solo se i pezzi non sono parole.
            if self.sentenze(a) < SENTENZE_PAROLA_VERA and self.sentenze(b) < SENTENZE_PAROLA_VERA:
                return "stesso testo"
        return None


def correggi_testo(
    testo: str,
    fonte: str = "sito",
    prove: Prove | None = None,
    eccezioni: Iterable[tuple[str, str]] = (),
) -> TestoCorretto:
    """Applica le regole in ordine fisso e restituisce il testo corretto con le modifiche.

    ``eccezioni``: coppie (originale, corretto) rifiutate dall'utente, che non si applicano.
    Se una regola cambiasse lettere o cifre, il risultato è il testo originale senza modifiche.
    """
    if not testo:
        return TestoCorretto(testo or "")
    prove = prove or Prove(testo=testo, fonte=fonte)
    rifiutate = set(eccezioni)
    modifiche: list[Modifica] = []
    non_provate: list[tuple[str, str, int]] = []
    originale = testo
    testo, n_caratteri = normalizza_caratteri(testo)
    stato: dict = {}

    def contesto(m: re.Match) -> str:
        return m.string[max(0, m.start() - 40) : m.end() + 40]

    def applica(m: re.Match, regola: str, corretto: str, prova: str, vere: bool = False) -> str:
        if (m.group(0), corretto) in rifiutate:
            return m.group(0)
        modifiche.append(
            Modifica(regola, m.group(0), corretto, prova, m.start(), contesto(m), vere)
        )
        return corretto

    def sillabazione(m: re.Match) -> str:
        a, b = m.group(1), m.group(2)
        if b in ("ed", "od"):  # «pre- ed post-»
            return m.group(0)
        prova = prove.prova(a + b, a, b)
        if prova:
            return applica(m, "sillabazione", a + b, prova)
        non_provate.append(("sillabazione", m.group(0), m.start()))
        return m.group(0)

    def lettera_staccata(m: re.Match) -> str:
        lettera, pezzo = m.group(1), m.group(2)
        if MARCHE_LETTERA.search(m.string[max(0, m.start() - 14) : m.start()]):
            return m.group(0)
        if lettera in "DL" and pezzo[0] in VOCALI:  # apostrofo perso: «D Amico», «L omesso»
            return m.group(0)
        vera = prove.sentenze(pezzo) >= SENTENZE_PAROLA_VERA
        if fonte == "pdf" and prove.gemello_per_posizione(stato["indice"], m.start(2)):
            return applica(m, "lettera_staccata", lettera + pezzo, "gemello", vera)
        # A, E, I, O sono parole: senza il gemello il pezzo dopo deve essere una non-parola.
        if (lettera in VOCALI and vera) or not prove.frammento(pezzo, lettera + pezzo):
            return m.group(0)
        prova = prove.prova(lettera + pezzo, lettera, pezzo)
        if prova:
            return applica(m, "lettera_staccata", lettera + pezzo, prova, vera)
        non_provate.append(("lettera_staccata", m.group(0), m.start()))
        return m.group(0)

    def spazio_nella_parola(m: re.Match) -> str:
        a, b = m.group(1), m.group(2)
        pa, pb = piega(a), piega(b)
        intera = a + b
        vere = prove.voc.get(pa, 0) >= SENTENZE_PAROLA_VERA and (
            prove.voc.get(pb, 0) >= SENTENZE_PAROLA_VERA
        )
        if vere and (
            not prove.unisci_parole_vere
            or (pa, pb) in COPPIE_CHE_RESTANO
            or (prove.coppia_rara is not None and not prove.coppia_rara(pa, pb))
        ):
            return m.group(0)
        if fonte == "pdf" and prove.gemello_per_posizione(stato["indice"], m.start(2)):
            # Due parole vere si uniscono solo se anche la forma unita è nota.
            if not vere or prove.nota(intera):
                return applica(m, "spazio_nella_parola", intera, "gemello", vere)
            return m.group(0)
        if vere:  # vocabolario e stesso testo non bastano per due parole vere
            return m.group(0)
        # Un pezzo raro che compare anche fuori da questa coppia è una parola della sentenza.
        if len(pa) >= 4 and prove.voc.get(pa, 0) < SENTENZE_PAROLA_VERA:
            if prove.stesso[pa] > stato["coppie"][(pa, pb)]:
                return m.group(0)
        if len(pb) >= 4 and prove.voc.get(pb, 0) < SENTENZE_PAROLA_VERA:
            if prove.stesso[pb] > stato["coppie"][(pa, pb)]:
                return m.group(0)
        prova = prove.prova(intera, a, b)
        if prova:
            return applica(m, "spazio_nella_parola", intera, prova)
        return m.group(0)

    def data_dopo(m: re.Match) -> str:
        return applica(m, "data_incollata", m.group(1) + " ", "forma")

    def data_prima(m: re.Match) -> str:
        return applica(m, "data_incollata", " ", "forma")

    def indice() -> tuple[list[int], str] | None:
        return prove.indice_lettere(testo) if fonte == "pdf" else None

    testo = (RE_SILL_PDF if fonte == "pdf" else RE_SILL_SITO).sub(sillabazione, testo)
    stato["indice"] = indice()
    testo = RE_LETTERA.sub(lettera_staccata, testo)
    stato["indice"] = indice()
    testo = RE_LETTERA_MAIUSC.sub(lettera_staccata, testo)
    stato["indice"] = indice()
    stato["coppie"] = collections.Counter(
        (piega(m.group(1)), piega(m.group(2))) for m in RE_COPPIA.finditer(testo)
    )
    testo = RE_COPPIA.sub(spazio_nella_parola, testo)
    testo = RE_DATA_DOPO.sub(data_dopo, testo)
    testo = RE_DATA_PRIMA.sub(data_prima, testo)
    if lettere_e_cifre(testo) != lettere_e_cifre(originale):
        log.error("correzione annullata: una regola ha cambiato lettere o cifre")
        return TestoCorretto(originale)
    return TestoCorretto(testo, modifiche, non_provate, n_caratteri)


def correggi_nome(nome: str, modifiche: Iterable[Modifica]) -> str:
    """Applica a un nome (per esempio estratto prima della correzione) le unioni già trovate nel
    testo della stessa sentenza: «S andro» diventa «Sandro» se il testo l'ha unito."""
    if not nome:
        return nome
    for m in modifiche:
        if m.tipo == "unione" and m.originale in nome:
            nome = nome.replace(m.originale, m.corretto)
    return nome
