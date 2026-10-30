from iudex.export import paragrafa, risultati_csv


def test_paragrafa_intestazioni_e_punti():
    testo = (
        "Corte di Cassazione sezione lavoro.FATTI DI CAUSA1. Con sentenza del 2024 la Corte "
        "di appello ha respinto il gravame. 2. Avverso la sentenza ricorre Tizio; 2.1. Con il "
        "primo motivo deduce la violazione dell'art. 18 legge n. 300/1970. RAGIONI DELLA "
        "DECISIONE3. Il ricorso è fondato.P.Q.M.La Corte accoglie il ricorso."
    )
    t, pos = paragrafa(testo)
    assert "\n\nFATTI DI CAUSA\n\n" in t
    assert "\n\nRAGIONI DELLA DECISIONE\n\n" in t
    assert "\n\n2. Avverso" in t and "\n\n2.1. Con il primo" in t
    # "n. 300/1970." non è un punto numerato
    assert "\n\n300/1970" not in t
    assert pos is not None and t[pos:].startswith("P.Q.M.")
    assert "\n\nP.Q.M.\n\nLa Corte accoglie" in t


def test_paragrafa_vuoto_e_con_a_capo():
    assert paragrafa(None) == ("", None)
    t, pos = paragrafa("riga uno\nriga due")
    assert t == "riga uno\nriga due" and pos is None


def test_csv_senza_tag():
    csv = risultati_csv([{"id": "x", "frammenti": ['a <em class="hit">b</em> c']}])
    assert "a b c" in csv and "<em" not in csv


def test_ftm_entita_e_id_stabili():
    import json

    from iudex.export import consultate_ftm, entita_ftm, id_ftm

    doc = {
        "archivio": "Civile",
        "sezione": "Lavoro",
        "tipo": "Sentenza",
        "numero": "26495",
        "anno": "2026",
        "data_decisione": "2026-09-22",
        "data_deposito": "2026-10-09",
        "ecli": "ECLI:IT:CASS:2026:26495CIV",
        "filename": "./20261014/snciv@sL0@a2026@n26495@tS.pdf",
        "presidente": "ROSSI MARIO",
        "relatore": "",
        "materia": ["LAVORO SUBORDINATO"],
        "massima": "P.Q.M. rigetta",
        "riferimenti_normativi": [{"testo": "art. 18 legge 300/1970"}],
    }
    grezzo = {"kind": "snciv", "ocr": ["Testo.P.Q.M.La Corte rigetta."]}
    entita = entita_ftm("snciv2026L26495S", doc, grezzo, "da citare")
    per_schema = {e["schema"]: e for e in entita}
    assert set(per_schema) == {"Document", "CourtCase", "Person", "CourtCaseParty"}
    caso, documento = per_schema["CourtCase"], per_schema["Document"]
    assert caso["properties"]["caseNumber"] == ["26495/2026"]
    assert caso["properties"]["category"] == ["civile"]
    assert caso["properties"]["alias"] == ["ECLI:IT:CASS:2026:26495CIV"]
    assert "art. 18 legge 300/1970" in caso["properties"]["keywords"]
    assert caso["properties"]["proof"] == [documento["id"]]
    assert documento["properties"]["fileName"] == ["snciv@sL0@a2026@n26495@tS.pdf"]
    assert "P.Q.M." in documento["properties"]["bodyText"][0]
    parte = per_schema["CourtCaseParty"]["properties"]
    assert parte["role"] == ["presidente"] and parte["case"] == [caso["id"]]
    # Proprietà sempre in liste, nessun valore vuoto (il relatore manca).
    assert all(isinstance(v, list) and v for e in entita for v in e["properties"].values())
    assert id_ftm("persona", "ROSSI MARIO") == per_schema["Person"]["id"]
    # Lo stesso magistrato in due sentenze compare una volta sola.
    righe = consultate_ftm([("a", doc, grezzo, None), ("b", doc, grezzo, None)]).splitlines()
    schemi = [json.loads(r)["schema"] for r in righe]
    assert schemi.count("Person") == 1 and schemi.count("CourtCase") == 2


