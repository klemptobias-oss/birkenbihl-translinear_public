// work.js — universelle Werkseite

import { loadCatalog, getWorkMeta } from "./catalog.js";

// 1) KONFIG
const GH_OWNER = "klemptobias-oss";
const GH_REPO = "Antike-Translinear";
const GH_BASE = `https://github.com/${GH_OWNER}/${GH_REPO}/releases/download`;
const GH_RAW_BRANCH = "main";
const GH_RAW_BASE = `https://raw.githubusercontent.com/${GH_OWNER}/${GH_REPO}/${GH_RAW_BRANCH}`;
const GH_ACTIONS_URL = `https://github.com/${GH_OWNER}/${GH_REPO}/actions`;

const WORKER_BASE = "https://antike-translinear-draft.klemp-tobias.workers.dev"; // Externer Worker
const GH_RELEASE_PROXY = `${WORKER_BASE}/release`;
const TXT_BASE = "texte"; // texte/<kind>/<author>/<work>/
const DRAFT_BASE = "pdf_drafts"; // pdf_drafts/<kind>_drafts/<author>/<work>/
const IS_LOCAL_ENVIRONMENT =
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1" ||
    window.location.protocol === "file:");

// Tag-Definitionen (aus den Python-Codes)
const SUP_TAGS = [
  "N",
  "D",
  "G",
  "A",
  "V",
  "Du",
  "Abl", // NEU: Ablativ für Latein
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
  "Fu1", // NEU: Futur 1 für Latein
  "Fu2", // NEU: Futur 2 für Latein
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
  "Ger", // NEU: Gerundium für Latein
  "Gdv", // NEU: Gerundivum für Latein
  "Spn", // NEU: Supinum für Latein
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
  toggleTranslationsHiddenBtn: document.getElementById(
    "toggleAllTranslationsHidden"
  ),
  togglePipesHiddenBtn: document.getElementById("togglePipesHidden"),

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
  category: getParam("category", ""), // NEU: Kategorie (Epos, Drama, Lyrik, etc.)
  author: getParam("author", "Unsortiert"),
  work: getParam("work", "Unbenannt"),
  languages: getParam("languages", "2"), // NEU: 2 oder 3 sprachig
  meterMode: getParam("meter", "false"), // NEU: "true" oder "false" - ob Versmaß-Version geladen werden soll
  translationTarget: getParam("target", "de"),

  workMeta: null, // Wird nach dem Laden des Katalogs gefüllt

  // UI-Optionen
  source: "original", // original | draft
  strength: "", // Wird dynamisch gesetzt: GR_Fett für Griechisch, LAT_Fett für Latein
  color: "Colour", // Colour | BlackWhite
  tags: "Tag", // Tag | NoTags
  meter: "without", // with | without  (nur für PDF-Rendering, wenn Versmaß-Marker angezeigt werden sollen)

  meterSupported: false,
  meterPageActive: false,
  lastDraftUrl: null, // vom Worker zurückbekommen
  pendingDraftFilename: null, // merkt sich den zuletzt gestarteten Build
  draftBase: null,
  manualDraftBuildRequired: false,
  manualDraftCommand: null,
  draftBuildActive: false,
  draftHasResult: false,
  originalBirkenbihlText: "", // Zum Zurücksetzen des Entwurfs

  // Modal-Konfiguration
  tagConfig: {
    supTags: new Set(SUP_TAGS),
    subTags: new Set(SUB_TAGS),
    placementOverrides: {}, // Tag -> "sup" | "sub" | "off"
    tagColors: {}, // Tag -> "red" | "orange" | "blue" | "green" | "violett"
    hiddenTags: new Set(), // Tags die nicht angezeigt werden sollen
  },
};

function needsVersmassRendering() {
  return Boolean(state.workMeta?.versmass) || state.meter === "with";
}

function getDraftWorkPath() {
  if (state.workMeta?.path) {
    console.log("✓ Using workMeta.path:", state.workMeta.path);
    return state.workMeta.path;
  }
  const segments = [
    state.lang,
    state.kind,
    state.category,
    state.author,
    state.work,
  ].filter(Boolean);
  const constructedPath = segments.join("/");
  console.log("⚠ Constructed path from state:", constructedPath, {
    lang: state.lang,
    kind: state.kind,
    category: state.category,
    author: state.author,
    work: state.work,
  });
  return constructedPath;
}

function buildDraftUploadFilename() {
  let base = state.workMeta?.filename_base || state.work;
  if (needsVersmassRendering() && !/_versmaß|_versmass/i.test(base)) {
    base += "_Versmaß";
  }
  return `${base}_birkenbihl_draft.txt`;
}

function getDraftStorageKey() {
  return `draftBase::${getDraftWorkPath()}`;
}

function getDraftFilenameStorageKey() {
  return `draftFilename::${getDraftWorkPath()}`;
}

function persistDraftBase() {
  if (!state.draftBase) return;
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    window.localStorage.setItem(getDraftStorageKey(), state.draftBase);
  } catch (e) {
    console.warn("Persisting draft base failed", e);
  }
}

function persistPendingDraftFilename() {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    if (state.pendingDraftFilename) {
      window.localStorage.setItem(
        getDraftFilenameStorageKey(),
        state.pendingDraftFilename
      );
    } else {
      window.localStorage.removeItem(getDraftFilenameStorageKey());
    }
  } catch (e) {
    console.warn("Persisting pending draft filename failed", e);
  }
}

function restoreDraftBase() {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    const stored = window.localStorage.getItem(getDraftStorageKey());
    if (stored) {
      state.draftBase = normalizeReleaseBase(stored);
      state.draftHasResult = false;
      state.draftBuildActive = false;
      state.manualDraftBuildRequired = false;
    }

    // Restore pending draft filename
    const storedFilename = window.localStorage.getItem(
      getDraftFilenameStorageKey()
    );
    if (storedFilename) {
      state.pendingDraftFilename = storedFilename;
    }
  } catch (e) {
    console.warn("Restoring draft base failed", e);
  }
}

let draftProbeInFlight = false;
async function probeDraftAvailability() {
  if (draftProbeInFlight) return;
  if (!state.draftBase) return;
  const draftName = buildDraftPdfFilename();
  if (!draftName || draftName === "error.pdf") return;
  const url = buildDraftPdfUrl(draftName);
  draftProbeInFlight = true;
  try {
    const probeUrl =
      url + (url.includes("?") ? "&" : "?") + "probe=" + Date.now();
    const res = await fetch(probeUrl, { method: "HEAD", cache: "no-store" });
    if (res && res.ok) {
      state.draftBuildActive = false;
      state.draftHasResult = true;
      state.manualDraftBuildRequired = false;
      state.lastDraftUrl = url;
      updatePdfView(true);
    } else {
      // PDF noch nicht verfügbar → Retry in 5 Sekunden (wenn noch buildActive)
      if (state.draftBuildActive) {
        setTimeout(() => {
          draftProbeInFlight = false;
          probeDraftAvailability();
        }, 5000);
        return; // WICHTIG: Nicht draftProbeInFlight = false setzen (wird im setTimeout gemacht)
      }
    }
  } catch (e) {
    console.warn("Draft probe failed", e);
    // Retry bei Fehler (wenn noch buildActive)
    if (state.draftBuildActive) {
      setTimeout(() => {
        draftProbeInFlight = false;
        probeDraftAvailability();
      }, 5000);
      return;
    }
  } finally {
    draftProbeInFlight = false;
  }
}

function buildBirkenbihlBaseCandidates(base) {
  if (!base) return [];
  const match = base.match(/_(gr|lat)_([a-z_]+)_stil1/);
  if (!match) return [base];
  const langCode = match[1];
  const translationSegment = match[2];
  const prefix = base.slice(0, match.index);
  const suffix = base.slice(match.index + match[0].length);
  const candidates = [];
  const seen = new Set();

  const addCandidate = (segment) => {
    if (!segment) return;
    const candidate = `${prefix}_${langCode}_${segment}_stil1${suffix}`;
    if (!seen.has(candidate)) {
      seen.add(candidate);
      candidates.push(candidate);
    }
  };

  if (state.languages === "3") addCandidate("de_en");
  if (state.translationTarget === "en") {
    addCandidate("en");
    addCandidate("de_en");
  } else {
    addCandidate("de");
  }

  addCandidate(translationSegment);
  addCandidate("de_en");
  addCandidate("de");
  addCandidate("en");

  return candidates.length ? candidates : [base];
}

async function fetchBirkenbihlText(textBasePath, baseCandidates) {
  if (!baseCandidates || !baseCandidates.length) return null;
  const meterSuffixes = state.meter === "with" ? ["_Versmaß", ""] : [""];

  for (const candidate of baseCandidates) {
    for (const suffix of meterSuffixes) {
      const fileBase = `${candidate}${suffix}`;
      const candidatePath = `texte/${textBasePath}/${fileBase}_birkenbihl.txt`;
      try {
        const resp = await fetch(candidatePath, { cache: "no-store" });
        if (resp.ok) {
          const text = await resp.text();
          return { text, path: candidatePath, base: fileBase };
        }
      } catch (err) {
        console.warn("Fetch Birkenbihl candidate failed", candidatePath, err);
      }
    }
  }
  return null;
}

function getDraftTextAbsolutePath(filename = "") {
  const base = getDraftWorkPath();
  const parts = ["texte_drafts", base, filename].filter(Boolean);
  return parts.join("/").replace(/\/+/g, "/");
}

// Debug: URL-Parameter ausgeben
console.log("URL-Parameter:", {
  lang: state.lang,
  kind: state.kind,
  author: state.author,
  work: state.work,
  fullUrl: location.href,
});

