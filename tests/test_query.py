"""Il costruttore di query deve produrre le stesse clausole del sito (o migliori, dove la
sintassi del sito tradisce l'intenzione: NOT, caratteri speciali con gli operatori)."""

from iudex.query import (
    analizza_citazione,
    clausola_segnale,
    controlla_estremi,
    costruisci_query,
    escape_solr,
    formatta_riferimenti,
    normalizza_documento,
    normalizza_facet,
    normalizza_segnali,
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
    assert [v for k, v in parametri if k == "facet.query"] == [
        'ocr:("contrasto giurisprudenziale" OR "difforme orientamento")',
        'ocr:("orientamento consolidato" OR "in senso conforme")',
    ]
    senza = parametri_ricerca("q", "hl", 0, 10, "udienza", con_facet=False)
    assert not [k for k, _ in senza if k.startswith("facet")]


def test_segnali_query_e_conteggi():
    # Senza segnale la query resta quella del sito; con il segnale si aggiunge la clausola,
    # anche all'evidenziazione.
    base = costruisci_query("mobbing", None, {})[0]
    assert base == costruisci_query("mobbing", None, {}, None)[0]
    q, hl = costruisci_query("mobbing", None, {}, "contrasto")
    assert q.endswith(" AND " + clausola_segnale("contrasto"))
    assert hl.endswith(clausola_segnale("contrasto"))
    assert costruisci_query("mobbing", None, {}, "altro")[0] == base
    risposta = {clausola_segnale("contrasto"): 3, clausola_segnale("conformita"): 54, "x": 1}
    assert normalizza_segnali(risposta) == {"contrasto": 3, "conformita": 54}
    assert normalizza_segnali(None) == {}


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


def test_formatta_riferimenti_codici_del_ced_con_suffisso():
    # Riferimenti inventati: i codici arrivano come "COD" con il codice in "rnc-gen".
    rnc = {
        "sp": ["COD", "COD", "COD"],
        "gen": ["PC", "PV", "CC"],
        "art": ["0380 02", "0111 03", "2043 00"],
    }
    voci = formatta_riferimenti(rnc)
    assert [v["testo"] for v in voci] == [
        "art. 380-bis c.p.c.",
        "art. 111-ter c.p.p.",
        "art. 2043 c.c.",
    ]
    assert voci[0] == {
        "tipo": "c.p.c.",
        "numero": "",
        "anno": "",
        "articolo": "380-bis",
        "testo": "art. 380-bis c.p.c.",
        "ricerca": "art. 380-bis c.p.c.",
    }


def test_formatta_riferimenti_decreto_con_numero_e_anno():
    rnc = {
        "sp": ["COD", "DPR", "COD"],
        "gen": ["CC", "LS", "CR"],
        "num": ["0309"],
        "dat": ["1990 10 09"],
        "art": ["2043 00", "0073 00", "0111 00"],
    }
    voci = formatta_riferimenti(rnc)
    assert [v["testo"] for v in voci] == [
        "art. 2043 c.c.",
        "art. 73 d.P.R. 309/1990",
        "art. 111 Cost.",
    ]
    assert (voci[1]["numero"], voci[1]["anno"], voci[1]["tipo"]) == ("309", "1990", "d.P.R.")


def test_formatta_riferimenti_num_piu_corto_dell_elenco():
    # rnc-num e rnc-dat portano solo i valori degli atti che non sono codici.
    rnc = {
        "sp": ["COD", "DLG", "COD", "LS", "COD"],
        "gen": ["PV", "LS", "CP", "LS", "PV"],
        "num": ["0271", "0241"],
        "dat": ["1989 07 28", "1990"],
        "art": ["0310 00", "0173 00", "0001 00", "0002 02", "0582 00"],
    }
    assert [v["testo"] for v in formatta_riferimenti(rnc)] == [
        "art. 310 c.p.p.",
        "art. 173 d.lgs. 271/1989",
        "art. 1 c.p.",
        "art. 2-bis legge 241/1990",
        "art. 582 c.p.p.",
    ]


def test_formatta_riferimenti_riferimento_senza_numero():
    # Tre atti e due numeri: non si sa quale atto ne è privo, nessuno riceve un numero a caso.
    rnc = {
        "sp": ["LS", "RD", "DPR"],
        "gen": ["LS", "LS", "LS"],
        "num": ["0241", "0115"],
        "dat": ["1990", "2002"],
        "art": ["0001 00", "0013 00", "0010 00"],
    }
    voci = formatta_riferimenti(rnc)
    assert [v["testo"] for v in voci] == ["art. 1 legge", "art. 13 r.d.", "art. 10 d.P.R."]
    assert all(v["numero"] == "" and v["anno"] == "" for v in voci)


def test_formatta_riferimenti_articoli_compattati_solo_dove_certi():
    # Un articolo in meno: manca a uno dei due d.P.R. citati per intero. I codici fra i due
    # non si possono allineare; quello dopo l'ultimo d.P.R. sì.
    rnc = {
        "sp": ["DPR", "COD", "COD", "DPR", "COD"],
        "gen": ["LS", "PV", "CP", "LS", "PV"],
        "num": ["0309", "0309"],
        "dat": ["1990", "1990"],
        "art": ["0238 00", "0603 00", "0073 00", "0597 00"],
    }
    assert [v["testo"] for v in formatta_riferimenti(rnc)] == [
        "d.P.R. 309/1990",
        "c.p.p.",
        "c.p.",
        "art. 597 c.p.p.",
    ]
    # Se mancano tanti articoli quanti sono gli atti non codici, l'allineamento è certo.
    rnc = {
        "sp": ["DPR", "COD"],
        "gen": ["LS", "CC"],
        "num": ["0115"],
        "dat": ["2002"],
        "art": ["2043 00"],
    }
    assert [v["testo"] for v in formatta_riferimenti(rnc)] == ["d.P.R. 115/2002", "art. 2043 c.c."]


def test_citazione_con_numero_e_anno():
    assert analizza_citazione("Cass. civ. sez. III n. 1234/2020", 2026) == {
        "kind": "snciv",
        "numdec": "1234",
        "anno": "2020",
        "sezione": "3",
    }
    assert analizza_citazione("Cass. pen. n. 1234/2020", 2026) == {
        "kind": "snpen",
        "numdec": "1234",
        "anno": "2020",
        "sezione": None,
    }
    assert analizza_citazione("Cass. pen. sez. VI n. 1234/2020", 2026)["sezione"] == "6"
    assert analizza_citazione("Cass. 5821/2021", 2026) == {
        "kind": None,
        "numdec": "5821",
        "anno": "2021",
        "sezione": None,
    }
    assert analizza_citazione("CASS. CIV. N. 99 DEL 2025", 2026)["numdec"] == "99"


def test_citazione_con_le_virgole_e_la_data():
    assert analizza_citazione("Cass. civ., Sez. Un., 11 novembre 2008, n. 26972", 2026) == {
        "kind": "snciv",
        "numdec": "26972",
        "anno": "2008",
        "sezione": "U",
    }
    # La data in cifre non si confonde con numero/anno.
    assert analizza_citazione("Cass. pen., Sez. III, 12/01/2022, n. 1234", 2026) == {
        "kind": "snpen",
        "numdec": "1234",
        "anno": "2022",
        "sezione": "3",
    }
    # Lavoro e tributaria sono sezioni civili.
    lavoro = analizza_citazione("Cass., sez. lav., 3 marzo 2021, n. 5821", 2026)
    assert lavoro["kind"] == "snciv" and lavoro["sezione"] == "L" and lavoro["anno"] == "2021"
    assert analizza_citazione("Cass. sez. trib. n. 123/2019", 2026)["kind"] == "snciv"
    assert analizza_citazione("Cass. sez. V n. 123/2019", 2026)["kind"] is None


def test_citazione_per_esteso_e_anno_a_due_cifre():
    assert analizza_citazione("Cassazione civile sezione lavoro 16924/2025", 2026) == {
        "kind": "snciv",
        "numdec": "16924",
        "anno": "2025",
        "sezione": "L",
    }
    assert analizza_citazione("Cass. S.U. n. 500/1999", 2026)["sezione"] == "U"
    assert analizza_citazione("Cass. civ. ord. n. 1234/24", 2026)["anno"] == "2024"
    assert analizza_citazione("Cass. civ. n. 1234/99", 2026)["anno"] == "1999"
    # Nessun controllo sull'anno: lo scarto degli anni futuri spetta a chi chiama.
    assert analizza_citazione("Cass. 1234/2031", 2026)["anno"] == "2031"


def test_citazione_non_interpretabile():
    assert analizza_citazione("testo qualsiasi", 2026) is None
    assert analizza_citazione("Cass. civ. sez. III", 2026) is None  # senza numero
    assert analizza_citazione("cassa integrazione 12/2020", 2026) is None
    assert analizza_citazione("Trib. Milano n. 1234/2020", 2026) is None
    assert analizza_citazione("Cass. civ. n. 1234", 2026) is None  # senza anno né data
    assert analizza_citazione("", 2026) is None
