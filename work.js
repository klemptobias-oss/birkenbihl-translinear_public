// work.js — eine Datei für alle Werke (Poesie & Prosa)
//
// Liest Konfiguration aus data-Attributen ODER URL-Parametern:
//   genre: "poesie" | "prosa"
//   author: z.B. "Aischylos"
//   work:   z.B. "Der_gefesselte_Prometheus"
//
// Erwartete Struktur (wie von dir definiert):
//  Texte (Original/Birkenbihl):
//    texte/<genre>/<Author>/<Work>.txt
//    texte/<genre>/<Author>/<Work>_birkenbihl.txt
//  PDFs (Original/Drafts):
//    pdf/original_<genre>_pdf/<Author>/<Base>_<Strength>_<Color>_<Tag>[ _Versmaß ].pdf
//    pdf_drafts/draft_<genre>_pdf/<Author>/<Base>_<Strength>_<Color>_<Tag>[ _Versmaß ].pdf
//
// UI-Erwartung (optional, wird robust geprüft):
//   - <pre id="orig-text">, <pre id="birk-text">
//   - <iframe id="pdf-frame">
//   - Radiogruppen (name-Attribute oder data-role):
//       Gruppe Quelle:    name="mode-origin" -> values: "Original" | "Entwurf"
//       Gruppe Stärke:    name="opt-strength" -> values: "NORMAL" | "GR_FETT" | "DE_FETT"
//       Gruppe Farbe:     name="opt-color"    -> values: "Colour" | "BlackWhite"
//       Gruppe Tags:      name="opt-tags"     -> values: "Tag" | "NoTag"
//       Gruppe Versmaß:   name="opt-meter"    -> values: "Versmass" | "Ohne"
//   - Falls IDs stattdessen genutzt werden: Buttons mit data-role="option" und data-group="..." data-value="..."
//     werden ebenfalls unterstützt.
//
// Hinweise:
//  - Umlaute/Leerzeichen werden unverändert übernommen. Achte darauf, Work/Author genau so zu benennen,
//    wie die Dateien heißen (z.B. "Der_gefesselte_Prometheus").
//

// ---------------------- Utilities ----------------------
function qs(sel, root = document) { return root.querySelector(sel); }
function qsa(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }

function getParam(name, fallback = "") {
  const u = new URL(window.location.href);
  return u.searchParams.get(name) || fallback;
}

function getDataOrParam(key, fallback = "") {
  const root = document.body || document.documentElement;
  const dataVal = root?.dataset?.[key] || "";
  return getParam(key, dataVal || fallback);
}

function textExistsElem(id) { return !!qs(`#${id}`); }
function setText(id, txt) { const el = qs(`#${id}`); if (el) el.textContent = txt; }

async function fetchTextOrNull(url) {
  try {
    const resp = await fetch(url, { cache: "no-store" });
    if (!resp.ok) return null;
    return await resp.text();
  } catch { return null; }
}

async function urlExists(url) {
  try {
    const resp = await fetch(url, { method: "HEAD", cache: "no-store" });
    return resp.ok;
  } catch { return false; }
}

// ---------------------- Config aus Seite/URL ----------------------
function readWorkConfig() {
  // genre: "poesie" | "prosa"
  const genre = (getDataOrParam("genre", "poesie") || "").toLowerCase();
  const author = getDataOrParam("author", "");
  const work = getDataOrParam("work", "");

  // Normierte Basen/Ordner
  const txtBase = `texte/${genre}/${author}/${work}`;
  const pdfBaseOriginal = `pdf/original_${genre}_pdf/${author}/`;
  const pdfBaseDraft   = `pdf_drafts/draft_${genre}_pdf/${author}/`;

  return {
    genre, author, work,
    paths: {
      txtOrig: `${txtBase}.txt`,
      txtBirk: `${txtBase}_birkenbihl.txt`,
      pdfOriginalDir: pdfBaseOriginal,
      pdfDraftDir: pdfBaseDraft
    }
  };
}

// ---------------------- Selection-Reader ----------------------
// liest radiogruppen ODER data-role Buttons (Fallbacks gesetzt)
function readSelection(groupName, fallbackValue) {
  // 1) Radiobuttons mit name=groupName
  const radios = qsa(`input[type="radio"][name="${groupName}"]`);
  const sel = radios.find(r => r.checked);
  if (sel) return sel.value;

  // 2) Buttons/Links mit data-role="option" und data-group="groupName"
  const active = qs(`[data-role="option"][data-group="${groupName}"][aria-pressed="true"]`);
  if (active) return active.dataset.value;

  // 3) Fallback
  return fallbackValue;
}

