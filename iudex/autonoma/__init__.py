"""Iudex (e Praeco) come app autonoma: cartelle dei dati per sistema, server locale con
``/health`` e sorveglianza del processo che lo ha avviato, finestra nativa con icona
nell'area di notifica, backup del database.

Il disegno segue quello di Voicebox (github.com/jamiepine/voicebox): il backend è un
server FastAPI avviato con ``--data-dir``, ``--port`` e ``--parent-pid``; la finestra è
un guscio che lo apre. Qui il guscio è pywebview, in Python come il resto.
"""
