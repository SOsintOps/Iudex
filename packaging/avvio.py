"""Punto di ingresso dell'eseguibile (PyInstaller): la finestra di Iudex, su Windows (WebView2)
come su Linux (WebKitGTK di sistema). Non c'è più il ripiego sul browser: Iudex si usa solo
dalla sua finestra."""

from iudex.desktop import main

if __name__ == "__main__":
    main()
