/* Iudex: logica dell'interfaccia. Nessuna dipendenza esterna. */
(function () {
  "use strict";

  const $ = (sel, radice) => (radice || document).querySelector(sel);
  const $$ = (sel, radice) => Array.from((radice || document).querySelectorAll(sel));

  const CAMPI_FACET = ["kind", "tipoprov", "szdec", "anno", "ssz", "materia"];
  // Il segnale nel testo viaggia come un filtro (indirizzo, cronologia, diario) ma ha un
  // solo valore e non è un campo di Solr: i conteggi arrivano da facet.query.
  const CAMPI_FILTRO = ["segnale", ...CAMPI_FACET];
  const SEGNALI = {
    contrasto: "Contrasto",
    conformita: "Orientamento consolidato",
  };
  const SEPARATORI = { materia: ";" };
  const TITOLI_FACET = {
    kind: "Archivio",
    tipoprov: "Tipo di provvedimento",
    szdec: "Sezione",
    anno: "Anno di decisione",
    ssz: "Sottosezione",
    materia: "Materia",
    segnale: "Segnali nel testo",
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
    CAMPI_FILTRO.forEach((c) => {
      if (stato.filtri[c] && stato.filtri[c].length) p.set(c, stato.filtri[c].join(SEPARATORI[c] || ","));
    });
    if (stato.ordina !== "pubblicazione") p.set("ordina", stato.ordina);
    if (stato.righe !== 10) p.set("righe", String(stato.righe));
    const pg = pagina || stato.pagina;
    if (pg > 1) p.set("pagina", String(pg));
    return p;
  }

  const SCHEDE = ["risultati", "cronologia", "diario", "salvate", "preferiti", "stato", "impostazioni"];

  function leggiHash() {
    const h = location.hash.replace(/^#/, "");
    if (SCHEDE.includes(h)) { mostraScheda(h); return false; }
    const p = new URLSearchParams(h);
    stato.testo = p.get("testo") || "";
    stato.rif = p.get("rif") || "";
    stato.filtri = {};
    CAMPI_FILTRO.forEach((c) => {
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
      stato.segnaliUltimi = dati.segnali || null;
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
          ${badgeVista(doc.consultazione)}
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
          ${doc.pdf ? '<button type="button" class="discreto apri-pdf" title="Apri il PDF ufficiale: la prima volta si scarica e si salva, poi si apre dalla copia locale">PDF</button>' : ""}
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
    cont.innerHTML = gruppoSegnali() + CAMPI_FACET.map((campo) => {
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

  function gruppoSegnali() {
    const conteggi = stato.segnaliUltimi;
    if (!conteggi) return "";
    const scelto = (stato.filtri.segnale || [])[0];
    const righe = Object.keys(SEGNALI).map((codice) => {
      const n = conteggi[codice];
      if (n === undefined) return "";
      return `<label title="${escapa(SEGNALI[codice])}"><input type="checkbox" data-campo="segnale" value="${codice}" ${scelto === codice ? "checked" : ""}>
        <span class="nome-voce">${escapa(SEGNALI[codice])}</span><span class="n">${numero(n)}</span></label>`;
    }).join("");
    if (!righe) return "";
    return `<div class="gruppo gruppo-segnali"><h3>${TITOLI_FACET.segnale}</h3>${righe}
      <p class="nota-segnali">Conteggio delle frasi con cui il provvedimento lo dichiara («contrasto giurisprudenziale», «orientamento consolidato»…): un segnale testuale, non una classificazione.</p></div>`;
  }

  function disegnaChip() {
    const cont = $("#chip-filtri");
    const pezzi = [];
    CAMPI_FILTRO.forEach((campo) => {
      (stato.filtri[campo] || []).forEach((codice) => {
        let etichetta = campo === "segnale" ? (SEGNALI[codice] || codice) : codice;
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

  async function apriFascicolo(id, daiRisultati) {
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
      const p = new URLSearchParams();
      if (hl) p.set("evidenzia", hl);
      // La ricerca di provenienza, per il diario: solo quando la sentenza è aperta dai risultati.
      if (daiRisultati && stato.risposta && stato.risposta.permalink) p.set("da", stato.risposta.permalink);
      const d = await api("/api/sentenza/" + encodeURIComponent(id) + (p.toString() ? "?" + p.toString() : ""));
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
        </div>
        ${consultazioneHtml(d.consultazione)}`;
      const pdf = $("#fascicolo-pdf");
      pdf.hidden = !doc.pdf;
      pdf.dataset.id = id;
      pdf.dataset.da = daiRisultati && stato.risposta && stato.risposta.permalink ? stato.risposta.permalink : "";
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
        corpo += '<div class="rnc"><span>Riferimenti normativi:</span>' + rnc.map((r, i) =>
          `<span class="rif-norma"><span class="chip" role="button" tabindex="0" data-ricerca="${escapa(r.ricerca)}" title="Cerca le sentenze che citano questa norma">${escapa(r.testo)}</span>${bottoneNorma(r, i)}</span>`).join("") + '</div><div class="norme-aperte"></div>';
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

  // ---------- testo della norma (Normattiva) ----------

  // Bottone "Testo" solo per i riferimenti che il server ha letto con certezza (campo norma);
  // per regolamenti e direttive UE il link a EUR-Lex, solo se il server lo fornisce.
  function bottoneNorma(r, indice) {
    if (r.norma) {
      const n = r.norma;
      return `<button type="button" class="btn-testo" data-indice="${indice}" data-tipo="${escapa(n.tipo)}" data-numero="${escapa(n.numero)}" data-anno="${escapa(n.anno)}" data-articolo="${escapa(n.articolo)}" aria-expanded="false" title="Leggi il testo dell'articolo da Normattiva (una richiesta)">Testo</button>`;
    }
    if (r.norma_url_eurlex && /^https:\/\/eur-lex\.europa\.eu\//.test(r.norma_url_eurlex)) {
      return `<a class="link-eurlex" href="${escapa(r.norma_url_eurlex)}" target="_blank" rel="noopener" title="Apri l'atto su EUR-Lex">EUR-Lex</a>`;
    }
    return "";
  }

  // Il testo della fonte entra nella pagina solo come testo (textContent), mai come HTML.
  function elemento(tag, classe, testo) {
    const el = document.createElement(tag);
    if (classe) el.className = classe;
    if (testo !== undefined && testo !== null) el.textContent = testo;
    return el;
  }

  function righeNorma(testo) {
    return String(testo || "").split("\n").map((r) => r.trim()).filter(Boolean);
  }

  const FONTE_NORMATTIVA = "Normattiva (IPZS), CC BY 4.0";

  function riempiNorma(pannello, d) {
    const atto = d.atto || {};
    const art = d.articolo || {};
    const vig = d.vigenza || {};
    if (atto.titolo) pannello.appendChild(elemento("div", "norma-atto", atto.titolo));
    const intestazione = elemento("div", "norma-articolo", "Art. " + (art.numero || ""));
    if (art.rubrica) intestazione.appendChild(elemento("span", "rubrica", " – " + art.rubrica));
    pannello.appendChild(intestazione);
    const testo = elemento("div", "norma-testo");
    // Un paragrafo per comma; i segni (( )) di Normattiva restano come sono.
    righeNorma(art.testo).forEach((riga) => testo.appendChild(elemento("p", "comma", riga)));
    if (!testo.childNodes.length) testo.appendChild(elemento("p", "comma", "Testo non disponibile."));
    pannello.appendChild(testo);
    if (art.note) {
      const note = elemento("details", "norma-note");
      note.appendChild(elemento("summary", "", "Note e aggiornamenti"));
      righeNorma(art.note).forEach((riga) => note.appendChild(elemento("p", "", riga)));
      pannello.appendChild(note);
    }
    const vigenza = [];
    if (vig.inizio) vigenza.push("In vigore dal " + dataIt(vig.inizio));
    if (vig.fine) vigenza.push("fino al " + dataIt(vig.fine));
    if (vig.richiesta) vigenza.push("versione vigente al " + dataIt(vig.richiesta));
    if (vigenza.length) pannello.appendChild(elemento("div", "norma-vigenza", vigenza.join(", ")));
    pannello.appendChild(elemento("div", "norma-legenda", "(( )) = testo inserito o modificato · allegati e tabelle non sono mostrati"));
    const fonte = elemento("div", "fonte", "Fonte: " + (d.fonte || FONTE_NORMATTIVA));
    if (d.da_cache) fonte.appendChild(document.createTextNode(" · dalla cache locale"));
    if (d.url && /^https:\/\//.test(d.url)) {
      fonte.appendChild(document.createTextNode(" · "));
      const link = elemento("a", "", "Apri su Normattiva");
      link.href = d.url;
      link.target = "_blank";
      link.rel = "noopener";
      fonte.appendChild(link);
    }
    pannello.appendChild(fonte);
  }

  function erroreNorma(pannello, codice, dati) {
    const dalServer = dati && typeof dati.errore === "string" ? dati.errore : "";
    let testo;
    if (codice === 404) testo = dalServer || "Normattiva non ha questo articolo.";
    else if (codice === 429) {
      const secondi = Math.ceil((dati && dati.pausa_residua_s) || 0);
      testo = secondi > 0 ? `Normattiva: attendere ${secondi} s prima di una nuova richiesta.` : "Normattiva: attendere prima di una nuova richiesta.";
    } else if (codice === 0) testo = "Iudex non ha risposto: riprovare più tardi.";
    else testo = dalServer || `Errore ${codice}`;
    pannello.classList.add("errore");
    pannello.appendChild(elemento("div", "norma-errore", testo));
    pannello.appendChild(elemento("div", "norma-legenda", "Nessun nuovo tentativo automatico: per riprovare, chiudere e riaprire con il bottone Testo."));
  }

  // Una richiesta a /api/norma per clic, mai prima; il secondo clic richiude senza richieste.
  async function apriNorma(bottone) {
    const contenitore = $("#fascicolo-corpo .norme-aperte");
    if (!contenitore || bottone.disabled) return;
    const indice = bottone.dataset.indice;
    const aperto = contenitore.querySelector(`.norma[data-indice="${indice}"]`);
    if (aperto) {
      aperto.remove();
      bottone.setAttribute("aria-expanded", "false");
      bottone.classList.remove("attivo");
      return;
    }
    const pannello = elemento("div", "norma", "Caricamento…");
    pannello.dataset.indice = indice;
    contenitore.appendChild(pannello);
    bottone.setAttribute("aria-expanded", "true");
    bottone.classList.add("attivo");
    bottone.disabled = true;
    const p = new URLSearchParams();
    ["tipo", "numero", "anno", "articolo"].forEach((campo) => { if (bottone.dataset[campo]) p.set(campo, bottone.dataset[campo]); });
    let codice = 0;
    let dati = null;
    try {
      const r = await fetch("/api/norma?" + p.toString(), { headers: { "X-Iudex": "1" } });
      codice = r.status;
      try { dati = await r.json(); } catch (e) { dati = null; }
    } catch (e) { codice = 0; }
    bottone.disabled = false;
    if (!pannello.isConnected) return;
    pannello.textContent = "";
    if (codice === 200 && dati) riempiNorma(pannello, dati);
    else erroreNorma(pannello, codice, dati);
  }

  function descriviPermalink(permalink) {
    if (!permalink) return "";
    const p = new URLSearchParams(permalink);
    const v = { testo: p.get("testo"), riferimenti: p.get("rif"), filtri: {} };
    CAMPI_FILTRO.forEach((c) => { const x = p.get(c); if (x) v.filtri[c] = x.split(SEPARATORI[c] || ","); });
    const ordina = p.get("ordina");
    return descriviVoce(v) + (ordina && ordina !== "pubblicazione" ? ` (per ${ordina})` : "");
  }

  // Badge "già vista": il tooltip dice quando e da quali ricerche è stata aperta la sentenza
  // e in quali ricerche è uscita fra i risultati.
  function badgeVista(c) {
    if (!c || !c.volte) return "";
    const righe = [`Vista ${c.volte === 1 ? "una volta" : c.volte + " volte"}, l'ultima il ${quando(c.ultima)}${c.pdf ? " (anche il PDF)" : ""}`];
    if (c.aperta_da && c.aperta_da.length) {
      righe.push("Aperta da:");
      c.aperta_da.forEach((a) => righe.push(`  · ${a.descrizione} (${quando(a.quando)})`));
    }
    if (c.uscita_in && c.uscita_in.length) {
      righe.push("Uscita nelle ricerche:");
      c.uscita_in.forEach((u) => righe.push(`  · ${u.descrizione || "ricerca"} (${quando(u.quando)})`));
    }
    return `<span class="gia-vista" title="${escapa(righe.join("\n"))}">già vista</span>`;
  }

  // PDF: Iudex lo prepara (copia locale o primo scaricamento) e lo mostra nel pannello di
  // lettura, oppure lo apre con il programma del computer, come scelto nelle Impostazioni.
  async function apriPdf(id, da) {
    messaggio("");
    try {
      const r = await api("/api/pdf/" + encodeURIComponent(id), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ da: da || null }),
      });
      if (r.aperto_con_programma) {
        messaggio("PDF aperto con il programma del computer" + (r.salvato ? ` (salvato in ${r.percorso})` : " (non salvato: storico spento)") + ".");
        return;
      }
      mostraPdf(id, r);
    } catch (e) { messaggio("PDF non disponibile: " + (e.message || String(e))); }
  }

  function mostraPdf(id, r) {
    $("#fascicolo").hidden = false;
    $("#maniglia-fascicolo").hidden = false;
    $("#corpo").classList.add("con-fascicolo");
    $("#evidenziatore").hidden = true;
    $("#vai-pqm").hidden = true;
    if (stato.idAperto !== id) {
      stato.idAperto = id;
      $$(".voce").forEach((v) => v.classList.toggle("aperta", v.dataset.id === id));
      $("#fascicolo-estremi").textContent = "PDF della sentenza";
    }
    const nota = r.salvato ? `${r.gia_locale ? "Dalla copia locale" : "Scaricato e salvato"}: ${escapa(r.percorso)}` : "Non salvato: storico spento";
    $("#fascicolo-corpo").innerHTML = `
      <div class="visore-barra"><button type="button" class="discreto torna-al-testo" data-id="${escapa(id)}">Torna al testo</button> <span class="dettaglio">${nota}</span></div>
      <iframe class="visore-pdf" src="${escapa(r.url)}" title="PDF della sentenza"></iframe>`;
  }

  function consultazioneHtml(c) {
    if (!c || !c.volte) return "";
    // Le ricerche di provenienza, una volta ciascuna, dalla più recente.
    const viste = new Set();
    const ricerche = [];
    (c.aperture || []).forEach((a) => {
      if (!a.permalink || viste.has(a.permalink)) return;
      viste.add(a.permalink);
      ricerche.push(a);
    });
    const da = ricerche.slice(0, 4).map((a) =>
      `<a href="#${escapa(a.permalink)}" title="Riapri la ricerca">${escapa(descriviPermalink(a.permalink))}</a> <span class="quando">(${quando(a.quando)})</span>`).join(", ");
    const volte = c.volte === 1 ? "Prima apertura" : `Aperta <b>${c.volte}</b> volte, la prima ${quando(c.prima_volta)}`;
    const uscite = c.uscita_in || [];
    const uscita = uscite.slice(0, 4).map((u) =>
      `<a href="#${escapa(u.ricerca)}" title="Riapri la ricerca">${escapa(u.descrizione || descriviPermalink(u.ricerca))}</a> <span class="quando">(${quando(u.quando)})</span>`).join(", ");
    const righeUscita = uscite.length
      ? `<div class="consultazione">Uscita in <b>${uscite.length}</b> ricerc${uscite.length === 1 ? "a" : "he"}: ${uscita}${uscite.length > 4 ? ` e altre ${uscite.length - 4}` : ""}</div>`
      : "";
    return `<div class="consultazione">${volte}${da ? " · da: " + da : ""}${ricerche.length > 4 ? ` e altre ${ricerche.length - 4}` : ""} · <a href="#diario" class="vai-diario">Diario</a></div>${righeUscita}`;
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
    apriFascicolo(ids[i], true);
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
    SCHEDE.forEach((n) => { $("#pannello-" + n).hidden = n !== nome; });
    const conFiltri = nome === "risultati";
    $("#filtri").hidden = !conFiltri;
    $("#maniglia-filtri").hidden = !conFiltri;
    $("#corpo").classList.toggle("senza-filtri", !conFiltri);
    if (!conFiltri && !$("#fascicolo").hidden) chiudiFascicolo();
    if (nome === "cronologia") caricaCronologia();
    if (nome === "diario") caricaDiario();
    if (nome === "salvate") caricaSalvate();
    if (nome === "preferiti") caricaPreferiti();
    if (nome === "stato") caricaStato();
    if (nome === "impostazioni") caricaImpostazioni();
  }

  function descriviVoce(v) {
    const parti = [];
    if (v.testo) parti.push(v.testo);
    if (v.riferimenti) parti.push("rif. " + v.riferimenti);
    Object.keys(v.filtri || {}).forEach((k) => parti.push(k === "segnale"
      ? v.filtri[k].map((c) => SEGNALI[c] || c).join(", ")
      : `${TITOLI_FACET[k] || k}: ${v.filtri[k].join(", ")}`));
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

  function oraBreve(ts) {
    return ts ? new Date(ts * 1000).toLocaleTimeString("it-IT", { timeStyle: "short" }) : "";
  }

  async function caricaDiario() {
    const sel = $("#diario-giorno");
    const giorni = await api("/api/diario/giorni");
    const corpo = $("#diario-corpo");
    if (!giorni.length) {
      sel.innerHTML = "";
      corpo.innerHTML = '<p class="vuota">Il diario è vuoto: si riempie con la prima ricerca.</p>';
      return;
    }
    const scelto = giorni.some((g) => g.giorno === sel.value) ? sel.value : giorni[0].giorno;
    sel.innerHTML = giorni.map((g) => `<option value="${g.giorno}" ${g.giorno === scelto ? "selected" : ""}>${dataIt(g.giorno)} · ${g.ricerche} ricerche, ${g.sentenze} sentenze</option>`).join("");
    const voci = await api("/api/diario?giorno=" + encodeURIComponent(scelto) + "&limite=2000");
    corpo.innerHTML = disegnaDiario(voci);
  }

  function disegnaDiario(voci) {
    // Dal più vecchio al più recente: ogni apertura si aggancia all'ultima ricerca con lo stesso permalink.
    const blocchi = [];
    const perPermalink = new Map();
    let sciolte = null;
    voci.slice().reverse().forEach((v) => {
      if (v.tipo === "ricerca") {
        const b = { ricerca: v, aperture: [] };
        blocchi.push(b);
        perPermalink.set(v.permalink, b);
        return;
      }
      const b = v.permalink ? perPermalink.get(v.permalink) : null;
      if (b) { b.aperture.push(v); return; }
      if (!sciolte) { sciolte = { ricerca: null, aperture: [] }; blocchi.push(sciolte); }
      sciolte.aperture.push(v);
    });
    const apertura = (a) => {
      const e = a.documento || {};
      const estremi = e.numero ? estremiDoc(e) : escapa(a.id_sentenza);
      return `<li><span class="quando">${oraBreve(a.quando)}</span> <a href="#" class="apri-diario" data-id="${escapa(a.id_sentenza)}">${estremi}</a>${e.data_deposito ? ` <span class="dettaglio">dep. ${dataIt(e.data_deposito)}</span>` : ""}</li>`;
    };
    return blocchi.reverse().map((b) => {
      const r = b.ricerca;
      const testa = r
        ? `<div class="diario-ricerca"><span class="quando">${oraBreve(r.quando)}</span> <a class="titolo" href="#${escapa(r.permalink)}">${escapa(descriviVoce(r))}</a> <span class="dettaglio">${numero(r.trovati)} provvedimenti${r.pagina > 1 ? `, pagina ${r.pagina}` : ""}${r.ordinamento && r.ordinamento !== "pubblicazione" ? `, per ${escapa(r.ordinamento)}` : ""}</span></div>`
        : '<div class="diario-ricerca"><span class="dettaglio">Aperte senza una ricerca (dai preferiti, dal diario o da un indirizzo)</span></div>';
      const lista = b.aperture.length ? `<ul class="diario-aperture">${b.aperture.map(apertura).join("")}</ul>` : "";
      return `<div class="diario-blocco">${testa}${lista}</div>`;
    }).join("");
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
        <td><a class="titolo apri-preferito" href="#" data-id="${escapa(v.id_sentenza)}">${estremiDoc(e)}</a> ${badgeVista(v.consultazione)}${e.data_deposito ? `<div class="dettaglio">dep. ${dataIt(e.data_deposito)}</div>` : ""}</td>
        <td><span class="ecli">${escapa(e.ecli || "")}</span></td>
        <td><input class="nota" type="text" value="${escapa(v.nota || "")}" placeholder="aggiungi una nota" data-id="${escapa(v.id_sentenza)}"></td>
        <td class="azioni-td">${e.pdf ? `<button type="button" class="discreto apri-pdf" data-id="${escapa(v.id_sentenza)}">PDF</button>` : ""}<button type="button" class="discreto rimuovi-preferito" data-id="${escapa(v.id_sentenza)}">Rimuovi</button></td>
      </tr>`;
    }).join("");
  }

  async function caricaStato() {
    const s = await api("/api/stato");
    const righe = s.registro.map((r) => `<tr><td>${r.quando}</td><td>${escapa(r.tipo)}</td><td>${r.stato === null ? "rete" : r.stato}</td><td>${r.durata_ms} ms</td><td>${escapa(r.dettaglio)}</td></tr>`).join("");
    $("#stato").innerHTML = `
      <p>Iudex ${escapa(s.versione)} · richieste al server della Corte in questa sessione: <b>${s.chiamate_remote}</b> ·
         intervallo minimo fra richieste: ${s.intervallo_minimo_s} s${s.pausa_residua_s ? ` · <b>pausa chiesta dal server: ancora ${s.pausa_residua_s} s</b>` : ""} ·
         identità dichiarata oggi: <b>${escapa(s.impronta)}</b>${s.impronta_fissa ? " (fissa)" : ""}</p>
      <p>Cache locale: <b>${s.sentenze_in_cache}</b> testi di sentenze, <b>${s.risposte_in_cache}</b> risposte di ricerca · archivio: <code>${escapa(s.percorso_dati)}</code></p>
      ${s.aggiornamento && s.aggiornamento.disponibile ? `<p class="aggiornamento">È disponibile Iudex <b>${escapa(s.aggiornamento.versione)}</b> (in uso ${escapa(s.aggiornamento.attuale)})${s.aggiornamento.note ? ": " + escapa(s.aggiornamento.note) : ""}. <button type="button" id="installa-aggiornamento">Scarica e installa</button> <span class="dettaglio">l'installer si avvia dopo il controllo dello sha256 e chiude Iudex</span></p>` : ""}
      <p>Diario: <b>${numero(s.voci_diario)}</b> voci, <b>${numero(s.sentenze_consultate)}</b> sentenze consultate con il testo conservato (non vengono toccate dai pulsanti della cache) · <b>${numero(s.esecuzioni)}</b> pagine di risultati ricordate.</p>
      <p>PDF salvati: <b>${numero(s.pdf_salvati)}</b> in <code>${escapa(s.cartella_pdf)}</code></p>
      ${s.normattiva ? `<p>Normattiva: richieste in questa sessione: <b>${numero(s.normattiva.chiamate)}</b> · intervallo minimo: ${s.normattiva.intervallo_minimo_s} s${s.normattiva.pausa_residua_s ? ` · <b>pausa chiesta: ancora ${Math.ceil(s.normattiva.pausa_residua_s)} s</b>` : ""} · articoli in cache: <b>${numero(s.normattiva.norme_in_cache)}</b></p>` : ""}
      <table><thead><tr><th>Ora</th><th>Tipo</th><th>Stato</th><th>Durata</th><th>Note</th></tr></thead><tbody>${righe || '<tr><td colspan="5">Nessuna richiesta ancora.</td></tr>'}</tbody></table>`;
    const pulsante = $("#installa-aggiornamento");
    if (pulsante) pulsante.addEventListener("click", async () => {
      pulsante.disabled = true;
      try { const r = await api("/api/aggiornamento/installa", { method: "POST" }); messaggio(`Installer di Iudex ${r.versione} avviato.`); }
      catch (e) { messaggio(e.message || String(e)); pulsante.disabled = false; }
    });
  }

  // ---------- impostazioni ----------

  const CAMPI_IMPOSTAZIONI = ["conserva_storico", "cartella_pdf", "pdf_apertura", "impronta_modo",
    "impronta_fissa", "impronta_personalizzata", "rotazione_include_predefinite"];

  function esitoImpostazioni(testo) {
    const m = $("#impostazioni-esito");
    m.hidden = !testo;
    m.textContent = testo || "";
  }

  function mostraModoImpronta() {
    const modo = $("#impostazioni").elements.impronta_modo.value;
    $$("#impostazioni [data-modo]").forEach((el) => { el.hidden = el.dataset.modo !== modo; });
  }

  function compilaImpostazioni(r) {
    const f = $("#impostazioni").elements;
    const v = r.valori;
    f.impronta_fissa.innerHTML = r.codici_impronta.map((c) => `<option value="${escapa(c)}">${escapa(c)}</option>`).join("");
    const nomi = (v.impronte_personalizzate || []).map((i) => i.nome);
    f.impronta_personalizzata.innerHTML = nomi.length
      ? nomi.map((n) => `<option value="${escapa(n)}">${escapa(n)}</option>`).join("")
      : '<option value="">nessuna impronta personalizzata</option>';
    f.conserva_storico.checked = v.conserva_storico;
    f.rotazione_include_predefinite.checked = v.rotazione_include_predefinite;
    f.cartella_pdf.value = v.cartella_pdf || "";
    f.cartella_pdf.placeholder = r.cartella_pdf_predefinita;
    f.pdf_apertura.value = v.pdf_apertura;
    f.impronta_modo.value = v.impronta_modo;
    f.impronta_fissa.value = v.impronta_fissa;
    f.impronta_personalizzata.value = v.impronta_personalizzata || "";
    f.nome_macchina.value = (r.macchina && r.macchina.nome) || "";
    disegnaImpronte(v.impronte_personalizzate || []);
    const bloccata = r.bloccate.impronta_modo;
    f.impronta_modo.disabled = f.impronta_fissa.disabled = Boolean(bloccata);
    $("#impronta-bloccata").hidden = !bloccata;
    $("#impronta-bloccata").textContent = bloccata ? `Impronta ${bloccata}.` : "";
    mostraModoImpronta();
  }

  async function caricaImpostazioni() {
    esitoImpostazioni("");
    const orari = window.IudexTema ? window.IudexTema.leggiOrari() : { inizio: 19, fine: 7 };
    $("#tema-inizio").value = orari.inizio;
    $("#tema-fine").value = orari.fine;
    try { compilaImpostazioni(await api("/api/impostazioni")); }
    catch (e) { esitoImpostazioni(e.message || String(e)); }
  }

  async function salvaImpostazioni() {
    const f = $("#impostazioni").elements;
    const corpo = {};
    CAMPI_IMPOSTAZIONI.forEach((k) => {
      const campo = f[k];
      if (campo.disabled) return;
      corpo[k] = campo.type === "checkbox" ? campo.checked : (campo.value.trim() || null);
    });
    corpo.impronte_personalizzate = leggiImpronte();
    corpo.cartella_pdf_scelta = true;
    if (f.nome_macchina.value.trim()) corpo.nome_macchina = f.nome_macchina.value.trim();
    try {
      compilaImpostazioni(await api("/api/impostazioni", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corpo),
      }));
      esitoImpostazioni("Impostazioni salvate.");
    } catch (e) { esitoImpostazioni(e.message || String(e)); }
  }

  // Impronte personalizzate: una riga per impronta; si salvano con il pulsante Salva.
  function rigaImpronta(i) {
    const ua = (i.client_hints && i.client_hints["sec-ch-ua"]) || "";
    return `<tr class="impronta">
      <td><input class="input-field" data-campo="nome" value="${escapa(i.nome || "")}" size="12"></td>
      <td><input class="input-field" data-campo="user_agent" value="${escapa(i.user_agent || "")}" size="48" placeholder="Mozilla/5.0 (Windows NT 10.0; Win64; x64) …"></td>
      <td><input class="input-field" data-campo="accept_language" value="${escapa(i.accept_language || "")}" size="16" placeholder="it-IT,it;q=0.9"></td>
      <td><input class="input-field" data-campo="sec-ch-ua" value="${escapa(ua)}" size="24" placeholder="ricavato da Iudex"></td>
      <td class="azioni-td"><button type="button" class="discreto prova-una">Prova</button><button type="button" class="discreto togli-impronta">Togli</button></td>
    </tr>`;
  }

  function disegnaImpronte(voci) {
    $("#lista-impronte").innerHTML = voci.map(rigaImpronta).join("");
  }

  function voceImpronta(tr) {
    const campo = (n) => $(`[data-campo="${n}"]`, tr).value.trim();
    const ua = campo("sec-ch-ua");
    return { nome: campo("nome"), user_agent: campo("user_agent"), accept_language: campo("accept_language"), client_hints: ua ? { "sec-ch-ua": ua } : {} };
  }

  function leggiImpronte() {
    return $$("#lista-impronte tr.impronta").map(voceImpronta).filter((i) => i.nome || i.user_agent);
  }

  async function provaImpronta(voce) {
    const esito = $("#esito-impronta");
    esito.hidden = false;
    try {
      const r = await api("/api/impronta/prova", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(voce || {}),
      });
      esito.textContent = `${r.nome}\n` + Object.entries(r.header).map(([k, v]) => `${k}: ${v}`).join("\n");
    } catch (e) { esito.textContent = e.message || String(e); }
  }

  async function importaStorico() {
    const file = $("#file-importa").files[0];
    const esito = $("#esito-importa");
    if (!file) { esito.hidden = false; esito.textContent = "Scegli prima un file."; return; }
    const b = $("#importa");
    b.disabled = true;
    esito.hidden = false;
    esito.textContent = "Importo…";
    try {
      const r = await api("/api/importa?nome=" + encodeURIComponent(file.name), {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: file,
      });
      const voce = (t, n) => `${t}: <b>${r[n].aggiunte}</b> aggiunte, ${r[n].presenti} già presenti`;
      const p = r.pdf;
      esito.innerHTML = [
        `Importato (${escapa(r.formato)}). Copia di sicurezza: <code>${escapa(r.copia_di_sicurezza)}</code>`,
        voce("Ricerche", "ricerche"), voce("Pagine di risultati", "esecuzioni"),
        voce("Voci del diario", "diario"), voce("Sentenze consultate", "consultate"),
        `PDF: <b>${p.aggiunti}</b> aggiunti, ${p.presenti} già presenti` +
          (p.diversi.length ? `, ${p.diversi.length} diversi da quelli locali (tenuti i locali)` : "") +
          (p.rifiutati.length ? `, ${p.rifiutati.length} danneggiati nel pacchetto (scartati)` : ""),
      ].join("<br>");
    } catch (e) { esito.textContent = "Importazione non riuscita: " + (e.message || String(e)); }
    finally { b.disabled = false; }
  }

  async function aggiornaPie() {
    try {
      const s = await api("/api/stato");
      $("#pie-versione").textContent = `Iudex ${s.versione}` + (s.aggiornamento && s.aggiornamento.disponibile ? ` · disponibile la ${s.aggiornamento.versione} (scheda Stato)` : "");
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
    // Il segnale ha un solo valore: sceglierne uno toglie l'altro.
    const lista = new Set(campo === "segnale" ? [] : (stato.filtri[campo] || []));
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
    if (e.target.closest(".apri-pdf")) { apriPdf(voce.dataset.id, stato.risposta.permalink); return; }
    if (e.target.closest(".apri") || e.target.closest(".estremi")) apriFascicolo(voce.dataset.id, true);
  });

  $("#risultati").addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && e.target.classList.contains("estremi")) {
      e.preventDefault();
      apriFascicolo(e.target.closest(".voce").dataset.id, true);
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

  $("#fascicolo-pdf").addEventListener("click", (e) => {
    const b = e.currentTarget;
    apriPdf(b.dataset.id, b.dataset.da || null);
  });

  $("#fascicolo-corpo").addEventListener("click", (e) => {
    const torna = e.target.closest(".torna-al-testo");
    if (torna) { apriFascicolo(torna.dataset.id); return; }
    const testoNorma = e.target.closest(".btn-testo");
    if (testoNorma) { apriNorma(testoNorma); return; }
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
      else testo = `<b>${r.nuovi.length} nuov${r.nuovi.length === 1 ? "o" : "i"}:</b><ul>` + r.nuovi.map((d) => `<li><a href="#" class="apri-nuovo" data-id="${escapa(d.id)}">${estremiDoc(d)}</a> ${badgeVista(d.consultazione)} · dep. ${dataIt(d.data_deposito)}</li>`).join("") + "</ul>";
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
    const p = e.target.closest(".apri-pdf");
    if (p) { apriPdf(p.dataset.id, null); return; }
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

  function esitoStato(testo) {
    const m = $("#stato-esito");
    m.hidden = !testo;
    m.textContent = testo || "";
  }

  $("#diario-giorno").addEventListener("change", caricaDiario);
  $("#diario-corpo").addEventListener("click", (e) => {
    const a = e.target.closest(".apri-diario");
    if (!a) return;
    e.preventDefault();
    mostraScheda("risultati");
    $("#benvenuto").hidden = true;
    apriFascicolo(a.dataset.id);
  });
  $$(".esporta-diario").forEach((b) => b.addEventListener("click", () => scarica("/api/export/diario?formato=" + b.dataset.formato).catch((err) => messaggio("Esportazione non riuscita: " + err.message))));
  $$(".esporta-ricerche").forEach((b) => b.addEventListener("click", () => scarica("/api/export/ricerche?formato=" + b.dataset.formato).catch((err) => messaggio("Esportazione non riuscita: " + err.message))));
  $("#esporta-consultate").addEventListener("click", () => scarica("/api/export/consultate").catch((err) => messaggio("Esportazione non riuscita: " + err.message)));
  $("#esporta-ftm").addEventListener("click", () => scarica("/api/export/consultate?formato=ftm").catch((err) => messaggio("Esportazione non riuscita: " + err.message)));
  $("#copia-sicurezza").addEventListener("click", async (e) => {
    e.currentTarget.disabled = true;
    try {
      const r = await api("/api/backup", { method: "POST" });
      esitoStato(`Copia di sicurezza salvata in ${r.percorso}`);
    } catch (err) { esitoStato("Copia non riuscita: " + err.message); } finally { $("#copia-sicurezza").disabled = false; }
  });

  $("#svuota-cache").addEventListener("click", async () => { const r = await api("/api/cache", { method: "DELETE" }); caricaStato(); messaggio(`Cache delle ricerche svuotata (${r.rimosse} voci).`); });
  $("#svuota-testi").addEventListener("click", async () => { const r = await api("/api/cache/sentenze", { method: "DELETE" }); caricaStato(); aggiornaPie(); messaggio(`Testi in cache rimossi (${r.rimosse}).`); });

  $$(".scheda").forEach((b) => b.addEventListener("click", () => mostraScheda(b.dataset.scheda)));
  $("#salva-impostazioni").addEventListener("click", salvaImpostazioni);
  $("#importa").addEventListener("click", importaStorico);
  $("#aggiungi-impronta").addEventListener("click", () => {
    $("#lista-impronte").insertAdjacentHTML("beforeend", rigaImpronta({}));
  });
  $("#prova-impronta").addEventListener("click", () => provaImpronta(null));
  $("#lista-impronte").addEventListener("click", (e) => {
    const tr = e.target.closest("tr.impronta");
    if (!tr) return;
    if (e.target.closest(".togli-impronta")) tr.remove();
    if (e.target.closest(".prova-una")) provaImpronta(voceImpronta(tr));
  });
  $("#impostazioni").addEventListener("submit", (e) => { e.preventDefault(); salvaImpostazioni(); });
  $("#impostazioni").elements.impronta_modo.addEventListener("change", mostraModoImpronta);

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
      if (e.key === "Enter" && stato.rigaFuoco >= 0) { apriFascicolo(stato.risposta.documenti[stato.rigaFuoco].id, true); return; }
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

  // ---------- preferenze locali: densità, carattere, colonne (il tema è in tema.js) ----------

  try {
    if (localStorage.getItem("iudex.densita") === "compatta") document.body.classList.add("compatta");
  } catch (e) { /* storage non disponibile */ }
  const carattere = memoria("iudex.carattere");
  if (carattere) applicaCarattere(carattere);

  // Orari del tema automatico (scheda Impostazioni, gruppo Aspetto): valgono subito e restano
  // memorizzati nella finestra, senza passare dal pulsante Salva.
  $("#pannello-impostazioni").addEventListener("change", (e) => {
    if (!e.target.matches("#tema-inizio, #tema-fine") || !window.IudexTema) return;
    const inizio = Math.max(0, Math.min(23, parseInt($("#tema-inizio").value, 10) || 0));
    const fine = Math.max(0, Math.min(23, parseInt($("#tema-fine").value, 10) || 0));
    window.IudexTema.impostaOrari(inizio, fine);
    esitoImpostazioni(`Tema scuro automatico dalle ${inizio}:00 alle ${fine}:00.`);
  });

  // Le voci della barra rispondono anche a Invio e barra spaziatrice.
  $$(".menu > li.scheda").forEach((li) => li.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); li.click(); }
  }));

  $("#densita").addEventListener("click", (e) => {
    const c = document.body.classList.toggle("compatta");
    e.currentTarget.classList.toggle("attivo", c);
    try { localStorage.setItem("iudex.densita", c ? "compatta" : "normale"); } catch (err) { /* ignora */ }
  });
  if (document.body.classList.contains("compatta")) $("#densita").classList.add("attivo");

  preparaPannelli();
  $$(".tabella").forEach(rendiRidimensionabile);

  // ---------- avvio ----------

  // Primo avvio senza installer (Linux, sorgenti): la cartella dei PDF si sceglie qui.
  async function chiediCartellaPdf() {
    try {
      const r = await api("/api/impostazioni");
      if (!r.cartella_pdf_da_scegliere) return;
      $("#primo-avvio-cartella").value = r.cartella_pdf_predefinita;
      $("#primo-avvio").hidden = false;
    } catch (e) { /* silenzioso: resta la cartella predefinita */ }
  }
  $("#primo-avvio-conferma").addEventListener("click", async () => {
    try {
      await api("/api/impostazioni", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cartella_pdf: $("#primo-avvio-cartella").value.trim() || null, cartella_pdf_scelta: true }),
      });
      $("#primo-avvio").hidden = true;
    } catch (e) { messaggio("Cartella non utilizzabile: " + (e.message || String(e))); }
  });

  disegnaFacet(null);
  aggiornaPie();
  chiediCartellaPdf();
  if (leggiHash()) cerca(stato.pagina);
  else $("#testo").focus();
})();
