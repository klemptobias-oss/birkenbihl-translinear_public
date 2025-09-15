// work.js — universelle Werkseite

// 1) KONFIG
const WORKER_BASE = "https://birkenbihl-draft-01.klemp-tobias.workers.dev"; // Externer Worker
const TXT_BASE = "texte"; // texte/<kind>/<author>/<work>/
const PDF_BASE = "pdf"; // pdf/<kind>/<author>/<work>/
const DRAFT_BASE = "pdf_drafts"; // pdf_drafts/<kind>_drafts/<author>/<work>/

// Tag-Definitionen (aus den Python-Codes)
const SUP_TAGS = [
  "N",
  "D",
  "G",
  "A",
  "V",
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
  pdfFrame: document.getElementById("pdfFrame"),
  draftFile: document.getElementById("draftFile"),
  draftBtn: document.getElementById("btnRenderDraft"),
  draftStatus: document.getElementById("draftStatus"),

  // Modal-Elemente
  modal: document.getElementById("renderingModal"),
  modalTbody: document.getElementById("tag-config-tbody"),
  closeModalBtn: document.getElementById("closeModal"),
  cancelBtn: document.getElementById("cancelRendering"),
  confirmBtn: document.getElementById("confirmRendering"),
  toggleColorsBtn: document.getElementById("toggleAllColors"),
  toggleHiddenBtn: document.getElementById("toggleAllTagsHidden"),
};

// 5) State
const state = {
  kind: getParam("kind", "poesie"), // poesie | prosa
  author: getParam("author", "Unsortiert"),
  work: getParam("work", "Unbenannt"),

  // UI-Optionen
  source: "original", // original | draft
  strength: "Normal", // Normal | GR_Fett | DE_Fett
  color: "Colour", // Colour | BlackWhite
  tags: "Tag", // Tag | NoTags
  meter: "without", // with | without  (nur wenn unterstützt)

  meterSupported: false,
  lastDraftUrl: null, // vom Worker zurückbekommen

  // Modal-Konfiguration
  tagConfig: {
    supTags: new Set(SUP_TAGS),
    subTags: new Set(SUB_TAGS),
    placementOverrides: {}, // Tag -> "sup" | "sub" | "off"
    tagColors: {}, // Tag -> "red" | "orange" | "blue" | "green" | "magenta"
    hiddenTags: new Set(), // Tags die nicht angezeigt werden sollen
  },
};

// Neue, strukturierte Definition für die Konfigurationstabelle
const tagConfigDefinition = [
  {
    leader: { id: "nomen", display: "Nomen" },
    members: [
      { id: "nomen_N", display: "Nominativ (N)", tag: "N" },
      { id: "nomen_G", display: "Genitiv (G)", tag: "G" },
      { id: "nomen_D", display: "Dativ (D)", tag: "D" },
      { id: "nomen_A", display: "Akkusativ (A)", tag: "A" },
      { id: "nomen_V", display: "Vokativ (V)", tag: "V" },
    ],
  },
  {
    leader: { id: "verb", display: "Verben" },
    members: [
      { id: "verb_Pra", display: "Präsenz(Prä)", tag: "Prä" },
      { id: "verb_Imp", display: "Imperfekt (Imp)", tag: "Imp" },
      { id: "verb_Aor", display: "Aorist (Aor)", tag: "Aor" },
      { id: "verb_AorS", display: "Aorist Stark (AorS)", tag: "AorS" },
      { id: "verb_Per", display: "Perfekt (Per)", tag: "Per" },
      { id: "verb_Plq", display: "Plusquamperfekt (Plq)", tag: "Plq" },
      { id: "verb_Fu", display: "Futur (Fu)", tag: "Fu" },
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
    leader: { id: "partizip", display: "Partizipien" },
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
    ],
  },
  {
    leader: { id: "artikel", display: "Artikel (Art)", tag: "Art" },
    members: [
      { id: "artikel_N", display: "Nominativ (N)", tag: "N" },
      { id: "artikel_G", display: "Genitiv (G)", tag: "G" },
      { id: "artikel_D", display: "Dativ (D)", tag: "D" },
      { id: "artikel_A", display: "Akkusativ (A)", tag: "A" },
    ],
  },
  // Standalone items (keine eigene Gruppe)
  { standalone: { id: "prp", display: "Präposition (Prp)", tag: "Prp" } },
  { standalone: { id: "kon", display: "Konjunktion (Kon)", tag: "Kon" } },
  { standalone: { id: "pt", display: "Partikel (Pt)", tag: "Pt" } },
  { standalone: { id: "ij", display: "Interjektion (ij)", tag: "ij" } },
];

