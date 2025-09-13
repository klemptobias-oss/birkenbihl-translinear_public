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
  "Aj",
  "Pt",
  "Prp",
  "Av",
  "Ko",
  "Art",
  "≈",
  "Kmp",
  "Sup",
  "Ij",
];
const SUB_TAGS = [
  "Pre",
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
  "Kon",
  "Op",
  "Pr",
  "AorS",
  "M/P",
];
const COLOR_POS_WHITELIST = ["Aj", "Pt", "Prp", "Av", "Ko", "Art", "Pr", "Ij"];

// 2) URL-Parameter
function getParam(name, dflt = "") {
  const u = new URL(location.href);
  return u.searchParams.get(name) || dflt;
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
    colorTags: new Set(COLOR_POS_WHITELIST),
    placementOverrides: {}, // Tag -> "sup" | "sub" | "off"
    tagColors: {}, // Tag -> "red" | "blue" | "green"
    hiddenTags: new Set(), // Tags die nicht angezeigt werden sollen
    quickControls: {
      partizipeBlau: true,
      verbenGruen: true,
      nomenRot: true,
    },
  },
};

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
    const kindDraft =
      state.kind === "poesie" ? "poesie_drafts" : "prosa_drafts";
    return `${DRAFT_BASE}/${kindDraft}/${state.author}/${state.work}`;
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
  const draftPath = `texte_drafts/${state.kind}/${state.author}/${state.work}`;

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

  // Setze nur Aj auf blau (Standard)
  const ajBlauCheck = document.getElementById(`color_blue_Aj`);
  if (ajBlauCheck) {
    ajBlauCheck.checked = true;
    state.tagConfig.tagColors["Aj"] = "blue";
    const row = ajBlauCheck.closest(".tag-checkbox");
    if (row) updateTagRowColor(row, "Aj", "blue", true);
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
    updateTagColor(tag, "red", rotCheck.checked);
    updateTagRowColor(div, tag, "red", rotCheck.checked);
  });

  // Blau Checkbox (Spalte 5)
  const blauCheck = document.createElement("input");
  blauCheck.type = "checkbox";
  blauCheck.id = `color_blue_${tag}`;
  blauCheck.addEventListener("change", () => {
    updateTagColor(tag, "blue", blauCheck.checked);
    updateTagRowColor(div, tag, "blue", blauCheck.checked);
  });

  // Grün Checkbox (Spalte 6)
  const gruenCheck = document.createElement("input");
  gruenCheck.type = "checkbox";
  gruenCheck.id = `color_green_${tag}`;
  gruenCheck.addEventListener("change", () => {
    updateTagColor(tag, "green", gruenCheck.checked);
    updateTagRowColor(div, tag, "green", gruenCheck.checked);
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
    // Escape special characters in tag for CSS selector
    const escapedTag = tag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const hasRed = row.querySelector(`#color_red_${escapedTag}`).checked;
    const hasBlue = row.querySelector(`#color_blue_${escapedTag}`).checked;
    const hasGreen = row.querySelector(`#color_green_${escapedTag}`).checked;

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
      // Alle Farben deaktivieren
      [...SUP_TAGS, ...SUB_TAGS].forEach((tag) => {
        delete state.tagConfig.tagColors[tag];
        const escapedTag = tag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const rotCheck = document.getElementById(`color_red_${escapedTag}`);
        const blauCheck = document.getElementById(`color_blue_${escapedTag}`);
        const gruenCheck = document.getElementById(`color_green_${escapedTag}`);
        if (rotCheck) rotCheck.checked = false;
        if (blauCheck) blauCheck.checked = false;
        if (gruenCheck) gruenCheck.checked = false;
        const row = rotCheck?.closest(".tag-checkbox");
        if (row) updateTagRowColor(row, tag, "red", false);
      });
      toggleAllColorsBtn.dataset.state = "off";
      statusSpan.textContent = "Aus";
      statusSpan.className = "toggle-status red";
    } else {
      // Alle Farben aktivieren (zurück zu Standard)
      [...SUP_TAGS, ...SUB_TAGS].forEach((tag) => {
        // Nur Aj auf blau setzen (Standard)
        if (tag === "Aj") {
          state.tagConfig.tagColors[tag] = "blue";
          const escapedTag = tag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
          const blauCheck = document.getElementById(`color_blue_${escapedTag}`);
          if (blauCheck) {
            blauCheck.checked = true;
            const row = blauCheck.closest(".tag-checkbox");
            if (row) updateTagRowColor(row, tag, "blue", true);
          }
        }
      });
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
    // Entferne + Marker nur bei Partizipien (Pt, Prp), aber nicht bei Adjektiven (Aj)
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

    // Neue Tag-Konfiguration
    tag_config: {
      sup_tags: Array.from(state.tagConfig.supTags),
      sub_tags: Array.from(state.tagConfig.subTags),
      color_pos_whitelist: Array.from(state.tagConfig.colorTags),
      placement_overrides: state.tagConfig.placementOverrides,
      tag_colors: state.tagConfig.tagColors,
      hidden_tags: Array.from(state.tagConfig.hiddenTags),
      quick_controls: state.tagConfig.quickControls,
    },
  };

  const form = new FormData();
  form.append("file", file, file.name);
  form.append("options", JSON.stringify(payload));

  try {
    const res = await fetch(`${WORKER_BASE}/render`, {
      method: "POST",
      body: form,
      mode: "cors",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!data?.ok || !data?.pdf_url)
      throw new Error("Worker-Antwort unvollständig.");
    state.lastDraftUrl = data.pdf_url;
    // Quelle automatisch auf Entwurf schalten und anzeigen
    state.source = "draft";
    updatePdfView(true);
    el.draftStatus.textContent = "Entwurf erfolgreich gerendert!";
  } catch (e) {
    console.error(e);
    el.draftStatus.textContent = "Fehler beim Rendern des Entwurfs.";
  }
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

  // Draft-Button
  el.draftBtn?.addEventListener("click", () =>
    renderDraftViaWorker(el.draftFile.files?.[0])
  );

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