# --- norme citate nell'export FtM (sentenza di prova inventata) ---------------------------

# Una citazione leggibile da Normattiva (codice), una da EUR-Lex e una non leggibile (manca il
# numero dell'atto): solo le prime due diventano entità.
DOC_NORME = {
    "archivio": "Civile",
    "sezione": "3",
    "tipo": "Ordinanza",
    "numero": "1234",
    "anno": "2026",
    "data_decisione": "2026-05-04",
    "data_deposito": "2026-06-01",
    "ecli": "ECLI:IT:CASS:2026:1234CIV",
    "filename": "./20260601/snciv@s30@a2026@n01234@tO.pdf",
    "presidente": "BIANCHI ANNA",
    "relatore": "VERDI LUCA",
    "materia": ["RESPONSABILITA CIVILE"],
    "massima": "rigetta",
    "pdf": "https://example.invalid/x.pdf",
    "riferimenti_normativi": [
        {"tipo": "c.c.", "numero": "", "anno": "", "articolo": "2043", "testo": "art. 2043 c.c."},
        {
            "tipo": "reg. UE",
            "numero": "679",
            "anno": "2016",
            "articolo": "6",
            "testo": "art. 6 reg. UE 679/2016",
        },
        {"tipo": "legge", "numero": "", "anno": "1970", "articolo": "18", "testo": "art. 18 legge"},
    ],
}
GREZZO_NORME = {"kind": "snciv", "ocr": ["Fatto inventato.P.Q.M.La Corte rigetta."]}
ID_NORME = "snciv2026301234O"

# Le entità della stessa sentenza prodotte da export.py prima di questo passo (commit 5a81797):
# devono restare identiche, keywords comprese (Praeco).
ENTITA_PRIMA = [
    {
        "id": "cfc81109f31ef05377d571b3cd2f9ac1ca4c0788",
        "schema": "Document",
        "properties": {
            "fileName": ["snciv@s30@a2026@n01234@tO.pdf"],
            "title": ["Cass. pen., Sez. 3, Ordinanza n. 1234/2026"],
            "bodyText": ["Fatto inventato.\n\nP.Q.M.\n\nLa Corte rigetta."],
            "authoredAt": ["2026-05-04"],
            "publishedAt": ["2026-06-01"],
            "date": ["2026-06-01"],
            "language": ["ita"],
            "publisher": ["Corte Suprema di Cassazione, SentenzeWeb"],
            "sourceUrl": ["https://example.invalid/x.pdf"],
        },
    },
    {
        "id": "1a6c233f946227ce38ec75f248041ed744d0726a",
        "schema": "CourtCase",
        "properties": {
            "name": ["Cass. pen., Sez. 3, Ordinanza n. 1234/2026"],
            "caseNumber": ["1234/2026"],
            "court": ["Corte Suprema di Cassazione, Sezione 3"],
            "category": ["civile"],
            "type": ["Ordinanza"],
            "alias": ["ECLI:IT:CASS:2026:1234CIV"],
            "keywords": [
                "RESPONSABILITA CIVILE",
                "art. 2043 c.c.",
                "art. 6 reg. UE 679/2016",
                "art. 18 legge",
            ],
            "summary": ["rigetta"],
            "notes": ["nota"],
            "country": ["it"],
            "publisher": ["Corte Suprema di Cassazione, SentenzeWeb"],
            "sourceUrl": ["https://example.invalid/x.pdf"],
            "proof": ["cfc81109f31ef05377d571b3cd2f9ac1ca4c0788"],
        },
    },
    {
        "id": "0bc63e1b1c8c5fdbe89d421368d43af8f22d23a5",
        "schema": "Person",
        "properties": {"name": ["BIANCHI ANNA"]},
    },
    {
        "id": "12b29879bded377144fc1c9432e0162e446f4a0c",
        "schema": "CourtCaseParty",
        "properties": {
            "party": ["0bc63e1b1c8c5fdbe89d421368d43af8f22d23a5"],
            "case": ["1a6c233f946227ce38ec75f248041ed744d0726a"],
            "role": ["presidente"],
        },
    },
    {
        "id": "1f404d9c061e30d97122e13128a51d1446336155",
        "schema": "Person",
        "properties": {"name": ["VERDI LUCA"]},
    },
    {
        "id": "726658828782954714a8548a1e938de1b662d532",
        "schema": "CourtCaseParty",
        "properties": {
            "party": ["1f404d9c061e30d97122e13128a51d1446336155"],
            "case": ["1a6c233f946227ce38ec75f248041ed744d0726a"],
            "role": ["relatore"],
        },
    },
]


