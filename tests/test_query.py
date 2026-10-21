"""Il costruttore di query deve produrre le stesse clausole del sito (o migliori, dove la
sintassi del sito tradisce l'intenzione: NOT, caratteri speciali con gli operatori)."""

from iudex.query import (
    controlla_estremi,
    costruisci_query,
    escape_solr,
    formatta_riferimenti,
    normalizza_documento,
    normalizza_facet,
    parametri_ricerca,
    query_evidenziazione,
    query_riferimenti,
    query_testo_libero,
    url_pdf,
)


def test_escape_solr():
    assert escape_solr("a/b:c") == "a\\/b\\:c"
    assert escape_solr("parola") == "parola"


def test_estremi_numero_anno():
    assert controlla_estremi("12345/2024", 2026) == 'anno:"2024" AND numdec:"12345"'
    assert controlla_estremi("123 / 24", 2026) == 'anno:"2024" AND numdec:"00123"'
    assert controlla_estremi("sent. n. 99 del 2025", 2026) == (
        'anno:"2025" AND numdec:"00099" AND tipoprov:"Sentenza"'
    )
    assert controlla_estremi("ord. 5/2023", 2026) == (
        'anno:"2023" AND numdec:"00005" AND (tipoprov:"Ordinanza"'
        ' OR tipoprov:"Ordinanza Interlocutoria")'
    )


def test_estremi_varianti():
    assert controlla_estremi("Cass. civ. sent. n. 99 del 2025", 2026) == (
        'anno:"2025" AND numdec:"00099" AND tipoprov:"Sentenza"'
    )
    assert controlla_estremi("n. 99 del 2025 sent.", 2026) == (
        'anno:"2025" AND numdec:"00099" AND tipoprov:"Sentenza"'
    )
    assert controlla_estremi("99/25", 2026) == 'anno:"2025" AND numdec:"00099"'
    assert controlla_estremi("123-2024", 2026) == 'anno:"2024" AND numdec:"00123"'
    assert controlla_estremi("dec. 7/2026", 2026) == (
        'anno:"2026" AND numdec:"00007" AND tipoprov:"Decreto"'
    )
    assert controlla_estremi("99/27", 2026) is None  # anno futuro


def test_estremi_non_riconosciuti():
    assert controlla_estremi("licenziamento", 2026) is None
    assert controlla_estremi("123/1999", 2026) is None  # anno fuori dagli ultimi 7
    assert controlla_estremi("1234567/2024", 2026) is None  # numero troppo lungo


def test_testo_libero():
    assert query_testo_libero("licenziamento") == "licenziamento"
    assert query_testo_libero("giusta causa") == '"giusta causa"~7'
    assert query_testo_libero('"giusta causa"') == '"giusta causa"'
    assert query_testo_libero("licenz*") == "licenz*"
    assert query_testo_libero("a AND b") == "a AND b"
    assert query_testo_libero("  ") is None


def test_testo_libero_esclusioni_e_sintassi():
    # Il sito produce ` \-mobbing` e `"demansionamento -mobbing"~7`, che non escludono nulla.
    assert query_testo_libero("NOT mobbing") == "*:* -mobbing"
    assert query_testo_libero("demansionamento NOT mobbing") == "demansionamento -mobbing"
    assert query_testo_libero("demansionamento -mobbing") == "demansionamento -mobbing"
    assert query_testo_libero('"giusta causa" AND licenz*') == '"giusta causa" AND licenz*'
    assert query_testo_libero("(mobbing OR straining) AND danno") == (
        "( mobbing OR straining ) AND danno"
    )
    assert query_testo_libero("a:b OR c") == "a\\:b OR c"
    assert query_testo_libero('danno NOT "giusta causa"') == 'danno -"giusta causa"'
    assert query_testo_libero("NOTE spese") == '"NOTE spese"~7'
    assert query_testo_libero("art. 2043 c.c.") == '"art. 2043 c.c."~7'


def test_evidenziazione_solo_termini_positivi():
    assert query_evidenziazione("demansionamento NOT mobbing") == "demansionamento"
    assert query_evidenziazione('"giusta causa" AND licenz*') == '"giusta causa" licenz*'
    assert query_evidenziazione("NOT mobbing") is None


def test_riferimenti_con_graffe():
    normalizzato = "(18 300 {1970,70}) OR ({st,stat} {lav,lavoratori} 18) OR art. 18 legge 300/1970"
    atteso = (
        '"(18 300 1970)"~8 OR "(18 300 70)"~8 OR "(st lav 18)"~8 OR "(st lavoratori 18)"~8 OR '
        '"(stat lav 18)"~8 OR "(stat lavoratori 18)"~8 OR "art. 18 legge 300/1970"~8'
    )
    assert query_riferimenti(normalizzato) == atteso
    assert query_riferimenti("") is None


