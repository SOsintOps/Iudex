# Prova degli installer (Windows e Linux)

Lista da seguire su una macchina virtuale prima di pubblicare una versione (tag `v*`). Gli
installer escono dal workflow `Rilascio` (`.github/workflows/rilascio.yml`) oppure si
costruiscono a mano con i comandi in fondo. Segnare l'esito nel Diario di
[PROGRESS.md](PROGRESS.md), con versione, sistema e data.

## Windows 11 (o Windows 10 con WebView2)

1. **Installazione pulita** (utente senza diritti di amministratore): `Iudex-X.Y.Z-setup.exe`.
   - Su Windows 10 senza WebView2 compare l'avviso con il link per installarlo.
   - Pagina "Cartella dei PDF": proposta `%APPDATA%\Iudex\pdf`; sceglierne un'altra (anche con
     spazi e lettere accentate, per esempio `D:\Sentenze è qui`).
   - Fine: esistono `%LOCALAPPDATA%\Programs\Iudex\Iudex.exe` e
     `%APPDATA%\Iudex\installazione.ini` con `[pdf] cartella = ...`.
2. **Primo avvio** dal menu Start: si apre la finestra (nessun browser), con l'icona
   nell'area di notifica; la scheda Impostazioni mostra la cartella scelta e non chiede di
   sceglierla di nuovo.
3. **Accesso**: Chrome o Edge su http://127.0.0.1:8765/ mostra solo "Iudex si usa dalla sua
   finestra"; http://127.0.0.1:8765/health risponde.
4. **Ricerca** (con la rete che raggiunge SentenzeWeb): una ricerca, la pagina 2, una
   sentenza aperta, il suo PDF aperto nella finestra; il file è nella cartella scelta;
   riaperto, nella scheda Stato non c'è una nuova richiesta "pdf".
5. **Impostazioni**: PDF con il programma del computer (si apre il lettore di Windows);
   un'impronta personalizzata con "Prova"; storico spento → una ricerca non compare in
   Cronologia.
6. **Export e importazione**: pacchetto ZIP dalla Cronologia; importato in una seconda
   installazione (o reimportato nella stessa: niente duplicati nel riepilogo).
7. **Aggiornamento sopra la 0.7.0**: installare prima la 0.7.0, fare due ricerche, poi la
   versione nuova sopra. Le ricerche ci sono ancora; in `%APPDATA%\Iudex\backup` c'è la copia
   "prima della migrazione".
8. **Disinstallazione** da Impostazioni di Windows: il programma sparisce, `%APPDATA%\Iudex`
   (database, PDF, token) resta.

## Linux (Debian 13, per esempio la VM `london`; Ubuntu 22.04 o successiva)

1. Senza WebKitGTK: `chmod +x Iudex-X.Y.Z-x86_64.AppImage` e avvio da terminale → messaggio
   con il comando da usare (`sudo apt install gir1.2-webkit2-4.1 python3-gi`), nessun browser.
2. Con WebKitGTK: si apre la finestra; al primo avvio la barra in alto chiede la cartella dei
   PDF (proposta `~/.local/share/iudex/pdf`); "Usa questa cartella" e al riavvio non la chiede
   più.
3. Punti 3-6 come su Windows (il programma PDF del sistema si apre con `xdg-open`).
4. I dati sono in `~/.local/share/iudex` e restano cancellando l'AppImage.

## Costruzione a mano

```bat
rem Windows (nel venv di Iudex)
python -m pip install -e .[desktop] pyinstaller==6.22.3
python -m PyInstaller --noconfirm --distpath build/dist --workpath build/lavoro packaging/iudex.spec
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DVersione=0.8.0 packaging\iudex.iss
```

```sh
# Linux (Debian/Ubuntu); PyGObject < 3.51 perché l'hook di PyInstaller vuole GIRepository 2.0
sudo apt install libgirepository1.0-dev libcairo2-dev gir1.2-webkit2-4.1 \
  gir1.2-girepository-2.0 gir1.2-ayatanaappindicator3-0.1
python -m pip install -e .[desktop] "PyGObject<3.51" pyinstaller==6.22.3
python -m PyInstaller --noconfirm --distpath build/dist --workpath build/lavoro packaging/iudex.spec
sh packaging/costruisci_appimage.sh 0.8.0
```

Senza scrivania (via SSH) la finestra si prova in un display virtuale:
`Xvfb :99 &` e `DISPLAY=:99 APPIMAGE_EXTRACT_AND_RUN=1 dbus-run-session -- ./Iudex-*.AppImage`,
poi `import -window root schermata.png` (ImageMagick).

## Esiti

- **2026-10-28, Debian 13 (VM `london`, Python 3.13, snapshot "Speculator installato"):** 90
  test verdi; eseguibile e AppImage (68 MB) costruiti dopo aver fissato PyGObject 3.50.2.
  In Xvfb: la finestra entra con il token, senza token 401; icona nell'area di notifica con
  AyatanaAppIndicator; barra del primo avvio per la cartella dei PDF; importato il pacchetto
  ZIP dell'archivio Windows (38 ricerche, 3 esecuzioni, 55 voci di diario, 4 consultate, 1 PDF),
  reimportato senza duplicati. La finestra restava bianca finché non si è spento il renderer
  DMABUF di WebKitGTK (ora lo fa Iudex). Non provati: avvio senza WebKitGTK (era installato),
  ricerca e PDF dalla Corte (rete protetta), apertura con `xdg-open`.
- **2026-10-28, Windows 11:** installer compilato con Inno Setup 6.7.3 (25,5 MB), non ancora
  installato su una VM Windows.
