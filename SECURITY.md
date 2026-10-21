# Sicurezza

Iudex è un'applicazione locale: il server ascolta solo su `127.0.0.1` e le API
rispondono solo all'interfaccia di Iudex (header `X-Iudex`). Non conserva credenziali e
non invia dati a nessuno, a parte le ricerche al server pubblico della Corte di
Cassazione.

Se trovi una vulnerabilità (per esempio un modo per far interrogare le API locali da un
altro sito aperto nel browser, o per far uscire dati dalla cache), segnalala in privato
con la funzione **Report a vulnerability** della scheda Security di questo repository,
invece di aprire una segnalazione pubblica. Riceverai una risposta entro pochi giorni.
