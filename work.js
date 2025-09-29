// work.js — universelle Werkseite

import { loadCatalog, getWorkMeta } from "./catalog.js";

// 1) KONFIG
const WORKER_BASE = "https://birkenbihl-draft-01.klemp-tobias.workers.dev"; // Externer Worker
const TXT_BASE = "texte"; // texte/<kind>/<author>/<work>/
const PDF_BASE = "pdf"; // pdf/<kind>/<Sprache>/<author>/<work>/
const DRAFT_BASE = "pdf_drafts"; // pdf_drafts/<kind>_drafts/<author>/<work>/

// Tag-Definitionen (aus den Python-Codes)
const SUP_TAGS = [
  "N",
  "D",
  "G",
  "A",
  "V",
  "Du",
  "Adj",
  "Pt",
  "Prp",
  "Adv",
  "Kon",
  "Art",
  "≈",
  "Kmp",
  "Sup",
  "ij",
];
const SUB_TAGS = [
  "Prä",
  "Imp",
  "Aor",
  "Per",
  "Plq",
  "Fu",
  "Inf",
  "Imv",
  "Akt",
  "Med",
  "Pas",
  "Knj",
  "Op",
  "Pr",
  "AorS",
  "M/P",
];
// COLOR_POS_WHITELIST entfernt - Farben werden jetzt direkt in tag_colors definiert

// 2) URL-Parameter
function getParam(name, dflt = "") {
  const u = new URL(location.href);
  const value = u.searchParams.get(name);
  // Decode URL-encoded values and trim whitespace
  return value ? decodeURIComponent(value).trim() : dflt;
}

