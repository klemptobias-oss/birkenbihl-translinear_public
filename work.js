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
  // modalTbody ist veraltet, da wir jetzt mehrere haben
  closeModalBtn: document.getElementById("closeModal"),
  cancelBtn: document.getElementById("cancelRendering"),
  confirmBtn: document.getElementById("confirmRendering"),
  toggleColorsBtn: document.getElementById("toggleAllColors"),
  toggleHiddenBtn: document.getElementById("toggleAllTagsHidden"),

  // Neue Elemente
  toggleBirkenbihlTagsBtn: document.getElementById("toggleBirkenbihlTags"),
  toggleDraftTagsBtn: document.getElementById("toggleDraftTags"),
  resetDraftBtn: document.getElementById("resetDraft"),
  resetDraftModal: document.getElementById("resetDraftModal"),
  closeResetModalBtn: document.getElementById("closeResetModal"),
  cancelResetBtn: document.getElementById("cancelReset"),
  confirmResetBtn: document.getElementById("confirmReset"),
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
      const text = await r.text();
      state.originalBirkenbihlText = text; // Original speichern
      el.birkenbihlText.innerHTML = addSpansToTags(text);
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
  return buildPdfUrlFromSelection();
}

async function performRendering() {
  let file = el.draftFile.files?.[0];

  if (!file) {
    // Wenn keine Datei hochgeladen wurde, erstelle eine aus dem Editor-Inhalt
    const draftText = el.draftText.textContent;
    if (!draftText || draftText.trim() === "") {
      el.draftStatus.textContent =
        "Bitte zuerst Text eingeben oder Datei hochladen.";
      return;
    }
    const blob = new Blob([draftText], { type: "text/plain" });
    file = new File([blob], `${state.work}_birkenbihl_draft.txt`, {
      type: "text/plain",
    });
  }
  // Ab hier ist `file` entweder die hochgeladene oder die aus dem Editor erstellte Datei.

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
  const table = document.getElementById("tag-config-table");
  if (!table) return;

  // Alte tbody-Elemente entfernen
  table.querySelectorAll("tbody").forEach((tbody) => tbody.remove());

  tagConfigDefinition.forEach((group) => {
    const tbody = document.createElement("tbody");

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
    table.appendChild(tbody);
  });

  // 2. Initialkonfiguration anwenden
  applyInitialConfig();
  updateTableFromState();

  // 3. Event Listeners hinzufügen
  const tableBodyContainer = document.getElementById("tag-config-table");
  tableBodyContainer.removeEventListener("change", handleTableChange); // Alte Listener entfernen
  tableBodyContainer.addEventListener("change", handleTableChange);
  el.toggleColorsBtn.removeEventListener("click", toggleOriginalColors);
  el.toggleColorsBtn.addEventListener("click", toggleOriginalColors);
  el.toggleHiddenBtn.removeEventListener("click", toggleAllTagsHidden);
  el.toggleHiddenBtn.addEventListener("click", toggleAllTagsHidden);

  // 4. Modal anzeigen
  el.modal.style.display = "flex";
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
  const table = document.getElementById("tag-config-table");
  if (!table) return;
  const rows = table.querySelectorAll("tr[data-id]");
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
  const table = document.getElementById("tag-config-table");
  if (!table) return;

  const allIds = Array.from(table.querySelectorAll("tr[data-id]")).map(
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

  // "PDF aus Entwurf rendern"-Button öffnet das Modal
  el.draftBtn?.addEventListener("click", showTagConfigModal);

  // Modal-Buttons
  el.closeModalBtn?.addEventListener("click", hideTagConfigModal);
  el.cancelBtn?.addEventListener("click", hideTagConfigModal);
  el.confirmBtn?.addEventListener("click", () => {
    hideTagConfigModal();
    performRendering();
  });

  // Neue Event Listeners für Datei-Upload, Tag-Toggle und Reset
  el.draftFile?.addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        el.draftText.innerHTML = addSpansToTags(e.target.result);
        el.draftStatus.textContent = `Datei ${file.name} geladen.`;
      };
      reader.readAsText(file);
    }
  });

  el.toggleBirkenbihlTagsBtn?.addEventListener("click", () => {
    el.birkenbihlText.classList.toggle("tags-hidden");
    toggleButton(el.toggleBirkenbihlTagsBtn);
  });

  el.toggleDraftTagsBtn?.addEventListener("click", () => {
    el.draftText.classList.toggle("tags-hidden");
    toggleButton(el.toggleDraftTagsBtn);
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
    el.style.fontSize = currentSize + change + "px";
  }
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
})();
