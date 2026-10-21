/* Iudex: logica dell'interfaccia. Nessuna dipendenza esterna. */
(function () {
  "use strict";

  const $ = (sel, radice) => (radice || document).querySelector(sel);
  const $$ = (sel, radice) => Array.from((radice || document).querySelectorAll(sel));

  const CAMPI_FACET = ["kind", "tipoprov", "szdec", "anno", "ssz"];
  const TITOLI_FACET = {
    kind: "Archivio",
    tipoprov: "Tipo di provvedimento",
    szdec: "Sezione",
    anno: "Anno di decisione",
    ssz: "Sottosezione",
  };

  const stato = {
    testo: "",
    rif: "",
    filtri: {},
    ordina: "pubblicazione",
    righe: 10,
    pagina: 1,
    risposta: null,
    facetUltimi: null,
    idAperto: null,
    hits: [],
    hitCorrente: -1,
    scheda: "risultati",
  };

  // ---------- utilità ----------

  function html(strs, ...vals) {
    return strs.reduce((acc, s, i) => acc + s + (i < vals.length ? escapa(vals[i]) : ""), "");
  }

  function escapa(v) {
    if (v === null || v === undefined) return "";
    return String(v)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function frammentoSicuro(f) {
    // Il server restituisce solo <em class="hit">: tutto il resto va neutralizzato.
    return escapa(f)
      .replace(/&lt;em class=&quot;hit&quot;&gt;/g, "<em class=\"hit\">")
      .replace(/&lt;\/em&gt;/g, "</em>");
  }

  function numero(n) {
    return new Intl.NumberFormat("it-IT").format(n || 0);
  }

  function dataIt(iso) {
    if (!iso) return "";
    const [a, m, g] = iso.split("-");
    return `${g}/${m}/${a}`;
  }

  function quando(ts) {
    return new Date(ts * 1000).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });
  }

  function citazione(doc) {
    const arch = doc.kind === "snciv" ? "civ." : "pen.";
    const sez = doc.sezione ? `Sez. ${doc.sezione}, ` : "";
    const data = doc.data_deposito ? `, dep. ${dataIt(doc.data_deposito)}` : "";
    return `Cass. ${arch}, ${sez}${doc.tipo || ""} n. ${doc.numero}/${doc.anno}${data}${doc.ecli ? ` (${doc.ecli})` : ""}`;
  }

  async function api(percorso, opzioni) {
    const r = await fetch(percorso, opzioni);
    let dati = null;
    try { dati = await r.json(); } catch (e) { dati = null; }
    if (!r.ok) {
      const msg = (dati && (dati.errore || dati.detail)) || `errore ${r.status}`;
      throw new Error(msg);
    }
    return dati;
  }

  function messaggio(testo) {
    const m = $("#messaggio");
    if (!testo) { m.hidden = true; m.textContent = ""; return; }
    m.hidden = false;
    m.textContent = testo;
  }

  // ---------- permalink ----------

  function parametriRicerca(pagina) {
    const p = new URLSearchParams();
    if (stato.testo) p.set("testo", stato.testo);
    if (stato.rif) p.set("rif", stato.rif);
    CAMPI_FACET.forEach((c) => { if (stato.filtri[c] && stato.filtri[c].length) p.set(c, stato.filtri[c].join(",")); });
    if (stato.ordina !== "pubblicazione") p.set("ordina", stato.ordina);
    if (stato.righe !== 10) p.set("righe", String(stato.righe));
    const pg = pagina || stato.pagina;
    if (pg > 1) p.set("pagina", String(pg));
    return p;
  }

  function leggiHash() {
    const h = location.hash.replace(/^#/, "");
    const p = new URLSearchParams(h);
    stato.testo = p.get("testo") || "";
    stato.rif = p.get("rif") || "";
    stato.filtri = {};
    CAMPI_FACET.forEach((c) => { const v = p.get(c); if (v) stato.filtri[c] = v.split(",").filter(Boolean); });
    stato.ordina = p.get("ordina") || "pubblicazione";
    stato.righe = parseInt(p.get("righe") || "10", 10);
    stato.pagina = parseInt(p.get("pagina") || "1", 10);
    $("#testo").value = stato.testo;
    $("#rif").value = stato.rif;
    $("#ordina").value = stato.ordina;
    $("#righe").value = String(stato.righe);
    return h !== "";
  }

  let aggiornandoHash = false;
  function scriviHash() {
    aggiornandoHash = true;
    location.hash = parametriRicerca().toString();
    setTimeout(() => { aggiornandoHash = false; }, 0);
  }

  // ---------- ricerca ----------

  async function cerca(pagina) {
    stato.pagina = pagina || 1;
    scriviHash();
    mostraScheda("risultati");
    messaggio("");
    $("#benvenuto").hidden = true;
    $("#risultati").innerHTML = '<li class="voce"><span class="estremi">Interrogo SentenzeWeb…</span></li>';
    try {
      const dati = await api("/api/cerca?" + parametriRicerca().toString());
      stato.risposta = dati;
      stato.facetUltimi = dati.facet;
      disegnaRisultati(dati);
      disegnaFacet(dati.facet);
      disegnaChip();
      aggiornaPie();
    } catch (e) {
      $("#risultati").innerHTML = "";
      $("#barra-risultati").hidden = true;
      $("#paginazione").hidden = true;
      messaggio("Ricerca non riuscita: " + e.message);
    }
  }

  function disegnaRisultati(d) {
    const barra = $("#barra-risultati");
    barra.hidden = false;
    const cache = d.dalla_cache ? '<span class="cache">dalla cache locale</span>' : "";
    $("#sommario").innerHTML = `<b>${numero(d.trovati)}</b> provvedimenti per <i>${escapa(d.descrizione)}</i>${cache}`;
    const base = "/api/export?" + parametriRicerca().toString();
    $("#export-csv").href = base + "&formato=csv";
    $("#export-json").href = base + "&formato=json";
    $("#export-md").href = base + "&formato=md";

    const lista = $("#risultati");
    if (!d.documenti.length) {
      lista.innerHTML = "";
      messaggio("Nessun provvedimento corrisponde alla ricerca. Prova con meno parole, con un troncamento (licenz*) o togli un filtro.");
      $("#paginazione").hidden = true;
      return;
    }
    lista.innerHTML = d.documenti.map((doc, i) => `
      <li class="voce ${doc.id === stato.idAperto ? "aperta" : ""}" data-id="${escapa(doc.id)}">
        <div class="estremi" role="button" tabindex="0" title="Apri il testo">
          <span class="sezione">${escapa(doc.archivio)}${doc.sezione ? " · Sez. " + escapa(doc.sezione) : ""}${doc.sottosezione && doc.sottosezione !== "nessuna" ? " (" + escapa(doc.sottosezione) + ")" : ""}</span>
          ${escapa(doc.tipo || "")} <span class="numero">n. ${escapa(doc.numero)}/${escapa(doc.anno)}</span>
        </div>
        <div class="meta">
          <span>udienza ${dataIt(doc.data_decisione) || "?"}</span>
          <span>deposito ${dataIt(doc.data_deposito) || "?"}</span>
          ${doc.presidente ? `<span>pres. ${escapa(doc.presidente)}</span>` : ""}
          ${doc.relatore ? `<span>rel. ${escapa(doc.relatore)}</span>` : ""}
          ${doc.ecli ? `<span class="ecli">${escapa(doc.ecli)}</span>` : ""}
        </div>
        <div class="azioni">
          <button type="button" class="discreto apri">Apri testo</button>
          ${doc.pdf ? `<a class="discreto" href="${escapa(doc.pdf)}" target="_blank" rel="noopener">PDF ufficiale</a>` : ""}
          <button type="button" class="discreto preferisci ${doc.preferito ? "attivo" : ""}">${doc.preferito ? "★ Preferita" : "☆ Preferisci"}</button>
        </div>
        ${doc.frammenti && doc.frammenti.length ? `<ul class="frammenti">${doc.frammenti.map((f) => `<li>… ${frammentoSicuro(f)} …</li>`).join("")}</ul>` : ""}
      </li>`).join("");

    disegnaPaginazione(d);
  }

  function disegnaPaginazione(d) {
    const nav = $("#paginazione");
    const totale = Math.max(1, Math.ceil(d.trovati / d.righe));
    if (totale <= 1) { nav.hidden = true; return; }
    nav.hidden = false;
    const corrente = d.pagina;
    const da = Math.max(1, corrente - 4);
    const a = Math.min(totale, da + 9);
    let h = "";
    h += `<button type="button" data-pagina="${corrente - 1}" ${corrente === 1 ? "disabled" : ""}>‹ precedente</button>`;
    for (let i = da; i <= a; i++) {
      h += `<button type="button" data-pagina="${i}" class="${i === corrente ? "corrente" : ""}">${i}</button>`;
    }
    h += `<button type="button" data-pagina="${corrente + 1}" ${corrente === totale ? "disabled" : ""}>successiva ›</button>`;
    h += `<span class="tot">pagina ${corrente} di ${numero(totale)}</span>`;
    h += `<label class="tot">vai a <input type="number" min="1" max="${totale}" id="vai-pagina" value="${corrente}"></label>`;
    nav.innerHTML = h;
  }

  function disegnaFacet(facet) {
    const cont = $("#elenco-filtri");
    if (!facet) { cont.innerHTML = '<p class="vuoto">I filtri compaiono dopo la prima ricerca.</p>'; return; }
    cont.innerHTML = CAMPI_FACET.map((campo) => {
      const voci = facet[campo] || [];
      const scelte = stato.filtri[campo] || [];
      const righe = voci.length
        ? voci.map((v) => `
          <label><input type="checkbox" data-campo="${campo}" value="${escapa(v.codice)}" ${scelte.includes(v.codice) ? "checked" : ""}>
            <span class="nome-voce">${escapa(v.etichetta)}</span><span class="n">${numero(v.conteggio)}</span></label>`).join("")
        : '<p class="vuoto">nessun valore</p>';
      return `<div class="gruppo"><h3>${TITOLI_FACET[campo]}</h3>${righe}</div>`;
    }).join("");
  }

  function disegnaChip() {
    const cont = $("#chip-filtri");
    const pezzi = [];
    CAMPI_FACET.forEach((campo) => {
      (stato.filtri[campo] || []).forEach((codice) => {
        let etichetta = codice;
        const voce = ((stato.facetUltimi || {})[campo] || []).find((v) => v.codice === codice);
        if (voce) etichetta = voce.etichetta;
        pezzi.push(`<span class="chip">${TITOLI_FACET[campo]}: ${escapa(etichetta)}<button type="button" data-campo="${campo}" data-codice="${escapa(codice)}" title="Togli il filtro">×</button></span>`);
      });
    });
    cont.innerHTML = pezzi.join("");
  }

  // ---------- fascicolo ----------

  function terminiDaEvidenziare() {
    const t = (stato.testo || "").replace(/["*()]/g, " ");
    return t.split(/\s+/).map((w) => w.trim()).filter((w) => w.length > 2 && !/^(AND|OR|NOT)$/.test(w) && !/^\d+\/\d+$/.test(w) && !w.startsWith("-"));
  }

  function evidenzia(testo) {
    const termini = terminiDaEvidenziare();
    let h = escapa(testo);
    if (!termini.length) return h;
    const re = new RegExp("(" + termini.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")", "gi");
    return h.replace(re, "<mark>$1</mark>");
  }

  async function apriFascicolo(id) {
    stato.idAperto = id;
    $$(".voce").forEach((v) => v.classList.toggle("aperta", v.dataset.id === id));
    const f = $("#fascicolo");
    f.hidden = false;
    $("#corpo").classList.add("con-fascicolo");
    $("#fascicolo-estremi").textContent = "Carico il testo…";
    $("#fascicolo-corpo").innerHTML = "";
    $("#evidenziatore").hidden = true;
    try {
      const d = await api("/api/sentenza/" + encodeURIComponent(id));
      const doc = d.documento;
      $("#fascicolo-estremi").innerHTML = `
        <span class="sezione">${escapa(doc.archivio)}${doc.sezione ? " · Sez. " + escapa(doc.sezione) : ""}</span>
        ${escapa(doc.tipo || "")} n. ${escapa(doc.numero)}/${escapa(doc.anno)}
        <div class="meta">
          <span>udienza ${dataIt(doc.data_decisione) || "?"}</span><span>deposito ${dataIt(doc.data_deposito) || "?"}</span>
          ${doc.presidente ? `<span>pres. ${escapa(doc.presidente)}</span>` : ""}${doc.relatore ? `<span>rel. ${escapa(doc.relatore)}</span>` : ""}
          ${doc.ecli ? `<span class="ecli">${escapa(doc.ecli)}</span>` : ""}
          ${d.dalla_cache ? "<span>dalla cache locale</span>" : ""}
        </div>`;
      const pdf = $("#fascicolo-pdf");
      if (doc.pdf) { pdf.hidden = false; pdf.href = doc.pdf; } else { pdf.hidden = true; }
      $("#fascicolo-md").href = `/api/export/sentenza/${encodeURIComponent(id)}?formato=md`;
      $("#fascicolo-json").href = `/api/export/sentenza/${encodeURIComponent(id)}?formato=json`;
      $("#copia-citazione").dataset.citazione = citazione(doc);
      aggiornaBottonePreferito(doc.preferito);
      $("#preferito").dataset.id = id;
      $("#preferito").dataset.estremi = JSON.stringify({
        kind: doc.kind, archivio: doc.archivio, sezione: doc.sezione, tipo: doc.tipo, numero: doc.numero,
        anno: doc.anno, ecli: doc.ecli, data_deposito: doc.data_deposito, pdf: doc.pdf,
      });

      let corpo = "";
      if (doc.massima) corpo += `<div class="massima">${evidenzia(doc.massima)}</div>`;
      const rnc = doc.riferimenti_normativi || {};
      const chiavi = Object.keys(rnc).filter((k) => rnc[k] && rnc[k].length);
      if (chiavi.length) {
        corpo += '<dl class="rnc">' + chiavi.map((k) => `<dt>${escapa(k)}</dt><dd>${escapa([].concat(rnc[k]).join("; "))}</dd>`).join("") + "</dl>";
      }
      corpo += '<div class="intestazione-testo">Testo del provvedimento</div>';
      corpo += `<div class="testo">${d.testo ? evidenzia(d.testo) : "Testo non disponibile."}</div>`;
      $("#fascicolo-corpo").innerHTML = corpo;
      $("#fascicolo-corpo").scrollTop = 0;
      preparaHit();
    } catch (e) {
      $("#fascicolo-estremi").textContent = "Testo non caricato";
      $("#fascicolo-corpo").innerHTML = `<div class="messaggio">${escapa(e.message)}</div>`;
    }
  }

  function chiudiFascicolo() {
    $("#fascicolo").hidden = true;
    $("#corpo").classList.remove("con-fascicolo");
    stato.idAperto = null;
    $$(".voce").forEach((v) => v.classList.remove("aperta"));
  }

  function preparaHit() {
    stato.hits = $$("#fascicolo-corpo mark");
    stato.hitCorrente = -1;
    const ev = $("#evidenziatore");
    if (!stato.hits.length) { ev.hidden = true; return; }
    ev.hidden = false;
    vaiAHit(0);
  }

  function vaiAHit(i) {
    if (!stato.hits.length) return;
    const n = stato.hits.length;
    stato.hitCorrente = ((i % n) + n) % n;
    stato.hits.forEach((m, k) => m.classList.toggle("corrente", k === stato.hitCorrente));
    // Scorre solo il pannello del testo, non la pagina intera.
    const corpo = $("#fascicolo-corpo");
    const m = stato.hits[stato.hitCorrente];
    const y = m.getBoundingClientRect().top - corpo.getBoundingClientRect().top + corpo.scrollTop;
    corpo.scrollTop = Math.max(0, y - corpo.clientHeight / 2);
    $("#hit-pos").textContent = `${stato.hitCorrente + 1} / ${n}`;
  }

  function aggiornaBottonePreferito(attivo) {
    const b = $("#preferito");
    b.classList.toggle("attivo", !!attivo);
    b.textContent = attivo ? "★ Nei preferiti" : "☆ Aggiungi ai preferiti";
    b.dataset.attivo = attivo ? "1" : "0";
  }

  async function commutaPreferito(id, estremi, attivo) {
    if (attivo) {
      await api("/api/preferiti/" + encodeURIComponent(id), { method: "DELETE" });
    } else {
      await api("/api/preferiti", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id, estremi }) });
    }
    const nuovo = !attivo;
    if (stato.idAperto === id) aggiornaBottonePreferito(nuovo);
    $$(".voce").forEach((v) => {
      if (v.dataset.id !== id) return;
      const b = $(".preferisci", v);
      b.classList.toggle("attivo", nuovo);
      b.textContent = nuovo ? "★ Preferita" : "☆ Preferisci";
    });
    if (stato.risposta) stato.risposta.documenti.forEach((d) => { if (d.id === id) d.preferito = nuovo; });
  }

  // ---------- schede ----------

  function mostraScheda(nome) {
    stato.scheda = nome;
    $$(".scheda").forEach((b) => b.classList.toggle("attiva", b.dataset.scheda === nome));
    ["risultati", "cronologia", "salvate", "preferiti", "stato"].forEach((n) => { $("#pannello-" + n).hidden = n !== nome; });
    $("#filtri").hidden = nome !== "risultati";
    if (nome === "cronologia") caricaCronologia();
    if (nome === "salvate") caricaSalvate();
    if (nome === "preferiti") caricaPreferiti();
    if (nome === "stato") caricaStato();
  }

  async function caricaCronologia() {
    const voci = await api("/api/cronologia");
    const l = $("#lista-cronologia");
    if (!voci.length) { l.innerHTML = '<li class="vuota">Nessuna ricerca ancora. Le ricerche compaiono qui con il loro indirizzo.</li>'; return; }
    l.innerHTML = voci.map((v) => `
      <li><span class="quando">${quando(v.quando)}</span>
        <span class="testo-voce"><a href="#${escapa(v.permalink)}">${escapa(descriviVoce(v))}</a>
          <div class="dettaglio">${numero(v.trovati)} provvedimenti · ${escapa(v.ordinamento)} · ${v.righe} per pagina</div></span></li>`).join("");
  }

  function descriviVoce(v) {
    const parti = [];
    if (v.testo) parti.push(v.testo);
    if (v.riferimenti) parti.push("rif. " + v.riferimenti);
    Object.keys(v.filtri || {}).forEach((k) => parti.push(`${TITOLI_FACET[k] || k}: ${v.filtri[k].join(", ")}`));
    return parti.join(" · ") || "tutte le sentenze";
  }

  async function caricaSalvate() {
    const voci = await api("/api/salvate");
    const l = $("#lista-salvate");
    if (!voci.length) { l.innerHTML = '<li class="vuota">Nessuna ricerca salvata. Dalla pagina dei risultati usa "Salva ricerca".</li>'; return; }
    l.innerHTML = voci.map((v) => `
      <li><span class="quando">${quando(v.quando)}</span>
        <span class="testo-voce"><a href="#${escapa(v.permalink)}">${escapa(v.nome)}</a><div class="dettaglio">${escapa(v.permalink)}</div></span>
        <button type="button" class="discreto elimina-salvata" data-id="${v.id}">Elimina</button></li>`).join("");
  }

  async function caricaPreferiti() {
    const voci = await api("/api/preferiti");
    const l = $("#lista-preferiti");
    if (!voci.length) { l.innerHTML = '<li class="vuota">Nessuna sentenza preferita. Aprine una e usa "Aggiungi ai preferiti".</li>'; return; }
    l.innerHTML = voci.map((v) => {
      const e = v.estremi || {};
      return `<li><span class="quando">${quando(v.quando)}</span>
        <span class="testo-voce"><a href="#" class="apri-preferito" data-id="${escapa(v.id_sentenza)}">${escapa(e.archivio || "")}${e.sezione ? " · Sez. " + escapa(e.sezione) : ""} · ${escapa(e.tipo || "")} n. ${escapa(e.numero)}/${escapa(e.anno)}</a>
          <div class="dettaglio">${escapa(e.ecli || "")}${e.data_deposito ? " · dep. " + dataIt(e.data_deposito) : ""}</div></span>
        ${e.pdf ? `<a class="discreto" href="${escapa(e.pdf)}" target="_blank" rel="noopener">PDF</a>` : ""}
        <button type="button" class="discreto rimuovi-preferito" data-id="${escapa(v.id_sentenza)}">Rimuovi</button></li>`;
    }).join("");
  }

  async function caricaStato() {
    const s = await api("/api/stato");
    const righe = s.registro.map((r) => `<tr><td>${r.quando}</td><td>${escapa(r.tipo)}</td><td>${r.stato === null ? "rete" : r.stato}</td><td>${r.durata_ms} ms</td><td>${escapa(r.dettaglio)}</td></tr>`).join("");
    $("#stato").innerHTML = `
      <p>Iudex ${escapa(s.versione)} · richieste al server della Corte in questa sessione: <b>${s.chiamate_remote}</b> ·
         intervallo minimo fra richieste: ${s.intervallo_minimo_s} s · sentenze in cache locale: <b>${s.sentenze_in_cache}</b></p>
      <table><thead><tr><th>Ora</th><th>Tipo</th><th>Stato</th><th>Durata</th><th>Note</th></tr></thead><tbody>${righe || '<tr><td colspan="5">Nessuna richiesta ancora.</td></tr>'}</tbody></table>`;
  }

  async function aggiornaPie() {
    try {
      const s = await api("/api/stato");
      $("#pie-cache").textContent = `${s.chiamate_remote} richieste al server in questa sessione · ${s.sentenze_in_cache} sentenze in cache`;
      $("#conteggio-archivio").hidden = true;
    } catch (e) { /* silenzioso */ }
  }

  // ---------- suggerimenti per i riferimenti ----------

  let timerSugg = null;
  function suggerisci() {
    clearTimeout(timerSugg);
    const q = $("#rif").value.trim();
    const ul = $("#suggerimenti");
    if (q.length < 2) { ul.hidden = true; return; }
    timerSugg = setTimeout(async () => {
      try {
        const voci = await api("/api/estremi?q=" + encodeURIComponent(q.split(/\s+/).pop()));
        if (!voci.length) { ul.hidden = true; return; }
        ul.innerHTML = voci.map((v) => `<li data-sigla="${escapa(v.sigla)}"><span class="sigla">${escapa(v.sigla)}</span><span>${escapa(v.descrizione)}</span></li>`).join("");
        ul.hidden = false;
      } catch (e) { ul.hidden = true; }
    }, 250);
  }

  // ---------- eventi ----------

  function leggiForm() {
    stato.testo = $("#testo").value.trim();
    stato.rif = $("#rif").value.trim();
    stato.ordina = $("#ordina").value;
    stato.righe = parseInt($("#righe").value, 10);
  }

  $("#ricerca").addEventListener("submit", (e) => {
    e.preventDefault();
    leggiForm();
    cerca(1);
  });

  $("#ordina").addEventListener("change", () => { leggiForm(); if (stato.risposta) cerca(1); });
  $("#righe").addEventListener("change", () => { leggiForm(); if (stato.risposta) cerca(1); });

  $("#aiuto-sintassi").addEventListener("click", (e) => {
    const s = $("#sintassi");
    s.hidden = !s.hidden;
    e.currentTarget.setAttribute("aria-expanded", String(!s.hidden));
  });

  $("#elenco-filtri").addEventListener("change", (e) => {
    const cb = e.target;
    if (cb.type !== "checkbox") return;
    const campo = cb.dataset.campo;
    const lista = new Set(stato.filtri[campo] || []);
    if (cb.checked) lista.add(cb.value); else lista.delete(cb.value);
    stato.filtri[campo] = Array.from(lista);
    if (!stato.filtri[campo].length) delete stato.filtri[campo];
    cerca(1);
  });

  $("#chip-filtri").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-campo]");
    if (!b) return;
    const campo = b.dataset.campo;
    stato.filtri[campo] = (stato.filtri[campo] || []).filter((c) => c !== b.dataset.codice);
    if (!stato.filtri[campo].length) delete stato.filtri[campo];
    cerca(1);
  });

  $("#azzera-filtri").addEventListener("click", () => { stato.filtri = {}; if (stato.risposta) cerca(1); else disegnaChip(); });

  $("#risultati").addEventListener("click", (e) => {
    const voce = e.target.closest(".voce");
    if (!voce) return;
    if (e.target.closest(".preferisci")) {
      const doc = stato.risposta.documenti.find((d) => d.id === voce.dataset.id);
      commutaPreferito(doc.id, {
        kind: doc.kind, archivio: doc.archivio, sezione: doc.sezione, tipo: doc.tipo, numero: doc.numero,
        anno: doc.anno, ecli: doc.ecli, data_deposito: doc.data_deposito, pdf: doc.pdf,
      }, doc.preferito).catch((err) => messaggio(err.message));
      return;
    }
    if (e.target.closest(".apri") || e.target.closest(".estremi")) apriFascicolo(voce.dataset.id);
  });

  $("#risultati").addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && e.target.classList.contains("estremi")) {
      e.preventDefault();
      apriFascicolo(e.target.closest(".voce").dataset.id);
    }
  });

  $("#paginazione").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-pagina]");
    if (b && !b.disabled) cerca(parseInt(b.dataset.pagina, 10));
  });

  $("#paginazione").addEventListener("change", (e) => {
    if (e.target.id === "vai-pagina") cerca(Math.max(1, parseInt(e.target.value, 10) || 1));
  });

  $("#chiudi-fascicolo").addEventListener("click", chiudiFascicolo);
  $("#hit-prec").addEventListener("click", () => vaiAHit(stato.hitCorrente - 1));
  $("#hit-succ").addEventListener("click", () => vaiAHit(stato.hitCorrente + 1));

  $("#copia-citazione").addEventListener("click", async (e) => {
    const b = e.currentTarget;
    try {
      await navigator.clipboard.writeText(b.dataset.citazione || "");
      const vecchio = b.textContent; b.textContent = "Copiata"; setTimeout(() => { b.textContent = vecchio; }, 1200);
    } catch (err) { messaggio("Copia non riuscita: " + err.message); }
  });

  $("#preferito").addEventListener("click", (e) => {
    const b = e.currentTarget;
    commutaPreferito(b.dataset.id, JSON.parse(b.dataset.estremi || "{}"), b.dataset.attivo === "1").catch((err) => messaggio(err.message));
  });

  $("#salva-ricerca").addEventListener("click", () => {
    if (!stato.risposta) return;
    const modulo = $("#modulo-salva");
    modulo.hidden = !modulo.hidden;
    if (!modulo.hidden) {
      $("#nome-salva").value = stato.risposta.descrizione;
      $("#nome-salva").focus();
      $("#nome-salva").select();
    }
  });

  $("#modulo-salva").addEventListener("submit", async (e) => {
    e.preventDefault();
    const nome = $("#nome-salva").value.trim();
    if (!nome) return;
    await api("/api/salvate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nome, permalink: parametriRicerca(1).toString() }) });
    $("#modulo-salva").hidden = true;
    messaggio(`Ricerca salvata come "${nome}". La trovi nella scheda Ricerche salvate.`);
  });

  $("#svuota-cronologia").addEventListener("click", async () => {
    await api("/api/cronologia", { method: "DELETE" });
    caricaCronologia();
  });

  $("#lista-salvate").addEventListener("click", async (e) => {
    const b = e.target.closest(".elimina-salvata");
    if (!b) return;
    await api("/api/salvate/" + b.dataset.id, { method: "DELETE" });
    caricaSalvate();
  });

  $("#lista-preferiti").addEventListener("click", async (e) => {
    const r = e.target.closest(".rimuovi-preferito");
    if (r) { await api("/api/preferiti/" + encodeURIComponent(r.dataset.id), { method: "DELETE" }); caricaPreferiti(); return; }
    const a = e.target.closest(".apri-preferito");
    if (a) { e.preventDefault(); mostraScheda("risultati"); apriFascicolo(a.dataset.id); }
  });

  $$(".scheda").forEach((b) => b.addEventListener("click", () => mostraScheda(b.dataset.scheda)));

  $("#rif").addEventListener("input", suggerisci);
  $("#rif").addEventListener("blur", () => setTimeout(() => { $("#suggerimenti").hidden = true; }, 150));
  $("#suggerimenti").addEventListener("mousedown", (e) => {
    const li = e.target.closest("li[data-sigla]");
    if (!li) return;
    const campo = $("#rif");
    const parole = campo.value.trim().split(/\s+/);
    parole.pop();
    campo.value = (parole.join(" ") + " " + li.dataset.sigla + " ").replace(/^\s+/, "");
    $("#suggerimenti").hidden = true;
    campo.focus();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("#fascicolo").hidden) chiudiFascicolo();
    if (e.key === "/" && document.activeElement && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
      e.preventDefault();
      $("#testo").focus();
    }
    if (!$("#fascicolo").hidden && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
      if (e.key === "n") vaiAHit(stato.hitCorrente + 1);
      if (e.key === "p") vaiAHit(stato.hitCorrente - 1);
    }
  });

  window.addEventListener("hashchange", () => {
    if (aggiornandoHash) return;
    if (leggiHash()) cerca(stato.pagina);
  });

  // ---------- preferenze locali: tema e densità ----------

  function applicaTema(t) {
    if (t) document.documentElement.dataset.tema = t; else delete document.documentElement.dataset.tema;
  }
  try {
    const t = localStorage.getItem("iudex.tema");
    if (t) applicaTema(t);
    else if (window.matchMedia("(prefers-color-scheme: dark)").matches) applicaTema("scuro");
    if (localStorage.getItem("iudex.densita") === "compatta") document.body.classList.add("compatta");
  } catch (e) { /* storage non disponibile */ }

  $("#tema").addEventListener("click", () => {
    const scuro = document.documentElement.dataset.tema === "scuro";
    applicaTema(scuro ? "chiaro" : "scuro");
    try { localStorage.setItem("iudex.tema", scuro ? "chiaro" : "scuro"); } catch (e) { /* ignora */ }
  });

  $("#densita").addEventListener("click", (e) => {
    const c = document.body.classList.toggle("compatta");
    e.currentTarget.classList.toggle("attivo", c);
    try { localStorage.setItem("iudex.densita", c ? "compatta" : "normale"); } catch (err) { /* ignora */ }
  });
  if (document.body.classList.contains("compatta")) $("#densita").classList.add("attivo");

  // ---------- avvio ----------

  disegnaFacet(null);
  aggiornaPie();
  if (leggiHash()) cerca(stato.pagina);
  else $("#testo").focus();
})();