// 3) Mini-Kataloghelfer (nur für Meter-Schalter; rest über Dateikonvention)
async function fetchCatalog() {
  const res = await fetch("catalog.json", { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}
function findMeta(cat, kind, author, work) {
  try {
    const k = kind.toLowerCase();
    const a = author;
    const w = work;
    const bucket = cat?.[k] || {};
    const au = bucket?.[a] || {};
    return au?.works?.find((x) => x.id === w) || null;
  } catch {
    return null;
  }
}

// 4) DOM refs
const el = {
  pageTitle: document.getElementById("pageTitle"),
  origText: document.getElementById("origText"),
  birkenbihlText: document.getElementById("birkenbihlText"),
  draftText: document.getElementById("draftText"),
  meterRow: document.getElementById("opt-meter-row"),
  pdfRenderer: document.getElementById("pdfRenderer"),
  draftFile: document.getElementById("draftFile"),
  draftFileLabel: document.getElementById("draftFileLabel"),
  draftBtn: document.getElementById("btnRenderDraft"),
  draftStatus: document.getElementById("draftStatus"),

  // Modal-Elemente
  modal: document.getElementById("renderingModal"),
  // modalTbody ist veraltet, da wir jetzt mehrere haben
  closeModalBtn: document.getElementById("closeModal"),
  cancelBtn: document.getElementById("cancelRendering"),
  confirmBtn: document.getElementById("confirmRendering"),
  toggleColorsBtn: document.getElementById("toggleAllColors"),
  toggleHiddenBtn: document.getElementById("toggleAllTagsHidden"),

  // Neue Elemente
  toggleBirkenbihlTagsBtn: document.getElementById("toggleBirkenbihlTags"),
  toggleBirkenbihlMetrumBtn: document.getElementById("toggleBirkenbihlMetrum"),
  toggleDraftTagsBtn: document.getElementById("toggleDraftTags"),
  toggleDraftMetrumBtn: document.getElementById("toggleDraftMetrum"),
  resetDraftBtn: document.getElementById("resetDraft"),
  resetDraftModal: document.getElementById("resetDraftModal"),
  closeResetModalBtn: document.getElementById("closeResetModal"),
  cancelResetBtn: document.getElementById("cancelReset"),
  confirmResetBtn: document.getElementById("confirmReset"),
  grammarTagsBtn: document.getElementById("btnGrammarTags"), // Annahme: ID für den Button
};

// 5) State
const state = {
  lang: getParam("lang", "griechisch"),
  kind: getParam("kind", "poesie"), // poesie | prosa
  author: getParam("author", "Unsortiert"),
  work: getParam("work", "Unbenannt"),

  workMeta: null, // Wird nach dem Laden des Katalogs gefüllt

  // UI-Optionen
  source: "original", // original | draft
  strength: "Normal", // Normal | GR_Fett | DE_Fett
  color: "Colour", // Colour | BlackWhite
  tags: "Tag", // Tag | NoTags
  meter: "without", // with | without  (nur wenn unterstützt)

  meterSupported: false,
  lastDraftUrl: null, // vom Worker zurückbekommen
  originalBirkenbihlText: "", // Zum Zurücksetzen des Entwurfs

  // Modal-Konfiguration
  tagConfig: {
    supTags: new Set(SUP_TAGS),
    subTags: new Set(SUB_TAGS),
    placementOverrides: {}, // Tag -> "sup" | "sub" | "off"
    tagColors: {}, // Tag -> "red" | "orange" | "blue" | "green" | "magenta"
    hiddenTags: new Set(), // Tags die nicht angezeigt werden sollen
  },
};

// Debug: URL-Parameter ausgeben
console.log("URL-Parameter:", {
  lang: state.lang,
  kind: state.kind,
  author: state.author,
  work: state.work,
  fullUrl: location.href,
});

// Neue, strukturierte Definition für die Konfigurationstabelle
const tagConfigDefinition = [
  {
    leader: { id: "nomen", display: "Nomen", tag: "Nomen" },
    members: [
      { id: "nomen_N", display: "Nominativ (N)", tag: "N" },
      { id: "nomen_G", display: "Genitiv (G)", tag: "G" },
      { id: "nomen_D", display: "Dativ (D)", tag: "D" },
      { id: "nomen_A", display: "Akkusativ (A)", tag: "A" },
      { id: "nomen_V", display: "Vokativ (V)", tag: "V" },
      { id: "nomen_Du", display: "Dual (Du)", tag: "Du" },
    ],
  },
  {
    leader: { id: "verb", display: "Verben", tag: "Verben" },
    members: [
      { id: "verb_Pra", display: "Präsenz(Prä)", tag: "Prä" },
      { id: "verb_Imp", display: "Imperfekt (Imp)", tag: "Imp" },
      { id: "verb_Aor", display: "Aorist (Aor)", tag: "Aor" },
      { id: "verb_AorS", display: "Aorist Stark (AorS)", tag: "AorS" },
      { id: "verb_Per", display: "Perfekt (Per)", tag: "Per" },
      { id: "verb_Plq", display: "Plusquamperfekt (Plq)", tag: "Plq" },
      { id: "verb_Fu", display: "Futur (Fu)", tag: "Fu" },
      { id: "verb_Du", display: "Dual (Du)", tag: "Du" },
      { id: "verb_Akt", display: "Aktiv (Akt)", tag: "Akt" },
      { id: "verb_Med", display: "Medium (Med)", tag: "Med" },
      { id: "verb_Pas", display: "Passiv (Pas)", tag: "Pas" },
      { id: "verb_MP", display: "Medium/Passiv (M/P)", tag: "M/P" },
      { id: "verb_Inf", display: "Infinitiv (Inf)", tag: "Inf" },
      { id: "verb_Op", display: "Optativ (Op)", tag: "Op" },
      { id: "verb_Knj", display: "Konjunktiv (Knj)", tag: "Knj" },
      { id: "verb_Imv", display: "Imperativ (Imv)", tag: "Imv" },
    ],
  },
  {
    leader: { id: "partizip", display: "Partizipien", tag: "Partizipien" },
    members: [
      { id: "partizip_Pra", display: "Präsenz(Prä)", tag: "Prä" },
      { id: "partizip_Imp", display: "Imperfekt (Imp)", tag: "Imp" },
      { id: "partizip_Aor", display: "Aorist (Aor)", tag: "Aor" },
      { id: "partizip_AorS", display: "Aorist Stark (AorS)", tag: "AorS" },
      { id: "partizip_Per", display: "Perfekt (Per)", tag: "Per" },
      { id: "partizip_Plq", display: "Plusquamperfekt (Plq)", tag: "Plq" },
      { id: "partizip_Fu", display: "Futur (Fu)", tag: "Fu" },
      { id: "partizip_N", display: "Nominativ (N)", tag: "N" },
      { id: "partizip_G", display: "Genitiv (G)", tag: "G" },
      { id: "partizip_D", display: "Dativ (D)", tag: "D" },
      { id: "partizip_A", display: "Akkusativ (A)", tag: "A" },
      { id: "partizip_V", display: "Vokativ (V)", tag: "V" },
      { id: "partizip_Du", display: "Dual (Du)", tag: "Du" },
      { id: "partizip_Akt", display: "Aktiv (Akt)", tag: "Akt" },
      { id: "partizip_Med", display: "Medium (Med)", tag: "Med" },
      { id: "partizip_Pas", display: "Passiv (Pas)", tag: "Pas" },
      { id: "partizip_MP", display: "Medium/Passiv (M/P)", tag: "M/P" },
    ],
  },
  {
    leader: { id: "adjektiv", display: "Adjektiv (Adj)", tag: "Adj" },
    members: [
      { id: "adjektiv_N", display: "Nominativ (N)", tag: "N" },
      { id: "adjektiv_G", display: "Genitiv (G)", tag: "G" },
      { id: "adjektiv_D", display: "Dativ (D)", tag: "D" },
      { id: "adjektiv_A", display: "Akkusativ (A)", tag: "A" },
      { id: "adjektiv_V", display: "Vokativ (V)", tag: "V" },
      { id: "adjektiv_Du", display: "Dual (Du)", tag: "Du" },
      { id: "adjektiv_Kmp", display: "Komparativ (Kmp)", tag: "Kmp" },
      { id: "adjektiv_Sup", display: "Superlativ (Sup)", tag: "Sup" },
    ],
  },
  {
    leader: { id: "adverb", display: "Adverb (Adv)", tag: "Adv" },
    members: [
      { id: "adverb_Kmp", display: "Komparativ (Kmp)", tag: "Kmp" },
      { id: "adverb_Sup", display: "Superlativ (Sup)", tag: "Sup" },
    ],
  },
  {
    leader: { id: "pronomen", display: "Pronomen (Pr)", tag: "Pr" },
    members: [
      { id: "pronomen_N", display: "Nominativ (N)", tag: "N" },
      { id: "pronomen_G", display: "Genitiv (G)", tag: "G" },
      { id: "pronomen_D", display: "Dativ (D)", tag: "D" },
      { id: "pronomen_A", display: "Akkusativ (A)", tag: "A" },
      { id: "pronomen_Du", display: "Dual (Du)", tag: "Du" },
    ],
  },
  {
    leader: { id: "artikel", display: "Artikel (Art)", tag: "Art" },
    members: [
      { id: "artikel_N", display: "Nominativ (N)", tag: "N" },
      { id: "artikel_G", display: "Genitiv (G)", tag: "G" },
      { id: "artikel_D", display: "Dativ (D)", tag: "D" },
      { id: "artikel_A", display: "Akkusativ (A)", tag: "A" },
      { id: "artikel_Du", display: "Dual (Du)", tag: "Du" },
    ],
  },
  // Einzelne Grammatik-Tags als normale Zeilen (nicht als Gruppenleiter)
  { standalone: { id: "prp", display: "Präposition (Prp)", tag: "Prp" } },
  { standalone: { id: "kon", display: "Konjunktion (Kon)", tag: "Kon" } },
  { standalone: { id: "pt", display: "Partikel (Pt)", tag: "Pt" } },
  { standalone: { id: "ij", display: "Interjektion (ij)", tag: "ij" } },
];

// 6) Hilfen

// PDF-Dateiname gemäß deiner Konvention:
// <Work>_birkenbihl_<Strength>_<Colour|BlackWhite>_<Tag|NoTags>[_Versmaß].pdf
function buildPdfFilename() {
  if (!state.workMeta || !state.workMeta.filename_base) {
    console.error("Work metadata with filename_base not loaded!");
    return "error.pdf";
  }

  let filename = state.workMeta.filename_base;
  console.log("Building filename from base:", filename, "with options:", {
    source: state.source,
    strength: state.strength,
    color: state.color,
    tags: state.tags,
    meter: state.meter,
  });

  // Alle Dateien haben "birkenbihl" im Namen
  filename += "_birkenbihl";
  if (state.strength === "GR_Fett") filename += "_GR_Fett";
  else if (state.strength === "DE_Fett") filename += "_DE_Fett";
  if (state.color === "BlackWhite") filename += "_BlackWhite";
  else if (state.color === "Colour") filename += "_Colour";
  if (state.tags === "NoTags") filename += "_NoTags";
  else if (state.tags === "Tag") filename += "_Tag";
  if (state.meterSupported && state.meter === "with") filename += "_Versmaß";

  console.log("Generated filename:", filename + ".pdf");
  return filename + ".pdf";
}

function basePdfDir() {
  if (!state.workMeta || !state.workMeta.path) {
    console.error("Work metadata with path not loaded!");
    return "pdf/error";
  }

  // Der Pfad aus catalog.json ist der vollständige relative Pfad mit Sprachebene.
  // z.B. griechisch/poesie/Aischylos/Der_gefesselte_Prometheus
  const complete_path = state.workMeta.path;

  console.log("Work Meta Path:", state.workMeta.path);
  console.log("Building PDF directory path:", complete_path);
  console.log("PDF Base:", PDF_BASE, "Draft Base:", DRAFT_BASE);
  console.log("Source:", state.source);

  // Alle Dateien sind Birkenbihl-Versionen, daher verwenden wir den gleichen Pfad
  return `${PDF_BASE}/${complete_path}`;
}
function buildPdfUrlFromSelection() {
  const name = buildPdfFilename();
  return `${basePdfDir()}/${name}`;
}

function updatePdfView(fromWorker = false) {
  // Wenn Entwurf gewählt UND wir haben gerade eine Worker-URL -> die bevorzugen
  if (state.source === "draft" && state.lastDraftUrl && fromWorker) {
    loadPdfIntoRenderer(state.lastDraftUrl);
    return;
  }

  // Sicherstellen, dass pdfOptions mit state synchronisiert sind
  pdfOptions.strength = state.strength || "Normal";
  pdfOptions.color = state.color || "Colour";
  pdfOptions.tags = state.tags || "Tag";
  // Versmaß-Logik: Verwende state.meter (wurde bereits korrekt gesetzt)
  pdfOptions.meter = state.meter;

  console.log("updatePdfView Debug:", {
    stateMeter: state.meter,
    pdfOptionsMeter: pdfOptions.meter,
    meterSupported: state.meterSupported,
  });

  // Neue PDF-URL basierend auf aktuellen Optionen generieren
  const url = buildPdfUrlForRenderer();
  loadPdfIntoRenderer(url);
}

function loadPdfIntoRenderer(pdfUrl) {
  // PDF-Renderer direkt im PDF-Fenster initialisieren
  initPdfRenderer();

  // Sicherstellen, dass pdfOptions mit state synchronisiert sind
  pdfOptions.strength = state.strength || "Normal";
  pdfOptions.color = state.color || "Colour";
  pdfOptions.tags = state.tags || "Tag";
  // Versmaß-Logik: Verwende state.meter (wurde bereits korrekt gesetzt)
  pdfOptions.meter = state.meter;

  loadPdfIntoRendererDirect(pdfUrl);
}

// 7) Texte laden (angepasst an die neue Struktur)
async function loadTexts() {
  if (
    !state.workMeta ||
    !state.workMeta.path ||
    !state.workMeta.filename_base
  ) {
    console.error("Work metadata with path and filename_base not loaded!");
    el.origText.textContent = "Fehler: Werk-Metadaten unvollständig.";
    el.birkenbihlText.textContent = "Fehler: Werk-Metadaten unvollständig.";
    return;
  }

  // Der Pfad aus dem Katalog ist der vollständige relative Pfad mit Sprachebene.
  // z.B. "griechisch/poesie/Aischylos/Der_gefesselte_Prometheus"
  const textBasePath = state.workMeta.path; // Bereits vollständig
  const filenameBase = state.workMeta.filename_base;

  console.log("Loading texts from:", textBasePath, "filename:", filenameBase);

  // Original
  try {
    const r = await fetch(`texte/${textBasePath}/${filenameBase}.txt`, {
      cache: "no-store",
    });
    if (r.ok) {
      el.origText.textContent = await r.text();
      console.log("Original text loaded successfully");
    } else {
      el.origText.textContent = `Original nicht gefunden: texte/${textBasePath}/${filenameBase}.txt`;
      console.error(
        "Original text not found:",
        `texte/${textBasePath}/${filenameBase}.txt`
      );
    }
  } catch (e) {
    el.origText.textContent = "Fehler beim Laden.";
    console.error("Error loading original text:", e);
  }

  // Birkenbihl
  try {
    const r = await fetch(
      `texte/${textBasePath}/${filenameBase}_birkenbihl.txt`,
      {
        cache: "no-store",
      }
    );
    if (r.ok) {
      const text = await r.text();
      state.originalBirkenbihlText = text; // Original speichern
      el.birkenbihlText.innerHTML = addSpansToTags(text);
      console.log("Birkenbihl text loaded successfully");
    } else {
      el.birkenbihlText.textContent = `Birkenbihl-Text nicht gefunden: texte/${textBasePath}/${filenameBase}_birkenbihl.txt`;
      console.error(
        "Birkenbihl text not found:",
        `texte/${textBasePath}/${filenameBase}_birkenbihl.txt`
      );
    }
  } catch (e) {
    el.birkenbihlText.textContent = "Fehler beim Laden.";
    console.error("Error loading birkenbihl text:", e);
  }
}

// 8) Entwurfs-System
async function initializeDraftText() {
  // Lade den Birkenbihl-Text als Basis für den Entwurf
  // (wird jetzt nur noch aus dem State geladen)
  if (state.originalBirkenbihlText) {
    el.draftText.innerHTML = addSpansToTags(state.originalBirkenbihlText);
    el.draftStatus.textContent = "Entwurf bereit. Text bearbeitbar.";
  } else {
    el.draftText.textContent = "Fehler: Birkenbihl-Text nicht verfügbar.";
    el.draftStatus.textContent = "Fehler: Birkenbihl-Text nicht verfügbar.";
  }
}

function addSpansToTags(text) {
  // Regex, um (Tag)-Strukturen zu finden
  const tagRegex = /(\([A-Za-z0-9/≈äöüßÄÖÜ]+\))/g;
  return text.replace(tagRegex, '<span class="grammatik-tag">$1</span>');
}

async function saveDraftText() {
  const draftText = el.draftText.textContent;
  const draftPath = `texte_drafts/${state.kind}_drafts/${state.author}/${state.work}`;

  try {
    // Hier würde normalerweise der Text an den Server gesendet werden
    // Für jetzt simulieren wir das Speichern
    el.draftStatus.textContent = "Entwurf gespeichert.";
    console.log("Entwurf würde gespeichert werden:", draftPath, draftText);
  } catch (e) {
    el.draftStatus.textContent = "Fehler beim Speichern.";
    console.error(e);
  }
}

// 9) Modal-System für Tag-Konfiguration
// Die alte Sektion wurde entfernt, da sie durch die neue Logik ersetzt wurde.

// 10) Worker-Aufruf (Entwurf rendern)
// Die alte Sektion wurde entfernt, da sie durch die neue Logik ersetzt wurde.

// Hilfsfunktion für aktuelle PDF-URL
function getCurrentPdfUrl() {
  return buildPdfUrlForRenderer();
}

async function performRendering() {
  // Der Text aus dem Editor ist immer die Quelle der Wahrheit.
  const draftText = el.draftText.textContent;
  if (!draftText || draftText.trim() === "") {
    el.draftStatus.textContent =
      "Bitte zuerst Text eingeben oder Datei hochladen.";
    return;
  }

  // Erstelle eine Blob-Datei aus dem Editor-Inhalt
  const blob = new Blob([draftText], { type: "text/plain" });
  const file = new File([blob], `${state.work}_birkenbihl_draft.txt`, {
    type: "text/plain",
  });

  el.draftStatus.textContent = "Rendere Entwurf...";

  // Erweiterte Optionen mit Tag-Konfiguration
  const payload = {
    kind: state.kind, // poesie | prosa
    author: state.author, // Ordnername
    work: state.work, // Werk-ID (nur informativ)
    strength: state.strength, // Normal | GR_Fett | DE_Fett
    color_mode: state.color, // Colour | BlackWhite
    tag_mode: state.tags === "Tag" ? "TAGS" : "NO_TAGS",
    versmass: state.meterSupported && state.meter === "with" ? "ON" : "OFF",

    // Die gesamte, neue Tag-Konfiguration wird gesendet
    tag_config: state.tagConfig,
  };

  const form = new FormData();
  form.append("file", file, file.name);
  form.append("work", state.work.trim());
  form.append("filename", file.name);
  form.append("kind", state.kind.trim());
  form.append("author", state.author.trim());

  // Tag-Konfiguration als JSON hinzufügen
  form.append("tag_config", JSON.stringify(payload.tag_config));

  try {
    // Nur eine Anfrage an /draft - das ist der korrekte Endpoint
    const res = await fetch(`${WORKER_BASE}/draft`, {
      method: "POST",
      body: form,
      mode: "cors",
    });

    if (!res || !res.ok) {
      throw new Error(`Worker request failed with status ${res.status}`);
    }

    const data = await res.json();
    if (!data?.ok) throw new Error("Worker-Antwort unvollständig.");

    // Der Worker speichert den Text in texte_drafts/
    el.draftStatus.textContent = `Text gespeichert: ${data.filename}`;

    // Zeige Status basierend auf Worker-Antwort
    setTimeout(() => {
      if (data.workflow_triggered) {
        el.draftStatus.innerHTML = `
          <div style="color: #059669; font-weight: bold;">
            ✓ Text gespeichert: ${data.filename}
          </div>
          <div style="color: #059669; margin-top: 8px;">
            🚀 PDF-Generierung automatisch gestartet!
            <br><small style="color: #6b7280;">PDFs werden in wenigen Minuten verfügbar sein.</small>
          </div>
          <div style="color: #6b7280; margin-top: 8px; font-size: 12px;">
            <a href="https://github.com/klemptobias-oss/birkenbihl-translinear_public/actions" target="_blank">
              GitHub Actions anzeigen →
            </a>
          </div>
        `;
      } else {
        el.draftStatus.innerHTML = `
          <div style="color: #059669; font-weight: bold;">
            ✓ Text gespeichert: ${data.filename}
          </div>
          <div style="color: #dc2626; margin-top: 8px;">
            ⚠ PDF-Generierung: Führen Sie manuell aus:<br>
            <code style="background: #f3f4f6; padding: 2px 4px; border-radius: 3px;">
              python build_${state.kind}_drafts_adapter.py texte_drafts/${state.kind}_drafts/${state.author}/${state.work}/${data.filename}
            </code>
            <br><small style="color: #6b7280;">PDFs werden in pdf_drafts/${state.kind}_drafts/${state.author}/${state.work}/ erstellt</small>
          </div>
        `;
      }
    }, 1000);

    // Für PDF-Anzeige verwenden wir ein Fallback (falls PDFs bereits existieren)
    state.lastDraftUrl = getCurrentPdfUrl();
    state.source = "draft";
    updatePdfView(true);
  } catch (e) {
    console.error(e);
    if (
      e.message &&
      (e.message.includes("CORS") ||
        e.message.includes("Cross-Origin") ||
        e.message.includes("NetworkError"))
    ) {
      el.draftStatus.textContent =
        "CORS-Fehler: Worker nicht erreichbar. Bitte versuchen Sie es auf der GitHub-Seite (https://klemptobias-oss.github.io/birkenbihl-translinear_public/).";
    } else {
      el.draftStatus.textContent = "Fehler beim Fallback-Rendering.";
    }
  }
}

/**
 * PDF-Konfigurations-Modal
 */
function createTableRow(item, isGroupLeader = false) {
  const tr = document.createElement("tr");
  tr.dataset.id = item.id;
  if (isGroupLeader) {
    tr.classList.add("group-leader");
  }

  // Modifikations-Spalte (Name)
  tr.innerHTML = `<td>${item.display}</td>`;

  // Checkbox-Spalten
  const actions = [
    { type: "placement", value: "sup", label: "hochgestellt" },
    { type: "placement", value: "sub", label: "tiefgestellt" },
    { type: "color", value: "red", label: "rot" },
    { type: "color", value: "orange", label: "orange" },
    { type: "color", value: "blue", label: "blau" },
    { type: "color", value: "green", label: "grün" },
    { type: "color", value: "magenta", label: "magenta" },
    { type: "hide", value: "hide", label: "Tag nicht zeigen" },
  ];

  actions.forEach((action) => {
    const td = document.createElement("td");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.dataset.type = action.type;
    input.dataset.value = action.value;
    input.title = action.label;
    td.appendChild(input);
    tr.appendChild(td);
  });
  return tr;
}

function showTagConfigModal() {
  // 1. Container für kleine Tabellen leeren
  const tablesContainer = document.getElementById("tag-config-tables");
  if (!tablesContainer) return;

  // Container leeren
  tablesContainer.innerHTML = "";

  // 2. Für jede Gruppe eine eigene Tabelle erstellen
  const standaloneItems = []; // Sammle standalone Items für eine gemeinsame Tabelle

  tagConfigDefinition.forEach((group) => {
    if (group.leader) {
      // Neue Tabelle für diese Gruppe erstellen
      const table = document.createElement("table");
      table.className = "tag-group-table";

      // Header für die Tabelle
      const thead = document.createElement("thead");
      thead.innerHTML = `
        <tr>
          <th>Modifikation</th>
          <th>hochgestellt</th>
          <th>tiefgestellt</th>
          <th>rot</th>
          <th>orange</th>
          <th>blau</th>
          <th>grün</th>
          <th>magenta</th>
          <th>Tag nicht<br />zeigen</th>
        </tr>
      `;
      table.appendChild(thead);

      // Tbody für die Tabelle
      const tbody = document.createElement("tbody");

      // Gruppenleiter-Zeile nur anzeigen, wenn er einen konfigurierbaren Tag hat
      if (group.leader.tag) {
        const leaderRow = createTableRow(group.leader, true);
        leaderRow.classList.add("group-leader");
        leaderRow.dataset.group = group.leader.id;
        leaderRow.dataset.id = group.leader.id; // Wichtig: auch data-id setzen
        tbody.appendChild(leaderRow);
      }

      // Mitglieder-Zeilen
      if (group.members) {
        group.members.forEach((member) => {
          const memberRow = createTableRow(member);
          memberRow.dataset.group = group.leader.id;
          tbody.appendChild(memberRow);
        });
      }

      table.appendChild(tbody);
      tablesContainer.appendChild(table);
    } else if (group.standalone) {
      // Sammle standalone Items für eine gemeinsame Tabelle
      standaloneItems.push(group.standalone);
    }
  });

  // 3. Erstelle eine gemeinsame Tabelle für alle standalone Items
  if (standaloneItems.length > 0) {
    const table = document.createElement("table");
    table.className = "tag-group-table";

    // Header für die Tabelle
    const thead = document.createElement("thead");
    thead.innerHTML = `
      <tr>
        <th>Modifikation</th>
        <th>hochgestellt</th>
        <th>tiefgestellt</th>
        <th>rot</th>
        <th>orange</th>
        <th>blau</th>
        <th>grün</th>
        <th>magenta</th>
        <th>Tag nicht<br />zeigen</th>
      </tr>
    `;
    table.appendChild(thead);

    // Tbody für die Tabelle
    const tbody = document.createElement("tbody");

    // Alle standalone Items als gleichgestellte Zeilen hinzufügen
    standaloneItems.forEach((item) => {
      const row = createTableRow(item);
      tbody.appendChild(row);
    });

    table.appendChild(tbody);
    tablesContainer.appendChild(table);
  }

  // 4. Initialkonfiguration anwenden
  applyInitialConfig();
  updateTableFromState();

  // 5. Event Listeners hinzufügen
  tablesContainer.removeEventListener("change", handleTableChange); // Alte Listener entfernen
  tablesContainer.addEventListener("change", handleTableChange);
  el.toggleColorsBtn.removeEventListener("click", toggleOriginalColors);
  el.toggleColorsBtn.addEventListener("click", toggleOriginalColors);
  el.toggleHiddenBtn.removeEventListener("click", toggleAllTagsHidden);
  el.toggleHiddenBtn.addEventListener("click", toggleAllTagsHidden);

  // 6. Modal anzeigen
  el.modal.style.display = "flex";
}

function applyInitialConfig() {
  // Setzt die Standardkonfiguration (Farben und Platzierung)
  state.tagConfig = {}; // Reset

  // Standardfarben IMMER anwenden (nicht nur wenn Toggle aktiv ist)
  // Nomen -> rot
  const nomenGroup = tagConfigDefinition.find((g) => g.leader?.id === "nomen");
  if (nomenGroup?.leader?.tag) {
    state.tagConfig[nomenGroup.leader.id] = {
      ...state.tagConfig[nomenGroup.leader.id],
      color: "red",
    };
  }
  nomenGroup?.members.forEach((m) => {
    state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "red" };
  });

  // Verben -> grün
  const verbGroup = tagConfigDefinition.find((g) => g.leader?.id === "verb");
  if (verbGroup?.leader?.tag) {
    state.tagConfig[verbGroup.leader.id] = {
      ...state.tagConfig[verbGroup.leader.id],
      color: "green",
    };
  }
  verbGroup?.members.forEach((m) => {
    state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "green" };
  });

  // Partizipien -> blau
  const partizipGroup = tagConfigDefinition.find(
    (g) => g.leader?.id === "partizip"
  );
  if (partizipGroup?.leader?.tag) {
    state.tagConfig[partizipGroup.leader.id] = {
      ...state.tagConfig[partizipGroup.leader.id],
      color: "blue",
    };
  }
  partizipGroup?.members.forEach((m) => {
    state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "blue" };
  });

  // Adjektive -> blau
  const adjektivGroup = tagConfigDefinition.find(
    (g) => g.leader?.id === "adjektiv"
  );
  if (adjektivGroup?.leader?.tag) {
    state.tagConfig[adjektivGroup.leader.id] = {
      ...state.tagConfig[adjektivGroup.leader.id],
      color: "blue",
    };
  }
  adjektivGroup?.members.forEach((m) => {
    state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "blue" };
  });

  // Standardplatzierungen anwenden
  const allItems = tagConfigDefinition.flatMap((g) => {
    const items = [];
    // Füge den Leader hinzu, wenn er einen Tag hat
    if (g.leader && g.leader.tag) {
      items.push(g.leader);
    }
    // Füge die Members hinzu
    if (g.members) {
      items.push(...g.members);
    }
    // Füge Standalone-Items hinzu
    if (g.standalone) {
      items.push(g.standalone);
    }
    return items;
  });
  allItems.forEach((item) => {
    if (item && item.tag) {
      if (SUP_TAGS.includes(item.tag)) {
        state.tagConfig[item.id] = {
          ...state.tagConfig[item.id],
          placement: "sup",
        };
      }
      if (SUB_TAGS.includes(item.tag)) {
        state.tagConfig[item.id] = {
          ...state.tagConfig[item.id],
          placement: "sub",
        };
      }
    }
  });
}