// Neue, strukturierte Definition für die Konfigurationstabelle
// Griechische Tag-Konfiguration
const tagConfigDefinitionGreek = [
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
      { id: "verb_Pra", display: "Präsenz (Prä)", tag: "Prä" },
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
      { id: "partizip_Pra", display: "Präsenz (Prä)", tag: "Prä" },
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

// Lateinische Tag-Konfiguration
const tagConfigDefinitionLatin = [
  {
    leader: { id: "nomen", display: "Nomen", tag: "Nomen" },
    members: [
      { id: "nomen_N", display: "Nominativ (N)", tag: "N" },
      { id: "nomen_G", display: "Genitiv (G)", tag: "G" },
      { id: "nomen_D", display: "Dativ (D)", tag: "D" },
      { id: "nomen_A", display: "Akkusativ (A)", tag: "A" },
      { id: "nomen_Abl", display: "Ablativ (Abl)", tag: "Abl" },
      { id: "nomen_V", display: "Vokativ (V)", tag: "V" },
    ],
  },
  {
    leader: { id: "verb", display: "Verben", tag: "Verben" },
    members: [
      { id: "verb_Pra", display: "Präsens (Prä)", tag: "Prä" },
      { id: "verb_Imp", display: "Imperfekt (Imp)", tag: "Imp" },
      { id: "verb_Per", display: "Perfekt (Per)", tag: "Per" },
      { id: "verb_Plq", display: "Plusquamperfekt (Plq)", tag: "Plq" },
      { id: "verb_Fu1", display: "Futur 1 (Fu1)", tag: "Fu1" },
      { id: "verb_Fu2", display: "Futur 2 (Fu2)", tag: "Fu2" },
      { id: "verb_Akt", display: "Aktiv (Akt)", tag: "Akt" },
      { id: "verb_Pas", display: "Passiv (Pas)", tag: "Pas" },
      { id: "verb_Inf", display: "Infinitiv (Inf)", tag: "Inf" },
      { id: "verb_Knj", display: "Konjunktiv (Knj)", tag: "Knj" },
      { id: "verb_Imv", display: "Imperativ (Imv)", tag: "Imv" },
    ],
  },
  {
    leader: { id: "partizip", display: "Partizipien", tag: "Partizipien" },
    members: [
      { id: "partizip_Pra", display: "Präsens (Prä)", tag: "Prä" },
      { id: "partizip_Per", display: "Perfekt (Per)", tag: "Per" },
      { id: "partizip_Fu1", display: "Futur 1 (Fu1)", tag: "Fu1" },
      { id: "partizip_N", display: "Nominativ (N)", tag: "N" },
      { id: "partizip_G", display: "Genitiv (G)", tag: "G" },
      { id: "partizip_D", display: "Dativ (D)", tag: "D" },
      { id: "partizip_A", display: "Akkusativ (A)", tag: "A" },
      { id: "partizip_Abl", display: "Ablativ (Abl)", tag: "Abl" },
      { id: "partizip_V", display: "Vokativ (V)", tag: "V" },
      { id: "partizip_Akt", display: "Aktiv (Akt)", tag: "Akt" },
      { id: "partizip_Pas", display: "Passiv (Pas)", tag: "Pas" },
    ],
  },
  {
    leader: { id: "gerundium", display: "Gerundium (Ger)", tag: "Ger" },
    members: [
      { id: "gerundium_G", display: "Genitiv (G)", tag: "G" },
      { id: "gerundium_D", display: "Dativ (D)", tag: "D" },
      { id: "gerundium_A", display: "Akkusativ (A)", tag: "A" },
      { id: "gerundium_Abl", display: "Ablativ (Abl)", tag: "Abl" },
    ],
  },
  {
    leader: { id: "gerundivum", display: "Gerundivum (Gdv)", tag: "Gdv" },
    members: [
      { id: "gerundivum_N", display: "Nominativ (N)", tag: "N" },
      { id: "gerundivum_G", display: "Genitiv (G)", tag: "G" },
      { id: "gerundivum_D", display: "Dativ (D)", tag: "D" },
      { id: "gerundivum_A", display: "Akkusativ (A)", tag: "A" },
      { id: "gerundivum_Abl", display: "Ablativ (Abl)", tag: "Abl" },
      { id: "gerundivum_V", display: "Vokativ (V)", tag: "V" },
    ],
  },
  {
    leader: { id: "supinum", display: "Supinum (Spn)", tag: "Spn" },
    members: [
      { id: "supinum_A", display: "Akkusativ (A)", tag: "A" },
      { id: "supinum_Abl", display: "Ablativ (Abl)", tag: "Abl" },
    ],
  },
  {
    leader: { id: "adjektiv", display: "Adjektiv (Adj)", tag: "Adj" },
    members: [
      { id: "adjektiv_N", display: "Nominativ (N)", tag: "N" },
      { id: "adjektiv_G", display: "Genitiv (G)", tag: "G" },
      { id: "adjektiv_D", display: "Dativ (D)", tag: "D" },
      { id: "adjektiv_A", display: "Akkusativ (A)", tag: "A" },
      { id: "adjektiv_Abl", display: "Ablativ (Abl)", tag: "Abl" },
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
      { id: "pronomen_Abl", display: "Ablativ (Abl)", tag: "Abl" },
    ],
  },
  // Einzelne Grammatik-Tags als normale Zeilen (nicht als Gruppenleiter)
  { standalone: { id: "prp", display: "Präposition (Prp)", tag: "Prp" } },
  { standalone: { id: "kon", display: "Konjunktion (Kon)", tag: "Kon" } },
  { standalone: { id: "pt", display: "Partikel (Pt)", tag: "Pt" } },
  { standalone: { id: "ij", display: "Interjektion (ij)", tag: "ij" } },
];

// Wähle die richtige Konfiguration basierend auf der Sprache
const tagConfigDefinition =
  state.lang === "latein" ? tagConfigDefinitionLatin : tagConfigDefinitionGreek;

// 6) Hilfen

// PDF-Dateiname gemäß deiner Konvention:
// <Work>_<lang>_de[_en]_stil1_birkenbihl_<Strength>_<Colour|BlackWhite>_<Tag|NoTags>[_Versmass].pdf
function getLocalizedFilenameBase() {
  if (!state.workMeta || !state.workMeta.filename_base) {
    console.error("Work metadata with filename_base not loaded!");
    return null;
  }

  let filename = state.workMeta.filename_base;
  const hasDeEn = filename.includes("_de_en_");
  const hasPureDe = hasDeEn ? false : filename.includes("_de_");
  const hasPureEn = hasDeEn ? false : filename.includes("_en_");

  if (state.languages === "3") {
    if (!hasDeEn) {
      if (hasPureDe) filename = filename.replace("_de_", "_de_en_");
      else if (hasPureEn) filename = filename.replace("_en_", "_de_en_");
    }
  } else {
    if (state.translationTarget === "en") {
      if (hasDeEn) filename = filename.replace("_de_en_", "_en_");
      else if (hasPureDe) filename = filename.replace("_de_", "_en_");
    } else {
      if (hasDeEn) filename = filename.replace("_de_en_", "_de_");
      else if (hasPureEn) filename = filename.replace("_en_", "_de_");
    }
  }

  // Normalisiere alle Versmaß-Varianten zu "Versmass" (URL-sicher)
  // Regex: _Versm + (a|ä) + (s|ß){1,2} + optional weitere Buchstaben bis zum nächsten Unterstrich
  filename = filename.replace(/_[Vv]ersm[aä][sß]{1,2}[a-zßA-Z]*/g, "_Versmass");

  if (state.meter === "with" && !filename.includes("_Versmass")) {
    filename += "_Versmass";
  }

  if (!filename.includes("_birkenbihl")) {
    filename += "_birkenbihl";
  }

  return filename;
}

function normalizeReleaseBase(base) {
  if (!base) return null;

  // KRITISCH: Prüfe ob base bereits "_draft_translinear_DRAFT_TIMESTAMP" enthält
  // Wenn ja, NICHT normalisieren (ist bereits vollständiger Draft-Name)
  if (base.includes("_draft_translinear_DRAFT_")) {
    // Draft-Namen nicht normalisieren - behalten wie sie sind
    return base.includes("_birkenbihl") ? base : `${base}_birkenbihl`;
  }

  // Normalisiere Versmaß-Varianten zu "Versmass" (URL-sicher)
  let normalized = base.replace(
    /_[Vv]ersm[aä][sß]{1,2}[a-zßA-Z]*/g,
    "_Versmass"
  );
  return normalized.includes("_birkenbihl")
    ? normalized
    : `${normalized}_birkenbihl`;
}

function buildVariantSuffix(localizedBase) {
  const base = localizedBase || getLocalizedFilenameBase();
  if (!base) return "";
  const isGreek = base.includes("_gr_");
  const isLatin = base.includes("_lat_");

  let suffix = "";
  if (state.strength === "Normal") {
    suffix += "_Normal";
  } else {
    const marker =
      state.strength === "Fett"
        ? isGreek
          ? "_GR_Fett"
          : isLatin
          ? "_LAT_Fett"
          : state.lang === "latein"
          ? "_LAT_Fett"
          : "_GR_Fett"
        : isGreek
        ? "_GR_Fett"
        : isLatin
        ? "_LAT_Fett"
        : "";
    suffix += marker;
  }

  suffix += state.color === "BlackWhite" ? "_BlackWhite" : "_Colour";
  suffix += state.tags === "NoTags" ? "_NoTags" : "_Tag";

  return suffix;
}

function buildReleaseBase() {
  const localized = getLocalizedFilenameBase();
  if (!localized) return null;
  const metaPrefix = state.workMeta?.meta_prefix || "";
  return metaPrefix ? `${metaPrefix}__${localized}` : localized;
}

function buildFullReleaseName() {
  const base = buildReleaseBase();
  if (!base) return null;
  const suffix = buildVariantSuffix();
  return `${base}${suffix}`;
}

function buildDraftPdfFilename() {
  // EINFACHE LÖSUNG: PDF-Name = Pfad-Prefix (aus RELEASE_BASE) + Upload-Filename + Variant-Suffix
  //
  // Warum NICHT RELEASE_BASE für den Filename verwenden?
  // - RELEASE_BASE kann normalisiert sein (z.B. gr_de statt gr_de_en)
  // - GitHub Actions erstellt PDFs mit ORIGINAL Upload-Filename
  // - Browser muss PDFs anhand Upload-Filename finden (404 sonst!)
  //
  // Beispiel:
  // - Upload: agamemnon_gr_de_en_stil1_birkenbihl_draft_translinear_DRAFT_20251130_011301.txt
  // - RELEASE_BASE: GR_poesie_Drama_Aischylos_Agamemnon__agamemnon_gr_de_stil1_birkenbihl
  // - PDF-Name: GR_poesie_Drama_Aischylos_Agamemnon__agamemnon_gr_de_en_stil1_birkenbihl_draft_translinear_DRAFT_20251130_011301_GR_Fett_Colour_Tag.pdf
  //             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ Prefix aus RELEASE_BASE
  //                                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ ORIGINAL Upload-Filename
  //                                                                                                                     ^^^^^^^^^^^^^^^^^^^^^^^^ Variant-Suffix

  if (state.pendingDraftFilename && state.draftBase) {
    // GitHub Actions erstellt PDFs mit PATH_PREFIX (aus work meta) + UPLOAD_FILENAME
    // Format: GR_poesie_Drama_Autor_Werk__upload_filename_SESSION_xxx_DRAFT_yyy

    // NEU: Hole meta_prefix aus Upload-Filename STATT aus workMeta
    // Grund: workMeta.meta_prefix hat alte Präfixe (GR_poesie_Drama_...), aber wir wollen
    // nur Autor_Werk als Basis!
    let pathPrefix = "";

    // Versuche Autor_Werk aus pendingDraftFilename zu extrahieren
    // Format: Autor_Werk_xx_yy_zz_translinear_SESSION_xxx_DRAFT_yyy.txt
    const uploadBase = state.pendingDraftFilename.replace(/\.txt$/, "");

    // Extrahiere Autor_Werk (bis zum ersten "_translinear" oder "_gr_" oder "_lat_")
    const match = uploadBase.match(/^([^_]+_[^_]+)_(?:gr|lat|translinear)/i);
    if (match) {
      pathPrefix = match[1] + "__"; // z.B. "Aristophanes_Wolken__"
    }

    // Kombiniere: PATH_PREFIX + Upload-Filename + Variant-Suffix
    const filebase = pathPrefix + uploadBase;
    const name = `${filebase}${buildVariantSuffix()}.pdf`;
    console.log("✅ Generated draft filename:", name);
    return name;
  }

  // Fallback: Verwende draftBase direkt (für ältere Drafts ohne Timestamp)
  const releaseBase = state.draftBase || buildReleaseBase();
  if (!releaseBase) return "error.pdf";
  const name = `${releaseBase}${buildVariantSuffix()}.pdf`;
  console.log("Generated draft filename (from draftBase):", name);
  return name;
}

function buildPdfFilename() {
  const full = buildFullReleaseName();
  if (!full) return "error.pdf";
  const finalName = `${full}.pdf`;
  console.log("Generated filename:", finalName);
  return finalName;
}

function basePdfDir() {
  if (!state.workMeta || !state.workMeta.release_tag) {
    console.error("Work metadata with release_tag not loaded!");
    return GH_BASE;
  }

  return `${GH_BASE}/${state.workMeta.release_tag}`;
}

function buildReleaseProxyUrl(filename, disposition = "inline") {
  if (!state.workMeta || !state.workMeta.release_tag) {
    console.warn("No release metadata, falling back to direct GitHub URL");
    return `${basePdfDir()}/${encodeURIComponent(filename)}`;
  }
  const params = new URLSearchParams({
    tag: state.workMeta.release_tag,
    file: filename, // Filename wird vom Worker automatisch URL-encoded
    mode: disposition === "attachment" ? "attachment" : "inline",
  });
  return `${GH_RELEASE_PROXY}?${params.toString()}`;
}

function buildDraftRelativePath(filename) {
  const workPath = getDraftWorkPath();
  const segments = ["pdf_drafts", workPath, filename];
  const relativePath = segments.filter(Boolean).join("/").replace(/\/+/g, "/");
  console.log("🔍 Draft Path Debug:", {
    workPath,
    filename,
    relativePath,
    workMeta: state.workMeta,
  });
  return relativePath;
}

function buildDraftPdfUrl(filename) {
  const relativePath = buildDraftRelativePath(filename);
  if (IS_LOCAL_ENVIRONMENT) {
    return relativePath;
  }
  // NEU: Cache-Busting Parameter hinzufügen
  // GitHub Raw-Content cached sehr aggressiv (1-3 Minuten)
  // Timestamp-basierter Cache-Buster zwingt Browser zum Neu-Laden
  const cacheBuster = Date.now();
  return `${GH_RAW_BASE}/${relativePath}?cb=${cacheBuster}`;
}

function buildPdfUrlFromSelection() {
  if (state.source === "draft") {
    const name = buildDraftPdfFilename();
    return buildDraftPdfUrl(name);
  }
  const name = buildPdfFilename();
  return buildReleaseProxyUrl(name, "inline");
}

/**
 * Verkürzt einen PDF-Dateinamen für Downloads
 * Entfernt: GR_poesie_Drama_ Präfix, doppelte Autor_Werk, SESSION_xxx_DRAFT_timestamp, temp_
 * Beispiel: GR_poesie_Drama_Euripides_Kyklops__Euripides_Kyklops_gr_de_translinear_SESSION_xxx_DRAFT_20251201_001511_Normal_Colour_Tag.pdf
 *        → Euripides_Kyklops_gr_de_translinear_Normal_Colour_Tag.pdf
 */
function shortenPdfFilename(filename) {
  if (!filename || !filename.toLowerCase().endsWith(".pdf")) {
    return filename;
  }

  let baseName = filename;

  // Schritt 1: Entferne Sprach/Gattungs/Kategorie-Präfix (GR_poesie_Drama_, LAT_prosa_Historie_, etc.)
  baseName = baseName.replace(/^(GR|LAT)_(poesie|prosa)_[^_]+_/i, "");

  // Schritt 2: Entferne doppelte Autor_Werk-Wiederholung (Autor_Werk__Autor_Werk → Autor_Werk)
  baseName = baseName.replace(/([^_]+_[^_]+)__\1/g, "$1");

  // Schritt 3: Entferne SESSION und DRAFT Timestamps
  baseName = baseName.replace(
    /_translinear_SESSION_[a-f0-9]+_DRAFT_\d{8}_\d{6}/gi,
    "_translinear"
  );

  // Schritt 4: Entferne übriggebliebene doppelte Unterstriche
  baseName = baseName.replace(/__+/g, "_");

  // Schritt 5: Entferne temp_ Prefix (falls vorhanden)
  baseName = baseName.replace(/^temp_/gi, "");

  return baseName;
}

/**
 * Analysiert hochgeladenen Translinear-Text und extrahiert Metadaten für Dateinamen-Generierung
 *
 * STRATEGIE (Fallback-Hierarchie):
 * 1. Metadaten aus Text (## METADATUM: Author=..., Work=...)
 * 2. Dateiname-Analyse (_gr_de_, _lat_en_, _Versmaß_, etc.)
 * 3. Sprach-Erkennung aus Code (EN/DE Zeilen zählen)
 * 4. Work-Kontext (falls auf Werkseite)
 * 5. Generisch (einfach Dateinamen + Suffixe)
 *
 * @param {string} text - Translinear-Text Inhalt
 * @param {string} filename - Original Dateiname (z.B. "Kyklops_gr_de_Versmass_translinear.txt")
 * @returns {object} { author, work, language, hasVersmaß, hasDE, hasEN, confidence }
 */
function analyzeTranslinearText(text, filename) {
  const result = {
    author: null,
    work: null,
    language: null, // 'gr' oder 'lat'
    hasDE: false,
    hasEN: false,
    hasVersmaß: false,
    confidence: "unknown", // 'high', 'medium', 'low', 'unknown'
    source: "none", // 'metadata', 'filename', 'code', 'context', 'generic'
  };

  // SCHRITT 1: Metadaten aus Text extrahieren
  const metaAuthor = text.match(/##\s*METADATUM:\s*Author\s*=\s*(.+?)$/im);
  const metaWork = text.match(/##\s*METADATUM:\s*Work\s*=\s*(.+?)$/im);

  if (metaAuthor || metaWork) {
    result.author = metaAuthor ? metaAuthor[1].trim() : null;
    result.work = metaWork ? metaWork[1].trim() : null;
    result.source = "metadata";
    result.confidence = "high";
  }

  // SCHRITT 2: Dateiname analysieren (ohne .txt Extension)
  const baseFilename = filename.replace(/\.txt$/i, "");

  // Erkenne Sprache aus Dateinamen (_gr_, _lat_)
  if (/_gr[_\.]|^gr_/i.test(baseFilename)) {
    result.language = "gr";
  } else if (/_lat[_\.]|^lat_/i.test(baseFilename)) {
    result.language = "lat";
  }

  // Erkenne Übersetzungs-Sprachen aus Dateinamen
  // WICHTIG: _gr_de_en_ ist 3-sprachig (immer gr_de_en, niemals gr_en_de!)
  // WICHTIG: _gr_de_ oder _gr_en_ ist 2-sprachig
  if (/_gr_de_en[_\.]|_lat_de_en[_\.]/i.test(baseFilename)) {
    result.hasDE = true;
    result.hasEN = true;
    if (result.confidence === "unknown") {
      result.confidence = "medium";
      result.source = "filename";
    }
  } else if (/_gr_de[_\.]|_lat_de[_\.]/i.test(baseFilename)) {
    result.hasDE = true;
    if (result.confidence === "unknown") {
      result.confidence = "medium";
      result.source = "filename";
    }
  } else if (/_gr_en[_\.]|_lat_en[_\.]/i.test(baseFilename)) {
    result.hasEN = true;
    if (result.confidence === "unknown") {
      result.confidence = "medium";
      result.source = "filename";
    }
  }

  // Erkenne Versmaß aus Dateinamen (mehrere Schreibweisen!)
  if (/_(Versmaß|Versmass|versmaß|versmass)[_\.]/i.test(baseFilename)) {
    result.hasVersmaß = true;
  }

  // SCHRITT 3: Code-Analyse (wenn Dateiname keine klare Sprach-Info hat)
  if (!result.hasDE && !result.hasEN) {
    const lines = text.split("\n");
    let deCount = 0;
    let enCount = 0;

    // Zähle Zeilen mit erkennbar deutschen/englischen Wörtern
    // Sampling: Erste 50 Übersetzungs-Zeilen
    let sampleCount = 0;
    for (const line of lines) {
      if (sampleCount >= 50) break;

      // Skip Kommentare, Metadaten, leere Zeilen
      if (
        line.trim().startsWith("#") ||
        line.trim().startsWith("##") ||
        !line.trim()
      ) {
        continue;
      }

      // Skip griechische/lateinische Zeilen (haben meist (Tag) oder Unicode-Greek)
      if (/\(.*\)|[α-ωΑ-Ω]/.test(line)) {
        continue;
      }

      // Deutsche Indizien: der|die|das|und|ist|sein|werden|zu|von
      if (
        /\b(der|die|das|und|ist|sind|sein|war|werden|zu|von|mit|für|auf|dem|den|des)\b/i.test(
          line
        )
      ) {
        deCount++;
        sampleCount++;
        continue;
      }

      // Englische Indizien: the|and|is|are|to|be|of|in|for|with
      if (
        /\b(the|and|is|are|was|were|be|to|of|in|for|with|from|on|at)\b/i.test(
          line
        )
      ) {
        enCount++;
        sampleCount++;
        continue;
      }

      sampleCount++;
    }

    // Wenn genug Samples: Setze Sprachen
    if (sampleCount >= 10) {
      result.hasDE = deCount > 2;
      result.hasEN = enCount > 2;
      if (result.confidence === "unknown") {
        result.confidence = "low";
        result.source = "code";
      }
    }
  }

  // SCHRITT 4: Versmaß aus Code erkennen ({{METER:...}} Marker)
  if (!result.hasVersmaß && /\{\{METER:/i.test(text)) {
    result.hasVersmaß = true;
  }

  return result;
}

function updatePdfView(fromWorker = false) {
  if (state.source === "draft") {
    if (state.draftBuildActive) {
      showDraftWaitingPlaceholder({});
      probeDraftAvailability();
      return;
    }
    if (state.manualDraftBuildRequired && !state.draftHasResult) {
      showDraftManualPlaceholder({});
      return;
    }
    if (!state.draftBase) {
      showDraftEmptyPlaceholder();
      return;
    }
    const draftFilename = buildDraftPdfFilename();
    if (!draftFilename || draftFilename === "error.pdf") {
      showDraftEmptyPlaceholder();
      return;
    }
    const draftUrl = buildDraftPdfUrl(draftFilename);
    state.lastDraftUrl = draftUrl;
    loadPdfIntoRenderer(draftUrl);
    return;
  }

  // Sicherstellen, dass pdfOptions mit state synchronisiert sind
  pdfOptions.strength = state.strength; // "Fett" oder "Normal" (wird später zu GR_Fett/LAT_Fett/Normal aufgelöst)
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
  pdfOptions.strength = state.strength; // "Fett" oder "Normal" (wird später zu GR_Fett/LAT_Fett/Normal aufgelöst)
  pdfOptions.color = state.color || "Colour";
  pdfOptions.tags = state.tags || "Tag";
  // Versmaß-Logik: Verwende state.meter (wurde bereits korrekt gesetzt)
  pdfOptions.meter = state.meter;

  loadPdfIntoRendererDirect(pdfUrl);
}

function escapeHtml(str = "") {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function showPdfPlaceholder(kind, opts = {}) {
  initPdfRenderer();
  const pages = pdfRenderer.elements?.pages;
  pdfRenderer.pdf = null;
  pdfRenderer.currentPage = 1;
  if (pdfRenderer.elements?.pageCount)
    pdfRenderer.elements.pageCount.textContent = "–";
  if (pdfRenderer.elements?.pageNum)
    pdfRenderer.elements.pageNum.textContent = "–";

  if (!pages) return;

  const iconHtml = opts.icon
    ? `<div class="pdf-placeholder-icon">${opts.icon}</div>`
    : "";
  const titleHtml = opts.title ? `<h3>${opts.title}</h3>` : "";
  const messageHtml = opts.message ? `<p>${opts.message}</p>` : "";
  const detailsHtml = opts.details
    ? `<div class="pdf-placeholder-details">${opts.details}</div>`
    : "";

  pages.innerHTML = `
    <div class="pdf-placeholder ${escapeHtml(kind)}">
      ${iconHtml}
      <div class="pdf-placeholder-content">
        ${titleHtml}
        ${messageHtml}
        ${detailsHtml}
      </div>
    </div>
  `;
}

function showDraftWaitingPlaceholder(extra = {}) {
  const filename = extra.filename || state.pendingDraftFilename;
  const url = extra.url || state.lastDraftUrl;
  // Ersetze "birkenbihl" durch "translinear" im Dateinamen
  const displayFilename = filename
    ? filename
        .replace(/_birkenbihl_/g, "_translinear_")
        .replace(/birkenbihl/g, "translinear")
    : "translinear.txt";
  const extraInfo = `
    <p style="margin: 10px 0;">
      <strong>Datei:</strong> <code style="font-size: 0.9em;">${escapeHtml(
        displayFilename
      )}</code>
    </p>
    <p style="margin: 15px 0;">
      <a href="${GH_ACTIONS_URL}" target="_blank" rel="noopener" 
         style="display: inline-block; padding: 8px 16px; background: #2563eb; color: white; 
                text-decoration: none; border-radius: 6px; font-weight: 500;">
        📊 Build-Status live verfolgen
      </a>
    </p>
  `;

  showPdfPlaceholder("draft-waiting", {
    icon: "🚀",
    title: "PDF-Generierung läuft …",
    message:
      "Der Entwurf wurde gespeichert. GitHub erstellt nun alle 8 PDF-Varianten – das dauert meist 1-2 Minuten.",
    details: extraInfo,
  });
}

function showDraftEmptyPlaceholder() {
  showPdfPlaceholder("draft-empty", {
    icon: "📝",
    title: "Noch kein Entwurfs-PDF vorhanden",
    message:
      "Nutzen Sie den grünen Button „PDF aus Entwurf erstellen“, um aus einem neuen Entwurf PDFs zu erstellen. Sobald der PDF-Builder fertig ist, erscheinen sie automatisch in der PDF-Ansicht.",
  });
}

function showDraftManualPlaceholder(extra = {}) {
  const commandValue = extra.command || state.manualDraftCommand || "";
  const command = commandValue
    ? `<code>${escapeHtml(commandValue)}</code>`
    : "";
  showPdfPlaceholder("draft-manual", {
    icon: "🛠️",
    title: "Manuelle PDF-Erstellung erforderlich",
    message:
      "Für diesen Entwurf konnte keine GitHub-Aktion gestartet werden. Führen Sie den folgenden Befehl lokal aus, um die PDFs zu erzeugen und hochzuladen:",
    details: command ? `<p>${command}</p>` : "",
  });
}

function showDraftErrorPlaceholder(extra = {}) {
  const safeMessage = extra.message ? escapeHtml(extra.message) : "";
  const safeUrl = extra.url ? escapeHtml(extra.url) : "";

  const detailsHtml =
    safeMessage || safeUrl
      ? `
    <details style="margin-top: 10px;">
      <summary style="cursor: pointer; color: #6b7280; user-select: none;">Technische Details anzeigen</summary>
      <div style="margin-top: 8px; font-size: 0.85em; color: #9ca3af;">
        ${safeMessage ? `<p><strong>Fehler:</strong> ${safeMessage}</p>` : ""}
        ${
          safeUrl
            ? `<p><strong>URL:</strong> <code style="word-break: break-all;">${safeUrl}</code></p>`
            : ""
        }
      </div>
    </details>
  `
      : "";

  showPdfPlaceholder("draft-error", {
    icon: "⚠️",
    title: "Entwurfs-PDF nicht verfügbar",
    message:
      'Das PDF konnte nicht geladen werden. Bitte warten Sie einen Moment und versuchen Sie es erneut, oder wechseln Sie auf "Original".',
    details: detailsHtml,
  });
}

function showOriginalPdfErrorPlaceholder(extra = {}) {
  const safeMessage = extra.message ? escapeHtml(extra.message) : "";
  const safeUrl = extra.url ? escapeHtml(extra.url) : "";

  const detailsHtml =
    safeMessage || safeUrl
      ? `
    <details style="margin-top: 10px;">
      <summary style="cursor: pointer; color: #6b7280; user-select: none;">Technische Details anzeigen</summary>
      <div style="margin-top: 8px; font-size: 0.85em; color: #9ca3af;">
        ${safeMessage ? `<p><strong>Fehler:</strong> ${safeMessage}</p>` : ""}
        ${
          safeUrl
            ? `<p><strong>URL:</strong> <code style="word-break: break-all;">${safeUrl}</code></p>`
            : ""
        }
      </div>
    </details>
  `
      : "";

  showPdfPlaceholder("pdf-error", {
    icon: "⚠️",
    title: "Original-PDF nicht verfügbar",
    message:
      'Das PDF konnte nicht geladen werden. Bitte nutzen Sie "PDF in neuem Tab öffnen" oder laden Sie die Seite neu.',
    details: detailsHtml,
  });
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

  // Setze den Browser-Tab-Titel auf den Werknamen
  if (state.work) {
    document.title = state.work;
  }

  // Der Pfad aus dem Katalog ist der vollständige relative Pfad mit Sprachebene.
  // z.B. "griechisch/poesie/Aischylos/Der_gefesselte_Prometheus"
  const textBasePath = state.workMeta.path; // Bereits vollständig
  const filenameBase = state.workMeta.filename_base;

  console.log("Loading texts from:", textBasePath, "filename:", filenameBase);

  // Original (nur laden, wenn der Pane existiert - ist aktuell auskommentiert)
  if (el.origText) {
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
  } else {
    console.log("Original text pane is not active, skipping load");
  }

  try {
    const birkenbihlCandidates = buildBirkenbihlBaseCandidates(filenameBase);
    const result = await fetchBirkenbihlText(
      textBasePath,
      birkenbihlCandidates
    );

    if (result && result.text) {
      const text = result.text;
      state.originalBirkenbihlText = text;

      // WICHTIG: Speichere den TATSÄCHLICH geladenen Dateinamen-Base für Entwurf-Downloads!
      // result.base enthält z.B. "agamemnon_gr_en_stil1_Versmaß" (ohne _birkenbihl.txt)
      // Dies ist die korrekte Sprach-Kombination der geladenen Datei!
      state.loadedBirkenbihlBase = result.base;

      console.log("✅ Birkenbihl text loaded from", result.path);
      console.log("✅ Loaded base filename:", result.base);

      // Versuche, gespeicherten Draft-Text aus localStorage zu laden
      const workKey = `${state.lang}_${state.kind}_${state.category}_${state.author}_${state.work}`;
      const savedDraft = localStorage.getItem(`draft_${workKey}`);

      if (el.draftText) {
        if (savedDraft) {
          console.log("✅ Gespeicherter Draft-Text wiederhergestellt");
          el.draftText.innerHTML = addSpansToTags(savedDraft);
        } else {
          el.draftText.innerHTML = addSpansToTags(text);
        }
      }
      if (el.birkenbihlText) {
        el.birkenbihlText.innerHTML = addSpansToTags(text);
      }
    } else {
      const attempted = birkenbihlCandidates.join(", ");
      const errMsg = `Birkenbihl-Text nicht gefunden (Versuch: ${attempted})`;
      console.error("❌", errMsg);
      if (el.draftText) {
        el.draftText.textContent = errMsg;
      }
    }
  } catch (e) {
    console.error("❌ Error loading birkenbihl text:", e);
    if (el.draftText) {
      el.draftText.textContent = "Fehler beim Laden des Birkenbihl-Textes.";
    }
  }
}

// 8) Entwurfs-System
async function initializeDraftText() {
  // Der Birkenbihl-Text wird bereits in loadTexts() in el.draftText geladen
  // Diese Funktion prüft nur, ob der Text erfolgreich geladen wurde
  if (
    el.draftText &&
    el.draftText.textContent &&
    el.draftText.textContent.trim()
  ) {
    console.log("Draft text already loaded, skipping initialization");

    // Event-Listener für Auto-Save hinzufügen
    setupDraftAutoSave();
    return;
  }

  // Fallback: Lade aus state.originalBirkenbihlText, falls noch nicht geladen
  if (state.originalBirkenbihlText) {
    el.draftText.innerHTML = addSpansToTags(state.originalBirkenbihlText);
    console.log("Draft text initialized from state");
  } else {
    el.draftText.textContent = "Fehler: Birkenbihl-Text nicht verfügbar.";
    console.error("Birkenbihl text not available in state");
  }

  // Event-Listener für Auto-Save hinzufügen
  setupDraftAutoSave();
}

function setupDraftAutoSave() {
  if (!el.draftText || el.draftText.dataset.autoSaveSetup) return;

  // Markiere, dass Auto-Save bereits eingerichtet ist
  el.draftText.dataset.autoSaveSetup = "true";

  let saveTimeout;
  el.draftText.addEventListener("input", () => {
    // Debounce: Speichere erst nach 1 Sekunde Inaktivität
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => {
      const workKey = `${state.lang}_${state.kind}_${state.category}_${state.author}_${state.work}`;
      const draftContent = el.draftText.textContent || "";
      localStorage.setItem(`draft_${workKey}`, draftContent);
      console.log("💾 Draft auto-saved");
    }, 1000);
  });

  console.log("✅ Draft auto-save eingerichtet");
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

  // NEUE ARCHITEKTUR: Entkopplung von PFAD und NAME
  // - PFAD: Von der Werkseite (state.workMeta.path) → für Ordnerstruktur
  // - NAME: Vom Upload/Analysis → für Dateiname

  // STRATEGIE für releaseBase (NAME-Komponente):
  // 1. state.uploadBase (wenn Datei hochgeladen wurde)
  // 2. Analysiere Text-Inhalt (author + work extrahieren)
  // 3. Generiere aus state.loadedBirkenbihlBase (eingebetteter Entwurf)
  // 4. Fallback: buildReleaseBase() (Work-Kontext)

  let releaseBase;
  let useWorkPagePath = false; // Flag: Soll Work-Page-Pfad verwendet werden?

  if (state.uploadBase) {
    // FALL 1: Datei wurde hochgeladen → Nutze Upload-Basis für NAME
    console.log("🎯 Nutze Upload-Basis für PDF-Namen:", state.uploadBase);
    releaseBase = state.uploadBase;
    useWorkPagePath = true; // Pfad von Work-Page verwenden
  } else {
    // FALL 2: Kein Upload → Analysiere Text-Inhalt
    // Extrahiere Autor/Werk aus Text (## METADATUM: Author/Work)
    const analysis = analyzeTranslinearText(draftText, "draft.txt");

    if (
      analysis.author &&
      analysis.work &&
      (analysis.hasDE || analysis.hasEN)
    ) {
      // Text hat Metadaten → Baue Namen daraus
      const author = analysis.author.replace(/\s+/g, "_");
      const work = analysis.work.replace(/\s+/g, "_");

      // KRITISCHER FIX: Verwende AKTUELLE target-Einstellung, NICHT aus analysis!
      // Wenn User target=en hat, soll Dateiname "gr_en" sein, NICHT "gr_de_en"!
      let langs = "";
      if (analysis.language) {
        // Prüfe AKTUELLE Zielsprache aus state.target
        const currentTarget = state.target || "de"; // Default: Deutsch

        if (analysis.hasDE && analysis.hasEN) {
          // Text hat beide Sprachen → verwende AKTUELLE Zielsprache!
          if (currentTarget === "en") {
            langs = `${analysis.language}_en`;
          } else {
            langs = `${analysis.language}_de`;
          }
        } else if (analysis.hasDE) {
          langs = `${analysis.language}_de`;
        } else if (analysis.hasEN) {
          langs = `${analysis.language}_en`;
        }
      }

      // KRITISCHER FIX: Verwende AKTUELLE meter-Einstellung, NICHT aus analysis!
      // analysis.hasVersmaß sagt nur OB das Werk Versmaß HAT, nicht ob User es AKTIV hat!
      const versmaßSuffix = needsVersmassRendering() ? "_Versmass" : "";
      releaseBase = `${author}_${work}_${langs}${versmaßSuffix}`;
      useWorkPagePath = true; // Pfad von Work-Page verwenden

      console.log("📝 Generiere Release-Base aus Text-Analyse:", {
        author: analysis.author,
        work: analysis.work,
        currentTarget: state.target,
        langs,
        versmaßSuffix,
        meterActive: needsVersmassRendering(),
        releaseBase,
      });
    } else if (state.loadedBirkenbihlBase) {
      // FALL 3: Eingebetteter Entwurf → Generiere aus loadedBirkenbihlBase
      const author = state.author || "";
      const work = state.work || "";

      // Extrahiere Sprach-Segment und Versmaß aus loadedBirkenbihlBase
      const loadedBase = state.loadedBirkenbihlBase;
      const langMatch = loadedBase.match(/_(gr|lat)_(de_en|en|de)(?:_stil1)?/);
      const hasVersmaß = loadedBase.match(/_[Vv]ersm[aä][sß]{1,2}/);

      if (langMatch) {
        const langs = `${langMatch[1]}_${langMatch[2]}`;
        const versmaßSuffix = hasVersmaß ? "_Versmass" : "";
        releaseBase = `${author}_${work}_${langs}${versmaßSuffix}`;
        console.log("📝 Generiere Release-Base aus loadedBirkenbihlBase:", {
          loadedBase,
          langs,
          versmaßSuffix,
          releaseBase,
        });
      } else {
        // Fallback: Kann Sprache nicht extrahieren, nutze Work-Kontext
        releaseBase = buildReleaseBase();
        console.warn(
          "⚠️ Konnte Sprache nicht aus loadedBirkenbihlBase extrahieren, nutze Work-Kontext"
        );
      }
    } else {
      // FALL 4: Fallback → Nutze Work-Kontext
      releaseBase = buildReleaseBase();
      if (!releaseBase) {
        el.draftStatus.textContent =
          "Metadaten fehlen – bitte laden Sie die Seite neu.";
        return;
      }
      console.log("📄 Nutze Work-Basis für PDF-Namen (Fallback):", releaseBase);
    }
  }

  state.draftBase = releaseBase;
  persistDraftBase();

  // NEU: Extrahiere Pfad-Prefix separat vom Namen
  // Der releaseBase kann format haben: "GR_poesie_Drama_Autor_Werk__dateiname_gr_de"
  // Wir trennen das auf in:
  // - pathPrefix: "GR_poesie_Drama_Autor_Werk" (für Ordnerstruktur in PDFs)
  // - releaseName: "dateiname_gr_de" (für PDF-Dateinamen)

  let pathPrefix = "";
  let releaseName = releaseBase;

  if (releaseBase.includes("__")) {
    // Format: "prefix__name" → Trenne
    const parts = releaseBase.split("__");
    pathPrefix = parts[0]; // Alles vor "__"
    releaseName = parts.slice(1).join("__"); // Alles nach "__" (falls mehrere __)
    console.log("🔧 Trenne Pfad-Prefix vom Namen:", {
      releaseBase,
      pathPrefix,
      releaseName,
    });
  } else {
    // Kein "__" → Baue Pfad-Prefix aus Work-Kontext
    if (state.workMeta?.meta_prefix) {
      pathPrefix = state.workMeta.meta_prefix;
      console.log("🔧 Verwende meta_prefix als Pfad-Prefix:", pathPrefix);
    }
  }

  // Erstelle eine Blob-Datei aus dem Editor-Inhalt
  const blob = new Blob([draftText], { type: "text/plain" });
  const uploadFilename = buildDraftUploadFilename();
  const file = new File([blob], uploadFilename, {
    type: "text/plain",
  });

  el.draftStatus.textContent = "Rendere Entwurf...";
  state.draftBuildActive = true;
  state.draftHasResult = false;
  state.manualDraftBuildRequired = false;
  state.pendingDraftFilename = null;

  // Erweiterte Optionen mit Tag-Konfiguration
  const payload = {
    kind: state.kind, // poesie | prosa
    author: state.author, // Ordnername
    work: state.work, // Werk-ID (nur informativ)
    strength: state.strength, // "Fett" | "Normal" (wird im Worker zu GR_Fett/LAT_Fett/Normal aufgelöst)
    color_mode: state.color, // Colour | BlackWhite
    tag_mode: state.tags === "Tag" ? "TAGS" : "NO_TAGS",
    versmass: state.meterSupported && state.meter === "with" ? "ON" : "OFF",
    hide_pipes: pdfOptions.hidePipes, // Pipes (|) in Übersetzungen verstecken

    // Die gesamte, neue Tag-Konfiguration wird gesendet
    tag_config: state.tagConfig,
  };

  const form = new FormData();
  form.append("file", file, file.name);
  form.append("work", state.work.trim());
  form.append("filename", file.name);
  form.append("kind", state.kind.trim());
  form.append("author", state.author.trim());
  form.append("language", state.lang.trim());
  form.append("category", (state.category || "").trim());
  if (state.workMeta?.path) {
    form.append("work_path", state.workMeta.path);
  }
  // NEU: Sende path_prefix und release_name separat (statt kombiniert als release_base)
  if (pathPrefix) {
    form.append("path_prefix", pathPrefix);
  }
  form.append("release_name", releaseName);
  // DEPRECATED: release_base wird nicht mehr verwendet (durch path_prefix + release_name ersetzt)
  // Aber für Kompatibilität mit älteren Versionen noch senden
  form.append("release_base", releaseBase);
  form.append("translation_target", state.translationTarget);
  form.append("versmass", needsVersmassRendering() ? "true" : "false");
  form.append("meter_mode", state.meter === "with" ? "with" : "without");
  form.append("hide_pipes", pdfOptions.hidePipes ? "true" : "false");

  // Tag-Konfiguration als JSON hinzufügen
  form.append("tag_config", JSON.stringify(payload.tag_config));

  try {
    // Nur eine Anfrage an /draft - das ist der korrekte Endpoint
    const res = await fetch(`${WORKER_BASE}/draft`, {
      method: "POST",
      body: form,
      mode: "cors",
      credentials: "include", // WICHTIG: Cookies senden/empfangen
    });

    if (!res || !res.ok) {
      // Spezielle Behandlung für HTTP 413 (Payload Too Large)
      if (res && res.status === 413) {
        throw new Error(
          `Ihr translinear.txt ist zu groß (>975 KB). ` +
            `Nicht alle 8 PDF-Varianten können erzeugt werden. ` +
            `Die wichtigsten Varianten werden trotzdem erstellt. ` +
            `Bitte verwenden Sie einen gekürzten translinear.txt, ` +
            `falls Sie alle Varianten erzeugen wollen.`
        );
      }
      throw new Error(`Worker request failed with status ${res.status}`);
    }

    const data = await res.json();
    if (!data?.ok) throw new Error("Worker-Antwort unvollständig.");

    // WICHTIG: Session-ID speichern (für spätere Requests)
    if (data.session_id) {
      sessionStorage.setItem("birkenbihl_session", data.session_id);
      console.log("Session-ID gespeichert:", data.session_id);
    }

    const releaseBaseFromWorker = normalizeReleaseBase(
      data.release_base || null
    );
    const draftBaseFromWorker = (data.filename || "").replace(/\.txt$/, "");
    if (releaseBaseFromWorker) {
      state.draftBase = releaseBaseFromWorker;
      state.draftHasResult = false;
      persistDraftBase();
    } else if (draftBaseFromWorker) {
      state.draftBase = normalizeReleaseBase(draftBaseFromWorker);
      state.draftHasResult = false;
      persistDraftBase();
    }

    const draftFilePath = getDraftTextAbsolutePath(data.filename);
    const manualCommand = `python build_${state.kind}_drafts_adapter.py ${draftFilePath}`;
    const buildActive = !!data.workflow_triggered;
    const manualRequired = !buildActive;
    const draftPdfName = buildDraftPdfFilename();
    const draftPdfUrl = buildDraftPdfUrl(draftPdfName);

    state.source = "draft";
    state.lastDraftUrl = draftPdfUrl;
    state.pendingDraftFilename = data.filename;
    persistPendingDraftFilename(); // Speichere Filename persistent
    state.draftBuildActive = buildActive;
    state.draftHasResult = false;
    state.manualDraftBuildRequired = manualRequired;
    state.manualDraftCommand = manualRequired ? manualCommand : null;

    // KRITISCHER FIX: Display-Name OHNE SESSION und DRAFT für bessere UX!
    // User soll nur sehen: "Autor_Werk_gr_de_Versmass_translinear.txt"
    // NICHT: "..._SESSION_xxx_DRAFT_yyy.txt" (das ist nur intern!)
    let displayName = data.filename
      .replace(/_birkenbihl_/g, "_translinear_")
      .replace(/birkenbihl/g, "translinear");

    // Entferne SESSION und DRAFT aus dem Anzeige-Namen (aber NICHT aus data.filename!)
    // Beispiel: "Autor_Werk_gr_de_Versmass_translinear_SESSION_xxx_DRAFT_yyy.txt"
    // → "Autor_Werk_gr_de_Versmass_translinear.txt"
    displayName = displayName.replace(
      /_SESSION_[a-f0-9]+_DRAFT_\d{8}_\d{6}/g,
      ""
    );

    el.draftStatus.textContent = `✓ Text gespeichert: ${displayName}`;

    if (buildActive) {
      el.draftStatus.textContent = `✓ Text gespeichert: ${displayName} – PDFs werden gleich angezeigt.`;
      showDraftWaitingPlaceholder({
        filename: data.filename,
        url: draftPdfUrl,
      });
    } else {
      el.draftStatus.innerHTML = `
          <div style="color: #059669; font-weight: bold;">
          ✓ Text gespeichert: ${displayName}
          </div>
        <div style="color: #dc2626; margin-top: 6px;">
          Bitte lokal ausführen:<br>
          <code style="background: #f3f4f6; padding: 2px 4px; border-radius: 3px; display: inline-block; margin-top: 4px;">
            ${manualCommand}
            </code>
          </div>
        `;
      showDraftManualPlaceholder({ command: manualCommand });
    }

    updatePdfView(true);
  } catch (e) {
    console.error("Draft submit error:", e);
    state.draftBuildActive = false;
    state.pendingDraftFilename = null;
    state.manualDraftBuildRequired = false;
    state.manualDraftCommand = null;
    state.draftHasResult = false;
    if (
      e.message &&
      (e.message.includes("CORS") ||
        e.message.includes("Cross-Origin") ||
        e.message.includes("NetworkError"))
    ) {
      el.draftStatus.textContent =
        "CORS-Fehler: Worker nicht erreichbar. Bitte versuchen Sie es auf der GitHub-Seite (https://klemptobias-oss.github.io/Antike-Translinear/).";
    } else {
      el.draftStatus.textContent = `Fehler beim PDF-Erstellen: ${
        e.message || "Unbekannter Fehler"
      }`;
      console.error("Draft submit stack:", e.stack);
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
    { type: "color", value: "violett", label: "violett" },
    { type: "hide", value: "hide", label: "Tag nicht zeigen" },
    {
      type: "translation",
      value: "translation",
      label: "Übersetzung ausblenden",
    },
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
  // 0. Setze dynamische Überschriften basierend auf Sprache und Typ
  const langName = state.lang === "latein" ? "Latein" : "Griechisch";
  const typeName = state.kind === "poesie" ? "Poesie" : "Prosa";

  const mainTitle = document.getElementById("modal-main-title");
  const subtitle = document.getElementById("modal-subtitle");

  if (mainTitle) {
    mainTitle.textContent = "PDF Builder";
  }
  if (subtitle) {
    subtitle.textContent = `${langName} ${typeName}: Tag- und Farbkonfiguration`;
  }

  // 1. Lade gespeicherte Tag-Konfiguration aus localStorage (falls vorhanden)
  const langKey = state.lang; // "griechisch" oder "latein"
  const savedConfig = localStorage.getItem(`tagConfig_${langKey}`);
  if (savedConfig) {
    try {
      state.tagConfig = JSON.parse(savedConfig);
      console.log(
        `✅ Tag-Konfiguration für ${langKey} aus localStorage geladen`
      );
    } catch (e) {
      console.error("❌ Fehler beim Laden der Tag-Konfiguration:", e);
      state.tagConfig = {};
    }
  }

  // ESC-Taste schließt Dialog
  function escHandler(e) {
    if (e.key === "Escape" || e.key === "Esc") {
      hideTagConfigModal();
      document.removeEventListener("keydown", escHandler);
    }
  }
  document.addEventListener("keydown", escHandler);

  // 2. Container für kleine Tabellen leeren
  const tablesContainer = document.getElementById("tag-config-tables");
  if (!tablesContainer) return;

  // Container leeren
  tablesContainer.innerHTML = "";

  // 3. Für jede Gruppe eine eigene Tabelle erstellen
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
          <th>violett</th>
          <th>Tag nicht<br />zeigen</th>
          <th>Übersetzung<br />ausblenden</th>
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
        <th>violett</th>
        <th>Tag nicht<br />zeigen</th>
        <th>Übersetzung<br />ausblenden</th>
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

  if (el.toggleTranslationsHiddenBtn) {
    el.toggleTranslationsHiddenBtn.removeEventListener(
      "click",
      toggleAllTranslationsHidden
    );
    el.toggleTranslationsHiddenBtn.addEventListener(
      "click",
      toggleAllTranslationsHidden
    );
  }

  if (el.togglePipesHiddenBtn) {
    el.togglePipesHiddenBtn.removeEventListener("click", togglePipesHidden);
    el.togglePipesHiddenBtn.addEventListener("click", togglePipesHidden);

    // Lade gespeicherten State aus localStorage
    const workKey = `${state.lang}_${state.kind}_${state.category}_${state.author}_${state.work}`;
    const savedHidePipes = localStorage.getItem(`hidePipes_${workKey}`);
    if (savedHidePipes !== null) {
      pdfOptions.hidePipes = JSON.parse(savedHidePipes);
      // Aktualisiere Button-State
      if (pdfOptions.hidePipes) {
        el.togglePipesHiddenBtn.dataset.state = "on";
        const status = el.togglePipesHiddenBtn.querySelector(".toggle-status");
        if (status) {
          status.textContent = "An";
          status.classList.remove("red");
          status.classList.add("green");
        }
      } else {
        el.togglePipesHiddenBtn.dataset.state = "off";
        const status = el.togglePipesHiddenBtn.querySelector(".toggle-status");
        if (status) {
          status.textContent = "Aus";
          status.classList.remove("green");
          status.classList.add("red");
        }
      }
    }
  }

  // 6. Modal anzeigen
  el.modal.style.display = "flex";

  // Register modal for ESC key handler
  if (el.modal && typeof window.setTagConfigOpen === "function") {
    window.setTagConfigOpen(el.modal);
  }
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

  // Partizipien -> violett
  const partizipGroup = tagConfigDefinition.find(
    (g) => g.leader?.id === "partizip"
  );
  if (partizipGroup?.leader?.tag) {
    state.tagConfig[partizipGroup.leader.id] = {
      ...state.tagConfig[partizipGroup.leader.id],
      color: "violett",
    };
  }
  partizipGroup?.members.forEach((m) => {
    state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "violett" };
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

  // Lateinische Verbformen -> violett (nur für Latein)
  if (state.lang === "latein") {
    // Gerundium -> violett
    const gerundiumGroup = tagConfigDefinition.find(
      (g) => g.leader?.id === "gerundium"
    );
    if (gerundiumGroup?.leader?.tag) {
      state.tagConfig[gerundiumGroup.leader.id] = {
        ...state.tagConfig[gerundiumGroup.leader.id],
        color: "violett",
      };
    }
    gerundiumGroup?.members.forEach((m) => {
      state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "violett" };
    });

    // Gerundivum -> violett
    const gerundivumGroup = tagConfigDefinition.find(
      (g) => g.leader?.id === "gerundivum"
    );
    if (gerundivumGroup?.leader?.tag) {
      state.tagConfig[gerundivumGroup.leader.id] = {
        ...state.tagConfig[gerundivumGroup.leader.id],
        color: "violett",
      };
    }
    gerundivumGroup?.members.forEach((m) => {
      state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "violett" };
    });

    // Supinum -> violett
    const supinumGroup = tagConfigDefinition.find(
      (g) => g.leader?.id === "supinum"
    );
    if (supinumGroup?.leader?.tag) {
      state.tagConfig[supinumGroup.leader.id] = {
        ...state.tagConfig[supinumGroup.leader.id],
        color: "violett",
      };
    }
    supinumGroup?.members.forEach((m) => {
      state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "violett" };
    });
  }

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
        if (type === "translation" && config.hideTranslation) cb.checked = true;
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
        "color-bg-violett"
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

    if (updateType === "translation") {
      if (isChecked) currentConfig.hideTranslation = true;
      else delete currentConfig.hideTranslation;
      return;
    }

    // WICHTIG: Für "hide" immer true/false setzen, nicht den String-Wert
    if (updateType === "hide") {
      if (isChecked) {
        currentConfig.hide = true; // Immer true, nicht "hide"
      } else {
        delete currentConfig.hide;
      }
      return;
    }

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

  // Speichere Tag-Konfiguration in localStorage (pro Sprache)
  const langKey = state.lang; // "griechisch" oder "latein"
  localStorage.setItem(`tagConfig_${langKey}`, JSON.stringify(state.tagConfig));
  console.log(`💾 Tag-Konfiguration für ${langKey} gespeichert`);
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
          violett: "#9370DB", // Sanftes Violett (Medium Purple)
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
        color: "violett",
      };
    }
    partizipGroup?.members.forEach((m) => {
      state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "violett" };
    });

    // Lateinische Verbformen -> violett (nur für Latein)
    if (state.lang === "latein") {
      const gerundiumGroup = tagConfigDefinition.find(
        (g) => g.leader?.id === "gerundium"
      );
      if (gerundiumGroup?.leader?.tag) {
        state.tagConfig[gerundiumGroup.leader.id] = {
          ...state.tagConfig[gerundiumGroup.leader.id],
          color: "violett",
        };
      }
      gerundiumGroup?.members.forEach((m) => {
        state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "violett" };
      });

      const gerundivumGroup = tagConfigDefinition.find(
        (g) => g.leader?.id === "gerundivum"
      );
      if (gerundivumGroup?.leader?.tag) {
        state.tagConfig[gerundivumGroup.leader.id] = {
          ...state.tagConfig[gerundivumGroup.leader.id],
          color: "violett",
        };
      }
      gerundivumGroup?.members.forEach((m) => {
        state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "violett" };
      });

      const supinumGroup = tagConfigDefinition.find(
        (g) => g.leader?.id === "supinum"
      );
      if (supinumGroup?.leader?.tag) {
        state.tagConfig[supinumGroup.leader.id] = {
          ...state.tagConfig[supinumGroup.leader.id],
          color: "violett",
        };
      }
      supinumGroup?.members.forEach((m) => {
        state.tagConfig[m.id] = { ...state.tagConfig[m.id], color: "violett" };
      });
    }

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

function toggleAllTranslationsHidden() {
  const turnOn = toggleButton(el.toggleTranslationsHiddenBtn);
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
      state.tagConfig[id].hideTranslation = true;
    } else {
      delete state.tagConfig[id].hideTranslation;
    }
  });
  updateTableFromState();
}

