# Sicurezza

Iudex è un'applicazione locale: il server ascolta solo su `127.0.0.1` e pagine, API e PDF
rispondono solo alla finestra di Iudex e a chi ha il token del file `token` nella cartella
dei dati (cookie di sessione HttpOnly e SameSite=Strict per la finestra, header
`X-Iudex-Token` per il server MCP); le API vogliono anche l'header `X-Iudex` e un `Host`
locale. Non conserva credenziali e non invia dati a nessuno, a parte le ricerche e i PDF
chiesti al server pubblico della Corte di Cassazione. Lo storico, i testi e i PDF salvati
restano nella cartella dei dati e vanno custoditi come un fascicolo di studio.

Se trovi una vulnerabilità (per esempio un modo per usare le pagine o le API locali senza il
token, da un altro sito aperto nel browser o da un altro programma, o per far uscire dati
dall'archivio o dalla cartella dei PDF), segnalala in privato
con la funzione **Report a vulnerability** della scheda Security di questo repository,
invece di aprire una segnalazione pubblica. Riceverai una risposta entro pochi giorni.