function updateTableFromState() {
  const tablesContainer = document.getElementById("tag-config-tables");
  if (!tablesContainer) return;

  const tables = tablesContainer.querySelectorAll(".tag-group-table");
  tables.forEach((table) => {
    const rows = table.querySelectorAll("tr[data-id]");
    rows.forEach((tr) => {
      const id = tr.dataset.id;
      const config = state.tagConfig[id] || {};
      const checkboxes = tr.querySelectorAll("input[type=checkbox]");

      let rowColor = config.color || "";

      checkboxes.forEach((cb) => {
        const { type, value } = cb.dataset;
        cb.checked = false; // Reset

        if (type === "placement" && config.placement === value)
          cb.checked = true;
        if (type === "color" && config.color === value) cb.checked = true;
        if (type === "hide" && config.hide) cb.checked = true;
      });

      tr.className = tr.classList.contains("group-leader")
        ? "group-leader"
        : "";
      // Entferne alle color-bg Klassen, da wir jetzt inline-Styles verwenden
      tr.classList.remove(
        "color-bg-red",
        "color-bg-green",
        "color-bg-blue",
        "color-bg-orange",
        "color-bg-magenta"
      );
    });
  });

  // Hintergrundfarben der Zellen aktualisieren
  updateCellBackgroundColors();
}