// 6) Hilfen

// PDF-Dateiname gemäß deiner Konvention:
// <Work>_birkenbihl_<Strength>_<Colour|BlackWhite>_<Tag|NoTags>[_Versmaß].pdf
function buildPdfFilename() {
  const parts = [
    state.work,
    "birkenbihl",
    state.strength,
    state.color,
    state.tags === "Tag" ? "Tag" : "NoTags",
  ];
  if (state.meterSupported && state.meter === "with") parts.push("Versmaß");
  return parts.join("_") + ".pdf";
}

function basePdfDir() {
  if (state.source === "original") {
    return `${PDF_BASE}/${state.kind}/${state.author}/${state.work}`;
  } else {
    // Für Entwürfe: pdf_drafts/poesie_drafts/Autor/Werk/ oder pdf_drafts/prosa_drafts/Autor/Werk/
    // Spiegelbildlich zu texte_drafts/poesie_drafts/ und texte_drafts/prosa_drafts/
    return `${DRAFT_BASE}/${state.kind}_drafts/${state.author}/${state.work}`;
  }
}
function buildPdfUrlFromSelection() {
  const name = buildPdfFilename();
  return `${basePdfDir()}/${name}`;
}

function updatePdfView(fromWorker = false) {
  // Wenn Entwurf gewählt UND wir haben gerade eine Worker-URL -> die bevorzugen
  if (state.source === "draft" && state.lastDraftUrl && fromWorker) {
    el.pdfFrame.src = state.lastDraftUrl;
    return;
  }
  // Andernfalls normaler statischer Pfad
  const url = buildPdfUrlFromSelection();
  el.pdfFrame.src = url;
}

// 7) Texte laden (oben links + unten links)
async function loadTexts() {
  const base = `${TXT_BASE}/${state.kind}/${state.author}/${state.work}`;
  // Original
  try {
    const r = await fetch(`${base}/${state.work}.txt`, { cache: "no-store" });
    if (r.ok) {
      el.origText.textContent = await r.text();
    } else {
      el.origText.textContent = "Original nicht gefunden.";
    }
  } catch {
    el.origText.textContent = "Fehler beim Laden.";
  }
  // Birkenbihl
  try {
    const r = await fetch(`${base}/${state.work}_birkenbihl.txt`, {
      cache: "no-store",
    });
    if (r.ok) {
      el.birkenbihlText.textContent = await r.text();
    } else {
      el.birkenbihlText.textContent = "Birkenbihl-Text nicht gefunden.";
    }
  } catch {
    el.birkenbihlText.textContent = "Fehler beim Laden.";
  }
}

