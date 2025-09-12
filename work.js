// work.js — universelles Werk-Script mit Worker-Anbindung
// Erwartet URL-Parameter: kind=poesie|prosa, author=..., work=...
// Benötigt catalog.js (loadCatalog, getWorkMeta, txtPaths) im <script type="module"> in work.html
//
// DOM-Erwartungen (IDs/Names):
// - iframe#pdfFrame
// - span#pdfStatus
// - Radios name="srcSel"         values: original|draft
// - Radios name="strengthSel"    values: Normal|GR_Fett|DE_Fett
// - Radios name="colorSel"       values: Colour|BlackWhite
// - Radios name="tagSel"         values: Tag|NoTags
// - Radios name="meterSel"       values: On|Off      (optional; nur wenn meter_capable)
// - input#draftFile (accept .txt), button#draftUploadBtn
//
// Pfad-Konvention PDF (original):
// pdf/original_poesie_pdf/<Author>/<WorkId>_<Strength>_<Colour|BlackWhite>_<Tag|NoTags>[ _Versmaß].pdf
// pdf/original_prosa_pdf/<Author>/<WorkId>_<Strength>_<Colour|BlackWhite>_<Tag|NoTags>.pdf
//
// Pfad-Konvention PDF (draft, durch Renderer erzeugt):
// pdf_drafts/draft_poesie_pdf/<Author>/<WorkId>_<Strength>_<Colour|BlackWhite>_<Tag|NoTags>[ _Versmaß].pdf
// pdf_drafts/draft_prosa_pdf/<Author>/<WorkId>_<Strength>_<Colour|BlackWhite>_<Tag|NoTags>.pdf
//
// Cloudflare Worker (Upload/Status):
// - POST  {WORKER_BASE}/drafts/upload  (multipart/form-data: file, kind, author, work, strength, color_mode, tag_mode, meter_on)
// - GET   {WORKER_BASE}/drafts/status?jobId=...
//
// WICHTIG: WORKER_BASE unten eintragen!

import { loadCatalog, getWorkMeta } from './catalog.js';

// ======================================================================
// Einstellungen
// ======================================================================

const WORKER_BASE = 'https://birkenbihl-draft-01.klemp-tobias.workers.dev';  // <<< HIER deine Worker-URL eintragen

// ======================================================================
// DOM-Utils
// ======================================================================

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function getParam(name, def = '') {
  const u = new URL(location.href);
  return u.searchParams.get(name) || def;
}

function setStatus(msg) {
  const el = $('#pdfStatus');
  if (el) el.textContent = msg || '';
}

function selectedValue(groupName, fallback) {
  const el = $$(`input[name="${groupName}"]`).find(r => r.checked);
  return el ? el.value : fallback;
}

function setRadio(groupName, value) {
  const found = $$(`input[name="${groupName}"]`).find(r => r.value === value);
  if (found) found.checked = true;
}

function show(el, on = true) {
  if (!el) return;
  el.style.display = on ? '' : 'none';
}

function byId(id) {
  const el = document.getElementById(id);
  if (!el) console.warn(`[work.js] Element #${id} fehlt`);
  return el;
}

// ======================================================================
// Optionen lesen/schreiben
// ======================================================================

function currentOptions(meta) {
  const source = selectedValue('srcSel', 'original'); // original|draft
  const strength = selectedValue('strengthSel', 'Normal'); // Normal|GR_Fett|DE_Fett
  const color_mode = selectedValue('colorSel', 'Colour'); // Colour|BlackWhite
  const tag_mode = selectedValue('tagSel', 'Tag'); // Tag|NoTags

  let meter_on = false;
  if (meta?.meter_capable) {
    meter_on = (selectedValue('meterSel', 'Off') === 'On');
  }
  return { source, strength, color_mode, tag_mode, meter_on };
}

function normalizeOptionsForKind(opts, kind) {
  // Bei PROSA gibt es kein Versmaß — sicherheitshalber aus
  if (kind === 'prosa') return { ...opts, meter_on: false };
  return opts;
}