function handleTableChange(event) {
  const checkbox = event.target;
  if (checkbox.type !== "checkbox") return;

  const tr = checkbox.closest("tr");
  const table = tr.closest("table"); // Benötigt für Gruppen-Selektor
  const id = tr.dataset.id;
  const { type, value } = checkbox.dataset;

  // Funktion zum Aktualisieren eines einzelnen Eintrags
  const updateConfig = (targetId, updateType, updateValue, isChecked) => {
    state.tagConfig[targetId] = state.tagConfig[targetId] || {};
    const currentConfig = state.tagConfig[targetId];

    if (isChecked) {
      currentConfig[updateType] = updateValue;
    } else {
      delete currentConfig[updateType];
    }
  };

  // Exklusivität für placement und hide sicherstellen
  if (checkbox.checked) {
    if (type === "placement") {
      updateConfig(id, "hide", false, false); // hide entfernen
    } else if (type === "hide") {
      updateConfig(id, "placement", null, false); // placement entfernen
    }
  }

  // Wenn ein Gruppenanführer geändert wird, wende es auf alle Mitglieder an
  if (tr.classList.contains("group-leader")) {
    const groupId = tr.dataset.group;
    const memberRows = table.querySelectorAll(`tr[data-group="${groupId}"]`);
    memberRows.forEach((memberTr) => {
      if (memberTr === tr || memberTr.classList.contains("group-separator"))
        return;

      // Exklusivität auch für Gruppenmitglieder anwenden
      if (checkbox.checked) {
        if (type === "placement")
          updateConfig(memberTr.dataset.id, "hide", false, false);
        if (type === "hide")
          updateConfig(memberTr.dataset.id, "placement", null, false);
      }

      updateConfig(memberTr.dataset.id, type, value, checkbox.checked);
    });
  }

  // Aktualisiere den State für das geklickte Element
  updateConfig(id, type, value, checkbox.checked);

  // Exklusivität sicherstellen (innerhalb der Zeile für den geklickten Typ)
  if (checkbox.checked) {
    const groupSelector = `input[data-type="${type}"]`;
    tr.querySelectorAll(groupSelector).forEach((cb) => {
      if (cb !== checkbox) cb.checked = false;
    });
  }

  // UI komplett aktualisieren, um alle Änderungen (auch Gruppen) widerzuspiegeln
  updateTableFromState();

  // Hintergrundfarben der Zellen aktualisieren
  updateCellBackgroundColors();
}

