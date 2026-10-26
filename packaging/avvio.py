"""Punto di ingresso dell'eseguibile (PyInstaller): la finestra di Iudex o, dove la finestra
nativa non è inclusa (AppImage per Linux), il server con il browser predefinito."""

import sys

if __name__ == "__main__":
    try:
        from iudex.desktop import main
    except (ImportError, SystemExit):  # pywebview non incluso: server e browser
        from iudex.__main__ import main as main_server

        sys.exit(main_server(["--apri", *sys.argv[1:]]))
    main()