function togglePipesHidden() {
  const turnOn = toggleButton(el.togglePipesHiddenBtn);
  pdfOptions.hidePipes = turnOn;
  // Speichere in localStorage für Persistenz
  const workKey = `${state.lang}_${state.kind}_${state.category}_${state.author}_${state.work}`;
  localStorage.setItem(`hidePipes_${workKey}`, JSON.stringify(turnOn));
}

function hideTagConfigModal() {
  if (el.modal) el.modal.style.display = "none";
  // Clear ESC key handler registration
  if (typeof window.clearTagConfigOpen === "function") {
    window.clearTagConfigOpen();
  }
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
        const uploadedText = e.target.result;
        el.draftText.innerHTML = addSpansToTags(uploadedText);
        el.draftStatus.textContent = `Datei ${file.name} geladen.`;

        // WICHTIG: Analysiere hochgeladenen Text für intelligente Namensbildung
        const analysis = analyzeTranslinearText(uploadedText, file.name);
        console.log("📊 Translinear-Analyse:", analysis);

        // Speichere Analyse im State für spätere Verwendung
        state.uploadAnalysis = analysis;
        state.uploadFilename = file.name;

        // STRATEGIE: Baue draftBase basierend auf Upload-Analyse
        // Falls hochgeladen: Verwende Upload-Dateinamen als Basis (nicht Work-Kontext!)
        // Dies stellt sicher, dass PDFs korrekt benannt werden

        // Extrahiere Basis-Namen (ohne .txt und _translinear)
        let uploadBase = file.name
          .replace(/\.txt$/i, "")
          .replace(/_translinear$/i, "");

        // Falls der hochgeladene Text Metadaten hat (hohe Konfidenz), nutze diese
        if (
          analysis.confidence === "high" &&
          analysis.author &&
          analysis.work
        ) {
          // Nutze Metadaten für konsistente Benennung
          const author = analysis.author.replace(/\s+/g, "_");
          const work = analysis.work.replace(/\s+/g, "_");

          // Baue Sprach-Suffix
          let langSuffix = "";
          if (analysis.hasDE && analysis.hasEN) {
            langSuffix =
              analysis.language === "lat" ? "_lat_de_en" : "_gr_de_en";
          } else if (analysis.hasDE) {
            langSuffix = analysis.language === "lat" ? "_lat_de" : "_gr_de";
          } else if (analysis.hasEN) {
            langSuffix = analysis.language === "lat" ? "_lat_en" : "_gr_en";
          } else {
            langSuffix = analysis.language === "lat" ? "_lat" : "_gr";
          }

          // Versmaß-Suffix
          const versmaßSuffix = analysis.hasVersmaß ? "_Versmaß" : "";

          uploadBase = `${author}_${work}${langSuffix}${versmaßSuffix}`;
          console.log("✨ Nutze Metadaten für Basis:", uploadBase);
        } else {
          // Fallback: Nutze Upload-Dateinamen (robust, keine Annahmen!)
          console.log("📝 Nutze Upload-Dateinamen als Basis:", uploadBase);
        }

        // Setze draftBase (wird später mit Timestamp/Variant kombiniert)
        // Format: uploadBase (ohne _translinear, das wird später hinzugefügt)
        state.uploadBase = uploadBase;

        console.log("💾 Upload verarbeitet - Basis:", state.uploadBase);

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
    // Lösche gespeicherten Draft aus localStorage
    const workKey = `${state.lang}_${state.kind}_${state.category}_${state.author}_${state.work}`;
    localStorage.removeItem(`draft_${workKey}`);
    console.log("✅ Gespeicherter Draft gelöscht");

    // Lade Original-Text
    if (state.originalBirkenbihlText && el.draftText) {
      el.draftText.innerHTML = addSpansToTags(state.originalBirkenbihlText);
      el.draftStatus.textContent = "Entwurf zurückgesetzt.";
      console.log("✅ Original-Text wiederhergestellt");
    }

    el.resetDraftModal.style.display = "none";
  });

  // Entwurfs-Text Auto-Save (optional)
  el.draftText?.addEventListener("input", () => {
    el.draftStatus.textContent = "Entwurf geändert. Bereit zum Rendern.";
    state.draftHasResult = false;
    state.draftBuildActive = false;
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

// Funktion zum Laden der Werk-Metadaten aus dem Katalog
async function loadWorkMeta() {
  try {
    const cat = await loadCatalog();
    state.workMeta = getWorkMeta(
      cat,
      state.lang,
      state.kind,
      state.category,
      state.author,
      state.work
    );

    if (!state.workMeta) {
      throw new Error("Werk nicht im Katalog gefunden.");
    }

    if (!state.draftBase) {
      const inferredBase = buildReleaseBase();
      if (inferredBase) {
        state.draftBase = normalizeReleaseBase(inferredBase);
        persistDraftBase();
      }
    } else {
      state.draftBase = normalizeReleaseBase(state.draftBase);
    }

    state.meterSupported = state.workMeta.versmass; // true/false (ob Versmaß-PDFs existieren)
    state.meterPageActive =
      state.meterMode === "true" && state.meterSupported === true;

    // Setze strength auf "Fett" als Standard (wird später zu GR_Fett/LAT_Fett aufgelöst)
    if (!state.strength) {
      state.strength = "Fett";
      console.log("Strength automatisch gesetzt auf:", state.strength);
    }

    // Titel setzen
    el.pageTitle.textContent = `${
      state.workMeta.author_display || state.author
    } – ${state.workMeta.title || state.work}`;

    // UI-Elemente basierend auf Metadaten aktualisieren
    // Versmaß-Buttons nur anzeigen, wenn wir auf einer Versmaß-Seite sind (meterMode === "true")
    const showMeterControls = state.meterPageActive;

    if (el.meterRow) {
      el.meterRow.style.display = showMeterControls ? "" : "none";
    }

    if (el.grammarTagsBtn) {
      el.grammarTagsBtn.style.display = showMeterControls ? "" : "none";
    }

    // Metrum-Marker Buttons ein-/ausblenden (nur auf Versmaß-Seiten)
    const birkenbihlMetrumBtn = document.getElementById(
      "toggleBirkenbihlMetrum"
    );
    const draftMetrumBtn = document.getElementById("toggleDraftMetrum");

    if (birkenbihlMetrumBtn) {
      if (showMeterControls) {
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
      if (showMeterControls) {
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
      meterGroup.style.display = showMeterControls ? "" : "none";
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
    const birkenbihlMetrumBtnFallback = document.getElementById(
      "toggleBirkenbihlMetrum"
    );
    const draftMetrumBtnFallback = document.getElementById("toggleDraftMetrum");

    if (birkenbihlMetrumBtnFallback) {
      birkenbihlMetrumBtnFallback.style.display = "none";
    }
    if (draftMetrumBtnFallback) {
      draftMetrumBtnFallback.style.display = "none";
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
}

// Hauptinitialisierung
(async function init() {
  console.log("work.js init started");

  restoreDraftBase();

  // Warten, bis DOM geladen ist
  if (document.readyState === "loading") {
    await new Promise((resolve) => {
      document.addEventListener("DOMContentLoaded", resolve);
    });
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

        // Extrahiere Sprach-Infos aus dem originalen Dateinamen
        // z.B. "werkeundtage_gr_de_en_stil1_Versmass_birkenbihl.txt"
        const author = state.author || "";
        const work = state.work || "";

        // Erkenne Sprach-Kombination aus filenameBase
        let langSuffix = "";
        if (
          filenameBase.includes("_gr_de_en_") ||
          filenameBase.includes("_gr_de_en")
        ) {
          langSuffix = "_gr_de_en";
        } else if (
          filenameBase.includes("_lat_de_en_") ||
          filenameBase.includes("_lat_de_en")
        ) {
          langSuffix = "_lat_de_en";
        } else if (
          filenameBase.includes("_gr_de_") ||
          filenameBase.includes("_gr_de")
        ) {
          langSuffix = "_gr_de";
        } else if (
          filenameBase.includes("_gr_en_") ||
          filenameBase.includes("_gr_en")
        ) {
          langSuffix = "_gr_en";
        } else if (
          filenameBase.includes("_lat_de_") ||
          filenameBase.includes("_lat_de")
        ) {
          langSuffix = "_lat_de";
        } else if (
          filenameBase.includes("_lat_en_") ||
          filenameBase.includes("_lat_en")
        ) {
          langSuffix = "_lat_en";
        }

        // Erkenne Versmaß aus filenameBase
        let versmassSuffix = "";
        if (filenameBase.match(/_[Vv]ersm[aä][sß]{1,2}/)) {
          versmassSuffix = "_Versmass";
        }

        // Baue schönen Dateinamen: Autor_Werk_Sprache_[Versmass]_translinear.txt
        const filename = `${author}_${work}${langSuffix}${versmassSuffix}_translinear.txt`;

        const a = document.createElement("a");
        a.href = birkenbihlUrl;
        a.download = filename;
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

        // WICHTIG: Nutze den TATSÄCHLICH geladenen Birkenbihl-Text-Base!
        // state.loadedBirkenbihlBase enthält z.B. "agamemnon_gr_en_stil1_Versmaß"
        // Dies ist die korrekte Sprach-Kombination der geladenen Datei!
        const author = state.author || "";
        const work = state.work || "";

        // Extrahiere Sprach-Segment aus dem geladenen Base
        // Regex: _(gr|lat)_(de_en|en|de)(?:_stil1)?
        let langs = "";
        let versmassSuffix = "";

        if (state.loadedBirkenbihlBase) {
          // PERFEKT! Wir haben den tatsächlich geladenen Dateinamen
          const loadedBase = state.loadedBirkenbihlBase;

          const langMatch = loadedBase.match(
            /_(gr|lat)_(de_en|en|de)(?:_stil1)?/
          );
          if (langMatch) {
            langs = `${langMatch[1]}_${langMatch[2]}`;
          }

          // Versmaß aus geladenem Base extrahieren
          if (loadedBase.match(/_[Vv]ersm[aä][sß]{1,2}/)) {
            versmassSuffix = "_Versmass";
          }
        } else {
          // Fallback 1: Versuche filenameBase aus Metadaten
          if (filenameBase) {
            const langMatch = filenameBase.match(
              /_(gr|lat)_(de_en|en|de)(?:_stil1)?/
            );
            if (langMatch) {
              langs = `${langMatch[1]}_${langMatch[2]}`;
            }
            if (filenameBase.match(/_[Vv]ersm[aä][sß]{1,2}/)) {
              versmassSuffix = "_Versmass";
            }
          }

          // Fallback 2: Nutze URL-Parameter
          if (!langs) {
            const lang =
              state.lang === "griechisch"
                ? "gr"
                : state.lang === "latein"
                ? "lat"
                : state.lang;
            langs = `${lang}_de`;
            if (state.languages === 3) {
              langs += "_en";
            }
          }
        }

        const filename = `${author}_${work}_${langs}${versmassSuffix}_Entwurf_translinear.txt`;

        console.log("📥 Entwurf-Download:", {
          loadedBirkenbihlBase: state.loadedBirkenbihlBase,
          filenameBase,
          detectedLangs: langs,
          versmassSuffix,
          finalFilename: filename,
        });

        const blob = new Blob([draftText], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
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
        a.download = "translinear.pdf";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      });
    }
  }

  updateDownloadButtons();

  // WICHTIG: Lade Werk-Metadaten aus dem Katalog (setzt strength, meterSupported, etc.)
  try {
    await loadWorkMeta();
  } catch (error) {
    console.error("❌ FEHLER beim Laden der Werk-Metadaten:", error);
    el.pageTitle.textContent = "Fehler beim Laden";
    return;
  }

  // Titel setzen (wird bereits in loadWorkMeta() gesetzt, aber sicherheitshalber nochmal)
  el.pageTitle.textContent = `${
    state.workMeta?.author_display || state.author
  } – ${state.workMeta?.title || state.work}`;

  // Inhalte laden
  try {
    await loadTexts();
  } catch (error) {
    console.error("❌ FEHLER beim Laden der Texte:", error);
  }

  wireEvents();

  // Entwurfs-Text initialisieren
  try {
    await initializeDraftText();
  } catch (error) {
    console.error("❌ FEHLER beim Initialisieren des Draft-Textes:", error);
  }

  // PDF-Ansicht wird bereits in loadWorkMeta() via updatePdfView() geladen
})();

// PDF-Renderer direkt im PDF-Fenster
// PDF-Optionen Status
let pdfOptions = {
  source: "original",
  strength: "", // Wird dynamisch gesetzt: GR_Fett oder LAT_Fett
  color: "Colour",
  tags: "Tag",
  meter: "without", // Wird basierend auf meterSupported dynamisch gesetzt
  hidePipes: false, // Pipes (|) in Übersetzungen verstecken
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
  // Entwurfs-PDF?
  if (state.source === "draft") {
    const draftName = buildDraftPdfFilename();
    const draftUrl = buildDraftPdfUrl(draftName);
    console.log("Draft PDF URL:", draftUrl);
    return draftUrl;
  }

  if (!state.workMeta || !state.workMeta.filename_base) {
    console.error("Work metadata with filename_base not loaded!");
    return "";
  }

  const finalName = buildPdfFilename();
  const url = buildReleaseProxyUrl(finalName, "inline");

  console.log("Generated PDF URL:", url);
  console.log("PDF Options Debug:", {
    strength: pdfOptions.strength,
    color: pdfOptions.color,
    tags: pdfOptions.tags,
    meter: pdfOptions.meter,
    meterSupported: state.meterSupported,
    languages: state.languages,
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

  bindPdfUtilityButtons();
}

function bindPdfUtilityButtons() {
  const { openTabBtn, downloadBtn } = pdfRenderer.elements || {};

  if (openTabBtn && !openTabBtn.dataset.boundClick) {
    openTabBtn.dataset.boundClick = "true";
    openTabBtn.addEventListener("click", () => {
      let pdfUrl = getCurrentPdfUrl();
      if (!pdfUrl) return;

      // Für Draft-PDFs: Verwende Worker-Proxy, um Content-Disposition zu überschreiben
      if (
        state.source === "draft" &&
        pdfUrl.includes("raw.githubusercontent.com")
      ) {
        // Entferne Cache-Buster (?cb=...) aus der URL
        const urlWithoutCacheBuster = pdfUrl.split("?")[0];

        // Extrahiere den Dateipfad aus der GitHub RAW URL
        // Der Pfad ist bereits vollständig (inkl. pdf_drafts/), also nur den Teil nach main/ nehmen
        const match = urlWithoutCacheBuster.match(
          /raw\.githubusercontent\.com\/[^\/]+\/[^\/]+\/[^\/]+\/(.+)$/
        );
        if (match) {
          let filePath = match[1];
          // Entferne "pdf_drafts/" am Anfang, da der Worker es automatisch hinzufügt
          if (filePath.startsWith("pdf_drafts/")) {
            filePath = filePath.substring("pdf_drafts/".length);
          }
          pdfUrl = `${WORKER_BASE}/release?file=${encodeURIComponent(
            filePath
          )}&mode=inline&draft=true`;
        }
      }

      const newWindow = window.open(pdfUrl, "_blank");
      if (newWindow) newWindow.focus();
    });
  }

  if (downloadBtn && !downloadBtn.dataset.boundClick) {
    downloadBtn.dataset.boundClick = "true";
    downloadBtn.addEventListener("click", async () => {
      const filename =
        state.source === "draft" ? buildDraftPdfFilename() : buildPdfFilename();

      // WICHTIG: Verkürze den Filename für den Download (entfernt Präfixe, SESSION, etc.)
      const shortFilename = shortenPdfFilename(filename);
      console.log("🔧 Download Debug:", {
        original: filename,
        shortened: shortFilename,
      });

      const pdfUrl =
        state.source === "draft"
          ? buildDraftPdfUrl(filename)
          : buildReleaseProxyUrl(filename, "attachment");
      if (!pdfUrl) return;

      // NEU: Fetch PDF als Blob und download mit korrektem Namen
      // (Cross-Origin URLs ignorieren a.download, daher Blob-Trick)
      try {
        const response = await fetch(pdfUrl);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = shortFilename; // Jetzt funktioniert der Name!
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        // Cleanup
        setTimeout(() => URL.revokeObjectURL(blobUrl), 100);
      } catch (error) {
        console.error("Download fehlgeschlagen:", error);
        alert("PDF-Download fehlgeschlagen. Bitte versuche es später erneut.");
      }
    });
  }
}

// PDF neu laden
async function loadPdfIntoRendererDirect(pdfUrl) {
  // GitHub-Releases lassen keine CORS-Requests für pdf.js zu → Hinweis statt Fehler
  if (pdfUrl.startsWith("https://github.com/")) {
    pdfRenderer.pdf = null;
    pdfRenderer.currentPage = 1;
    if (pdfRenderer.elements?.pageCount) {
      pdfRenderer.elements.pageCount.textContent = "–";
    }
    if (pdfRenderer.elements?.pageNum) {
      pdfRenderer.elements.pageNum.textContent = "–";
    }
    if (pdfRenderer.elements?.pages) {
      pdfRenderer.elements.pages.innerHTML = `
        <div class="pdf-loading">
          Dieses PDF liegt in einem externen GitHub-Release.<br>
          Bitte nutze „PDF in neuem Tab öffnen“ oder „Herunterladen“, um es anzusehen.
        </div>
      `;
    }
    return;
  }

  try {
    // PDF.js Library verfügbar machen
    const pdfjs = window["pdfjs-dist/build/pdf"];

    // PDF laden
    const task = pdfjs.getDocument(pdfUrl);
    pdfRenderer.pdf = await task.promise;
    if (state.source === "draft") {
      // WICHTIG: pendingDraftFilename NICHT zurücksetzen!
      // Es wird benötigt, um alle Varianten zu laden (mit SESSION_ID und TIMESTAMP)
      state.manualDraftBuildRequired = false;
      state.manualDraftCommand = null;
      state.draftBuildActive = false;
      state.draftHasResult = true;
    }

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
    const message = error?.message || "";

    // NEU: Fallback für NoTrans PDFs
    // Wenn ein PDF mit _Tag nicht gefunden wird, versuche _Tag_NoTrans und umgekehrt
    const is404 =
      /Missing PDF/i.test(message) ||
      /Unexpected server response/i.test(message) ||
      message.includes("404");

    if (is404 && state.source === "draft") {
      // Extrahiere Dateinamen aus URL (entferne Cache-Buster)
      const urlWithoutCache = pdfUrl.split("?")[0];
      const filename = urlWithoutCache.substring(
        urlWithoutCache.lastIndexOf("/") + 1
      );

      // Versuche die andere Variante (mit/ohne _NoTrans)
      let alternativeFilename = null;
      if (filename.includes("_Tag_NoTrans.pdf")) {
        // NoTrans → Standard (ohne NoTrans)
        alternativeFilename = filename.replace("_Tag_NoTrans.pdf", "_Tag.pdf");
      } else if (
        filename.includes("_Tag.pdf") &&
        !filename.includes("_NoTags")
      ) {
        // Standard → NoTrans
        alternativeFilename = filename.replace("_Tag.pdf", "_Tag_NoTrans.pdf");
      }

      if (alternativeFilename) {
        console.log(
          `404 für ${filename}, versuche Fallback: ${alternativeFilename}`
        );
        const alternativeUrl = buildDraftPdfUrl(alternativeFilename);

        // Rekursiver Aufruf mit Fallback-URL (nur 1x, um Endlosschleife zu vermeiden)
        // Verhindere doppelten Fallback mit Flag
        if (!pdfUrl.includes("_FALLBACK_")) {
          const markedUrl = alternativeUrl.replace(".pdf", "_FALLBACK_.pdf");
          try {
            await loadPdfIntoRendererDirect(alternativeUrl);
            return; // Erfolg! Beende diese Funktion
          } catch (fallbackError) {
            console.log(`Fallback fehlgeschlagen, zeige Fehlerplatzhalter`);
            // Fallback hat auch nicht funktioniert, zeige ursprünglichen Fehler
          }
        }
      }
    }

    if (state.source === "draft") {
      // NEU: Spezialfall für 404 bei Draft-PDFs
      // GitHub Raw-Content cached aggressiv → PDF kann 1-3 Minuten brauchen
      if (is404) {
        // Zeige Hinweis dass PDF noch nicht verfügbar ist (GitHub Cache)
        showPdfPlaceholder("draft-waiting", {
          icon: "⏳",
          title: "PDF wird geladen...",
          message:
            "Das PDF wurde gerade erstellt und wird von GitHub verarbeitet.",
          details: `
            <p style="margin-top: 10px; font-size: 14px; color: #666;">
              <strong>GitHub ist am Arbeiten:</strong> Es kann 1-3 Minuten dauern,
              bis neue PDFs verfügbar sind.
            </p>
            <p style="margin-top: 8px; font-size: 14px; color: #666;">
              💡 <strong>Tipp:</strong> Wechsle kurz zu einer anderen PDF-Variante
              (z.B. Normal → Fett) und dann zurück - oft ist es dann da!
            </p>
            <button onclick="location.reload()" style="margin-top: 15px; padding: 8px 16px; background: #0066cc; color: white; border: none; border-radius: 4px; cursor: pointer;">
              🔄 Seite neu laden
            </button>
          `,
        });
        state.draftHasResult = false;
        return;
      }

      if (state.manualDraftBuildRequired && !state.draftHasResult) {
        showDraftManualPlaceholder({ command: state.manualDraftCommand });
      } else if (state.draftBuildActive) {
        showDraftWaitingPlaceholder({
          filename: state.pendingDraftFilename,
          url: pdfUrl,
        });
      } else if (
        /Missing PDF/i.test(message) ||
        /Unexpected server response/i.test(message)
      ) {
        state.draftHasResult = false;
        showDraftEmptyPlaceholder();
      } else {
        showDraftErrorPlaceholder({ message, url: pdfUrl });
      }
    } else {
      showOriginalPdfErrorPlaceholder({ message, url: pdfUrl });
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
        if (val === "draft") {
          if (!state.lastDraftUrl) {
            showDraftEmptyPlaceholder();
            return;
          }
          loadPdfIntoRendererDirect(state.lastDraftUrl);
          return;
        }
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

      // PDF neu laden (nur für Original-PDFs, Entwurf wurde bereits oben geladen)
      const newPdfUrl = buildPdfUrlForRenderer();
      loadPdfIntoRendererDirect(newPdfUrl);
    });
  });

  // Standard-Optionen aktivieren (mit CSS-Klasse)
  const originalBtn = document.querySelector(
    '#pdfRendererContainer [data-opt="source"][data-val="original"]'
  );
  const fettBtn = document.querySelector(
    '#pdfRendererContainer [data-opt="strength"][data-val="Fett"]'
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
    fettBtn: !!fettBtn,
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
  // strength wird in loadWorkMeta() basierend auf der Sprache gesetzt
  if (!state.color) state.color = "Colour";
  if (!state.tags) state.tags = "Tag";

  const meterActive = state.meterPageActive;
  state.meter = meterActive ? "with" : "without";

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
  // Aktiviere "Fett" Button (Standard), nicht "Normal"
  if (fettBtn) fettBtn.classList.add("active");
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

/* -----------------------------------------------------------------------------
   Close tag/config panels on ESC
   Adds a robust Escape-key handler that attempts to close the tag/config
   UI. It is defensive: it looks for common modal/panel selectors and for a
   close-button inside them (and clicks it). If no button is found it will
   hide the panel by setting style.display='none' and adding a 'hidden' class.
   This avoids errors if the exact DOM shape varies between builds.
   -------------------------------------------------------------------------- */
(function () {
  function tryCloseElement(el) {
    if (!el) return false;
    try {
      // If an explicit close button exists, click it (this will run the existing close logic)
      const closeBtn = el.querySelector(
        ".close, .btn-close, .tag-config-close, .close-button, .modal-close"
      );
      if (closeBtn) {
        // prefer built-in click behaviour
        closeBtn.click();
        return true;
      }

      // If element is visible, hide it gracefully
      const style = window.getComputedStyle(el);
      if (style && style.display !== "none" && el.offsetParent !== null) {
        // mark hidden for potential CSS
        el.classList.add("hidden");
        el.style.display = "none";
        // If there is an ARIA attribute, keep it consistent
        try {
          el.setAttribute("aria-hidden", "true");
        } catch (e) {}
        return true;
      }
    } catch (e) {
      // swallow errors - we don't want ESC to break anything
      console.error("tryCloseElement error", e);
    }
    return false;
  }

  function closeTagConfigOnEsc(ev) {
    // only handle plain Escape (not when user focuses an input while pressing Esc for other reasons)
    if (!ev || (ev.key !== "Escape" && ev.key !== "Esc")) return;

    // Candidate selectors for your tag/config UI. This list is intentionally broad.
    const selectors = [
      "#tag-config-modal",
      "#tag-config",
      "#renderingModal",
      ".tag-config-modal",
      ".tag-config",
      ".tag-config-panel",
      ".config-table",
      ".tag-config-drawer",
      ".panel-tag-config",
      "[data-tag-config]",
      "[data-tag-config-panel]",
      ".tag-configuration",
    ];

    // Try each selector and attempt to close the first visible one
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && tryCloseElement(el)) {
        ev.preventDefault();
        ev.stopPropagation();
        return;
      }
    }

    // If nothing found above: try to find elements that are visible and likely settings panels
    const fallbackCandidates = Array.from(
      document.querySelectorAll(".modal, .drawer, .panel, .overlay")
    );
    for (const el of fallbackCandidates) {
      // Heuristic: look for nodes that contain words like "tag" or "config"
      const txt = (el.textContent || "").toLowerCase();
      if (
        txt.includes("tag") ||
        txt.includes("konfig") ||
        txt.includes("config") ||
        txt.includes("configuration")
      ) {
        if (tryCloseElement(el)) {
          ev.preventDefault();
          ev.stopPropagation();
          return;
        }
      }
    }

    // Last resort: if a dedicated global close element exists, click it.
    const globalClose = document.querySelector(
      ".tag-config-global-close, #tag-config-close, .close-tag-config"
    );
    if (globalClose) {
      try {
        globalClose.click();
        ev.preventDefault();
        ev.stopPropagation();
      } catch (e) {}
    }
  }

  // Attach on DOMContentLoaded so we won't run too early
  document.addEventListener("DOMContentLoaded", function () {
    // Listen on keydown globally to allow ESC from anywhere
    window.addEventListener("keydown", closeTagConfigOnEsc, { capture: false });
  });

  // Also attach immediately in case work.js is loaded after DOMContentLoaded
  if (
    document.readyState === "interactive" ||
    document.readyState === "complete"
  ) {
    window.addEventListener("keydown", closeTagConfigOnEsc, { capture: false });
  }
})();

/* -----------------------------------------------------------------------------
   Tag-config hook helpers
   Provide a precise way for other code to register the currently-open
   tag/config panel: call window.setTagConfigOpen(panelElement)
   Then ESC will close that element quickly via window.closeTagConfig()
   This is more robust than selector heuristics.
 ----------------------------------------------------------------------------- */
if (typeof window !== "undefined") {
  // only add once
  if (!window.setTagConfigOpen) {
    window._tagConfigOpen = null;

    // Register the currently open panel (call from your "open panel" logic)
    window.setTagConfigOpen = function (panelElement) {
      try {
        window._tagConfigOpen = panelElement || null;
      } catch (e) {
        window._tagConfigOpen = null;
      }
    };

    // Clear registration (call from your "close panel" logic)
    window.clearTagConfigOpen = function () {
      window._tagConfigOpen = null;
    };

    // Close the registered panel (returns true when it actually closed something)
    window.closeTagConfig = function () {
      var el = window._tagConfigOpen;
      if (!el) return false;
      try {
        // prefer an explicit close button if present
        var closeBtn = null;
        if (el.querySelector) {
          closeBtn = el.querySelector(
            ".close, .btn-close, .tag-config-close, .close-button, .modal-close, [data-close]"
          );
        }
        if (closeBtn) {
          try {
            closeBtn.click();
          } catch (e) {
            /* fall through to hide fallback */
          }
          // assume click closed it; clear the handle
          window._tagConfigOpen = null;
          return true;
        }

        // fallback: hide gracefully
        try {
          el.classList.add("hidden");
          el.style.display = "none";
          el.setAttribute && el.setAttribute("aria-hidden", "true");
        } catch (e) {
          /* ignore */
        }
        window._tagConfigOpen = null;
        return true;
      } catch (e) {
        console.error("window.closeTagConfig error", e);
        window._tagConfigOpen = null;
        return false;
      }
    };
  }
}

/* Quick ESC hook for the explicit hook-based close.
   If a panel has been registered via setTagConfigOpen, prefer closing that
   element before running other heuristics. This listener is lightweight
   and only prevents event propagation when it actually closed something. */
if (typeof window !== "undefined") {
  window.addEventListener &&
    window.addEventListener(
      "keydown",
      function (ev) {
        if (ev.key !== "Escape" && ev.key !== "Esc") return;
        try {
          if (typeof window.closeTagConfig === "function") {
            var closed = false;
            try {
              closed = window.closeTagConfig();
            } catch (e) {
              closed = false;
            }
            if (closed) {
              ev.preventDefault();
              ev.stopPropagation();
            }
          }
        } catch (e) {
          /* swallow */
        }
      },
      { capture: false }
    );
}