// ======================================================================
// Pfade/URLs
// ======================================================================

function pdfBaseDir(kind, variant /* original|draft */) {
  const isDraft = (variant === 'draft');
  if (kind === 'poesie') return isDraft ? 'pdf_drafts/draft_poesie_pdf' : 'pdf/original_poesie_pdf';
  if (kind === 'prosa')  return isDraft ? 'pdf_drafts/draft_prosa_pdf'  : 'pdf/original_prosa_pdf';
  return isDraft ? 'pdf_drafts' : 'pdf';
}

function buildPdfName(workId, strength, color_mode, tag_mode, meter_on, kind) {
  // Stärke
  // Normal|GR_Fett|DE_Fett  →  Normal / GR_Fett / DE_Fett (1:1)
  const strengthPart = strength;

  // Farbe
  // Colour|BlackWhite → Colour / BlackWhite (1:1)
  const colorPart = color_mode;

  // Tags
  // Tag|NoTags → Tag / NoTags (1:1)
  const tagPart = tag_mode;

  // Versmaß (nur bei Poesie): Suffix "_Versmaß"
  const meterPart = (kind === 'poesie' && meter_on) ? '_Versmaß' : '';

  return `${workId}_${strengthPart}_${colorPart}_${tagPart}${meterPart}.pdf`;
}

function pdfUrl(kind, author, workId, opts) {
  const baseDir = pdfBaseDir(kind, opts.source);
  const name = buildPdfName(workId, opts.strength, opts.color_mode, opts.tag_mode, opts.meter_on, kind);
  return `${baseDir}/${author}/${name}`;
}

// ======================================================================
// Worker-Anbindung (Upload + Polling)
// ======================================================================

async function uploadDraft(kind, author, workId, file, opts) {
  if (!WORKER_BASE.includes('workers.dev')) {
    throw new Error('WORKER_BASE nicht konfiguriert (work.js)');
  }
  const fd = new FormData();
  fd.append('file', file);
  fd.append('kind', kind);
  fd.append('author', author);
  fd.append('work', workId);
  fd.append('strength', opts.strength);
  fd.append('color_mode', opts.color_mode);
  fd.append('tag_mode', opts.tag_mode);
  fd.append('meter_on', String(opts.meter_on));

  const res = await fetch(`${WORKER_BASE}/drafts/upload`, { method: 'POST', body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.error || `Upload fehlgeschlagen (${res.status})`);
  }
  return data; // { jobId, draftPdfUrl:null }
}

async function pollDraft(jobId, { maxTries = 180, intervalMs = 2000 } = {}) {
  for (let i = 0; i < maxTries; i++) {
    const res = await fetch(`${WORKER_BASE}/drafts/status?jobId=${encodeURIComponent(jobId)}`, { cache: 'no-store' });
    const s = await res.json().catch(() => ({}));
    if (s.state === 'done' && s.draftPdfUrl) return s.draftPdfUrl;
    if (s.state === 'error') throw new Error('Render-Fehler beim Worker');
    await new Promise(r => setTimeout(r, intervalMs));
  }
  throw new Error('Timeout beim Rendern');
}

// ======================================================================
// PDF-Viewer steuern
// ======================================================================

function setPdfFrame(url) {
  const frame = byId('pdfFrame');
  if (frame) {
    frame.src = url;
  }
}

function refreshPdf(kind, author, workId, meta) {
  const raw = currentOptions(meta);
  const opts = normalizeOptionsForKind(raw, kind);
  const url = pdfUrl(kind, author, workId, opts);
  setStatus('PDF laden …');
  setPdfFrame(url);
  // Setze Status nach kurzer Zeit wieder neutral
  setTimeout(() => setStatus(''), 500);
}

// ======================================================================
// UI-Hooks / Initialisierung
// ======================================================================

