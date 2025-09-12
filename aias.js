/* aias.js – Poesie-Ansicht (Aias)
 * Baut die neue Button-Hierarchie im PDF-Viewer dynamisch
 * und setzt die Pfade für TXT/PDF (Original & Draft).
 */

(function () {
  // ---------- Helpers ----------
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const htmlEl = document.documentElement;
  const GENRE  = htmlEl.getAttribute('data-genre')  || 'poesie';
  const AUTHOR = htmlEl.getAttribute('data-author') || 'Sophokles';
  const WORK   = htmlEl.getAttribute('data-work')   || 'Aias';
  const BASE   = htmlEl.getAttribute('data-base')   || WORK; // optional override via data-base

  // Pfade
  const TXT_ORIG = `texte/${GENRE}/${AUTHOR}/${WORK}.txt`;
  const TXT_DRAFT_DIR = `texte_drafts/${GENRE}_drafts/${AUTHOR}/`;
  // Hinweis: Draft-Dateiname ist dynamisch; fürs Einbetten zeigen wir den Editor, Download steuert aias.js selbst.

  const PDF_ORIG_DIR  = `pdf/original_${GENRE}_pdf/${AUTHOR}/`;
  const PDF_DRAFT_DIR = `pdf_drafts/draft_${GENRE}_pdf/${AUTHOR}/`;

  // Dom-Knoten
  const pdfControls = $('.pdf-controls');
  const pdfFrame    = $('#pdf-frame');
  const pdfBusy     = $('#pdf-busy');
  const pdfDL       = $('#pdf-download');
  const pdfOpen     = $('#pdf-open');
  const pdfMeta     = $('#pdf-meta');
  const pdfRefresh  = $('#pdf-refresh');

  const origTxtLink = $('#dl-original-txt');
  const origTxtObj  = $('#orig-txt-frame');

  const editor      = $('#bb-editor');
  const draftView   = $('#bb-draft-view');
  const draftNote   = $('#draft-view-note');

  // ---------- Control Model ----------
  const state = {
    source:   'original',            // 'original' | 'draft'
    strength: 'Normal',              // 'Normal' | 'GR_Fett' | 'DE_Fett'
    color:    'Colour',              // 'Colour' | 'BlackWhite'
    tags:     'Tag',                 // 'Tag' | 'NoTags'
    meter:    'Off',                 // 'On' | 'Off'  (Off = Ohne Versmaß)
  };

  // Mapping für Dateinamen-Komponenten
  function filenameStrength() {
    switch (state.strength) {
      case 'GR_Fett': return 'GR_Fett';
      case 'DE_Fett': return 'DE_Fett';
      default:        return 'Normal';
    }
  }
  function filenameColor() {
    return state.color === 'BlackWhite' ? 'BlackWhite' : 'Colour';
  }
  function filenameTags() {
    return state.tags === 'NoTags' ? 'NoTags' : 'Tag';
  }
  function meterSuffix() {
    return state.meter === 'On' ? '_Versmaß' : '';
  }

  function currentPdfDir() {
    return state.source === 'draft' ? PDF_DRAFT_DIR : PDF_ORIG_DIR;
  }

  function currentPdfName() {
    const base = BASE;
    const parts = [
      base,
      filenameStrength(),
      filenameColor(),
      filenameTags()
    ];
    return parts.join('_') + meterSuffix() + '.pdf';
  }

  function currentPdfUrl() {
    return currentPdfDir() + currentPdfName();
  }

  // ---------- Build Control UI ----------
  // Wir ersetzen die alte Mini-Steuerung durch 5 Gruppen (Radio-Buttons).
  function buildControls() {
    if (!pdfControls) return;

    pdfControls.innerHTML = ''; // leeren

    const groups = [
      {
        id: 'grp-source',
        label: 'Quelle',
        options: [
          { id:'src-original', text:'Original', value:'original', default:true },
          { id:'src-draft',    text:'Entwurf',  value:'draft' }
        ],
        onChange: v => { state.source = v; updatePdf(); },
      },
      {
        id: 'grp-strength',
        label: 'Stärke',
        options: [
          { id:'st-normal', text:'Normal',  value:'Normal',  default:true },
          { id:'st-grf',    text:'Fett',    value:'GR_Fett' },
          { id:'st-def',    text:'DE-Fett', value:'DE_Fett' },
        ],
        onChange: v => { state.strength = v; updatePdf(); },
      },
      {
        id: 'grp-color',
        label: 'Farbe',
        options: [
          { id:'col-colour',     text:'Colour',     value:'Colour',     default:true },
          { id:'col-blackwhite', text:'BlackWhite', value:'BlackWhite' },
        ],
        onChange: v => { state.color = v; updatePdf(); },
      },
      {
        id: 'grp-tags',
        label: 'Kürzel',
        options: [
          { id:'tg-tag',   text:'Tags',  value:'Tag',   default:true },
          { id:'tg-notag', text:'NoTag', value:'NoTags' },
        ],
        onChange: v => { state.tags = v; updatePdf(); },
      },
      {
        id: 'grp-meter',
        label: 'Versmaß',
        options: [
          { id:'mt-on',  text:'Versmaß',       value:'On' },
          { id:'mt-off', text:'Ohne Versmaß',  value:'Off', default:true },
        ],
        onChange: v => { state.meter = v; updatePdf(); },
      },
    ];

    for (const g of groups) {
      const wrap = document.createElement('div');
      wrap.className = 'radio-group';
      const lab = document.createElement('span');
      lab.className = 'muted';
      lab.style.marginRight = '8px';
      lab.textContent = g.label + ':';
      wrap.appendChild(lab);

      for (const opt of g.options) {
        const span = document.createElement('span');
        span.className = 'radio';
        const inp = document.createElement('input');
        inp.type = 'radio';
        inp.name = g.id;
        inp.id = opt.id;
        inp.value = opt.value;
        if (opt.default) inp.checked = true;
        const lbl = document.createElement('label');
        lbl.setAttribute('for', opt.id);
        lbl.textContent = opt.text;
        span.appendChild(inp);
        span.appendChild(lbl);
        wrap.appendChild(span);

        inp.addEventListener('change', () => {
          if (inp.checked) g.onChange(inp.value);
        });
      }
      pdfControls.appendChild(wrap);
    }

    // Refresh-Button wieder anhängen (falls vorhanden)
    if (pdfRefresh) {
      pdfControls.appendChild(pdfRefresh);
    }
    // Download / Open Buttons bleiben bestehen (IDs schon im DOM)
    if (pdfDL)   pdfControls.appendChild(pdfDL);
    if (pdfOpen) pdfControls.appendChild(pdfOpen);
  }

  // ---------- PDF Update ----------
  function setBusy(on) {
    if (!pdfBusy) return;
    pdfBusy.setAttribute('aria-hidden', on ? 'false' : 'true');
    pdfBusy.style.display = on ? '' : 'none';
  }

  function updatePdf() {
    const url = currentPdfUrl();
    if (pdfDL)   pdfDL.href = url;
    if (pdfOpen) pdfOpen.href = url;
    if (pdfMeta) pdfMeta.textContent = [
      state.source === 'draft' ? 'Entwurf' : 'Original',
      filenameStrength(),
      filenameColor(),
      filenameTags(),
      (state.meter === 'On' ? 'Versmaß' : 'Ohne Versmaß')
    ].join(' · ');

    if (pdfFrame) {
      setBusy(true);
      // kleines Timeout, damit Spinner sichtbar ist
      setTimeout(() => {
        pdfFrame.data = url;
        // Best effort: nach kurzer Zeit Busy wieder aus
        setTimeout(() => setBusy(false), 300);
      }, 30);
    }
  }

  // ---------- TXT-Anzeige & Links ----------
  function initTxt() {
    if (origTxtLink) {
      origTxtLink.href = TXT_ORIG;
    }
    if (origTxtObj) {
      origTxtObj.data = TXT_ORIG;
    }
  }

  // ---------- Optionen-Dialog → Payload sammeln ----------
  // Das versteckte Feld #selected-tags-json füllen wir bereits in aias.html per Inline-Script,
  // hier nur noch ein Hook, falls du später per JS direkt auf den Builder feuerst.
  function getSelectedPayload() {
    const hidden = $('#selected-tags-json');
    if (!hidden) return {};
    try {
      return JSON.parse(hidden.value || '{}');
    } catch {
      return {};
    }
  }

  // ---------- PDF „aktualisieren“ ----------
  if (pdfRefresh) {
    pdfRefresh.addEventListener('click', () => {
      // Hier könntest du optional einen API-Call triggern, der Drafts baut
      // und payload.json speichert. Frontend-seitig aktualisieren wir „nur“ die Anzeige:
      updatePdf();
    });
  }

  // ---------- Scroll-Link der zwei Text-Panes (optional) ----------
  (function linkScrolling() {
    const chk = $('#scroll-link input[type=checkbox]');
    if (!chk) return;
    let lock = false;
    const left = $('#bb-original-pre');
    const right = $('#bb-draft-view');
    if (!left || !right) return;

    function sync(from, to) {
      if (lock) return;
      if (!chk.checked) return;
      lock = true;
      const ratio = from.scrollTop / (from.scrollHeight - from.clientHeight || 1);
      to.scrollTop = ratio * (to.scrollHeight - to.clientHeight);
      requestAnimationFrame(() => (lock = false));
    }

    left && left.addEventListener('scroll', () => sync(left, right));
    right && right.addEventListener('scroll', () => sync(right, left));
  })();

  // ---------- Init ----------
  buildControls();
  initTxt();
  updatePdf();
})();