function updateCellBackgroundColors() {
  const tablesContainer = document.getElementById("tag-config-tables");
  if (!tablesContainer) return;

  const tables = tablesContainer.querySelectorAll(".tag-group-table");
  tables.forEach((table) => {
    // Alle Zeilen zurücksetzen
    const allRows = table.querySelectorAll("tr");
    allRows.forEach((row) => {
      const cells = row.querySelectorAll("td");
      cells.forEach((cell) => {
        cell.style.backgroundColor = "#ffffff";
      });
    });

    // Nur Zeilen mit data-id durchgehen und basierend auf state.tagConfig färben
    const dataRows = table.querySelectorAll("tr[data-id]");
    dataRows.forEach((row) => {
      const cells = row.querySelectorAll("td");
      const id = row.dataset.id;
      const config = state.tagConfig[id] || {};
      const isGroupLeader = row.classList.contains("group-leader");

      // Priorität: color > placement (hide beeinflusst die Farbe NICHT)
      let backgroundColor = "#ffffff";

      // Prüfe auf Farben (höchste Priorität)
      if (config.color) {
        const colorMap = {
          red: "#ef4444", // Kräftigeres Rot
          orange: "#f97316", // Kräftigeres Orange
          blue: "#3b82f6", // Kräftigeres Blau
          green: "#22c55e", // Kräftigeres Grün
          magenta: "#c084fc", // Kräftigeres Magenta
        };
        backgroundColor = colorMap[config.color] || "#ffffff";
      } else if (config.placement) {
        // Prüfe auf placement (hochgestellt/tiefgestellt)
        backgroundColor = "#e5e7eb"; // Grau
      } else if (isGroupLeader) {
        // Gruppenanführer ohne Farbe und ohne Platzierung werden grau
        backgroundColor = "#e5e7eb"; // Grau
      }

      // "Tag nicht zeigen" beeinflusst die Hintergrundfarbe NICHT
      // Es wird nur für die PDF-Generierung verwendet

      // Ganze Zeile mit der ermittelten Farbe färben
      cells.forEach((cell) => {
        cell.style.backgroundColor = backgroundColor;
      });
    });
  });
}

function toggleButton(btn, forceState) {
  let currentState =
    forceState !== undefined
      ? forceState
      : btn.dataset.state === "on"
      ? "off"
      : "on";
  btn.dataset.state = currentState;
  const status = btn.querySelector(".toggle-status");
  if (currentState === "on") {
    status.textContent = "An";
    status.classList.remove("red");
    status.classList.add("green");
  } else {
    status.textContent = "Aus";
    status.classList.remove("green");
    status.classList.add("red");
  }
  return currentState === "on";
}

function toggleMetrumMarkers(textElement, buttonElement) {
  const isCurrentlyOn = buttonElement.dataset.state === "on";
  const newState = isCurrentlyOn ? "off" : "on";

  // Button-Status aktualisieren
  toggleButton(buttonElement, newState);

  // Speichere den aktuellen Zustand der Metrum-Marker
  textElement.dataset.metrumHidden = newState === "off" ? "true" : "false";

  // Text basierend auf beiden Toggle-Zuständen neu rendern
  updateTextDisplay(textElement);
}

function updateTextDisplay(textElement) {
  // Hole den Originaltext
  let originalText;
  if (textElement.id === "birkenbihlText") {
    originalText = state.originalBirkenbihlText
      ? addSpansToTags(state.originalBirkenbihlText)
      : textElement.innerHTML;
  } else if (textElement.id === "draftText") {
    originalText = state.originalBirkenbihlText
      ? addSpansToTags(state.originalBirkenbihlText)
      : textElement.innerHTML;
  } else {
    originalText = textElement.innerHTML;
  }

  let processedText = originalText;

  // Prüfe Metrum-Marker Status
  const metrumHidden = textElement.dataset.metrumHidden === "true";
  if (metrumHidden) {
    // EINFACHERE LÖSUNG: Zeilenweise verarbeiten
    const lines = processedText.split("\n");
    const processedLines = lines.map((line) => {
      // Entferne Sprecher-Bezeichnungen aus der Analyse: [ΚΡΑΤ:] etc.
      const lineWithoutSpeakers = line.replace(/\[.*?\]/g, "");

      // Prüfe, ob die Zeile (ohne Sprecher) griechische Buchstaben enthält
      const hasGreekLetters =
        /[αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ]/.test(
          lineWithoutSpeakers
        );

      if (hasGreekLetters) {
        // Griechische Zeile: Entferne Metrum-Marker, aber schütze Grammatik-Tags
        return line.replace(/[iLr|](?![^<]*>)/g, (match, offset, string) => {
          const beforeMatch = string.substring(0, offset);
          const openParens = (beforeMatch.match(/\(/g) || []).length;
          const closeParens = (beforeMatch.match(/\)/g) || []).length;

          // Wenn wir innerhalb von Klammern sind, behalte das Zeichen
          if (openParens > closeParens) {
            return match;
          }

          // Andernfalls entferne es
          return "";
        });
      } else {
        // Deutsche Zeile: Behalte alle Zeichen
        return line;
      }
    });

    processedText = processedLines.join("\n");
  }

  // Prüfe Grammatik-Tags Status
  const tagsHidden = textElement.classList.contains("tags-hidden");
  if (tagsHidden) {
    // Grammatik-Tags ausblenden - erweitertes Pattern für alle Grammatik-Tags
    // Erlaubt lateinische Buchstaben, Umlaute, Schrägstriche, Symbole und andere Sonderzeichen
    // Jetzt auch für mehrstellige Tags wie "Du" (Dual)
    processedText = processedText.replace(/\([A-Za-zäöüÄÖÜß/≈]+\)/g, "");
  }

  textElement.innerHTML = processedText;
}

function toggleOriginalColors() {
  const isOn = toggleButton(el.toggleColorsBtn);

  if (isOn) {
    // Button ist jetzt AN - Nur Standardfarben anwenden (nicht placement)
    const nomenGroup = tagConfigDefinition.find(
      (g) => g.leader?.id === "nomen"
    );
    if (nomenGroup?.leader?.tag) {
      state.tagConfig[nomenGroup.leader.id] = {
        ...state.tagConfig[nomenGroup.leader.id],
        color: "red",
      };
    }
    nomenGroup?.members.forEach((m) => {
      state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "red" };
    });

    const verbGroup = tagConfigDefinition.find((g) => g.leader?.id === "verb");
    if (verbGroup?.leader?.tag) {
      state.tagConfig[verbGroup.leader.id] = {
        ...state.tagConfig[verbGroup.leader.id],
        color: "green",
      };
    }
    verbGroup?.members.forEach((m) => {
      state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "green" };
    });

    const partizipGroup = tagConfigDefinition.find(
      (g) => g.leader?.id === "partizip"
    );
    if (partizipGroup?.leader?.tag) {
      state.tagConfig[partizipGroup.leader.id] = {
        ...state.tagConfig[partizipGroup.leader.id],
        color: "blue",
      };
    }
    partizipGroup?.members.forEach((m) => {
      state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "blue" };
    });

    const adjektivGroup = tagConfigDefinition.find(
      (g) => g.leader?.id === "adjektiv"
    );
    if (adjektivGroup?.leader?.tag) {
      state.tagConfig[adjektivGroup.leader.id] = {
        ...state.tagConfig[adjektivGroup.leader.id],
        color: "blue",
      };
    }
    adjektivGroup?.members.forEach((m) => {
      state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "blue" };
    });
  } else {
    // Button ist jetzt AUS - Alle Farben entfernen
    const tablesContainer = document.getElementById("tag-config-tables");
    if (!tablesContainer) return;

    const tables = tablesContainer.querySelectorAll(".tag-group-table");
    const allIds = [];

    tables.forEach((table) => {
      const tableIds = Array.from(table.querySelectorAll("tr[data-id]")).map(
        (tr) => tr.dataset.id
      );
      allIds.push(...tableIds);
    });

    allIds.forEach((id) => {
      if (state.tagConfig[id]) {
        delete state.tagConfig[id].color;
        // Entferne leere Objekte
        if (Object.keys(state.tagConfig[id]).length === 0) {
          delete state.tagConfig[id];
        }
      }
    });
  }

  updateTableFromState();
}

function toggleAllTagsHidden() {
  const turnOn = toggleButton(el.toggleHiddenBtn);
  const tablesContainer = document.getElementById("tag-config-tables");
  if (!tablesContainer) return;

  const tables = tablesContainer.querySelectorAll(".tag-group-table");
  const allIds = [];

  tables.forEach((table) => {
    const tableIds = Array.from(table.querySelectorAll("tr[data-id]")).map(
      (tr) => tr.dataset.id
    );
    allIds.push(...tableIds);
  });

  allIds.forEach((id) => {
    state.tagConfig[id] = state.tagConfig[id] || {};
    if (turnOn) {
      state.tagConfig[id].hide = true;
    } else {
      delete state.tagConfig[id].hide;
    }
  });
  updateTableFromState();
}

function hideTagConfigModal() {
  if (el.modal) el.modal.style.display = "none";
}