def _norme_e_collegamenti(entita: list[dict]) -> tuple[list[dict], list[dict]]:
    collegamenti = [e for e in entita if e["schema"] == "Documentation"]
    id_norme = {c["properties"]["document"][0] for c in collegamenti}
    return [e for e in entita if e["id"] in id_norme], collegamenti


def test_ftm_entita_preesistenti_invariate_con_norma():
    from iudex.export import entita_ftm

    entita = entita_ftm(ID_NORME, DOC_NORME, GREZZO_NORME, "nota")
    assert entita[: len(ENTITA_PRIMA)] == ENTITA_PRIMA
    caso = next(e for e in entita if e["schema"] == "CourtCase")
    assert caso["properties"]["keywords"] == [
        "RESPONSABILITA CIVILE",
        "art. 2043 c.c.",
        "art. 6 reg. UE 679/2016",
        "art. 18 legge",
    ]
    norme, collegamenti = _norme_e_collegamenti(entita)
    assert len(norme) == len(collegamenti) == 2
    assert len(entita) == len(ENTITA_PRIMA) + len(norme) + len(collegamenti)


def test_ftm_norma_documento_e_documentation():
    from iudex.export import entita_ftm, id_ftm

    entita = entita_ftm(ID_NORME, DOC_NORME, GREZZO_NORME, None)
    caso = next(e for e in entita if e["schema"] == "CourtCase")
    norme, collegamenti = _norme_e_collegamenti(entita)
    per_titolo = {n["properties"]["title"][0]: n for n in norme}
    assert set(per_titolo) == {"art. 2043 c.c.", "art. 6 reg. UE 679/2016"}
    codice = per_titolo["art. 2043 c.c."]
    assert codice["schema"] == "Document"
    assert codice["id"] == id_ftm("norma", "CC|||2043")
    assert codice["properties"]["sourceUrl"] == [
        "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262:2~art2043"
    ]
    assert codice["properties"]["publisher"] == ["Normattiva (IPZS)"]
    assert codice["properties"]["language"] == ["ita"]
    ue = per_titolo["art. 6 reg. UE 679/2016"]
    assert ue["properties"]["sourceUrl"] == [
        "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32016R0679"
    ]
    assert ue["properties"]["publisher"] == ["EUR-Lex"]
    for collegamento in collegamenti:
        assert collegamento["properties"]["entity"] == [caso["id"]]
        assert collegamento["properties"]["role"] == ["norma citata"]
    assert {c["properties"]["document"][0] for c in collegamenti} == {n["id"] for n in norme}


def test_ftm_norma_stesso_id_in_due_sentenze():
    import json

    from iudex.export import consultate_ftm, entita_ftm

    altro = {
        **DOC_NORME,
        "numero": "999",
        "ecli": None,
        "riferimenti_normativi": [{"tipo": "c.c.", "articolo": "2043", "testo": "art. 2043 c.c."}],
    }
    norme_a, _ = _norme_e_collegamenti(entita_ftm("a", DOC_NORME, GREZZO_NORME, None))
    norme_b, _ = _norme_e_collegamenti(entita_ftm("b", altro, GREZZO_NORME, None))
    assert len(norme_b) == 1 and norme_b[0]["id"] in {n["id"] for n in norme_a}
    righe = [
        json.loads(r)
        for r in consultate_ftm(
            [("a", DOC_NORME, GREZZO_NORME, None), ("b", altro, GREZZO_NORME, None)]
        ).splitlines()
    ]
    titoli = [r["properties"]["title"][0] for r in righe if r["schema"] == "Document"]
    # La norma comune compare una volta sola; i collegamenti restano uno per sentenza e norma.
    assert titoli.count("art. 2043 c.c.") == 1
    assert sum(1 for r in righe if r["schema"] == "Documentation") == 3


