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
