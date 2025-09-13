// work.js — universelle Werkseite

// 1) KONFIG
const WORKER_BASE = "https://birkenbihl-draft-01.klemp-tobias.workers.dev"; // <— HIER deine Worker-URL
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
  // SUP_TAGS Container füllen
  const supContainer = document.getElementById("supTagsContainer");
  supContainer.innerHTML = "";

  SUP_TAGS.forEach((tag) => {
    const checkbox = createTagCheckbox(
      tag,
      "sup",
      state.tagConfig.supTags.has(tag)
    );
    supContainer.appendChild(checkbox);
  });

  // SUB_TAGS Container füllen
  const subContainer = document.getElementById("subTagsContainer");
  subContainer.innerHTML = "";

  SUB_TAGS.forEach((tag) => {
    const checkbox = createTagCheckbox(
      tag,
      "sub",
      state.tagConfig.subTags.has(tag)
    );
    subContainer.appendChild(checkbox);
  });

  // COLOR_TAGS Container füllen
  const colorContainer = document.getElementById("colorTagsContainer");
  colorContainer.innerHTML = "";

  COLOR_POS_WHITELIST.forEach((tag) => {
    const checkbox = createTagCheckbox(
      tag,
      "color",
      state.tagConfig.colorTags.has(tag)
    );
    colorContainer.appendChild(checkbox);
  });
}

function createTagCheckbox(tag, type, checked) {
  const div = document.createElement("div");
  div.className = "tag-checkbox";

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.id = `${type}_${tag}`;
  checkbox.checked = checked;
  checkbox.addEventListener("change", () =>
    updateTagConfig(tag, type, checkbox.checked)
  );

  const label = document.createElement("label");
  label.htmlFor = `${type}_${tag}`;
  label.textContent = tag;

  div.appendChild(checkbox);
  div.appendChild(label);

  return div;
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
  const disableAllColorsBtn = document.getElementById("disableAllColors");
  const enableAllColorsBtn = document.getElementById("enableAllColors");

  // Modal schließen
  closeBtn?.addEventListener("click", hideRenderingModal);
  cancelBtn?.addEventListener("click", hideRenderingModal);

  // Modal bestätigen
  confirmBtn?.addEventListener("click", () => {
    hideRenderingModal();
    performRendering();
  });

  // Quick Controls
  disableAllTagsBtn?.addEventListener("click", () => {
    document
      .querySelectorAll("#supTagsContainer input, #subTagsContainer input")
      .forEach((cb) => {
        cb.checked = false;
        const tag = cb.id.split("_")[1];
        const type = cb.id.split("_")[0];
        updateTagConfig(tag, type, false);
      });
  });

  enableAllTagsBtn?.addEventListener("click", () => {
    document
      .querySelectorAll("#supTagsContainer input, #subTagsContainer input")
      .forEach((cb) => {
        cb.checked = true;
        const tag = cb.id.split("_")[1];
        const type = cb.id.split("_")[0];
        updateTagConfig(tag, type, true);
      });
  });

  disableAllColorsBtn?.addEventListener("click", () => {
    document.querySelectorAll("#colorTagsContainer input").forEach((cb) => {
      cb.checked = false;
      const tag = cb.id.split("_")[1];
      updateTagConfig(tag, "color", false);
    });
  });

  enableAllColorsBtn?.addEventListener("click", () => {
    document.querySelectorAll("#colorTagsContainer input").forEach((cb) => {
      cb.checked = true;
      const tag = cb.id.split("_")[1];
      updateTagConfig(tag, "color", true);
    });
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

async function performRendering() {
  let file = el.draftFile.files?.[0];

  if (!file) {
    // Wenn keine Datei hochgeladen wurde, verwende den aktuellen Entwurfs-Text
    const draftText = el.draftText.textContent;
    if (!draftText || draftText.trim() === "") {
      el.draftStatus.textContent =
        "Bitte zuerst Text eingeben oder Datei hochladen.";
      return;
    }

    // Erstelle eine Blob-Datei aus dem Text
    const blob = new Blob([draftText], { type: "text/plain" });
    file = new File([blob], `${state.work}_birkenbihl_draft.txt`, {
      type: "text/plain",
    });
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
    },
  };

  const form = new FormData();
  form.append("file", file, file.name);
  form.append("options", JSON.stringify(payload));

  try {
    const res = await fetch(`${WORKER_BASE}/render`, {
      method: "POST",
      body: form,
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
        const blob = new Blob([draftText], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        draftDownload.href = url;
        draftDownload.download = `${state.work}_birkenbihl_entwurf.txt`;
        // Cleanup nach dem Download
        setTimeout(() => URL.revokeObjectURL(url), 1000);
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
