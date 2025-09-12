// work.js – universelles Werk-Script mit dynamischer Knopfleiste
// Erwartete URL-Parameter: kind, author, work
// nutzt catalog.json zum Ermitteln von Titel/Versmaß-Fähigkeit

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
  const parts = [
    workId,
    opts.strength,                                  // NORMAL | GR_FETT | DE_FETT
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
  const mSel  = document.querySelector('input[name="meterSel"]:checked')?.value || 'METER_OFF';
  return { source: src, strength: str, color_mode: col, tag_mode: tag, meter_on: (mSel === 'METER_ON') };
}

function applyHideToggles(srcEl, hideTagsChk, hideColorsChk) {
  function filterText() {
    let t = srcEl.dataset.raw || '';
    if (hideColorsChk.checked) {
      // entferne führende Farbcodes (# + -) vor einem Token
      t = t.replace(/(^|\s)[#\+\-](?=[^\s\[\(]+)/g, '$1');
    }
    if (hideTagsChk.checked) {
      // entferne (TAG) Blöcke
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
      const ratio = src.scrollTop / (src.scrollHeight - src.clientHeight + 0.0001);
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

/* ------------------------- dynamische Knopfleiste ------------------------- */
function radioGroup({name, title, items, checked, hidden=false}) {
  const div = document.createElement('div');
  div.className = 'group';
  if (hidden) div.style.display = 'none';
  const h = document.createElement('h4'); h.textContent = title; div.appendChild(h);
  const row = document.createElement('div'); row.className = 'row'; div.appendChild(row);

  items.forEach(it => {
    const id = `${name}_${it.value}`;
    const lab = document.createElement('label');
    const inp = document.createElement('input');
    inp.type = 'radio';
    inp.name = name;
    inp.value = it.value;
    inp.id = id;
    if (it.value === checked) inp.checked = true;
    lab.setAttribute('for', id);
    lab.appendChild(inp);
    lab.appendChild(document.createTextNode(it.label));
    row.appendChild(lab);
  });
  return div;
}

function buildControls(container, meterCapable) {
  container.innerHTML = '';

  // Quelle: Original / Entwurf
  container.appendChild(radioGroup({
    name: 'srcSel', title: 'Quelle',
    items: [
      {value:'original', label:'Original'},
      {value:'draft',    label:'Entwurf'}
    ],
    checked: 'original'
  }));

  // Stärke: Normal / Fett / DE-Fett
  container.appendChild(radioGroup({
    name: 'strengthSel', title: 'Schriftstärke',
    items: [
      {value:'NORMAL',  label:'Normal'},
      {value:'GR_FETT', label:'Fett'},
      {value:'DE_FETT', label:'DE-Fett'}
    ],
    checked: 'NORMAL'
  }));

  // Farbe: Colour / BlackWhite
  container.appendChild(radioGroup({
    name: 'colorSel', title: 'Farbdarstellung',
    items: [
      {value:'COLOUR',      label:'Colour'},
      {value:'BLACK_WHITE', label:'BlackWhite'}
    ],
    checked: 'COLOUR'
  }));

  // Tags: Tags / NoTag
  container.appendChild(radioGroup({
    name: 'tagSel', title: 'Grammatik-Tags',
    items: [
      {value:'TAGS',   label:'Tags'},
      {value:'NO_TAGS',label:'NoTag'}
    ],
    checked: 'TAGS'
  }));

  // Versmaß (nur falls erlaubt)
  container.appendChild(radioGroup({
    name: 'meterSel', title: 'Versmaß',
    items: [
      {value:'METER_ON',  label:'Versmaß'},
      {value:'METER_OFF', label:'Ohne Versmaß'}
    ],
    checked: 'METER_OFF',
    hidden: !meterCapable
  }));
}

function bindAllRadiosTo(handler) {
  ['srcSel','strengthSel','colorSel','tagSel','meterSel'].forEach(name => {
    document.querySelectorAll(`input[name="${name}"]`).forEach(inp => {
      inp.addEventListener('change', handler);
    });
  });
}

/* ------------------------------ PDF/Viewer ------------------------------- */
function setPdf(kind, author, workId) {
  const opts = currentOptions();
  const base = (opts.source === 'draft') ? draftPdfBase(kind, author) : pdfBase(kind, author);
  const name = choosePdfName(workId, opts, opts.meter_on);
  const full = base + name;

  const frame = document.getElementById('pdfFrame');
  const status = document.getElementById('pdfStatus');
  status.textContent = 'PDF-Status: Lade …';
  frame.src = '';

  fetch(full, { method:'HEAD', cache:'no-store' })
    .then(r => {
      if (!r.ok) throw new Error('nicht gefunden');
      frame.src = full;
      status.textContent = 'PDF-Status: bereit.';
    })
    .catch(() => {
      status.textContent = `PDF-Status: Nicht gefunden (${full}).`;
    });
}

/* --------------------------------- init ---------------------------------- */
(async function init() {
  const kind   = qs('kind') || 'poesie';
  const author = qs('author') || 'Aischylos';
  const workId = qs('work') || 'Der_gefesselte_Prometheus';

  const titleEl = document.getElementById('work-title');
  const controls = document.getElementById('controls');

  // Katalog
  const cat = await loadCatalog();
  const aEntry = findAuthorEntry(cat, kind, author);
  const wEntry = findWork(cat, kind, author, workId);

  if (!aEntry || !wEntry) {
    titleEl.textContent = 'Werkseite – Eintrag nicht im Katalog.';
  } else {
    titleEl.textContent = `${aEntry.author_display} — ${wEntry.title}`;
  }

  // Knopfleiste dynamisch erzeugen
  buildControls(controls, !!(wEntry && wEntry.meter_capable));

  // Texte laden
  const origEl  = document.getElementById('origSrc');
  const birkEl  = document.getElementById('birkSrc');
  const draftEl = document.getElementById('draftEditor');

  try {
    const orig = await loadText(pathText(kind, author, workId, false));
    origEl.dataset.raw = orig;
    origEl.textContent = orig;
  } catch {
    origEl.textContent = 'Lade Original… (Datei fehlt?)';
  }
  try {
    const birk = await loadText(pathText(kind, author, workId, true));
    birkEl.dataset.raw = birk;
    birkEl.textContent = birk;
  } catch {
    birkEl.textContent = 'Lade Birkenbihl… (Datei fehlt?)';
  }

  // Draft = Birkenbihl-Fallback
  draftEl.value = birkEl.dataset.raw || '';

  // Tools/Bedienung
  applyHideToggles(origEl, document.getElementById('origHideTags'), document.getElementById('origHideColors'));
  applyHideToggles(birkEl, document.getElementById('birkHideTags'), document.getElementById('birkHideColors'));

  document.getElementById('resetDraftBtn').addEventListener('click', () => {
    if (confirm('Fortfahren? Ihr Entwurf wird verworfen. (Zuvor sichern, wenn nötig.)')) {
      draftEl.value = birkEl.dataset.raw || '';
    }
  });

  bindFontButtons(document.getElementById('origSizeMinus'),  document.getElementById('origSizePlus'),  origEl);
  bindFontButtons(document.getElementById('birkSizeMinus'),  document.getElementById('birkSizePlus'),  birkEl);
  bindFontButtons(document.getElementById('draftSizeMinus'), document.getElementById('draftSizePlus'), draftEl);

  syncScroll(origEl, birkEl, document.getElementById('syncScroll'));

  // PDF-Umschalten
  bindAllRadiosTo(() => setPdf(kind, author, workId));
  setPdf(kind, author, workId);
})();
