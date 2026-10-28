from iudex import config


def test_certificato_intermedio_nel_pacchetto():
    assert config.impostazioni.certificato_intermedio.is_file()


def test_radice_dei_sorgenti_sopra_src():
    # Con il layout src/ i dati dei sorgenti restano accanto a pyproject.toml.
    assert (config.RADICE / "pyproject.toml").is_file()
    assert config.PACCHETTO.parent.name == "src"
