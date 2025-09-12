// work.js – universelles Werk-Script
// Erwartete URL-Parameter: kind, author, work
// Nutzt catalog.json, um Versmaß-Fähigkeit und Anzeigenamen zu bestimmen.

import { loadCatalog, findAuthorEntry, findWork } from './catalog.js';

function qs(name) {
  const u = new URL(location.href);
  return u.searchParams.get(name) || '';
}

function pathText(kind, author, workId, birk=false) {
  const base = `texte/${kind}/${author}/${workId}`;
  return birk ? `${base}_birkenbihl.txt` : `${base}.txt`;
}

function pdfBase(kind, author) {
  return `pdf/original_${kind}_pdf/${author}/`;
}
function draftPdfBase(kind, author) {
  return `pdf_drafts/draft_${kind}_pdf/${author}/`;
}

function choosePdfName(workId, opts, meterOn) {
  // Einheitliche Namensbildung gemäß shared/naming.py-Konvention:
  // <Werk>_<Strength>_<Colour|BlackWhite>_<Tag|NoTags>[ _Versmaß].pdf
  const parts = [
    workId,
    opts.strength,
    (opts.color_mode === 'COLOUR' ? 'Colour' : 'BlackWhite'),
    (opts.tag_mode === 'TAGS' ? 'Tag' : 'NoTags')
  ];
  if (meterOn) parts.push('Versmaß');
  return parts.join('_') + '.pdf';
}

function currentOptions() {
  const src   = document.querySelector('input[name="srcSel"]:checked')?.value || 'original';
  const str   = document.querySelector('input[name="strengthSel"]:checked')?.value || 'NORMAL';
  const col   = document.querySelector('input[name="colorSel"]:checked')?.value || 'COLOUR';
  const tag   = document.querySelector('input[name="tagSel"]:checked')?.value || 'TAGS';
  const meter = document.querySelector('input[name="meterSel"]:checked')?.value || 'METER_OFF';
  return {
    source: src,
    strength: str,
    color_mode: col,
    tag_mode: tag,
    meter_on: (meter === 'METER_ON')
  };
}

function bindRadioGroup(name, handler) {
  document.querySelectorAll(`input[name="${name}"]`).forEach(el => {
    el.addEventListener('change', handler);
  });
}