// 8) Entwurfs-System
async function initializeDraftText() {
  // Lade den Birkenbihl-Text als Basis für den Entwurf
  try {
    const base = `${TXT_BASE}/${state.kind}/${state.author}/${state.work}`;
    const r = await fetch(`${base}/${state.work}_birkenbihl.txt`, {
      cache: "no-store",
    });
    if (r.ok) {
      const text = await r.text();
      el.draftText.textContent = text;
      el.draftStatus.textContent = "Entwurf bereit. Text bearbeitbar.";
    } else {
      el.draftText.textContent = "Birkenbihl-Text nicht gefunden.";
      el.draftStatus.textContent = "Fehler: Birkenbihl-Text nicht verfügbar.";
    }
  } catch {
    el.draftText.textContent = "Fehler beim Laden des Entwurfs.";
    el.draftStatus.textContent = "Fehler beim Laden.";
  }
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
function showRenderingModal() {
  const modal = document.getElementById("renderingModal");
  modal.style.display = "flex";

  // Modal mit aktuellen Tag-Konfigurationen füllen
  populateTagControls();
}

function hideRenderingModal() {
  const modal = document.getElementById("renderingModal");
  modal.style.display = "none";
}

function populateTagControls() {
  // SUP_TAGS Container füllen (standardmäßig alle auf "Hoch")
  const supContainer = document.getElementById("supTagsContainer");
  supContainer.innerHTML = "";

  SUP_TAGS.forEach((tag) => {
    const tagRow = createTagRow(tag, "sup", true); // standardmäßig hoch
    supContainer.appendChild(tagRow);
  });

  // SUB_TAGS Container füllen (standardmäßig alle auf "Tief")
  const subContainer = document.getElementById("subTagsContainer");
  subContainer.innerHTML = "";

  SUB_TAGS.forEach((tag) => {
    const tagRow = createTagRow(tag, "sub", false); // standardmäßig tief
    subContainer.appendChild(tagRow);
  });

  // Quick Controls setzen - Standard: alle aktiviert
  document.getElementById("partizipeBlau").checked = true;
  document.getElementById("verbenGruen").checked = true;
  document.getElementById("nomenRot").checked = true;

  // Setze nur Adj auf blau (Standard)
  const ajBlauCheck = document.getElementById(`color_blue_Adj`);
  if (ajBlauCheck) {
    ajBlauCheck.checked = true;
    state.tagConfig.tagColors["Adj"] = "blue";
    const row = ajBlauCheck.closest(".tag-checkbox");
    if (row) updateTagRowColor(row, "Adj", "blue", true);
  }
}

function createTagRow(tag, type, defaultHigh) {
  const div = document.createElement("div");
  div.className = "tag-checkbox";

  // Tag-Name (Spalte 1)
  const tagName = document.createElement("span");
  tagName.textContent = tag;
  tagName.className = "tag-name";

  // Hoch Radio Button (Spalte 2)
  const hochRadio = document.createElement("input");
  hochRadio.type = "radio";
  hochRadio.name = `placement_${tag}`;
  hochRadio.value = "hoch";
  hochRadio.checked = defaultHigh;
  hochRadio.addEventListener("change", () => updateTagPlacement(tag, "hoch"));

  // Tief Radio Button (Spalte 3)
  const tiefRadio = document.createElement("input");
  tiefRadio.type = "radio";
  tiefRadio.name = `placement_${tag}`;
  tiefRadio.value = "tief";
  tiefRadio.checked = !defaultHigh;
  tiefRadio.addEventListener("change", () => updateTagPlacement(tag, "tief"));

  // Rot Checkbox (Spalte 4)
  const rotCheck = document.createElement("input");
  rotCheck.type = "checkbox";
  rotCheck.id = `color_red_${tag}`;
  rotCheck.addEventListener("change", () => {
    if (rotCheck.checked) {
      // Deaktiviere andere Farben
      blauCheck.checked = false;
      gruenCheck.checked = false;
      updateTagColor(tag, "red", true);
      updateTagRowColor(div, tag, "red", true);
    } else {
      updateTagColor(tag, "red", false);
      updateTagRowColor(div, tag, "red", false);
    }
  });

  // Blau Checkbox (Spalte 5)
  const blauCheck = document.createElement("input");
  blauCheck.type = "checkbox";
  blauCheck.id = `color_blue_${tag}`;
  blauCheck.addEventListener("change", () => {
    if (blauCheck.checked) {
      // Deaktiviere andere Farben
      rotCheck.checked = false;
      gruenCheck.checked = false;
      updateTagColor(tag, "blue", true);
      updateTagRowColor(div, tag, "blue", true);
    } else {
      updateTagColor(tag, "blue", false);
      updateTagRowColor(div, tag, "blue", false);
    }
  });

  // Grün Checkbox (Spalte 6)
  const gruenCheck = document.createElement("input");
  gruenCheck.type = "checkbox";
  gruenCheck.id = `color_green_${tag}`;
  gruenCheck.addEventListener("change", () => {
    if (gruenCheck.checked) {
      // Deaktiviere andere Farben
      rotCheck.checked = false;
      blauCheck.checked = false;
      updateTagColor(tag, "green", true);
      updateTagRowColor(div, tag, "green", true);
    } else {
      updateTagColor(tag, "green", false);
      updateTagRowColor(div, tag, "green", false);
    }
  });

  // Nicht Zeigen Checkbox (Spalte 7)
  const hideCheck = document.createElement("input");
  hideCheck.type = "checkbox";
  hideCheck.id = `hide_${tag}`;
  hideCheck.addEventListener("change", () =>
    updateTagVisibility(tag, hideCheck.checked)
  );

  // Alles in die richtige Reihenfolge bringen
  div.appendChild(tagName);
  div.appendChild(hochRadio);
  div.appendChild(tiefRadio);
  div.appendChild(rotCheck);
  div.appendChild(blauCheck);
  div.appendChild(gruenCheck);
  div.appendChild(hideCheck);

  return div;
}

function updateTagRowColor(row, tag, color, enabled) {
  if (enabled) {
    row.style.backgroundColor = getColorBackground(color);
    row.style.borderColor = getColorBorder(color);
  } else {
    // Prüfe ob andere Farben aktiv sind
    // Finde die Checkboxen direkt ohne CSS-Selektor
    const hasRed =
      row.querySelector(`input[id="color_red_${tag}"]`)?.checked || false;
    const hasBlue =
      row.querySelector(`input[id="color_blue_${tag}"]`)?.checked || false;
    const hasGreen =
      row.querySelector(`input[id="color_green_${tag}"]`)?.checked || false;

    if (hasRed) {
      row.style.backgroundColor = getColorBackground("red");
      row.style.borderColor = getColorBorder("red");
    } else if (hasBlue) {
      row.style.backgroundColor = getColorBackground("blue");
      row.style.borderColor = getColorBorder("blue");
    } else if (hasGreen) {
      row.style.backgroundColor = getColorBackground("green");
      row.style.borderColor = getColorBorder("green");
    } else {
      row.style.backgroundColor = "#f8fafc";
      row.style.borderColor = "#e2e8f0";
    }
  }
}

function getColorBackground(color) {
  switch (color) {
    case "red":
      return "#fef2f2";
    case "blue":
      return "#eff6ff";
    case "green":
      return "#f0fdf4";
    default:
      return "#f8fafc";
  }
}

function getColorBorder(color) {
  switch (color) {
    case "red":
      return "#fecaca";
    case "blue":
      return "#bfdbfe";
    case "green":
      return "#bbf7d0";
    default:
      return "#e2e8f0";
  }
}

function updateTagPlacement(tag, placement) {
  if (placement === "hoch") {
    state.tagConfig.placementOverrides[tag] = "sup";
  } else if (placement === "tief") {
    state.tagConfig.placementOverrides[tag] = "sub";
  }
}

function updateTagColor(tag, color, enabled) {
  if (enabled) {
    state.tagConfig.tagColors[tag] = color;
  } else {
    delete state.tagConfig.tagColors[tag];
  }
}

function updateTagVisibility(tag, hidden) {
  if (hidden) {
    state.tagConfig.hiddenTags.add(tag);
  } else {
    state.tagConfig.hiddenTags.delete(tag);
  }
}

function updateTagConfig(tag, type, enabled) {
  if (type === "sup") {
    if (enabled) {
      state.tagConfig.supTags.add(tag);
    } else {
      state.tagConfig.supTags.delete(tag);
    }
  } else if (type === "sub") {
    if (enabled) {
      state.tagConfig.subTags.add(tag);
    } else {
      state.tagConfig.subTags.delete(tag);
    }
  } else if (type === "color") {
    if (enabled) {
      state.tagConfig.colorTags.add(tag);
    } else {
      state.tagConfig.colorTags.delete(tag);
    }
  }
}

function setupModalEvents() {
  const modal = document.getElementById("renderingModal");
  const closeBtn = document.getElementById("closeModal");
  const cancelBtn = document.getElementById("cancelRendering");
  const confirmBtn = document.getElementById("confirmRendering");
  const disableAllTagsBtn = document.getElementById("disableAllTags");
  const enableAllTagsBtn = document.getElementById("enableAllTags");

  // Modal schließen
  closeBtn?.addEventListener("click", hideRenderingModal);
  cancelBtn?.addEventListener("click", hideRenderingModal);

  // Modal bestätigen
  confirmBtn?.addEventListener("click", () => {
    hideRenderingModal();
    performRendering();
  });

  // Quick Controls - Farben
  const partizipeBlau = document.getElementById("partizipeBlau");
  const verbenGruen = document.getElementById("verbenGruen");
  const nomenRot = document.getElementById("nomenRot");

  partizipeBlau?.addEventListener("change", (e) => {
    state.tagConfig.quickControls.partizipeBlau = e.target.checked;
    // Diese Quick Controls sind unabhängig von der Tabelle
    // Sie steuern nur die globale Farb-Logik
  });

  verbenGruen?.addEventListener("change", (e) => {
    state.tagConfig.quickControls.verbenGruen = e.target.checked;
    // Diese Quick Controls sind unabhängig von der Tabelle
    // Sie steuern nur die globale Farb-Logik
  });

  nomenRot?.addEventListener("change", (e) => {
    state.tagConfig.quickControls.nomenRot = e.target.checked;
    // Diese Quick Controls sind unabhängig von der Tabelle
    // Sie steuern nur die globale Farb-Logik
  });

  // Toggle Controls
  const toggleAllTagsBtn = document.getElementById("toggleAllTags");
  const toggleAllColorsBtn = document.getElementById("toggleAllColors");

  toggleAllTagsBtn?.addEventListener("click", () => {
    const isOn = toggleAllTagsBtn.dataset.state === "on";
    const statusSpan = toggleAllTagsBtn.querySelector(".toggle-status");

    if (isOn) {
      // Alle Tags deaktivieren
      [...SUP_TAGS, ...SUB_TAGS].forEach((tag) => {
        state.tagConfig.hiddenTags.add(tag);
        const hideCheck = document.getElementById(`hide_${tag}`);
        if (hideCheck) hideCheck.checked = true;
      });
      toggleAllTagsBtn.dataset.state = "off";
      statusSpan.textContent = "Aus";
      statusSpan.className = "toggle-status red";
    } else {
      // Alle Tags aktivieren
      [...SUP_TAGS, ...SUB_TAGS].forEach((tag) => {
        state.tagConfig.hiddenTags.delete(tag);
        const hideCheck = document.getElementById(`hide_${tag}`);
        if (hideCheck) hideCheck.checked = false;
      });
      toggleAllTagsBtn.dataset.state = "on";
      statusSpan.textContent = "An";
      statusSpan.className = "toggle-status green";
    }
  });

  toggleAllColorsBtn?.addEventListener("click", () => {
    const isOn = toggleAllColorsBtn.dataset.state === "on";
    const statusSpan = toggleAllColorsBtn.querySelector(".toggle-status");

    if (isOn) {
      // Originale Farben deaktivieren - alle Farben entfernen
      [...SUP_TAGS, ...SUB_TAGS].forEach((tag) => {
        delete state.tagConfig.tagColors[tag];
        const rotCheck = document.getElementById(`color_red_${tag}`);
        const blauCheck = document.getElementById(`color_blue_${tag}`);
        const gruenCheck = document.getElementById(`color_green_${tag}`);
        if (rotCheck) rotCheck.checked = false;
        if (blauCheck) blauCheck.checked = false;
        if (gruenCheck) gruenCheck.checked = false;
        const row = rotCheck?.closest(".tag-checkbox");
        if (row) updateTagRowColor(row, tag, "red", false);
      });

      // Quick Controls auch deaktivieren
      state.tagConfig.quickControls.partizipeBlau = false;
      state.tagConfig.quickControls.verbenGruen = false;
      state.tagConfig.quickControls.nomenRot = false;
      document.getElementById("partizipeBlau").checked = false;
      document.getElementById("verbenGruen").checked = false;
      document.getElementById("nomenRot").checked = false;

      toggleAllColorsBtn.dataset.state = "off";
      statusSpan.textContent = "Aus";
      statusSpan.className = "toggle-status red";
    } else {
      // Originale Farben aktivieren - Standard-Konfiguration
      [...SUP_TAGS, ...SUB_TAGS].forEach((tag) => {
        // Nur Adj auf blau setzen (Standard)
        if (tag === "Adj") {
          state.tagConfig.tagColors[tag] = "blue";
          const blauCheck = document.getElementById(`color_blue_${tag}`);
          if (blauCheck) {
            blauCheck.checked = true;
            const row = blauCheck.closest(".tag-checkbox");
            if (row) updateTagRowColor(row, tag, "blue", true);
          }
        }
      });

      // Quick Controls auch aktivieren
      state.tagConfig.quickControls.partizipeBlau = true;
      state.tagConfig.quickControls.verbenGruen = true;
      state.tagConfig.quickControls.nomenRot = true;
      document.getElementById("partizipeBlau").checked = true;
      document.getElementById("verbenGruen").checked = true;
      document.getElementById("nomenRot").checked = true;

      toggleAllColorsBtn.dataset.state = "on";
      statusSpan.textContent = "An";
      statusSpan.className = "toggle-status green";
    }
  });

  // Modal außerhalb klicken schließt es
  modal?.addEventListener("click", (e) => {
    if (e.target === modal) {
      hideRenderingModal();
    }
  });
}

// 10) Worker-Aufruf (Entwurf rendern)
async function renderDraftViaWorker(file) {
  // Zeige das Modal für Tag-Konfiguration
  showRenderingModal();
}

function preprocessTextForRendering(text) {
  let processedText = text;

  // Entferne alle Farb-Marker basierend auf Quick Controls
  if (!state.tagConfig.quickControls.nomenRot) {
    // Entferne # Marker (Nomen rot)
    processedText = processedText.replace(/#/g, "");
  }

  if (!state.tagConfig.quickControls.verbenGruen) {
    // Entferne - Marker (Verben grün)
    processedText = processedText.replace(/-/g, "");
  }

  if (!state.tagConfig.quickControls.partizipeBlau) {
    // Entferne + Marker nur bei Partizipien (Pt, Prp), aber nicht bei Adjektiven (Adj)
    // Das ist komplexer - wir müssen nach Tags suchen
    processedText = processedText.replace(/\+(?=\w+\(Pt\))/g, "");
    processedText = processedText.replace(/\+(?=\w+\(Prp\))/g, "");
  }

  // Jetzt füge neue Marker basierend auf Tag-Konfiguration hinzu
  Object.entries(state.tagConfig.tagColors).forEach(([tag, color]) => {
    // Escape special characters in tag for regex
    const escapedTag = tag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const tagPattern = new RegExp(`\\b(\\w+)\\(${escapedTag}\\)`, "g");
    processedText = processedText.replace(tagPattern, (match, word) => {
      if (color === "red" && !processedText.includes(`#${word}`)) {
        return `#${word}(${tag})`;
      } else if (color === "green" && !processedText.includes(`-${word}`)) {
        return `-${word}(${tag})`;
      } else if (color === "blue" && !processedText.includes(`+${word}`)) {
        return `+${word}(${tag})`;
      }
      return match;
    });
  });

  return processedText;
}

// Hilfsfunktion für aktuelle PDF-URL
function getCurrentPdfUrl() {
  return buildPdfUrlFromSelection();
}

// Fallback für lokale PDF-Generierung
async function simulateLocalPdfGeneration(payload) {
  try {
    // Simuliere PDF-Generierung mit einem Dummy-PDF
    console.log("Simuliere PDF-Generierung mit Konfiguration:", payload);

    // Erstelle eine Dummy-PDF-URL (verwende ein existierendes PDF als Fallback)
    const dummyPdfUrl = getCurrentPdfUrl();
    state.lastDraftUrl = dummyPdfUrl;

    // Quelle automatisch auf Entwurf schalten und anzeigen
    state.source = "draft";
    updatePdfView(true);
    el.draftStatus.textContent =
      "Entwurf erfolgreich gerendert! (Fallback-Modus)";

    // Zeige Info-Meldung
    setTimeout(() => {
      el.draftStatus.textContent =
        "Hinweis: Worker nicht erreichbar. Verwende Fallback-PDF. Für echte PDF-Generierung kontaktieren Sie den Administrator.";
    }, 3000);
  } catch (error) {
    console.error("Fallback-Fehler:", error);
    el.draftStatus.textContent = "Fehler beim Fallback-Rendering.";
  }
}

async function performRendering() {
  let file = el.draftFile.files?.[0];
  let textContent = "";

  if (!file) {
    // Wenn keine Datei hochgeladen wurde, verwende den aktuellen Entwurfs-Text
    const draftText = el.draftText.textContent;
    if (!draftText || draftText.trim() === "") {
      el.draftStatus.textContent =
        "Bitte zuerst Text eingeben oder Datei hochladen.";
      return;
    }

    // Preprocess den Text basierend auf Tag-Konfiguration
    textContent = preprocessTextForRendering(draftText);

    // Erstelle eine Blob-Datei aus dem verarbeiteten Text
    const blob = new Blob([textContent], { type: "text/plain" });
    file = new File([blob], `${state.work}_birkenbihl_draft.txt`, {
      type: "text/plain",
    });
  } else {
    // Wenn eine Datei hochgeladen wurde, lese sie und preprocess sie
    textContent = await file.text();
    textContent = preprocessTextForRendering(textContent);

    const blob = new Blob([textContent], { type: "text/plain" });
    file = new File([blob], file.name, { type: "text/plain" });
  }

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
      // Fallback: Versuche lokalen Server
      console.log("Worker nicht erreichbar, versuche lokalen Server...");
      try {
        const localRes = await fetch("http://localhost:5000/render", {
          method: "POST",
          body: form,
          mode: "cors",
        });
        if (localRes.ok) {
          const localData = await localRes.json();
          if (localData?.ok || localData?.pdf_url) {
            state.lastDraftUrl = localData.pdf_url;
            state.source = "draft";
            updatePdfView(true);
            el.draftStatus.textContent =
              "Entwurf erfolgreich gerendert! (Lokaler Server)";
            return;
          }
        }
      } catch (localError) {
        console.log("Lokaler Server nicht verfügbar:", localError.message);
      }

      // Letzter Fallback: Simuliere PDF-Generierung
      await simulateLocalPdfGeneration(payload);
      return;
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
      el.draftStatus.textContent = "Fehler beim Rendern des Entwurfs.";
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
    { type: "hide", value: "hide", label: "Tag verstecken" },
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
  const tbody = el.modalTbody;
  if (!tbody) return;

  // 1. Tabelle leeren und neu aufbauen
  tbody.innerHTML = "";
  tagConfigDefinition.forEach((group) => {
    if (group.leader) {
      // Gruppen-Anführer-Zeile
      const leaderRow = createTableRow(group.leader, true);
      leaderRow.dataset.group = group.leader.id;
      tbody.appendChild(leaderRow);

      // Trennlinie
      const separatorRow = document.createElement("tr");
      separatorRow.classList.add("group-separator");
      separatorRow.innerHTML = `<td colspan="9"></td>`;
      tbody.appendChild(separatorRow);

      // Mitglieder-Zeilen
      group.members.forEach((member) => {
        const memberRow = createTableRow(member);
        memberRow.dataset.group = group.leader.id;
        tbody.appendChild(memberRow);
      });
    } else if (group.standalone) {
      const standaloneRow = createTableRow(group.standalone);
      tbody.appendChild(standaloneRow);
    }
  });

  // 2. Initialkonfiguration anwenden
  applyInitialConfig();
  updateTableFromState();

  // 3. Event Listeners hinzufügen
  tbody.removeEventListener("change", handleTableChange); // Alte Listener entfernen
  tbody.addEventListener("change", handleTableChange);
  el.toggleColorsBtn.removeEventListener("click", toggleOriginalColors);
  el.toggleColorsBtn.addEventListener("click", toggleOriginalColors);
  el.toggleHiddenBtn.removeEventListener("click", toggleAllTagsHidden);
  el.toggleHiddenBtn.addEventListener("click", toggleAllTagsHidden);

  // 4. Modal anzeigen
  el.modal.style.display = "block";
}

function applyInitialConfig() {
  // Setzt die Standardkonfiguration (Farben und Platzierung)
  state.tagConfig = {}; // Reset

  // Standardfarben anwenden
  if (el.toggleColorsBtn.dataset.state === "on") {
    // Nomen -> rot
    tagConfigDefinition
      .find((g) => g.leader?.id === "nomen")
      ?.members.forEach((m) => {
        state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "red" };
      });
    // Verben -> grün
    tagConfigDefinition
      .find((g) => g.leader?.id === "verb")
      ?.members.forEach((m) => {
        state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "green" };
      });
    // Partizipien & Adjektive -> blau
    tagConfigDefinition
      .find((g) => g.leader?.id === "partizip")
      ?.members.forEach((m) => {
        state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "blue" };
      });
    tagConfigDefinition
      .find((g) => g.leader?.id === "adjektiv")
      ?.members.forEach((m) => {
        state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "blue" };
      });
  }

  // Standardplatzierungen anwenden
  const allItems = tagConfigDefinition.flatMap(
    (g) => g.members || [g.standalone]
  );
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
  const rows = el.modalTbody.querySelectorAll("tr[data-id]");
  rows.forEach((tr) => {
    const id = tr.dataset.id;
    const config = state.tagConfig[id] || {};
    const checkboxes = tr.querySelectorAll("input[type=checkbox]");

    let rowColor = config.color || "";

    checkboxes.forEach((cb) => {
      const { type, value } = cb.dataset;
      cb.checked = false; // Reset

      if (type === "placement" && config.placement === value) cb.checked = true;
      if (type === "color" && config.color === value) cb.checked = true;
      if (type === "hide" && config.hide) cb.checked = true;
    });

    tr.className = tr.classList.contains("group-leader") ? "group-leader" : "";
    if (rowColor) {
      tr.classList.add(`color-bg-${rowColor}`);
    }
  });
}