def test_costruisci_query_come_il_sito():
    q, hl = costruisci_query("licenziamento", None, {})
    assert q == '(licenziamento) AND ((kind:"snciv" OR kind:"snpen"))'
    assert hl == "nomatch AND (licenziamento)"


def test_costruisci_query_con_filtri():
    q, hl = costruisci_query("mobbing", None, {"kind": ["snciv"], "anno": ["2025", "2026"]})
    assert q == (
        '(mobbing) AND ((kind:"snciv" OR kind:"snpen")) AND kind:"snciv"'
        ' AND (anno:"2025" OR anno:"2026")'
    )
    assert hl == 'nomatch AND (mobbing) AND kind:"snciv" AND (anno:"2025" OR anno:"2026")'


def test_costruisci_query_estremi_senza_evidenziazione():
    q, hl = costruisci_query("12345/2024", None, {})
    assert q.startswith('(anno:"2024" AND numdec:"12345")')
    assert hl == "nomatch"


def test_parametri_ricerca_contengono_i_facet():
    parametri = parametri_ricerca("q", "hl", 20, 10, "udienza")
    coppie = dict(parametri)
    assert coppie["start"] == "20" and coppie["rows"] == "10"
    assert coppie["sort"] == "datdec desc,pd desc,numdec desc"
    assert [v for k, v in parametri if k == "facet.field"] == [
        "kind",
        "tipoprov",
        "szdec",
        "anno",
        "ssz",
        "materia",
    ]
    assert coppie["f.materia.facet.limit"] == "60"
    assert dict(parametri_ricerca("q", "hl", 0, 10, "rilevanza")).get("sort") is None


def test_formatta_riferimenti():
    rnc = {
        "sp": ["DLG", "LS", "CC", "DLG"],
        "num": ["0368", "0296", "", "0368"],
        "dat": ["2001", "2006", "", "2001"],
        "art": ["0001 00", "0001 00", "2043 00", "0001 00"],
        "com": ["0004", "0519", "", "0004"],
    }
    voci = formatta_riferimenti(rnc)
    assert [v["testo"] for v in voci] == [
        "art. 1 d.lgs. 368/2001",
        "art. 1 legge 296/2006",
        "art. 2043 c.c.",
    ]
    assert voci[0]["ricerca"] == "art. 1 d.lgs. 368/2001"
    assert voci[2]["ricerca"] == "art. 2043 c.c."
    assert formatta_riferimenti({}) == []


def test_filtro_materia_nel_query():
    q, _ = costruisci_query("mobbing", None, {"materia": ["LAVORO SUBORDINATO"]})
    assert q.endswith(' AND materia:"LAVORO SUBORDINATO"')


def test_url_pdf():
    url = url_pdf("snciv", "./20210722/snciv@s50@a2021@n21018@tO.pdf")
    assert url == (
        "https://www.italgiure.giustizia.it/xway/application/nif/clean/hc.dll"
        "?verbo=attach&db=snciv&id=.%2F20210722%2Fsnciv%40s50%40a2021%40n21018%40tO.clean.pdf"
    )


def test_normalizza_documento():
    doc = {
        "id": "snpen2026636099S",
        "kind": "snpen",
        "numdec": "36099",
        "anno": "2026",
        "szdec": "6",
        "ssz": "0",
        "tipoprov": "Sentenza",
        "datdec": "20260904",
        "datdep": ["20261014"],
        "presidente": ["RICCIARELLI MASSIMO"],
        "relatore": ["ROSATI MARTINO"],
        "filename": ["./20261014/snpen@s60@a2026@n36099@tS.pdf"],
    }
    hl = {"snpen2026636099S": {"ocr": ['... <em class="hit">licenziamento</em> ...']}}
    n = normalizza_documento(doc, hl)
    assert n["archivio"] == "Penale" and n["sezione"] == "Sesta"
    assert n["ecli"] == "ECLI:IT:CASS:2026:36099PEN"
    assert n["data_decisione"] == "2026-09-04" and n["data_deposito"] == "2026-10-14"
    assert n["frammenti"] == hl["snpen2026636099S"]["ocr"]
    assert n["pdf"].endswith("n36099%40tS.clean.pdf")
    osc = normalizza_documento({**doc, "ocr": ["Provvedimento in fase di oscuramento"]})
    assert osc["pdf"] is None


def test_normalizza_facet():
    f = normalizza_facet({"kind": ["snciv", 3658, "snpen", 367], "anno": ["2021", 1, "2026", 2]})
    assert f["kind"][0] == {"codice": "snciv", "etichetta": "Civile", "conteggio": 3658}
    assert [v["codice"] for v in f["anno"]] == ["2026", "2021"]