function applyHideToggles(srcEl, hideTagsChk, hideColorsChk) {
  function filterText() {
    let t = srcEl.dataset.raw || '';
    // Farben entfernen = führende # +, - Marker (dein Farbsystem) entfernen
    if (hideColorsChk.checked) {
      t = t.replace(/(^|\s)[#\+\-](?=[^\s\[\(]+)/g, '$1');
    }
    // Tags entfernen = Klammergruppen (…)
    if (hideTagsChk.checked) {
      t = t.replace(/\([A-Za-z/≈]+\)/g, '');
    }
    srcEl.textContent = t;
  }
  hideTagsChk.addEventListener('change', filterText);
  hideColorsChk.addEventListener('change', filterText);
  filterText();
}

function bindFontButtons(minusBtn, plusBtn, targetEl) {
  let size = 14;
  function apply() { targetEl.style.fontSize = size + 'px'; }
  minusBtn.addEventListener('click', () => { size = Math.max(10, size - 1); apply(); });
  plusBtn.addEventListener('click', () => { size = Math.min(36, size + 1); apply(); });
  apply();
}

function syncScroll(a, b, checkbox) {
  let lock = false;
  function link(src, dst) {
    src.addEventListener('scroll', () => {
      if (!checkbox.checked || lock) return;
      lock = true;
      const ratio = src.scrollTop / (src.scrollHeight - src.clientHeight);
      dst.scrollTop = ratio * (dst.scrollHeight - dst.clientHeight);
      lock = false;
    });
  }
  link(a, b); link(b, a);
}

async function loadText(path) {
  const res = await fetch(path, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Datei fehlt: ${path}`);
  return await res.text();
}

function setPdf(kind, author, workId) {
  const opts = currentOptions();
  const base = (opts.source === 'draft') ? draftPdfBase(kind, author) : pdfBase(kind, author);
  const name = choosePdfName(workId, opts, opts.meter_on);
  const full = base + name;

  const frame = document.getElementById('pdfFrame');
  const status = document.getElementById('pdfStatus');

  // Vorab Status setzen
  status.textContent = 'PDF-Status: Lade …';
  frame.src = '';

  // Nur HEAD testen, dann einbetten
  fetch(full, { method: 'HEAD', cache: 'no-store' })
    .then(r => {
      if (!r.ok) throw new Error('nicht gefunden');
      frame.src = full;
      status.textContent = 'PDF-Status: bereit.';
    })
    .catch(() => {
      status.textContent = `PDF-Status: Nicht gefunden (${full}).`;
    });
}

(async function init() {
  const kind   = qs('kind') || 'poesie';
  const author = qs('author') || 'Aischylos';
  const workId = qs('work') || 'Der_gefesselte_Prometheus';

  const titleEl = document.getElementById('work-title');

  // Katalog laden, Anzeigenamen/Versmaß bestimmen
  const cat = await loadCatalog();
  const aEntry = findAuthorEntry(cat, kind, author);
  const wEntry = findWork(cat, kind, author, workId);
  if (!aEntry || !wEntry) {
    titleEl.textContent = 'Werkseite – Eintrag nicht im Katalog.';
  } else {
    titleEl.textContent = `${aEntry.author_display} — ${wEntry.title}`;
  }

  // Versmaß-Zeile sichtbar/unsichtbar
  const meterRow = document.getElementById('meterRow');
  meterRow.style.display = (wEntry && wEntry.meter_capable) ? '' : 'none';

  // Texte laden (Original/Birkenbihl)
  const origEl = document.getElementById('origSrc');
  const birkEl = document.getElementById('birkSrc');
  const draftEl = document.getElementById('draftEditor');

  try {
    const orig = await loadText(pathText(kind, author, workId, false));
    origEl.dataset.raw = orig;
    origEl.textContent = orig;
  } catch (e) {
    origEl.textContent = 'Lade Original… (Datei fehlt?)';
  }

  try {
    const birk = await loadText(pathText(kind, author, workId, true));
    birkEl.dataset.raw = birk;
    birkEl.textContent = birk;
  } catch (e) {
    birkEl.textContent = 'Lade Birkenbihl… (Datei fehlt?)';
  }

  // Draft initial füllen = Birkenbihl (wenn geladen), sonst leer
  draftEl.value = birkEl.dataset.raw || '';

  // Hide/Show-Toggles & Schriftgröße
  applyHideToggles(origEl,  document.getElementById('origHideTags'),  document.getElementById('origHideColors'));
  applyHideToggles(birkEl,  document.getElementById('birkHideTags'),  document.getElementById('birkHideColors'));

  document.getElementById('resetDraftBtn').addEventListener('click', () => {
    if (confirm('Fortfahren? Ihr Entwurf wird verworfen. (Zuvor sichern, wenn nötig.)')) {
      draftEl.value = birkEl.dataset.raw || '';
    }
  });

  bindFontButtons(document.getElementById('origSizeMinus'),  document.getElementById('origSizePlus'),  origEl);
  bindFontButtons(document.getElementById('birkSizeMinus'),  document.getElementById('birkSizePlus'),  birkEl);
  bindFontButtons(document.getElementById('draftSizeMinus'), document.getElementById('draftSizePlus'), draftEl);

  syncScroll(origEl, birkEl, document.getElementById('syncScroll'));

  // PDF-Schalter binden
  ['srcSel','strengthSel','colorSel','tagSel','meterSel'].forEach(n => bindRadioGroup(n, () => setPdf(kind, author, workId)));

  // Erstes PDF setzen
  setPdf(kind, author, workId);
})();
