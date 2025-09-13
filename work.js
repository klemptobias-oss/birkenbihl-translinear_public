// work.js — universelle Werkseite

// 1) KONFIG
const WORKER_BASE = "https://birkenbihl-draft-01.klemp-tobias.workers.dev"; // <— HIER deine Worker-URL
const TXT_BASE    = 'texte';        // texte/<kind>/<author>/<work>.txt
const PDF_BASE    = 'pdf';          // pdf/original_..._pdf/<author>/*.pdf
const DRAFT_BASE  = 'pdf_drafts';   // pdf_drafts/draft_..._pdf/<author>/*.pdf

// 2) URL-Parameter
function getParam(name, dflt = '') {
  const u = new URL(location.href);
  return u.searchParams.get(name) || dflt;
}

// 3) Mini-Kataloghelfer (nur für Meter-Schalter; rest über Dateikonvention)
async function fetchCatalog() {
  const res = await fetch('catalog.json', { cache: 'no-store' });
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
    return au?.works?.find(x => x.id === w) || null;
  } catch { return null; }
}

// 4) DOM refs
const el = {
  pageTitle:   document.getElementById('pageTitle'),
  origPre:     document.getElementById('origPre'),
  origStatus:  document.getElementById('origStatus'),
  bkvPre:      document.getElementById('bkvPre'),
  bkvStatus:   document.getElementById('bkvStatus'),
  meterRow:    document.getElementById('meterRow'),
  pdfFrame:    document.getElementById('pdfFrame'),
  pdfStatus:   document.getElementById('pdfStatus'),
  dlBtn:       document.getElementById('downloadBtn'),
  draftFile:   document.getElementById('draftFile'),
  draftBtn:    document.getElementById('draftUploadBtn'),
};

// 5) State
const state = {
  kind:   getParam('kind', 'poesie'),     // poesie | prosa
  author: getParam('author', 'Unsortiert'),
  work:   getParam('work', 'Unbenannt'),

  // UI-Optionen
  source:   'original',  // original | draft
  strength: 'Normal',    // Normal | GR_Fett | DE_Fett
  color:    'Colour',    // Colour | BlackWhite
  tags:     'Tag',       // Tag | NoTags
  meter:    'Off',       // Off | On  (nur wenn unterstützt)

  meterSupported: false,
  lastDraftUrl:   null,  // vom Worker zurückbekommen
};

// 6) Hilfen
function setStatus(node, msg) { if (node) node.textContent = msg || ''; }
function clearPre(node) { if (node) node.textContent = ''; }

// PDF-Dateiname gemäß deiner Konvention:
// <Author><Work>_<Strength>_<Colour|BlackWhite>_<Tag|NoTags>[_Versmaß].pdf
function buildPdfFilename() {
  const base = `${state.author}${state.work}`;
  const parts = [base, state.strength, state.color, (state.tags === 'Tag' ? 'Tag' : 'NoTags')];
  if (state.meterSupported && state.meter === 'On') parts.push('Versmaß');
  return parts.join('_') + '.pdf';
}

function basePdfDir() {
  if (state.source === 'original') {
    return state.kind === 'poesie'
      ? `${PDF_BASE}/original_poesie_pdf/${state.author}`
      : `${PDF_BASE}/original_prosa_pdf/${state.author}`;
  } else {
    return state.kind === 'poesie'
      ? `${DRAFT_BASE}/draft_poesie_pdf/${state.author}`
      : `${DRAFT_BASE}/draft_prosa_pdf/${state.author}`;
  }
}
function buildPdfUrlFromSelection() {
  const name = buildPdfFilename();
  return `${basePdfDir()}/${name}`;
}

function updatePdfView(fromWorker = false) {
  // Wenn Entwurf gewählt UND wir haben gerade eine Worker-URL -> die bevorzugen
  if (state.source === 'draft' && state.lastDraftUrl && fromWorker) {
    el.pdfFrame.src = state.lastDraftUrl;
    el.dlBtn.href = state.lastDraftUrl;
    setStatus(el.pdfStatus, 'Entwurf vom Worker geladen.');
    return;
  }
  // Andernfalls normaler statischer Pfad
  const url = buildPdfUrlFromSelection();
  el.pdfFrame.src = url;
  el.dlBtn.href = url;
  setStatus(el.pdfStatus, state.source === 'original'
    ? 'Original-PDF geladen.'
    : 'Draft-PDF (statisch) geladen. Falls leer → bitte Entwurf rendern.');
}