function updateStateFromTable() {
  // Diese Funktion ist jetzt in handleTableChange integriert und sollte nicht mehr separat benötigt werden
  // Der State wird bei jeder Änderung direkt aktualisiert.
}

// 9) Events
function wireEvents() {
  // Alle Segment-Buttons (Quelle, Stärke, Farbe, Tags, Versmaß)
  document.querySelectorAll(".seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const opt = btn.dataset.opt;
      const val = btn.dataset.val;

      // Aktiven Button markieren
      btn.parentElement
        .querySelectorAll(".seg-btn")
        .forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      // State aktualisieren
      if (opt === "source") state.source = val;
      else if (opt === "strength") state.strength = val;
      else if (opt === "color") state.color = val;
      else if (opt === "tags") state.tags = val;
      else if (opt === "meter") state.meter = val;

      // PDF aktualisieren
      updatePdfView(false);
    });
  });

  // "PDF aus Entwurf rendern"-Button öffnet das Modal
  el.draftBtn?.addEventListener("click", showTagConfigModal);

  // Modal-Buttons
  el.closeModalBtn?.addEventListener("click", hideTagConfigModal);
  el.cancelBtn?.addEventListener("click", hideTagConfigModal);
  el.confirmBtn?.addEventListener("click", () => {
    hideTagConfigModal();
    performRendering();
  });

  // Button für Datei-Upload triggert den versteckten File-Input
  el.draftFileLabel?.addEventListener("click", () => {
    el.draftFile?.click();
  });

  // Neue Event Listeners für Datei-Upload, Tag-Toggle und Reset
  el.draftFile?.addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        el.draftText.innerHTML = addSpansToTags(e.target.result);
        el.draftStatus.textContent = `Datei ${file.name} geladen.`;
        // Nach dem Laden leeren, um eine versehentliche Wiederverwendung zu vermeiden
        event.target.value = null;
      };
      reader.readAsText(file);
    }
  });

  el.toggleBirkenbihlTagsBtn?.addEventListener("click", () => {
    el.birkenbihlText.classList.toggle("tags-hidden");
    toggleButton(el.toggleBirkenbihlTagsBtn);
    updateTextDisplay(el.birkenbihlText);
  });

  el.toggleBirkenbihlMetrumBtn?.addEventListener("click", () => {
    toggleMetrumMarkers(el.birkenbihlText, el.toggleBirkenbihlMetrumBtn);
  });

  el.toggleDraftTagsBtn?.addEventListener("click", () => {
    el.draftText.classList.toggle("tags-hidden");
    toggleButton(el.toggleDraftTagsBtn);
    updateTextDisplay(el.draftText);
  });

  el.toggleDraftMetrumBtn?.addEventListener("click", () => {
    toggleMetrumMarkers(el.draftText, el.toggleDraftMetrumBtn);
  });

  el.resetDraftBtn?.addEventListener("click", () => {
    el.resetDraftModal.style.display = "flex";
  });

  el.closeResetModalBtn?.addEventListener("click", () => {
    el.resetDraftModal.style.display = "none";
  });

  el.cancelResetBtn?.addEventListener("click", () => {
    el.resetDraftModal.style.display = "none";
  });

  el.confirmResetBtn?.addEventListener("click", () => {
    initializeDraftText(); // Stellt den originalen, mit Spans versehenen Text wieder her
    el.resetDraftModal.style.display = "none";
  });

  // Entwurfs-Text Auto-Save (optional)
  el.draftText?.addEventListener("input", () => {
    el.draftStatus.textContent = "Entwurf geändert. Bereit zum Rendern.";
  });

  // Schriftgrößen-Buttons
  document
    .getElementById("btnOrigPlus")
    ?.addEventListener("click", () => updateFontSize("origText", 1));
  document
    .getElementById("btnOrigMinus")
    ?.addEventListener("click", () => updateFontSize("origText", -1));
  document
    .getElementById("btnBirPlus")
    ?.addEventListener("click", () => updateFontSize("birkenbihlText", 1));
  document
    .getElementById("btnBirMinus")
    ?.addEventListener("click", () => updateFontSize("birkenbihlText", -1));
  document
    .getElementById("btnDraftTextPlus")
    ?.addEventListener("click", () => updateFontSize("draftText", 1));
  document
    .getElementById("btnDraftTextMinus")
    ?.addEventListener("click", () => updateFontSize("draftText", -1));
}

function updateFontSize(elementId, change) {
  const el = document.getElementById(elementId);
  if (el) {
    let currentSize = parseFloat(
      window.getComputedStyle(el, null).getPropertyValue("font-size")
    );
    // Sehr feine Abstufungen: 0.25px statt 1px (sichtbar, aber fein)
    el.style.fontSize = currentSize + change * 0.4 + "px";
  }
}

