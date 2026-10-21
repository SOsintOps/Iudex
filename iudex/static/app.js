/* Iudex: logica dell'interfaccia. Nessuna dipendenza esterna. */
(function () {
  "use strict";

  const $ = (sel, radice) => (radice || document).querySelector(sel);
  const $$ = (sel, radice) => Array.from((radice || document).querySelectorAll(sel));

  const CAMPI_FACET = ["kind", "tipoprov", "szdec", "anno", "ssz", "materia"];
  const SEPARATORI = { materia: ";" };
  const TITOLI_FACET = {
    kind: "Archivio",
    tipoprov: "Tipo di provvedimento",
    szdec: "Sezione",
    anno: "Anno di decisione",
    ssz: "Sottosezione",
    materia: "Materia",
  };
  const FACET_CON_BARRE = ["szdec", "anno", "materia"];
  const MATERIE_VISIBILI = 15;
  const INTESTAZIONI = [
    "FATTI DI CAUSA", "RAGIONI DELLA DECISIONE", "RITENUTO IN FATTO", "CONSIDERATO IN DIRITTO",
    "MOTIVI DELLA DECISIONE", "SVOLGIMENTO DEL PROCESSO", "FATTO E DIRITTO", "RILEVATO CHE",
    "CONSIDERATO CHE", "RITENUTO CHE", "OSSERVA", "P.Q.M.",
  ];

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
    rigaFuoco: -1,
    materiaEspansa: false,
  };

  // ---------- utilità ----------

  function escapa(v) {
    if (v === null || v === undefined) return "";
    return String(v)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function conMarcature(testo) {
    // Il server restituisce solo <em class="hit">: tutto il resto va neutralizzato.
    return escapa(testo)
      .replace(/&lt;em class=&quot;hit&quot;&gt;/g, "<em class=\"hit\">")
      .replace(/&lt;\/em&gt;/g, "</em>");
  }

  function numero(n) { return new Intl.NumberFormat("it-IT").format(n || 0); }

  function dataIt(iso) {
    if (!iso) return "";
    const [a, m, g] = iso.split("-");
    return `${g}/${m}/${a}`;
  }

  function quando(ts) {
    if (!ts) return "";
    return new Date(ts * 1000).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });
  }

  function citazione(doc) {
    const arch = doc.kind === "snciv" ? "civ." : "pen.";
    const sez = doc.sezione ? `Sez. ${doc.sezione}, ` : "";
    const data = doc.data_deposito ? `, dep. ${dataIt(doc.data_deposito)}` : "";
    return `Cass. ${arch}, ${sez}${doc.tipo || ""} n. ${doc.numero}/${doc.anno}${data}${doc.ecli ? ` (${doc.ecli})` : ""}`;
  }

  function memoria(chiave, valore) {
    try {
      if (valore === undefined) return JSON.parse(localStorage.getItem(chiave));
      if (valore === null) localStorage.removeItem(chiave); else localStorage.setItem(chiave, JSON.stringify(valore));
    } catch (e) { return null; }
    return valore;
  }

  async function api(percorso, opzioni) {
    const o = Object.assign({}, opzioni || {});
    o.headers = Object.assign({ "X-Iudex": "1" }, o.headers || {});
    const r = await fetch(percorso, o);
    let dati = null;
    try { dati = await r.json(); } catch (e) { dati = null; }
    if (!r.ok) {
      const msg = (dati && (dati.errore || dati.detail)) || `errore ${r.status}`;
      throw new Error(msg);
    }
    return dati;
  }

  async function scarica(percorso) {
    const r = await fetch(percorso, { headers: { "X-Iudex": "1" } });
    if (!r.ok) {
      let msg = `errore ${r.status}`;
      try { const d = await r.json(); msg = d.errore || d.detail || msg; } catch (e) { /* vuoto */ }
      throw new Error(msg);
    }
    const nome = (r.headers.get("content-disposition") || "").match(/filename="([^"]+)"/);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = nome ? nome[1] : "iudex-export";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  function messaggio(testo) {
    const m = $("#messaggio");
    if (!testo) { m.hidden = true; m.textContent = ""; return; }
    m.hidden = false;
    m.textContent = testo;
  }

  function estremiDoc(e) {
    return `${escapa(e.archivio || "")}${e.sezione ? " · Sez. " + escapa(e.sezione) : ""} · ${escapa(e.tipo || "")} n. ${escapa(e.numero)}/${escapa(e.anno)}`;
  }

  function estremiPerPreferito(doc) {
    return {
      kind: doc.kind, archivio: doc.archivio, sezione: doc.sezione, tipo: doc.tipo, numero: doc.numero,
      anno: doc.anno, ecli: doc.ecli, data_deposito: doc.data_deposito, pdf: doc.pdf,
    };
  }

  // ---------- permalink ----------

  function parametriRicerca(pagina) {
    const p = new URLSearchParams();
    if (stato.testo) p.set("testo", stato.testo);
    if (stato.rif) p.set("rif", stato.rif);
    CAMPI_FACET.forEach((c) => {
      if (stato.filtri[c] && stato.filtri[c].length) p.set(c, stato.filtri[c].join(SEPARATORI[c] || ","));
    });
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
    CAMPI_FACET.forEach((c) => {
      const v = p.get(c);
      if (v) stato.filtri[c] = v.split(SEPARATORI[c] || ",").filter(Boolean);
    });
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
    stato.rigaFuoco = -1;
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
    $("#barra-risultati").hidden = false;
    const cache = d.dalla_cache ? '<span class="cache">dalla cache locale</span>' : "";
    $("#sommario").innerHTML = `<b>${numero(d.trovati)}</b> provvedimenti per <i>${escapa(d.descrizione)}</i>${cache}`;

    const lista = $("#risultati");
    if (!d.documenti.length) {
      lista.innerHTML = "";
      messaggio("Nessun provvedimento corrisponde alla ricerca. Prova con meno parole, con un troncamento (licenz*) o togli un filtro.");
      $("#paginazione").hidden = true;
      return;
    }
    lista.innerHTML = d.documenti.map((doc) => `
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
        ${doc.frammenti && doc.frammenti.length ? `<ul class="frammenti">${doc.frammenti.map((f) => `<li>… ${conMarcature(f)} …</li>`).join("")}</ul>` : ""}
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
    let h = `<button type="button" data-pagina="${corrente - 1}" ${corrente === 1 ? "disabled" : ""}>‹ precedente</button>`;
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
      let voci = facet[campo] || [];
      const scelte = stato.filtri[campo] || [];
      const massimo = Math.max(1, ...voci.map((v) => v.conteggio));
      let piede = "";
      if (campo === "materia" && voci.length > MATERIE_VISIBILI && !stato.materiaEspansa) {
        const nascoste = voci.slice(MATERIE_VISIBILI).filter((v) => !scelte.includes(v.codice));
        voci = voci.slice(0, MATERIE_VISIBILI).concat(voci.slice(MATERIE_VISIBILI).filter((v) => scelte.includes(v.codice)));
        piede = `<button type="button" class="discreto mostra-tutti" data-azione="espandi">mostra tutte (${nascoste.length + voci.length})</button>`;
      } else if (campo === "materia" && stato.materiaEspansa && voci.length > MATERIE_VISIBILI) {
        piede = '<button type="button" class="discreto mostra-tutti" data-azione="riduci">mostra meno</button>';
      }
      const righe = voci.length
        ? voci.map((v) => {
          const barra = FACET_CON_BARRE.includes(campo) ? `<span class="barra-f" style="--p:${(v.conteggio / massimo).toFixed(3)}"></span>` : "";
          return `<label title="${escapa(v.etichetta)}">${barra}<input type="checkbox" data-campo="${campo}" value="${escapa(v.codice)}" ${scelte.includes(v.codice) ? "checked" : ""}>
            <span class="nome-voce">${escapa(v.etichetta)}</span><span class="n">${numero(v.conteggio)}</span></label>`;
        }).join("")
        : '<p class="vuoto">nessun valore</p>';
      return `<div class="gruppo"><h3>${TITOLI_FACET[campo]}</h3>${righe}${piede}</div>`;
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
    const t = (stato.testo || "").replace(/["()]/g, " ");
    return t.split(/\s+/).map((w) => w.trim())
      .filter((w) => w.length > 2 && !/^(AND|OR|NOT)$/.test(w) && !/^\d+\/\d+$/.test(w) && !w.startsWith("-"))
      .map((w) => w.endsWith("*") ? w.slice(0, -1).replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "[\\wÀ-ÿ]*" : w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  }

  function evidenziaLocale(html) {
    const termini = terminiDaEvidenziare();
    if (!termini.length) return html;
    const re = new RegExp("(" + termini.join("|") + ")", "gi");
    return html.replace(re, "<mark>$1</mark>");
  }

  function inParagrafi(html) {
    return html.split(/\n\n+/).map((p) => {
      const pulito = p.replace(/\n/g, "<br>").trim();
      if (!pulito) return "";
      const nudo = pulito.replace(/<[^>]+>/g, "").trim();
      if (INTESTAZIONI.includes(nudo)) {
        const id = nudo === "P.Q.M." ? ' id="pqm"' : "";
        return `<p class="intestazione${nudo === "P.Q.M." ? " pqm" : ""}"${id}>${pulito}</p>`;
      }
      return `<p>${pulito}</p>`;
    }).join("");
  }

  async function apriFascicolo(id) {
    stato.idAperto = id;
    $$(".voce").forEach((v) => v.classList.toggle("aperta", v.dataset.id === id));
    const f = $("#fascicolo");
    f.hidden = false;
    $("#maniglia-fascicolo").hidden = false;
    $("#corpo").classList.add("con-fascicolo");
    $("#fascicolo-estremi").textContent = "Carico il testo…";
    $("#fascicolo-corpo").innerHTML = "";
    $("#evidenziatore").hidden = true;
    $("#vai-pqm").hidden = true;
    try {
      const hl = stato.risposta && stato.risposta.evidenzia && stato.risposta.evidenzia !== "nomatch" ? stato.risposta.evidenzia : "";
      const d = await api("/api/sentenza/" + encodeURIComponent(id) + (hl ? "?evidenzia=" + encodeURIComponent(hl) : ""));
      const doc = d.documento;
      $("#fascicolo-estremi").innerHTML = `
        <span class="sezione">${escapa(doc.archivio)}${doc.sezione ? " · Sez. " + escapa(doc.sezione) : ""}</span>
        ${escapa(doc.tipo || "")} n. ${escapa(doc.numero)}/${escapa(doc.anno)}
        <div class="meta">
          <span>udienza ${dataIt(doc.data_decisione) || "?"}</span><span>deposito ${dataIt(doc.data_deposito) || "?"}</span>
          ${doc.presidente ? `<span>pres. ${escapa(doc.presidente)}</span>` : ""}${doc.relatore ? `<span>rel. ${escapa(doc.relatore)}</span>` : ""}
          ${doc.ecli ? `<span class="ecli">${escapa(doc.ecli)}</span>` : ""}
          ${doc.materia && doc.materia.length ? `<span class="materia-voce">${escapa(doc.materia.join(", "))}</span>` : ""}
          ${d.dalla_cache ? "<span>dalla cache locale</span>" : ""}
        </div>`;
      const pdf = $("#fascicolo-pdf");
      if (doc.pdf) { pdf.hidden = false; pdf.href = doc.pdf; } else { pdf.hidden = true; }
      $("#copia-citazione").dataset.citazione = citazione(doc);
      aggiornaBottonePreferito(doc.preferito);
      $("#preferito").dataset.id = id;
      $("#preferito").dataset.estremi = JSON.stringify(estremiPerPreferito(doc));
      $("#esporta-sentenza-md").dataset.id = id;
      $("#esporta-sentenza-json").dataset.id = id;

      let corpo = "";
      if (doc.massima) corpo += `<div class="massima">${evidenziaLocale(escapa(doc.massima)).replace(/\n/g, "<br>")}</div>`;
      const rnc = doc.riferimenti_normativi || [];
      if (rnc.length) {
        corpo += '<div class="rnc"><span>Riferimenti normativi:</span>' + rnc.map((r) =>
          `<span class="chip" role="button" tabindex="0" data-ricerca="${escapa(r.ricerca)}" title="Cerca le sentenze che citano questa norma">${escapa(r.testo)}</span>`).join("") + "</div>";
      }
      corpo += '<div class="intestazione-testo">Testo del provvedimento</div>';
      const html = d.testo_evidenziato ? conMarcature(d.testo_evidenziato) : evidenziaLocale(escapa(d.testo || ""));
      corpo += `<div class="testo">${html ? inParagrafi(html) : "<p>Testo non disponibile.</p>"}</div>`;
      $("#fascicolo-corpo").innerHTML = corpo;
      $("#fascicolo-corpo").scrollTop = 0;
      $("#vai-pqm").hidden = !$("#pqm");
      preparaHit();
    } catch (e) {
      $("#fascicolo-estremi").textContent = "Testo non caricato";
      $("#fascicolo-corpo").innerHTML = `<div class="messaggio">${escapa(e.message)}</div>`;
    }
  }

  function chiudiFascicolo() {
    $("#fascicolo").hidden = true;
    $("#maniglia-fascicolo").hidden = true;
    $("#corpo").classList.remove("con-fascicolo");
    stato.idAperto = null;
    $$(".voce").forEach((v) => v.classList.remove("aperta"));
  }

  function apriAdiacente(delta) {
    if (!stato.risposta || !stato.idAperto) return;
    const ids = stato.risposta.documenti.map((d) => d.id);
    const i = ids.indexOf(stato.idAperto) + delta;
    if (i < 0 || i >= ids.length) return;
    apriFascicolo(ids[i]);
    const voce = $$(".voce")[i];
    if (voce) voce.scrollIntoView({ block: "nearest" });
  }

  function preparaHit() {
    stato.hits = $$("#fascicolo-corpo mark, #fascicolo-corpo em.hit");
    stato.hitCorrente = -1;
    const ev = $("#evidenziatore");
    if (!stato.hits.length) { ev.hidden = true; return; }
    ev.hidden = false;
    vaiAHit(0);
  }

  function scorriA(el) {
    const corpo = $("#fascicolo-corpo");
    const y = el.getBoundingClientRect().top - corpo.getBoundingClientRect().top + corpo.scrollTop;
    corpo.scrollTop = Math.max(0, y - corpo.clientHeight / 2);
  }

  function vaiAHit(i) {
    if (!stato.hits.length) return;
    const n = stato.hits.length;
    stato.hitCorrente = ((i % n) + n) % n;
    stato.hits.forEach((m, k) => m.classList.toggle("corrente", k === stato.hitCorrente));
    scorriA(stato.hits[stato.hitCorrente]);
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

  function applicaCarattere(px) {
    const v = Math.max(12, Math.min(26, px));
    document.documentElement.style.setProperty("--carattere-testo", v + "px");
    memoria("iudex.carattere", v);
    return v;
  }

  // ---------- schede ----------

  function mostraScheda(nome) {
    stato.scheda = nome;
    $$(".scheda").forEach((b) => b.classList.toggle("attiva", b.dataset.scheda === nome));
    ["risultati", "cronologia", "salvate", "preferiti", "stato"].forEach((n) => { $("#pannello-" + n).hidden = n !== nome; });
    const conFiltri = nome === "risultati";
    $("#filtri").hidden = !conFiltri;
    $("#maniglia-filtri").hidden = !conFiltri;
    $("#corpo").classList.toggle("senza-filtri", !conFiltri);
    if (!conFiltri && !$("#fascicolo").hidden) chiudiFascicolo();
    if (nome === "cronologia") caricaCronologia();
    if (nome === "salvate") caricaSalvate();
    if (nome === "preferiti") caricaPreferiti();
    if (nome === "stato") caricaStato();
  }

  function descriviVoce(v) {
    const parti = [];
    if (v.testo) parti.push(v.testo);
    if (v.riferimenti) parti.push("rif. " + v.riferimenti);
    Object.keys(v.filtri || {}).forEach((k) => parti.push(`${TITOLI_FACET[k] || k}: ${v.filtri[k].join(", ")}`));
    return parti.join(" · ") || "tutte le sentenze";
  }

  async function caricaCronologia() {
    const voci = await api("/api/cronologia");
    const l = $("#lista-cronologia");
    if (!voci.length) { l.innerHTML = '<tr><td class="vuota" colspan="6">Nessuna ricerca ancora. Le ricerche compaiono qui con il loro indirizzo.</td></tr>'; return; }
    l.innerHTML = voci.map((v) => `
      <tr>
        <td class="quando">${quando(v.quando)}</td>
        <td><a class="titolo" href="#${escapa(v.permalink)}">${escapa(descriviVoce(v))}</a></td>
        <td>${numero(v.trovati)}</td>
        <td>${escapa(v.ordinamento)}</td>
        <td>${v.righe}</td>
        <td class="azioni-td"><a class="discreto" href="#${escapa(v.permalink)}">Apri</a><button type="button" class="discreto elimina-ricerca" data-id="${v.id}">Elimina</button></td>
      </tr>`).join("");
  }

  async function caricaSalvate() {
    const voci = await api("/api/salvate");
    const l = $("#lista-salvate");
    if (!voci.length) { l.innerHTML = '<tr><td class="vuota" colspan="6">Nessuna ricerca salvata. Dalla pagina dei risultati usa "Salva ricerca".</td></tr>'; return; }
    l.innerHTML = voci.map((v) => `
      <tr data-id="${v.id}">
        <td class="quando">${quando(v.quando)}</td>
        <td><a class="titolo" href="#${escapa(v.permalink)}">${escapa(v.nome)}</a><div class="dettaglio">${escapa(decodeURIComponent(v.permalink.replace(/\+/g, " ")))}</div></td>
        <td class="quando">${v.ultimo_controllo ? quando(v.ultimo_controllo) : "mai"}</td>
        <td>${v.trovati === null || v.trovati === undefined ? "–" : numero(v.trovati)}</td>
        <td>${v.nuovi ? `<span class="novita-n">${v.nuovi} nuov${v.nuovi === 1 ? "o" : "i"}</span>` : (v.ultimo_controllo ? "nessuna" : "–")}</td>
        <td class="azioni-td"><button type="button" class="discreto controlla" data-id="${v.id}">Controlla novità</button><a class="discreto" href="#${escapa(v.permalink)}">Apri</a><button type="button" class="discreto elimina-salvata" data-id="${v.id}">Elimina</button></td>
      </tr>`).join("");
  }

  async function caricaPreferiti() {
    const voci = await api("/api/preferiti");
    const l = $("#lista-preferiti");
    if (!voci.length) { l.innerHTML = '<tr><td class="vuota" colspan="5">Nessuna sentenza preferita. Aprine una e usa "Aggiungi ai preferiti".</td></tr>'; return; }
    l.innerHTML = voci.map((v) => {
      const e = v.estremi || {};
      return `<tr data-id="${escapa(v.id_sentenza)}">
        <td class="quando">${quando(v.quando)}</td>
        <td><a class="titolo apri-preferito" href="#" data-id="${escapa(v.id_sentenza)}">${estremiDoc(e)}</a>${e.data_deposito ? `<div class="dettaglio">dep. ${dataIt(e.data_deposito)}</div>` : ""}</td>
        <td><span class="ecli">${escapa(e.ecli || "")}</span></td>
        <td><input class="nota" type="text" value="${escapa(v.nota || "")}" placeholder="aggiungi una nota" data-id="${escapa(v.id_sentenza)}"></td>
        <td class="azioni-td">${e.pdf ? `<a class="discreto" href="${escapa(e.pdf)}" target="_blank" rel="noopener">PDF</a>` : ""}<button type="button" class="discreto rimuovi-preferito" data-id="${escapa(v.id_sentenza)}">Rimuovi</button></td>
      </tr>`;
    }).join("");
  }

  async function caricaStato() {
    const s = await api("/api/stato");
    const righe = s.registro.map((r) => `<tr><td>${r.quando}</td><td>${escapa(r.tipo)}</td><td>${r.stato === null ? "rete" : r.stato}</td><td>${r.durata_ms} ms</td><td>${escapa(r.dettaglio)}</td></tr>`).join("");
    $("#stato").innerHTML = `
      <p>Iudex ${escapa(s.versione)} · richieste al server della Corte in questa sessione: <b>${s.chiamate_remote}</b> ·
         intervallo minimo fra richieste: ${s.intervallo_minimo_s} s</p>
      <p>Cache locale: <b>${s.sentenze_in_cache}</b> testi di sentenze, <b>${s.risposte_in_cache}</b> risposte di ricerca · archivio: <code>${escapa(s.percorso_dati)}</code></p>
      <table><thead><tr><th>Ora</th><th>Tipo</th><th>Stato</th><th>Durata</th><th>Note</th></tr></thead><tbody>${righe || '<tr><td colspan="5">Nessuna richiesta ancora.</td></tr>'}</tbody></table>`;
  }

  async function aggiornaPie() {
    try {
      const s = await api("/api/stato");
      $("#pie-cache").textContent = `${s.chiamate_remote} richieste al server in questa sessione · ${s.sentenze_in_cache} sentenze in cache`;
    } catch (e) { /* silenzioso */ }
  }

  // ---------- colonne ridimensionabili ----------

  function trascina(maniglia, alMovimento, allaFine) {
    let x0 = 0;
    let attivo = false;
    maniglia.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      attivo = true;
      x0 = e.clientX;
      maniglia.classList.add("attiva");
      document.body.classList.add("ridimensiona");
      alMovimento(0, true);
      try { maniglia.setPointerCapture(e.pointerId); } catch (err) { /* puntatore non catturabile */ }
      e.preventDefault();
    });
    maniglia.addEventListener("pointermove", (e) => { if (attivo) alMovimento(e.clientX - x0, false); });
    const fine = (e) => {
      if (!attivo) return;
      attivo = false;
      maniglia.classList.remove("attiva");
      document.body.classList.remove("ridimensiona");
      try { maniglia.releasePointerCapture(e.pointerId); } catch (err) { /* già rilasciato */ }
      allaFine();
    };
    maniglia.addEventListener("pointerup", fine);
    maniglia.addEventListener("pointercancel", fine);
  }

  function preparaPannelli() {
    const radice = document.documentElement;
    const salvate = memoria("iudex.colonne") || {};
    if (salvate.filtri) radice.style.setProperty("--larg-filtri", salvate.filtri + "px");
    if (salvate.fascicolo) radice.style.setProperty("--larg-fascicolo", salvate.fascicolo + "px");

    let base = 0;
    const filtri = $("#maniglia-filtri");
    trascina(filtri, (dx, inizio) => {
      if (inizio) { base = $("#filtri").getBoundingClientRect().width; return; }
      const larg = Math.max(160, Math.min(520, base + dx));
      radice.style.setProperty("--larg-filtri", larg + "px");
    }, () => {
      const v = memoria("iudex.colonne") || {};
      v.filtri = Math.round($("#filtri").getBoundingClientRect().width);
      memoria("iudex.colonne", v);
    });
    filtri.addEventListener("dblclick", () => {
      radice.style.removeProperty("--larg-filtri");
      const v = memoria("iudex.colonne") || {}; delete v.filtri; memoria("iudex.colonne", v);
    });
    filtri.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      const attuale = $("#filtri").getBoundingClientRect().width;
      const larg = Math.max(160, Math.min(520, attuale + (e.key === "ArrowRight" ? 16 : -16)));
      radice.style.setProperty("--larg-filtri", larg + "px");
      const v = memoria("iudex.colonne") || {}; v.filtri = larg; memoria("iudex.colonne", v);
      e.preventDefault();
    });

    let baseF = 0;
    const fasc = $("#maniglia-fascicolo");
    const limiteF = () => Math.max(360, Math.min(window.innerWidth * 0.72, 2000));
    trascina(fasc, (dx, inizio) => {
      if (inizio) { baseF = $("#fascicolo").getBoundingClientRect().width; return; }
      const larg = Math.max(360, Math.min(limiteF(), baseF - dx));
      radice.style.setProperty("--larg-fascicolo", larg + "px");
    }, () => {
      const v = memoria("iudex.colonne") || {};
      v.fascicolo = Math.round($("#fascicolo").getBoundingClientRect().width);
      memoria("iudex.colonne", v);
    });
    fasc.addEventListener("dblclick", () => {
      radice.style.removeProperty("--larg-fascicolo");
      const v = memoria("iudex.colonne") || {}; delete v.fascicolo; memoria("iudex.colonne", v);
    });
    fasc.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      const attuale = $("#fascicolo").getBoundingClientRect().width;
      const larg = Math.max(360, Math.min(limiteF(), attuale + (e.key === "ArrowLeft" ? 16 : -16)));
      radice.style.setProperty("--larg-fascicolo", larg + "px");
      const v = memoria("iudex.colonne") || {}; v.fascicolo = larg; memoria("iudex.colonne", v);
      e.preventDefault();
    });
  }

  function rendiRidimensionabile(tabella) {
    const chiave = "iudex.tabella." + tabella.dataset.chiave;
    const ths = $$("thead th", tabella);
    const salvate = memoria(chiave);
    if (Array.isArray(salvate)) ths.forEach((th, i) => { if (salvate[i]) th.style.width = salvate[i] + "px"; });
    const salva = () => memoria(chiave, ths.map((th) => Math.round(th.getBoundingClientRect().width)));
    ths.forEach((th, i) => {
      if (i === ths.length - 1) return;
      const m = document.createElement("span");
      m.className = "ridim";
      m.setAttribute("role", "separator");
      m.setAttribute("aria-orientation", "vertical");
      m.setAttribute("aria-label", "Larghezza della colonna " + th.textContent.trim());
      m.tabIndex = 0;
      m.title = "Trascina per ridimensionare, doppio clic per ripristinare";
      th.appendChild(m);
      let base = 0;
      trascina(m, (dx, inizio) => {
        if (inizio) {
          // Fissa le larghezze attuali di tutte le colonne, così si muove solo questa.
          ths.forEach((t) => { t.style.width = Math.round(t.getBoundingClientRect().width) + "px"; });
          base = th.getBoundingClientRect().width;
          return;
        }
        th.style.width = Math.max(60, base + dx) + "px";
      }, salva);
      m.addEventListener("dblclick", (e) => { e.stopPropagation(); ths.forEach((t) => { t.style.width = ""; }); memoria(chiave, null); });
      m.addEventListener("keydown", (e) => {
        if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
        ths.forEach((t) => { t.style.width = Math.round(t.getBoundingClientRect().width) + "px"; });
        th.style.width = Math.max(60, th.getBoundingClientRect().width + (e.key === "ArrowRight" ? 12 : -12)) + "px";
        salva();
        e.preventDefault();
      });
    });
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

  $("#ricerca").addEventListener("submit", (e) => { e.preventDefault(); leggiForm(); cerca(1); });
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

  $("#elenco-filtri").addEventListener("click", (e) => {
    const b = e.target.closest(".mostra-tutti");
    if (!b) return;
    stato.materiaEspansa = b.dataset.azione === "espandi";
    disegnaFacet(stato.facetUltimi);
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
    if (!voce || !stato.risposta) return;
    if (e.target.closest(".preferisci")) {
      const doc = stato.risposta.documenti.find((d) => d.id === voce.dataset.id);
      commutaPreferito(doc.id, estremiPerPreferito(doc), doc.preferito).catch((err) => messaggio(err.message));
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

  $$(".esporta").forEach((b) => b.addEventListener("click", async () => {
    if (!stato.risposta) return;
    const quanti = $("#export-quanti").value;
    const p = parametriRicerca();
    p.set("formato", b.dataset.formato);
    if (quanti !== "pagina") { p.set("massimo", quanti); p.delete("pagina"); }
    b.disabled = true;
    try { await scarica("/api/export?" + p.toString()); } catch (err) { messaggio("Esportazione non riuscita: " + err.message); } finally { b.disabled = false; }
  }));

  $("#esporta-sentenza-md").addEventListener("click", (e) => scarica(`/api/export/sentenza/${encodeURIComponent(e.currentTarget.dataset.id)}?formato=md`).catch((err) => messaggio(err.message)));
  $("#esporta-sentenza-json").addEventListener("click", (e) => scarica(`/api/export/sentenza/${encodeURIComponent(e.currentTarget.dataset.id)}?formato=json`).catch((err) => messaggio(err.message)));

  $("#chiudi-fascicolo").addEventListener("click", chiudiFascicolo);
  $("#hit-prec").addEventListener("click", () => vaiAHit(stato.hitCorrente - 1));
  $("#hit-succ").addEventListener("click", () => vaiAHit(stato.hitCorrente + 1));
  $("#vai-pqm").addEventListener("click", () => { const p = $("#pqm"); if (p) scorriA(p); });
  $("#carattere-meno").addEventListener("click", () => applicaCarattere((memoria("iudex.carattere") || 16) - 1));
  $("#carattere-piu").addEventListener("click", () => applicaCarattere((memoria("iudex.carattere") || 16) + 1));

  $("#fascicolo-corpo").addEventListener("click", (e) => {
    const chip = e.target.closest(".rnc .chip");
    if (!chip) return;
    $("#rif").value = chip.dataset.ricerca;
    $("#testo").value = "";
    leggiForm();
    cerca(1);
  });
  $("#fascicolo-corpo").addEventListener("keydown", (e) => {
    const chip = e.target.closest(".rnc .chip");
    if (chip && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); chip.click(); }
  });

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
    if (!modulo.hidden) { $("#nome-salva").value = stato.risposta.descrizione; $("#nome-salva").focus(); $("#nome-salva").select(); }
  });

  $("#modulo-salva").addEventListener("submit", async (e) => {
    e.preventDefault();
    const nome = $("#nome-salva").value.trim();
    if (!nome) return;
    await api("/api/salvate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nome, permalink: parametriRicerca(1).toString() }) });
    $("#modulo-salva").hidden = true;
    messaggio(`Ricerca salvata come "${nome}". La trovi nella scheda Ricerche salvate.`);
  });

  $("#svuota-cronologia").addEventListener("click", async () => { await api("/api/cronologia", { method: "DELETE" }); caricaCronologia(); });

  $("#lista-cronologia").addEventListener("click", async (e) => {
    const b = e.target.closest(".elimina-ricerca");
    if (!b) return;
    await api("/api/cronologia/" + b.dataset.id, { method: "DELETE" });
    caricaCronologia();
  });

  $("#lista-salvate").addEventListener("click", async (e) => {
    const el = e.target.closest(".elimina-salvata");
    if (el) { await api("/api/salvate/" + el.dataset.id, { method: "DELETE" }); caricaSalvate(); return; }
    const c = e.target.closest(".controlla");
    if (!c) return;
    c.disabled = true;
    c.textContent = "Controllo…";
    try {
      const r = await api("/api/salvate/" + c.dataset.id + "/controlla", { method: "POST" });
      await caricaSalvate();
      const riga = $(`#lista-salvate tr[data-id="${c.dataset.id}"]`);
      let testo;
      if (r.prima_volta) testo = `<b>Primo controllo:</b> ${numero(r.trovati)} provvedimenti registrati come punto di partenza. Dal prossimo controllo verranno segnalati i nuovi.`;
      else if (!r.nuovi.length) testo = `<b>Nessuna novità</b> (${numero(r.trovati)} provvedimenti in tutto${r.dalla_cache ? ", dalla cache locale" : ""}).`;
      else testo = `<b>${r.nuovi.length} nuov${r.nuovi.length === 1 ? "o" : "i"}:</b><ul>` + r.nuovi.map((d) => `<li><a href="#" class="apri-nuovo" data-id="${escapa(d.id)}">${estremiDoc(d)}</a> · dep. ${dataIt(d.data_deposito)}</li>`).join("") + "</ul>";
      const dett = document.createElement("tr");
      dett.className = "novita-riga";
      dett.innerHTML = `<td colspan="6">${testo}</td>`;
      riga.after(dett);
    } catch (err) {
      messaggio("Controllo non riuscito: " + err.message);
      c.disabled = false;
      c.textContent = "Controlla novità";
    }
  });

  $("#lista-salvate").addEventListener("click", (e) => {
    const a = e.target.closest(".apri-nuovo");
    if (!a) return;
    e.preventDefault();
    mostraScheda("risultati");
    if (!stato.risposta) { $("#benvenuto").hidden = true; }
    apriFascicolo(a.dataset.id);
  });

  $("#lista-preferiti").addEventListener("click", async (e) => {
    const r = e.target.closest(".rimuovi-preferito");
    if (r) { await api("/api/preferiti/" + encodeURIComponent(r.dataset.id), { method: "DELETE" }); caricaPreferiti(); return; }
    const a = e.target.closest(".apri-preferito");
    if (a) { e.preventDefault(); mostraScheda("risultati"); $("#benvenuto").hidden = true; apriFascicolo(a.dataset.id); }
  });

  $("#lista-preferiti").addEventListener("change", async (e) => {
    const campo = e.target.closest("input.nota");
    if (!campo) return;
    try {
      await api("/api/preferiti/" + encodeURIComponent(campo.dataset.id), { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nota: campo.value }) });
      campo.classList.add("salvata");
      setTimeout(() => campo.classList.remove("salvata"), 800);
    } catch (err) { messaggio("Nota non salvata: " + err.message); }
  });

  $("#svuota-cache").addEventListener("click", async () => { const r = await api("/api/cache", { method: "DELETE" }); caricaStato(); messaggio(`Cache delle ricerche svuotata (${r.rimosse} voci).`); });
  $("#svuota-testi").addEventListener("click", async () => { const r = await api("/api/cache/sentenze", { method: "DELETE" }); caricaStato(); aggiornaPie(); messaggio(`Testi in cache rimossi (${r.rimosse}).`); });

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

  function spostaFuoco(delta) {
    const voci = $$(".voce");
    if (!voci.length) return;
    stato.rigaFuoco = Math.max(0, Math.min(voci.length - 1, stato.rigaFuoco + delta));
    voci.forEach((v, i) => v.classList.toggle("a-fuoco", i === stato.rigaFuoco));
    voci[stato.rigaFuoco].scrollIntoView({ block: "nearest" });
  }

  document.addEventListener("keydown", (e) => {
    const inCampo = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if (e.key === "Escape" && !$("#fascicolo").hidden) { chiudiFascicolo(); return; }
    if (inCampo) return;
    if (e.key === "/") { e.preventDefault(); $("#testo").focus(); return; }
    if (stato.scheda === "risultati" && stato.risposta) {
      if (e.key === "j") { spostaFuoco(1); return; }
      if (e.key === "k") { spostaFuoco(-1); return; }
      if (e.key === "Enter" && stato.rigaFuoco >= 0) { apriFascicolo(stato.risposta.documenti[stato.rigaFuoco].id); return; }
    }
    if (!$("#fascicolo").hidden) {
      if (e.key === "n") vaiAHit(stato.hitCorrente + 1);
      if (e.key === "p") vaiAHit(stato.hitCorrente - 1);
      if (e.altKey && e.key === "ArrowRight") { e.preventDefault(); apriAdiacente(1); }
      if (e.altKey && e.key === "ArrowLeft") { e.preventDefault(); apriAdiacente(-1); }
    }
  });

  window.addEventListener("hashchange", () => {
    if (aggiornandoHash) return;
    if (leggiHash()) cerca(stato.pagina);
  });

  // ---------- preferenze locali: tema, densità, carattere, colonne ----------

  function applicaTema(t) {
    if (t) document.documentElement.dataset.tema = t; else delete document.documentElement.dataset.tema;
  }
  try {
    const t = localStorage.getItem("iudex.tema");
    if (t) applicaTema(t);
    else if (window.matchMedia("(prefers-color-scheme: dark)").matches) applicaTema("scuro");
    if (localStorage.getItem("iudex.densita") === "compatta") document.body.classList.add("compatta");
  } catch (e) { /* storage non disponibile */ }
  const carattere = memoria("iudex.carattere");
  if (carattere) applicaCarattere(carattere);

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

  preparaPannelli();
  $$(".tabella").forEach(rendiRidimensionabile);

  // ---------- avvio ----------

  disegnaFacet(null);
  aggiornaPie();
  if (leggiHash()) cerca(stato.pagina);
  else $("#testo").focus();
})();
