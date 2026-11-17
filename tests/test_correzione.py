"""Correzione dei testi con regole fisse (iudex.correzione): nessun nome vero, dati inventati."""

import pytest

from iudex import correzione as c
from iudex.correzione import (
    Modifica,
    Prove,
    correggi_nome,
    correggi_testo,
    lettere_e_cifre,
    normalizza_caratteri,
)

# Vocabolario finto: parola piegata → sentenze in cui compare.
VOC = {
    "sanzione": 5000,
    "san": 40,
    "rispetto": 9000,
    "ri": 20,
    "tribunale": 90000,
    "corte": 120000,
    "riforma": 22000,
    "iforma": 4,
    "logico": 3000,
    "giuridico": 4000,
    "omesso": 800,
    "espressamente": 7000,
    "espre": 1,
    "ssamente": 1,
    "da": 150000,
    "lla": 5,
    "dalla": 140000,
    "di": 160000,
    "rispettare": 900,
    "in": 160000,
    "fine": 30000,
    "infine": 20000,
    "ossia": 9000,
    "della": 160000,
    "ed": 50000,
}


def corretto(testo, fonte="sito", **kw):
    return correggi_testo(testo, fonte, Prove(VOC, testo, kw.pop("gemello", None), fonte, **kw))


def test_caratteri():
    testo, n = normalizza_caratteri("dell’avv. “prova”  nato in X il­")
    assert testo == 'dell\'avv. "prova" nato in X il'
    assert n >= 4
    # Gli a capo e le virgolette a caporale restano.
    assert normalizza_caratteri("«a»\nb")[0] == "«a»\nb"


def test_sillabazione_con_prova_e_composte_che_restano():
    r = corretto("la san- zione e il ri- spetto")
    assert r.testo == "la sanzione e il rispetto"
    assert {m.prova for m in r.modifiche} == {"vocabolario"}
    # Composta vera: la forma unita non è nota.
    assert corretto("il nesso logico- giuridico").testo == "il nesso logico- giuridico"
    # Trattino di inciso e «pre- ed post-»: restano.
    assert corretto("pre- ed post-").testo == "pre- ed post-"


def test_sillabazione_pdf_a_fine_riga():
    r = corretto("la san-\nzione", fonte="pdf")
    assert r.testo == "la sanzione"
    # Nel testo del sito la forma senza spazio non si distingue da una composta: resta.
    assert corretto("la san-zione").testo == "la san-zione"


def test_nome_spezzato_senza_prova_resta_e_si_segnala():
    r = corretto("difeso da Zorbe-\nlantis", fonte="pdf")
    assert "Zorbe-\nlantis" in r.testo
    assert r.non_provate and r.non_provate[0][0] == "sillabazione"


def test_lettera_staccata():
    assert corretto("il T ribunale e la C orte").testo == "il Tribunale e la Corte"
    r = corretto("la R iforma")  # «iforma» rarissimo, «riforma» frequente
    assert r.testo == "la Riforma"
    # Voce di elenco e apostrofo perso: restano.
    assert corretto("lett. B ossia").testo == "lett. B ossia"
    assert corretto("L omesso esame").testo == "L omesso esame"
    assert corretto("capo C della").testo == "capo C della"


def test_lettera_staccata_con_il_gemello_per_posizione():
    sito = "comparso poi Qwerbanto davanti alla corte di appello di Zeta nella causa"
    pdf = "comparso poi Q werbanto davanti alla corte di appello di Zeta nella causa"
    r = corretto(pdf, fonte="pdf", gemello=sito)
    assert "Qwerbanto" in r.testo
    assert r.modifiche[0].prova == "gemello"


def test_gemello_che_ha_lo_spazio_non_e_una_prova():
    sito = "comparso poi Q werbanto davanti alla corte di appello di Zeta nella causa"
    r = corretto(sito, fonte="pdf", gemello=sito)
    assert "Q werbanto" in r.testo


def test_spazio_nella_parola():
    r = corretto("come detto espre ssamente")
    assert r.testo == "come detto espressamente"
    # Due parole vere senza il gemello per posizione: restano («di rispettare»).
    assert corretto("l'obbligo di rispettare").testo == "l'obbligo di rispettare"
    # Coppia che esiste anche staccata: resta, anche con il gemello.
    sito = "e alla fine della discussione infine la corte ha deciso di rigettare tutto"
    pdf = "e alla fine della discussione in fine la corte ha deciso di rigettare tutto"
    assert "in fine" in corretto(pdf, fonte="pdf", gemello=sito).testo


def test_due_parole_vere_con_il_gemello_solo_se_la_forma_e_nota():
    sito = "come risulta dalla sentenza impugnata e dagli atti del processo di merito"
    pdf = "come risulta da lla sentenza impugnata e dagli atti del processo di merito"
    r = corretto(pdf, fonte="pdf", gemello=sito)
    assert "dalla sentenza" in r.testo and r.modifiche[0].parole_vere
    # Spenta la classe delle due parole vere: resta.
    r = corretto(pdf, fonte="pdf", gemello=sito, unisci_parole_vere=False)
    assert "da lla" in r.testo


def test_data_incollata():
    r = corretto("nato a Zeta il15/03/1963 e 28/11/1980avverso")
    assert r.testo == "nato a Zeta il 15/03/1963 e 28/11/1980 avverso"
    assert all(m.tipo == "divisione" and m.prova == "forma" for m in r.modifiche)
    # Numeri che non sono una data intera: restano.
    assert corretto("ricorso n. 12345/2020").testo == "ricorso n. 12345/2020"


def test_lettere_e_cifre_sempre_uguali_e_seconda_applicazione_senza_effetti():
    testi = [
        "la san- zione, il T ribunale, espre ssamente, il15/03/1963",
        "dell’avv.  nato a Zeta il1/2/1991",
    ]
    for t in testi:
        r = corretto(t)
        assert lettere_e_cifre(r.testo) == lettere_e_cifre(t)
        assert corretto(r.testo).testo == r.testo


def test_regola_guasta_restituisce_l_originale(monkeypatch):
    # Una regola guasta messa apposta: «5» diventa uno spazio, quindi una cifra sparisce.
    monkeypatch.setattr(c, "RE_SPAZI", c.re.compile(r"5"))
    risultato = correggi_testo("il T ribunale il 15/03/1963", "sito", Prove(VOC))
    assert risultato.testo == "il T ribunale il 15/03/1963" and not risultato.modifiche


def test_eccezione_rifiutata_non_si_applica():
    r = correggi_testo("il T ribunale", "sito", Prove(VOC), eccezioni={("T ribunale", "Tribunale")})
    assert r.testo == "il T ribunale" and not r.modifiche


def test_senza_vocabolario_solo_caratteri_e_date():
    r = correggi_testo("la san- zione, il T ribunale, il15/03/1963  fine")
    assert r.testo == "la san- zione, il T ribunale, il 15/03/1963 fine"


def test_correggi_nome():
    mod = [Modifica("lettera_staccata", "S andro", "Sandro", "gemello", 0, "")]
    assert correggi_nome("S andro Zeta", mod) == "Sandro Zeta"
    assert correggi_nome("", mod) == ""


def test_fonte_sconosciuta():
    with pytest.raises(ValueError):
        Prove(fonte="altro")
