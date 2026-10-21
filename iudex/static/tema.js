/* Iudex: tema chiaro/scuro con scelta automatica in base all'orario.
   Modalità: "auto" (scuro fra le ore di inizio e fine, per impostazione predefinita
   dalle 19 alle 7), "chiaro", "scuro". La scelta sta in localStorage ("iudex.tema"),
   gli orari in "iudex.tema.orari". Lo stesso calcolo è ripetuto inline nell'head di ogni
   pagina per evitare il lampo del tema sbagliato al caricamento. */
(function () {
  "use strict";
  const CHIAVE = "iudex.tema";
  const CHIAVE_ORARI = "iudex.tema.orari";
  const PREDEFINITI = { inizio: 19, fine: 7 };
  const MODALITA = ["auto", "chiaro", "scuro"];
  const NOMI = { auto: "automatico", chiaro: "chiaro", scuro: "scuro" };

  function leggiModalita() {
    try {
      const v = (localStorage.getItem(CHIAVE) || "auto").replace(/"/g, "");
      return MODALITA.includes(v) ? v : "auto";
    } catch (e) { return "auto"; }
  }

  function leggiOrari() {
    try {
      const o = JSON.parse(localStorage.getItem(CHIAVE_ORARI));
      if (o && Number.isInteger(o.inizio) && Number.isInteger(o.fine)) return o;
    } catch (e) { /* valore assente o non valido */ }
    return Object.assign({}, PREDEFINITI);
  }

  /* Funzione pura: data la modalità, l'ora (0-23) e gli orari, restituisce il tema. */
  function temaEffettivo(modalita, ora, orari) {
    if (modalita === "scuro") return "scuro";
    if (modalita === "chiaro") return "chiaro";
    const o = orari || PREDEFINITI;
    const notte = o.inizio > o.fine ? (ora >= o.inizio || ora < o.fine) : (ora >= o.inizio && ora < o.fine);
    return notte ? "scuro" : "chiaro";
  }

  function applica() {
    const m = leggiModalita();
    const t = temaEffettivo(m, new Date().getHours(), leggiOrari());
    document.documentElement.dataset.tema = t;
    const chiaro = document.getElementById("tema-chiaro");
    const scuro = document.getElementById("tema-scuro");
    if (chiaro && scuro) {
      chiaro.classList.toggle("attivo", t === "chiaro");
      scuro.classList.toggle("attivo", t === "scuro");
      const auto = m === "auto" ? " (scelto automaticamente in base all'ora; un altro clic sull'icona attiva torna all'automatico)" : " (clic sull'icona attiva per tornare all'automatico)";
      chiaro.title = "Tema chiaro" + (t === "chiaro" ? auto : "");
      scuro.title = "Tema scuro" + (t === "scuro" ? auto : "");
      const cont = document.getElementById("tema");
      if (cont) cont.classList.toggle("auto", m === "auto");
    }
    return t;
  }

  /* Clic su un'icona: sceglie quel tema; secondo clic sull'icona già attiva: automatico. */
  function scegli(tema) {
    const m = leggiModalita();
    return imposta(m === tema ? "auto" : tema);
  }

  function imposta(m) {
    try { localStorage.setItem(CHIAVE, m); } catch (e) { /* ignora */ }
    return applica();
  }

  function impostaOrari(inizio, fine) {
    try { localStorage.setItem(CHIAVE_ORARI, JSON.stringify({ inizio, fine })); } catch (e) { /* ignora */ }
    return applica();
  }

  function cicla() {
    return imposta(MODALITA[(MODALITA.indexOf(leggiModalita()) + 1) % MODALITA.length]);
  }

  function avvia() {
    applica();
    const chiaro = document.getElementById("tema-chiaro");
    const scuro = document.getElementById("tema-scuro");
    if (chiaro) chiaro.addEventListener("click", () => scegli("chiaro"));
    if (scuro) scuro.addEventListener("click", () => scegli("scuro"));
    setInterval(applica, 60000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) applica(); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", avvia); else avvia();

  window.IudexTema = { leggiModalita, leggiOrari, temaEffettivo, applica, imposta, impostaOrari, cicla, scegli, PREDEFINITI };
})();

// Pagine informative: scrive la versione nel piè di pagina (nella pagina principale lo fa app.js).
(function () {
  var e = document.getElementById("pie-versione");
  if (!e || document.getElementById("risultati")) return;
  fetch("/api/stato", { headers: { "X-Iudex": "1" } })
    .then(function (r) { return r.json(); })
    .then(function (s) { if (s && s.versione) e.textContent = "Iudex " + s.versione; })
    .catch(function () { /* resta "Iudex" */ });
})();
