# Istruzioni per Claude (e per chi riprende il lavoro)

Questo file viaggia con il repository: su qualunque computer, Claude Code lo legge aprendo
questa cartella. Le regole valgono anche per chi lavora a mano.

## Da dove ripartire

1. `git pull`, poi leggi `docs/PROGRESS.md` (passi fatti e da fare, diario) e il piano in
   corso in `docs/plan/` (il più recente; oggi `2026-10-28-entita.md`, fase B, che parte
   quando è definito il modello delle entità).
2. Prosegui dal primo passo non spuntato; se un piano è "da dettagliare", prima le domande
   all'utente, poi il piano scritto nel repository, poi il codice.
3. Note di contesto del PC di lavoro e piani di coordinamento con Praeco: nel repository
   privato di Praeco (`docs/claude/LEGGIMI.md`), non qui.

## Regole di lavoro (decise dall'utente)

- Tutto in **italiano**: interfaccia, documentazione, commenti, identificatori, commit.
- Un commit per passo, pubblicato (`git push`) appena sono verdi `ruff format`,
  `ruff check iudex tests packaging` e `pytest`. Controllo e commit in due comandi separati:
  mai un commit con un test rosso. Ripetere la suite con `-o faulthandler_timeout=60` se un
  test sembra instabile.
- Autore dei commit e dei tag: `Ramingo <28706121+SOsintOps@users.noreply.github.com>`
  (`git commit --author ...`; per i tag `GIT_COMMITTER_NAME`/`GIT_COMMITTER_EMAIL`).
  **Niente trailer AI** (`Co-Authored-By`) nei commit.
- Ogni modifica visibile: `CHANGELOG.md` ("Da rilasciare"), `iudex/static/versioni.html` al
  rilascio, guida e FAQ sia in `docs/` sia nelle pagine `iudex/static/*.html`. Spunta in
  `docs/PROGRESS.md` nello stesso commit, con l'hash nel commit successivo.
- Schema del database: solo migrazioni numerate nuove in `iudex/cache.py`, mai modificare
  quelle rilasciate; copia di sicurezza prima di migrare.
- Il tag `vX.Y.Z` avvia il workflow `Rilascio` (installer pubblici): solo su conferma
  dell'utente.

## Vincoli del progetto

- Server della Corte: una richiesta alla volta, intervallo minimo, nessuno scaricamento in
  blocco, nessuna ricerca per nome di persona. Le richieste in più vanno discusse prima.
- Quando l'utente è sull'**IP protetto** (VPN senza esclusione di 81.126.56.168) la Corte non
  risponde: niente richieste, si lavora sui dati locali; i test non usano la rete.
- Riservatezza: testi, PDF e storico contengono dati personali. Schermate solo da un archivio
  di prova, senza nomi delle parti né percorsi con il nome dell'utente.
- Praeco (`SOsintOps/Praeco`) dipende da Iudex: non cambiare le API usate da Praeco (`client`,
  `query`, `export`, `impronte`, `autonoma.*`, comprese `_richiesta` ed `_entita`) senza
  aggiornare Praeco; pubblicare Iudex prima dei commit di Praeco che lo usano.
- Questo repository è **pubblico**: Praeco si nomina soltanto (app che usa Iudex come
  libreria), senza percorsi, passi, piani o funzioni interne; i dettagli vanno nel repository
  privato di Praeco.
- Iudex si usa solo dalla sua finestra (`python -m iudex.desktop`); pagine e API vogliono il
  token del file `token` nella cartella dei dati.

## Comandi

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .[dev,desktop,mcp]
.venv\Scripts\python.exe -m ruff format iudex tests
.venv\Scripts\python.exe -m ruff check iudex tests packaging
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m iudex.desktop
```

Prove degli installer: `docs/prova-installazione.md`. Su una macchina virtuale, snapshot solo
a macchina spenta e ripristino dello snapshot di partenza a fine prova.
