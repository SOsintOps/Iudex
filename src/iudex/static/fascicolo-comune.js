/* Scheda della sentenza: funzioni di impaginazione senza stato, comuni a Iudex e alle altre app
   locali che mostrano lo stesso fascicolo (si caricano da /static/fascicolo-comune.js prima del
   codice della pagina). Espone window.FascicoloComune. */
(function (globale) {
  "use strict";

  // Titoli delle parti della motivazione: diventano intestazioni del testo; «P.Q.M.» apre il dispositivo.
  const INTESTAZIONI = [
    "FATTI DI CAUSA", "RAGIONI DELLA DECISIONE", "RITENUTO IN FATTO", "CONSIDERATO IN DIRITTO",
    "MOTIVI DELLA DECISIONE", "SVOLGIMENTO DEL PROCESSO", "FATTO E DIRITTO", "RILEVATO CHE",
    "CONSIDERATO CHE", "RITENUTO CHE", "OSSERVA", "P.Q.M.",
  ];

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

  function dataIt(iso) {
    if (!iso) return "";
    const [a, m, g] = String(iso).split("-");
    return g ? `${g}/${m}/${a}` : String(iso);
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

  // Il dispositivo quando manca il campo della Corte: dal «P.Q.M.» del testo alla fine, senza le
  // firme e le date di deposito che lo seguono.
  function dispositivoDalTesto(testo) {
    const t = String(testo || "");
    const m = /(^|\n|\s)P\.?\s?Q\.?\s?M\.?\s*/.exec(t);
    if (!m) return "";
    let resto = t.slice(m.index + m[0].length);
    const fine = /\s(Così (è )?deciso|Cosi' deciso|Depositat[ao] in cancelleria|Il Consigliere|Il Presidente|DEPOSITAT)/i.exec(resto);
    if (fine && fine.index > 20) resto = resto.slice(0, fine.index);
    resto = resto.replace(/\s+/g, " ").trim();
    return resto.length > 1500 ? resto.slice(0, 1500) + "…" : resto;
  }

  /* Estremi in testa: sezione, tipo e numero, poi le voci della riga «meta» (udienza, deposito,
     presidente, relatore, ECLI, materia) e, in coda, le voci in più della pagina (``altre``,
     già in HTML). */
  function estremiHtml(doc, altre) {
    const d = doc || {};
    const voci = [];
    if (d.pubblicazione) voci.push(`<span>pubbl. ${escapa(d.pubblicazione)}</span>`);
    voci.push(`<span>udienza ${dataIt(d.data_decisione) || "?"}</span>`);
    voci.push(`<span>deposito ${dataIt(d.data_deposito) || "?"}</span>`);
    if (d.presidente) voci.push(`<span>pres. ${escapa(d.presidente)}</span>`);
    if (d.relatore) voci.push(`<span>rel. ${escapa(d.relatore)}</span>`);
    if (d.ecli) voci.push(`<span class="ecli">${escapa(d.ecli)}</span>`);
    if (d.materia && d.materia.length) voci.push(`<span class="materia-voce">${escapa(d.materia.join(", "))}</span>`);
    return `
      <span class="sezione">${escapa(d.archivio)}${d.sezione ? " · Sez. " + escapa(d.sezione) : ""}</span>
      ${escapa(d.tipo || "")} n. ${escapa(d.numero)}/${escapa(d.anno)}
      <div class="meta">${voci.join("")}${(altre || []).join("")}</div>`;
  }

  // Riquadro del dispositivo (o della massima) in testa al corpo.
  function dispositivoHtml(html) {
    return html ? `<div class="massima">${html}</div>` : "";
  }

  /* Etichette dei riferimenti normativi: ``riferimenti`` è una lista di {testo, ricerca};
     ``bottone(r, i)`` aggiunge l'HTML accanto all'etichetta (per esempio «Testo»). */
  function riferimentiHtml(riferimenti, bottone, titolo) {
    if (!riferimenti || !riferimenti.length) return "";
    return `<div class="rnc"><span>${escapa(titolo || "Riferimenti normativi:")}</span>` + riferimenti.map((r, i) =>
      `<span class="rif-norma"><span class="chip"${r.ricerca ? ` role="button" tabindex="0" data-ricerca="${escapa(r.ricerca)}" title="Cerca le sentenze che citano questa norma"` : ""}>${escapa(r.testo)}</span>${bottone ? bottone(r, i) : ""}</span>`).join("") +
      '</div><div class="norme-aperte"></div>';
  }

  // Intestazione «Testo del provvedimento» e testo in paragrafi (``html`` già neutralizzato).
  function testoHtml(html, titolo) {
    return `<div class="intestazione-testo">${escapa(titolo || "Testo del provvedimento")}</div>` +
      `<div class="testo">${html ? inParagrafi(html) : "<p>Testo non disponibile.</p>"}</div>`;
  }

  function scorriA(corpo, el) {
    const y = el.getBoundingClientRect().top - corpo.getBoundingClientRect().top + corpo.scrollTop;
    corpo.scrollTop = Math.max(0, y - corpo.clientHeight / 2);
  }

  /* Navigatore delle occorrenze evidenziate (‹ 1 / 8 ›): ``corpo`` è il contenitore che scorre,
     ``riquadro`` lo nasconde quando non ci sono occorrenze, ``posizione`` mostra il contatore. */
  function navigatore(corpo, riquadro, posizione) {
    let occorrenze = [];
    let corrente = -1;
    function vai(i) {
      if (!occorrenze.length) return;
      const n = occorrenze.length;
      corrente = ((i % n) + n) % n;
      occorrenze.forEach((m, k) => m.classList.toggle("corrente", k === corrente));
      scorriA(corpo, occorrenze[corrente]);
      posizione.textContent = `${corrente + 1} / ${n}`;
    }
    return {
      prepara() {
        occorrenze = Array.from(corpo.querySelectorAll("mark, em.hit"));
        corrente = -1;
        riquadro.hidden = !occorrenze.length;
        if (occorrenze.length) vai(0);
      },
      nascondi() { occorrenze = []; corrente = -1; riquadro.hidden = true; },
      successiva() { vai(corrente + 1); },
      precedente() { vai(corrente - 1); },
    };
  }

  globale.FascicoloComune = {
    INTESTAZIONI, escapa, conMarcature, dataIt, inParagrafi, dispositivoDalTesto,
    estremiHtml, dispositivoHtml, riferimentiHtml, testoHtml, scorriA, navigatore,
  };
})(window);