function currentUiOptions() {
  // Quelle: Original/Entwurf
  const origin = readSelection("mode-origin", "Original"); // "Original" | "Entwurf"

  // Stärke
  const strength = readSelection("opt-strength", "NORMAL"); // "NORMAL" | "GR_FETT" | "DE_FETT"

  // Farbe
  // Achtung: Dateinamens-Suffixe sind "Colour" | "BlackWhite" (genau so!)
  const color = readSelection("opt-color", "Colour"); // "Colour" | "BlackWhite"

  // Tags
  const tags = readSelection("opt-tags", "Tag"); // "Tag" | "NoTag"

  // Versmaß
  const meter = readSelection("opt-meter", "Ohne"); // "Versmass" | "Ohne"

  return { origin, strength, color, tags, meter };
}

// ---------------------- PDF-Namenslogik ----------------------
function buildPdfFileName(base, opts) {
  // base = Werk-Name (Dateistamm), z.B. "Der_gefesselte_Prometheus"
  const colourPart = (opts.color === "Colour") ? "Colour" : "BlackWhite";
  const tagPart    = (opts.tags  === "Tag")    ? "Tag"    : "NoTags";
  const meterPart  = (opts.meter === "Versmass") ? "_Versmaß" : "";

  return `${base}_${opts.strength}_${colourPart}_${tagPart}${meterPart}.pdf`;
}

// ---------------------- Loader: Texte ----------------------
async function loadTexts(cfg) {
  if (textExistsElem("orig-text")) {
    setText("orig-text", "Lade Original…");
    const t = await fetchTextOrNull(cfg.paths.txtOrig);
    setText("orig-text", t ?? "Noch kein Original vorhanden.");
  }

  if (textExistsElem("birk-text")) {
    setText("birk-text", "Lade Birkenbihl…");
    const t = await fetchTextOrNull(cfg.paths.txtBirk);
    setText("birk-text", t ?? "Noch keine Birkenbihl-Datei vorhanden.");
  }
}

// ---------------------- Loader: PDF-Viewer ----------------------
async function updatePdfFrame(cfg) {
  const frame = qs("#pdf-frame");
  if (!frame) return;

  const { origin, strength, color, tags, meter } = currentUiOptions();

  const base = cfg.work; // Dateistamm = Work
  const pdfName = buildPdfFileName(base, { strength, color, tags, meter });
  const dir = (origin === "Entwurf") ? cfg.paths.pdfDraftDir : cfg.paths.pdfOriginalDir;
  const url = dir + pdfName;

  // Versuche die URL; wenn nicht vorhanden -> freundliche Meldung
  const ok = await urlExists(url);
  if (ok) {
    frame.src = url;
    qs("#pdf-status") && (qs("#pdf-status").textContent = "");
  } else {
    frame.removeAttribute("src");
    qs("#pdf-status") && (qs("#pdf-status").textContent = "PDF (noch) nicht vorhanden.");
  }
}

// ---------------------- Event-Wiring ----------------------
function wireControls(cfg) {
  // Für Radiogruppen: on change → PDF neu setzen
  ["mode-origin", "opt-strength", "opt-color", "opt-tags", "opt-meter"].forEach(group => {
    qsa(`input[type="radio"][name="${group}"]`).forEach(el => {
      el.addEventListener("change", () => updatePdfFrame(cfg));
    });
  });

  // Für data-role Buttons
  qsa(`[data-role="option"]`).forEach(btn => {
    btn.addEventListener("click", () => {
      const pressed = btn.getAttribute("aria-pressed") === "true";
      const group = btn.dataset.group;
      // in der Gruppe erst alle auf false, dann diesen auf true
      qsa(`[data-role="option"][data-group="${group}"]`).forEach(b => b.setAttribute("aria-pressed", "false"));
      btn.setAttribute("aria-pressed", pressed ? "false" : "true");
      updatePdfFrame(cfg);
    });
  });
}

// ---------------------- Bootstrap ----------------------
document.addEventListener("DOMContentLoaded", async () => {
  const cfg = readWorkConfig();

  // Wenn Work/Author fehlen, nicht abstürzen – zeige Hinweis
  if (!cfg.author || !cfg.work) {
    setText("orig-text", "Fehlende Parameter: author/work.");
    setText("birk-text", "Fehlende Parameter: author/work.");
    qs("#pdf-status") && (qs("#pdf-status").textContent = "Fehlende Parameter: author/work.");
    return;
  }

  await loadTexts(cfg);
  await updatePdfFrame(cfg);
  wireControls(cfg);

  // Expose für Debug/andere Skripte
  window.WORK_CTX = cfg;
});