function bindOptionGroup(groupName, handler) {
  $$(`input[name="${groupName}"]`).forEach(r => {
    r.addEventListener('change', handler);
  });
}

function initOptionBindings(kind, author, workId, meta) {
  const onChange = () => refreshPdf(kind, author, workId, meta);

  bindOptionGroup('srcSel', onChange);
  bindOptionGroup('strengthSel', onChange);
  bindOptionGroup('colorSel', onChange);
  bindOptionGroup('tagSel', onChange);
  bindOptionGroup('meterSel', onChange); // existiert evtl. nicht – macht nichts

  // Defaults setzen (falls kein vorgewählter Wert)
  if (!$$('input[name="srcSel"]').some(r => r.checked))       setRadio('srcSel', 'original');
  if (!$$('input[name="strengthSel"]').some(r => r.checked)) setRadio('strengthSel', 'Normal');
  if (!$$('input[name="colorSel"]').some(r => r.checked))    setRadio('colorSel', 'Colour');
  if (!$$('input[name="tagSel"]').some(r => r.checked))      setRadio('tagSel', 'Tag');
  if (meta?.meter_capable) {
    if (!$$('input[name="meterSel"]').some(r => r.checked))  setRadio('meterSel', 'Off');
  }
}

function initMeterVisibility(meterCapable) {
  // Wir erwarten einen Container um die Versmaß-Optionen,
  // z. B. <div id="meterRow">…</div>
  const row = byId('meterRow');
  show(row, !!meterCapable);
}

// Draft-Upload: Datei + Optionen → Worker → Polling → Entwurfs-PDF im Viewer
function initDraftUpload(kind, author, workId, meta) {
  const fileInp = byId('draftFile');
  const btn = byId('draftUploadBtn');
  if (!fileInp || !btn) return;

  btn.addEventListener('click', async () => {
    try {
      const f = fileInp.files?.[0];
      if (!f) {
        alert('Bitte zuerst eine .txt-Datei auswählen.');
        return;
      }
      const raw = currentOptions(meta);
      const opts = normalizeOptionsForKind(raw, kind);
      setStatus('Upload/Render gestartet …');

      const { jobId } = await uploadDraft(kind, author, workId, f, opts);
      setStatus('Warte auf PDF (Entwurf) …');

      const pdfUrlDraft = await pollDraft(jobId);
      // Quelle auf „Entwurf“ umschalten + PDF setzen
      setRadio('srcSel', 'draft');
      setPdfFrame(pdfUrlDraft);
      setStatus('Entwurfs-PDF bereit.');
    } catch (e) {
      console.error(e);
      setStatus('Fehler: ' + (e?.message || e));
      alert('Fehler beim Erzeugen des Entwurfs-PDF:\n' + (e?.message || e));
    }
  });
}

// ======================================================================
// Startpunkt
// ======================================================================

async function main() {
  const kind   = getParam('kind', 'poesie'); // poesie|prosa
  const author = getParam('author', 'Unsortiert');
  const workId = getParam('work', 'Unbenannt');

  try {
    const cat = await loadCatalog();
    const meta = getWorkMeta(cat, kind, author, workId);
    if (!meta) {
      setStatus('Fehler: Werk nicht im Katalog.');
      console.error('[work.js] Kein Eintrag im Katalog:', { kind, author, workId });
      return;
    }

    // Versmaß-Zeile ein-/ausblenden
    initMeterVisibility(!!meta.meter_capable);

    // Optionen binden + Defaults setzen
    initOptionBindings(kind, author, workId, meta);

    // Erste Anzeige
    refreshPdf(kind, author, workId, meta);

    // Draft-Upload aktivieren
    initDraftUpload(kind, author, workId, meta);

    // Debug-Info in der Konsole
    console.log('[work.js] Ready:', { kind, author, workId, meta });

  } catch (e) {
    console.error(e);
    setStatus('Fehler beim Initialisieren: ' + (e?.message || e));
  }
}

document.addEventListener('DOMContentLoaded', main);