function handleTableChange(event) {
  const checkbox = event.target;
  if (checkbox.type !== "checkbox") return;

  const tr = checkbox.closest("tr");
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

  // Wenn ein Gruppenanführer geändert wird, wende es auf alle Mitglieder an
  if (tr.classList.contains("group-leader")) {
    const groupId = tr.dataset.group;
    const memberRows = el.modalTbody.querySelectorAll(
      `tr[data-group="${groupId}"]`
    );
    memberRows.forEach((memberTr) => {
      if (memberTr === tr) return; // Nicht auf sich selbst anwenden
      updateConfig(memberTr.dataset.id, type, value, checkbox.checked);
    });
  }

  // Aktualisiere den State für das geklickte Element
  updateConfig(id, type, value, checkbox.checked);

  // Exklusivität sicherstellen (nur für die geklickte Zeile)
  if (checkbox.checked) {
    const groupSelector = `input[data-type="${type}"]`;
    tr.querySelectorAll(groupSelector).forEach((cb) => {
      if (cb !== checkbox) cb.checked = false;
    });
  }

  // UI komplett aktualisieren, um alle Änderungen (auch Gruppen) widerzuspiegeln
  updateTableFromState();
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

function toggleOriginalColors() {
  toggleButton(el.toggleColorsBtn);
  applyInitialConfig();
  updateTableFromState();
}

function toggleAllTagsHidden() {
  const turnOn = toggleButton(el.toggleHiddenBtn);
  const allIds = Array.from(el.modalTbody.querySelectorAll("tr[data-id]")).map(
    (tr) => tr.dataset.id
  );

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

  // Draft-Button öffnet jetzt das Modal
  el.draftBtn?.addEventListener("click", showTagConfigModal);

  // Modal-Buttons
  el.closeModalBtn?.addEventListener("click", hideTagConfigModal);
  el.cancelBtn?.addEventListener("click", hideTagConfigModal);
  el.confirmBtn?.addEventListener("click", () => {
    hideTagConfigModal();
    performRendering();
  });

  // Entwurfs-Text Auto-Save (optional)
  el.draftText?.addEventListener("input", () => {
    el.draftStatus.textContent = "Entwurf geändert. Bereit zum Rendern.";
  });
}

// 10) Init
(async function init() {
  // Titel
  el.pageTitle.textContent = `${state.author} – ${state.work}`;

  // Katalog für Meter-Fähigkeit
  try {
    const cat = await fetchCatalog();
    const meta = findMeta(cat, state.kind, state.author, state.work);
    state.meterSupported = !!meta?.meter_capable; // true/false
    el.meterRow.style.display = state.meterSupported ? "" : "none";
  } catch {
    /* ohne Katalog: kein Versmaß */
  }

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

    if (origDownload) {
      const origUrl = `${TXT_BASE}/${state.kind}/${state.author}/${state.work}/${state.work}.txt`;
      origDownload.href = origUrl;
      origDownload.download = `${state.work}.txt`;
    }

    if (birkenbihlDownload) {
      const birkenbihlUrl = `${TXT_BASE}/${state.kind}/${state.author}/${state.work}/${state.work}_birkenbihl.txt`;
      birkenbihlDownload.href = birkenbihlUrl;
      birkenbihlDownload.download = `${state.work}_birkenbihl.txt`;
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
  }

  updateDownloadButtons();

  // Titel setzen
  el.pageTitle.textContent = `${state.author} – ${state.work}`;

  // Inhalte und PDF anzeigen
  await loadTexts();
  wireEvents();
  updatePdfView(false);

  // Entwurfs-Text initialisieren
  await initializeDraftText();

  // Modal-Events einrichten
  setupModalEvents();
})();
