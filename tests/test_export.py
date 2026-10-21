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