// 10) Init
(async function init() {
  console.log("work.js init started");
  // Warten, bis DOM geladen ist
  if (document.readyState === "loading") {
    await new Promise((resolve) => {
      document.addEventListener("DOMContentLoaded", resolve);
    });
  }

  // Zuerst Katalog laden, um Metadaten zu erhalten
  try {
    const cat = await loadCatalog();
    state.workMeta = getWorkMeta(
      cat,
      state.lang,
      state.kind,
      state.author,
      state.work
    );

    if (!state.workMeta) {
      throw new Error("Werk nicht im Katalog gefunden.");
    }

    state.meterSupported = state.workMeta.versmass; // true/false

    // Titel setzen
    el.pageTitle.textContent = `${
      state.workMeta.author_display || state.author
    } – ${state.workMeta.title || state.work}`;

    // UI-Elemente basierend auf Metadaten aktualisieren
    if (el.meterRow) {
      el.meterRow.style.display = state.meterSupported ? "" : "none";
    }

    if (el.grammarTagsBtn) {
      el.grammarTagsBtn.style.display = state.meterSupported ? "" : "none";
    }

    // Metrum-Marker Buttons ein-/ausblenden
    const birkenbihlMetrumBtn = document.getElementById(
      "toggleBirkenbihlMetrum"
    );
    const draftMetrumBtn = document.getElementById("toggleDraftMetrum");

    if (birkenbihlMetrumBtn) {
      if (state.meterSupported) {
        birkenbihlMetrumBtn.style.removeProperty("display");
      } else {
        birkenbihlMetrumBtn.style.setProperty("display", "none", "important");
      }
      console.log(
        "Birkenbihl Metrum Button display gesetzt:",
        birkenbihlMetrumBtn.style.display
      );
    }
    if (draftMetrumBtn) {
      if (state.meterSupported) {
        draftMetrumBtn.style.removeProperty("display");
      } else {
        draftMetrumBtn.style.setProperty("display", "none", "important");
      }
      console.log(
        "Draft Metrum Button display gesetzt:",
        draftMetrumBtn.style.display
      );
    }

    console.log(
      "Metrum-Marker Buttons:",
      state.meterSupported ? "angezeigt" : "ausgeblendet"
    );
    console.log("Birkenbihl Metrum Button gefunden:", !!birkenbihlMetrumBtn);
    console.log("Draft Metrum Button gefunden:", !!draftMetrumBtn);

    // Versmaß-Button-Gruppe im PDF-Renderer ein-/ausblenden
    // Suche nach der Gruppe, die die meter-Buttons enthält
    const meterButtons = document.querySelectorAll(
      '#pdfRendererContainer [data-opt="meter"]'
    );
    const meterGroup =
      meterButtons.length > 0
        ? meterButtons[0].closest(".pdf-options-group")
        : null;

    if (meterGroup) {
      meterGroup.style.display = state.meterSupported ? "" : "none";
      console.log(
        "Versmaß-Button-Gruppe:",
        state.meterSupported ? "angezeigt" : "ausgeblendet"
      );
      console.log("Gefundene meter-Buttons:", meterButtons.length);
      console.log("Meter-Gruppe gefunden:", !!meterGroup);
      console.log("Meter-Gruppe display style:", meterGroup.style.display);
    } else {
      console.log("Versmaß-Button-Gruppe nicht gefunden!");
    }

    // Jetzt PDF-Optionen korrekt setzen und Controls initialisieren
    console.log("=== LOAD WORK META DEBUG ===");
    console.log("state.meterSupported:", state.meterSupported);
    console.log("state.meter:", state.meter);
    console.log("pdfOptions.meter:", pdfOptions.meter);

    // Erst Controls initialisieren (setzt state.meter korrekt)
    initPdfOptionControls();

    // Dann PDF laden mit korrekten Werten
    updatePdfView(false);
  } catch (e) {
    console.error("Fehler beim Laden des Katalogs oder der Werk-Metadaten:", e);
    // Fallback: Versmaß-Optionen ausblenden
    if (el.meterRow) {
      el.meterRow.style.display = "none";
    }
    if (el.grammarTagsBtn) {
      el.grammarTagsBtn.style.display = "none";
    }

    // Metrum-Marker Buttons ausblenden (Fallback)
    const birkenbihlMetrumBtn = document.getElementById(
      "toggleBirkenbihlMetrum"
    );
    const draftMetrumBtn = document.getElementById("toggleDraftMetrum");

    if (birkenbihlMetrumBtn) {
      birkenbihlMetrumBtn.style.display = "none";
    }
    if (draftMetrumBtn) {
      draftMetrumBtn.style.display = "none";
    }

    console.log("Metrum-Marker Buttons: ausgeblendet (Fallback)");

    // Versmaß-Button-Gruppe im PDF-Renderer ausblenden
    const meterButtons = document.querySelectorAll(
      '#pdfRendererContainer [data-opt="meter"]'
    );
    const meterGroup =
      meterButtons.length > 0
        ? meterButtons[0].closest(".pdf-options-group")
        : null;

    if (meterGroup) {
      meterGroup.style.display = "none";
      console.log("Versmaß-Button-Gruppe: ausgeblendet (Fallback)");
    }
  }

  // Titel (wird später nochmal mit korrekten Werten überschrieben)
  el.pageTitle.textContent = `${state.author} – ${state.work}`;

  // Standard-Buttons als aktiv markieren
  document.querySelectorAll(".seg-btn").forEach((btn) => {
    const opt = btn.dataset.opt;
    const val = btn.dataset.val;
    if (
      (opt === "source" && val === state.source) ||
      (opt === "strength" && val === state.strength) ||
      (opt === "color" && val === state.color) ||
      (opt === "tags" && val === state.tags) ||
      (opt === "meter" && val === state.meter)
    ) {
      btn.classList.add("active");
    }
  });

  // Download-Buttons initialisieren
  function updateDownloadButtons() {
    const origDownload = document.getElementById("btnOrigDownload");
    const birkenbihlDownload = document.getElementById("btnBirkenbihlDownload");
    const draftDownload = document.getElementById("btnDraftDownload");
    const pdfDownload = document.getElementById("btnPdfDownload");
    const filenameBase = state.workMeta?.filename_base || state.work;

    if (origDownload) {
      const origUrl = `texte/${state.workMeta.path.replace(
        /_/g,
        " "
      )}/${filenameBase}.txt`;
      origDownload.addEventListener("click", (e) => {
        e.preventDefault();
        const a = document.createElement("a");
        a.href = origUrl;
        a.download = `${filenameBase}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      });
      console.log("Original download URL:", origUrl);
    }

    if (birkenbihlDownload) {
      const birkenbihlUrl = `texte/${state.workMeta.path.replace(
        /_/g,
        " "
      )}/${filenameBase}_birkenbihl.txt`;
      birkenbihlDownload.addEventListener("click", (e) => {
        e.preventDefault();
        const a = document.createElement("a");
        a.href = birkenbihlUrl;
        a.download = `${filenameBase}_birkenbihl.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      });
      console.log("Birkenbihl download URL:", birkenbihlUrl);
    }

    if (draftDownload) {
      // Für den Entwurf-Download erstellen wir eine Blob-URL
      draftDownload.addEventListener("click", (e) => {
        e.preventDefault();
        const draftText = el.draftText.textContent;
        if (!draftText || draftText.trim() === "") {
          alert("Kein Entwurfs-Text vorhanden zum Herunterladen.");
          return;
        }
        const blob = new Blob([draftText], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${state.work}_birkenbihl_entwurf.txt`;
        a.style.display = "none";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      });
    }

    if (pdfDownload) {
      pdfDownload.addEventListener("click", (e) => {
        e.preventDefault();
        const pdfUrl = getCurrentPdfUrl();
        const a = document.createElement("a");
        a.href = pdfUrl;
        a.download = buildPdfFilename();
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      });
    }
  }

  updateDownloadButtons();

  // Titel setzen (wird bereits oben gesetzt, hier überschreiben wir es mit den korrekten Werten)
  el.pageTitle.textContent = `${
    state.workMeta?.author_display || state.author
  } – ${state.workMeta?.title || state.work}`;

  // Inhalte und PDF anzeigen
  await loadTexts();
  wireEvents();

  // PDF-Optionen vor dem ersten Laden synchronisieren
  pdfOptions.strength = state.strength || "Normal";
  pdfOptions.color = state.color || "Colour";
  pdfOptions.tags = state.tags || "Tag";
  // Versmaß-Logik: Wird später in loadWorkMeta() korrekt gesetzt
  // pdfOptions.meter wird erst nach dem Laden der Metadaten gesetzt

  // updatePdfView() wird später in loadWorkMeta() aufgerufen, nachdem meterSupported gesetzt wurde

  // Entwurfs-Text initialisieren
  await initializeDraftText();
})();

// PDF-Renderer direkt im PDF-Fenster
// PDF-Optionen Status
let pdfOptions = {
  source: "original",
  strength: "Normal",
  color: "Colour",
  tags: "Tag",
  meter: "without", // Wird basierend auf meterSupported dynamisch gesetzt
};

// PDF-Renderer Status
let pdfRenderer = {
  pdf: null,
  scale: 1.2,
  fitToWidth: false,
  currentPage: 1,
  rendering: false,
  elements: {},
};

// PDF-URL basierend auf Optionen erstellen
function buildPdfUrlForRenderer() {
  // Verwende pdfOptions für die PDF-URL-Generierung
  if (!state.workMeta || !state.workMeta.filename_base) {
    console.error("Work metadata with filename_base not loaded!");
    return "pdf/error/error.pdf";
  }

  let filename = state.workMeta.filename_base;

  // Alle Dateien haben "birkenbihl" im Namen
  filename += "_birkenbihl";

  // Stärke
  if (pdfOptions.strength === "GR_Fett") filename += "_GR_Fett";
  else if (pdfOptions.strength === "DE_Fett") filename += "_DE_Fett";
  else filename += "_Normal";

  // Farbe
  if (pdfOptions.color === "BlackWhite") filename += "_BlackWhite";
  else filename += "_Colour";

  // Tags
  if (pdfOptions.tags === "NoTags") filename += "_NoTags";
  else filename += "_Tag";

  // Versmaß (nur wenn aktiviert)
  if (pdfOptions.meter === "with") filename += "_Versmaß";

  const url = `${PDF_BASE}/${state.workMeta.path}/${filename}.pdf`;
  console.log("Generated PDF URL:", url);
  console.log("PDF Options Debug:", {
    strength: pdfOptions.strength,
    color: pdfOptions.color,
    tags: pdfOptions.tags,
    meter: pdfOptions.meter,
    meterSupported: state.meterSupported,
  });
  return url;
}

// Diese Funktion wurde entfernt - verwende stattdessen buildPdfFilename()

// PDF-Renderer initialisieren
function initPdfRenderer() {
  pdfRenderer.elements = {
    container: document.getElementById("pdfRendererContainer"),
    toolbar: document.getElementById("pdfToolbar"),
    pages: document.getElementById("pdfPages"),
    pageNum: document.getElementById("pdfPageNum"),
    pageCount: document.getElementById("pdfPageCount"),
    prev: document.getElementById("pdfPrev"),
    next: document.getElementById("pdfNext"),
    downloadBtn: document.getElementById("pdfDownloadBtn"),
    openTabBtn: document.getElementById("pdfOpenTabBtn"),
  };
}

// PDF neu laden
async function loadPdfIntoRendererDirect(pdfUrl) {
  try {
    // PDF.js Library verfügbar machen
    const pdfjs = window["pdfjs-dist/build/pdf"];

    // PDF laden
    const task = pdfjs.getDocument(pdfUrl);
    pdfRenderer.pdf = await task.promise;

    // UI aktualisieren
    if (pdfRenderer.elements.pageCount) {
      pdfRenderer.elements.pageCount.textContent = pdfRenderer.pdf.numPages;
    }

    // Lade-Animation entfernen
    if (pdfRenderer.elements.pages) {
      pdfRenderer.elements.pages.innerHTML = "";
    }

    // Alle Seiten rendern
    await renderAllPdfPages();

    // Events anhängen
    attachPdfEvents();
  } catch (error) {
    console.error("Fehler beim Laden des PDFs:", error);
    console.error("PDF URL war:", pdfUrl);
    if (pdfRenderer.elements.pages) {
      pdfRenderer.elements.pages.innerHTML = `
        <div class="pdf-loading" style="color: #ef4444;">
          ❌ Fehler beim Laden des PDFs<br>
          <small>URL: ${pdfUrl}</small><br>
          <small>Fehler: ${error.message}</small>
        </div>
      `;
    }
  }
}

// Alle PDF-Seiten rendern
async function renderAllPdfPages() {
  if (!pdfRenderer.pdf || !pdfRenderer.elements.pages) return;

  for (let n = 1; n <= pdfRenderer.pdf.numPages; n++) {
    const page = await pdfRenderer.pdf.getPage(n);
    const holder = document.createElement("div");
    holder.className = "pdf-page";

    const canvas = document.createElement("canvas");
    holder.appendChild(canvas);

    const label = document.createElement("div");
    label.className = "pdf-page-num";
    label.textContent = `Seite ${n}`;
    holder.appendChild(label);

    pdfRenderer.elements.pages.appendChild(holder);
    await renderPdfIntoCanvas(page, canvas);
  }
  updatePdfPageIndicator(1);
}

async function renderPdfIntoCanvas(page, canvas) {
  const context = canvas.getContext("2d", { alpha: false });

  // Höhere Standard-Skalierung für bessere Schärfe
  const scale = pdfRenderer.scale || 2.0; // Erhöht von 1.5 auf 2.0 für bessere Schärfe
  const viewport = page.getViewport({ scale });

  // Canvas-Größe direkt setzen
  canvas.width = viewport.width;
  canvas.height = viewport.height;

  // CSS-Größe für korrekte Darstellung (volle Breite)
  canvas.style.width = "100%";
  canvas.style.height = "auto";

  // PDF rendern
  await page.render({
    canvasContext: context,
    viewport: viewport,
    intent: "display",
    renderInteractiveForms: false,
  }).promise;
}

// Optionen-Schalter initialisieren
function initPdfOptionControls() {
  console.log("initPdfOptionControls aufgerufen");
  const optionBtns = document.querySelectorAll(
    "#pdfRendererContainer .pdf-option-btn"
  );
  console.log("Gefundene Buttons:", optionBtns.length);

  optionBtns.forEach((btn) => {
    btn.addEventListener("click", function () {
      const opt = this.dataset.opt;
      const val = this.dataset.val;

      // Aktiven Button in der Gruppe setzen
      const group = this.closest(".pdf-options-group");
      const buttons = group.querySelectorAll(".pdf-option-btn");
      buttons.forEach((b) => {
        b.classList.remove("active");
      });
      this.classList.add("active");

      // Option speichern
      pdfOptions[opt] = val;

      // Synchronisiere mit state für alte Funktionen
      if (opt === "source") {
        state.source = val;
        // pdfOptions.source wird nicht mehr verwendet
      } else if (opt === "strength") {
        state.strength = val;
        pdfOptions.strength = val;
      } else if (opt === "color") {
        state.color = val;
        pdfOptions.color = val;
      } else if (opt === "tags") {
        state.tags = val;
        pdfOptions.tags = val;
      } else if (opt === "meter") {
        state.meter = val;
        pdfOptions.meter = val;
      }

      // PDF neu laden
      const newPdfUrl = buildPdfUrlForRenderer();
      loadPdfIntoRendererDirect(newPdfUrl);
    });
  });

  // Standard-Optionen aktivieren (mit CSS-Klasse)
  const originalBtn = document.querySelector(
    '#pdfRendererContainer [data-opt="source"][data-val="original"]'
  );
  const normalBtn = document.querySelector(
    '#pdfRendererContainer [data-opt="strength"][data-val="Normal"]'
  );
  const colourBtn = document.querySelector(
    '#pdfRendererContainer [data-opt="color"][data-val="Colour"]'
  );
  const tagBtn = document.querySelector(
    '#pdfRendererContainer [data-opt="tags"][data-val="Tag"]'
  );
  const withBtn = document.querySelector(
    '#pdfRendererContainer [data-opt="meter"][data-val="with"]'
  );

  // Debug: Prüfe ob Buttons gefunden wurden
  console.log("Button Debug:", {
    originalBtn: !!originalBtn,
    normalBtn: !!normalBtn,
    colourBtn: !!colourBtn,
    tagBtn: !!tagBtn,
    withBtn: !!withBtn,
  });

  // Debug: Alle PDF-Option-Buttons auf der Seite finden
  const allPdfBtns = document.querySelectorAll(".pdf-option-btn");
  console.log("Alle PDF-Option-Buttons auf der Seite:", allPdfBtns.length);
  allPdfBtns.forEach((btn, index) => {
    console.log(`Button ${index}:`, {
      opt: btn.dataset.opt,
      val: btn.dataset.val,
      text: btn.textContent.trim(),
    });
  });

  // Standard-Werte für state und pdfOptions setzen
  // Alle Dateien sind Birkenbihl-Versionen, daher ist "source" nicht relevant
  if (!state.source) state.source = "original";
  if (!state.strength) state.strength = "Normal";
  if (!state.color) state.color = "Colour";
  if (!state.tags) state.tags = "Tag";

  // Versmaß-Logik: Immer basierend auf meterSupported setzen
  state.meter = state.meterSupported ? "with" : "without";

  console.log("=== INIT PDF OPTION CONTROLS DEBUG ===");
  console.log("state.meterSupported:", state.meterSupported);
  console.log("state.meter (after setting):", state.meter);

  // Synchronisiere pdfOptions mit state
  // pdfOptions.source wird nicht mehr verwendet
  pdfOptions.strength = state.strength;
  pdfOptions.color = state.color;
  pdfOptions.tags = state.tags;
  pdfOptions.meter = state.meter;

  if (originalBtn) originalBtn.classList.add("active");
  if (normalBtn) normalBtn.classList.add("active");
  if (colourBtn) colourBtn.classList.add("active");
  if (tagBtn) tagBtn.classList.add("active");

  // Versmaß-Button basierend auf meterSupported aktivieren
  // Zuerst alle Versmaß-Buttons deaktivieren
  const allMeterButtons = document.querySelectorAll(
    '#pdfRendererContainer [data-opt="meter"]'
  );
  allMeterButtons.forEach((btn) => btn.classList.remove("active"));

  // Debug-Logging
  console.log("Button-Aktivierung Debug:", {
    meterSupported: state.meterSupported,
    meter: state.meter,
    withBtn: !!withBtn,
  });

  // Dann den richtigen Button aktivieren
  if (state.meterSupported && state.meter === "with" && withBtn) {
    console.log("Aktiviere 'Versmaß' Button");
    withBtn.classList.add("active");
  } else {
    const withoutBtn = document.querySelector(
      '#pdfRendererContainer [data-opt="meter"][data-val="without"]'
    );
    console.log("Aktiviere 'Ohne Versmaß' Button");
    if (withoutBtn) withoutBtn.classList.add("active");
  }
}

function attachPdfEvents() {
  if (!pdfRenderer.elements.pages) return;

  // Seite beim Scrollen merken
  const io = new IntersectionObserver(
    (entries) => {
      let top = entries
        .filter((e) => e.isIntersecting)
        .map((e) => {
          const idx =
            [...pdfRenderer.elements.pages.children].indexOf(e.target) + 1;
          return { idx, ratio: e.intersectionRatio };
        })
        .sort((a, b) => b.ratio - a.ratio)[0];
      if (top) updatePdfPageIndicator(top.idx);
    },
    { root: null, threshold: [0.1, 0.25, 0.5, 0.75, 1] }
  );

  [...pdfRenderer.elements.pages.children].forEach((c) => io.observe(c));

  // Navigation
  if (pdfRenderer.elements.prev) {
    pdfRenderer.elements.prev.addEventListener("click", () =>
      scrollToPdfPage(pdfRenderer.currentPage - 1)
    );
  }
  if (pdfRenderer.elements.next) {
    pdfRenderer.elements.next.addEventListener("click", () =>
      scrollToPdfPage(pdfRenderer.currentPage + 1)
    );
  }

  // Open Tab Button
  if (pdfRenderer.elements.openTabBtn) {
    pdfRenderer.elements.openTabBtn.addEventListener("click", () => {
      const pdfUrl = getCurrentPdfUrl();
      const newWindow = window.open(pdfUrl, "_blank");
      if (newWindow) {
        newWindow.focus();
      }
    });
  }

  // Download Button
  if (pdfRenderer.elements.downloadBtn) {
    pdfRenderer.elements.downloadBtn.addEventListener("click", () => {
      const pdfUrl = getCurrentPdfUrl();
      const a = document.createElement("a");
      a.href = pdfUrl;
      a.download = buildPdfFilename();
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    });
  }

  // Bei Fenstergröße neu anpassen
  window.addEventListener(
    "resize",
    debouncePdf(async () => {
      if (pdfRenderer.fitToWidth) await rerenderPdf();
    }, 120)
  );
}

function updatePdfPageIndicator(n) {
  pdfRenderer.currentPage = Math.max(1, Math.min(n, pdfRenderer.pdf.numPages));
  if (pdfRenderer.elements.pageNum) {
    pdfRenderer.elements.pageNum.textContent = pdfRenderer.currentPage;
  }
}

function scrollToPdfPage(n) {
  n = Math.max(1, Math.min(n, pdfRenderer.pdf.numPages));
  const target = pdfRenderer.elements.pages.children[n - 1];
  if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function rerenderPdf() {
  if (!pdfRenderer.pdf) return;

  // Sämtliche Canvas neu zeichnen
  for (let i = 0; i < pdfRenderer.pdf.numPages; i++) {
    const page = await pdfRenderer.pdf.getPage(i + 1);
    const canvas =
      pdfRenderer.elements.pages.children[i].querySelector("canvas");
    await renderPdfIntoCanvas(page, canvas);
  }
}

function debouncePdf(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}