// 7) Texte laden (oben links + unten links)
async function loadTexts() {
  const base = `${TXT_BASE}/${state.kind}/${state.author}/${state.work}`;
  // Original
  try {
    const r = await fetch(`${base}.txt`, { cache:'no-store' });
    if (r.ok) {
      el.origPre.textContent = await r.text();
      setStatus(el.origStatus, 'Fertig.');
    } else {
      clearPre(el.origPre);
      setStatus(el.origStatus, 'Original nicht gefunden.');
    }
  } catch {
    clearPre(el.origPre);
    setStatus(el.origStatus, 'Fehler beim Laden.');
  }
  // Birkenbihl
  try {
    const r = await fetch(`${base}_birkenbihl.txt`, { cache:'no-store' });
    if (r.ok) {
      el.bkvPre.textContent = await r.text();
      setStatus(el.bkvStatus, 'Fertig.');
    } else {
      clearPre(el.bkvPre);
      setStatus(el.bkvStatus, 'Birkenbihl nicht gefunden.');
    }
  } catch {
    clearPre(el.bkvPre);
    setStatus(el.bkvStatus, 'Fehler beim Laden.');
  }
}

// 8) Worker-Aufruf (Entwurf rendern)
async function renderDraftViaWorker(file) {
  if (!file) return setStatus(el.pdfStatus, 'Bitte zuerst eine .txt-Datei wählen.');
  setStatus(el.pdfStatus, 'Sende Entwurf an Worker …');

  // Optionen payload wie bei deinen Renderern
  const payload = {
    kind: state.kind,          // poesie | prosa
    author: state.author,      // Ordnername
    work: state.work,          // Werk-ID (nur informativ)
    strength: state.strength,  // Normal | GR_Fett | DE_Fett
    color_mode: state.color,   // Colour | BlackWhite
    tag_mode: state.tags === 'Tag' ? 'TAGS' : 'NO_TAGS',
    versmass: (state.meterSupported && state.meter === 'On') ? 'ON' : 'OFF'
  };

  const form = new FormData();
  form.append('file', file, file.name);
  form.append('options', JSON.stringify(payload));

  try {
    const res = await fetch(`${WORKER_BASE}/render`, { method:'POST', body: form });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!data?.ok || !data?.pdf_url) throw new Error('Worker-Antwort unvollständig.');
    state.lastDraftUrl = data.pdf_url;
    // Quelle automatisch auf Entwurf schalten und anzeigen
    state.source = 'draft';
    document.querySelector('input[name="srcSel"][value="draft"]').checked = true;
    updatePdfView(true);
  } catch (e) {
    console.error(e);
    setStatus(el.pdfStatus, 'Worker-Fehler beim Rendern.');
  }
}

// 9) Events
function wireRadios() {
  // Quelle
  document.querySelectorAll('input[name="srcSel"]').forEach(r => {
    r.addEventListener('change', () => {
      state.source = r.value;
      updatePdfView(false);
    });
  });
  // Stärke
  document.querySelectorAll('input[name="strengthSel"]').forEach(r => {
    r.addEventListener('change', () => {
      state.strength = r.value;
      updatePdfView(false);
    });
  });
  // Farbe
  document.querySelectorAll('input[name="colorSel"]').forEach(r => {
    r.addEventListener('change', () => {
      state.color = r.value;
      updatePdfView(false);
    });
  });
  // Tags
  document.querySelectorAll('input[name="tagSel"]').forEach(r => {
    r.addEventListener('change', () => {
      state.tags = r.value;
      updatePdfView(false);
    });
  });
  // Versmaß (falls sichtbar)
  document.querySelectorAll('input[name="meterSel"]').forEach(r => {
    r.addEventListener('change', () => {
      state.meter = r.value;
      updatePdfView(false);
    });
  });

  // Draft-Button
  el.draftBtn?.addEventListener('click', () => renderDraftViaWorker(el.draftFile.files?.[0]));
}

// 10) Init
(async function init() {
  // Titel
  el.pageTitle.textContent = `${state.author} – ${state.work}`;

  // Katalog für Meter-Fähigkeit
  try {
    const cat = await fetchCatalog();
    const meta = findMeta(cat, state.kind, state.author, state.work);
    state.meterSupported = !!meta?.meter;  // true/false
    el.meterRow.style.display = state.meterSupported ? '' : 'none';
  } catch { /* ohne Katalog: kein Versmaß */ }

  // Inhalte und PDF anzeigen
  await loadTexts();
  wireRadios();
  updatePdfView(false);
})();