def test_ftm_riferimento_non_leggibile_senza_norma():
    from iudex.export import entita_ftm

    non_leggibili = [
        {"testo": "art. 18 legge 300/1970"},
        {"tipo": "legge", "numero": "", "anno": "1970", "articolo": "18"},
        {"tipo": "c.c.", "articolo": "duemila"},
        {"tipo": "CEDU", "articolo": "6"},
        {"tipo": "legge reg.", "numero": "1", "anno": "2000", "articolo": "1"},
        {"tipo": "reg. UE", "numero": "", "anno": "2016", "articolo": "6"},
    ]
    doc = {**DOC_NORME, "riferimenti_normativi": non_leggibili}
    schemi = [e["schema"] for e in entita_ftm(ID_NORME, doc, GREZZO_NORME, None)]
    assert "Documentation" not in schemi and schemi.count("Document") == 1


def test_norma_citata_lettura_stretta():
    from iudex.norme import norma_citata

    legge = norma_citata({"tipo": "legge", "numero": "0300", "anno": "1970", "articolo": "18"})
    assert legge["chiave"] == "LS|300|1970|18" and legge["titolo"] == "art. 18 legge 300/1970"
    # Senza la data completa dell'atto il link URN non si costruisce (nessuna richiesta).
    assert legge["url"] is None and legge["editore"] == "Normattiva (IPZS)"
    bis = norma_citata({"tipo": "c.p.c.", "articolo": "380bis"})
    assert bis["articolo"] == "380-bis" and bis["url"].endswith("~art380bis")
    assert norma_citata({"tipo": "c.p.c.", "articolo": "380-bis"})["chiave"] == bis["chiave"]
    trattato = norma_citata({"tipo": "TUE", "articolo": "6"})
    assert trattato["url"].endswith("CELEX:12016M/TXT") and trattato["titolo"] == "art. 6 TUE"
    assert norma_citata({"tipo": "legge", "anno": "1970", "articolo": "18"}) is None
    assert norma_citata({"tipo": "c.c."}) is None
    assert norma_citata({"tipo": "dir. UE", "numero": "x", "anno": "2019"}) is None


def test_ftm_schema_e_proprieta_validi_nel_modello():
    import json

    from followthemoney import model

    from iudex.export import consultate_ftm

    voci = [
        (ID_NORME, DOC_NORME, GREZZO_NORME, "nota"),
        ("snciv2026L26495S", {**DOC_NORME, "numero": "26495"}, GREZZO_NORME, None),
    ]
    entita = [json.loads(r) for r in consultate_ftm(voci).splitlines()]
    per_id = {e["id"]: e for e in entita}
    assert {"Documentation", "CourtCase", "Document", "Person", "CourtCaseParty"} <= {
        e["schema"] for e in entita
    }
    # Il modello installato non ha uno schema per gli atti normativi: Document + Documentation.
    assert not [s for s in model.schemata if "legislat" in s.lower() or "law" in s.lower()]
    for e in entita:
        schema = model.get(e["schema"])
        assert schema is not None and not schema.abstract, e["schema"]
        proxy = model.get_proxy(e, cleaned=False)
        for nome, valori in e["properties"].items():
            assert nome in schema.properties, (e["schema"], nome)
            # Ogni valore supera la pulizia del tipo FtM (date, url, lingua, paese, id).
            assert len(proxy.get(nome)) == len(valori), (e["schema"], nome, valori)
            intervallo = schema.properties[nome].range
            if intervallo is not None:
                for valore in valori:
                    assert model.get(per_id[valore]["schema"]).is_a(intervallo), (e, nome)
