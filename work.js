// work.js — universelle Werk-Logik (Poesie & Prosa)
// Lädt Texte/PDFs gemäß URL-Parametern ?kind=<poesie|prosa>&author=<Autor>&work=<Werk>
// und stellt die alte Funktionalität (Tags/Farben ausblenden, Textgröße ±, Scroll-Sync, PDF-Kombis) bereit.

(function () {
  // ---------- Helpers ----------
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  function getQS() {
    const u = new URL(location.href);
    const kind = (u.searchParams.get("kind") || "").toLowerCase(); // poesie | prosa
    const author = u.searchParams.get("author") || "";
    const work = u.searchParams.get("work") || "";
    return { kind, author, work };
  }

  function safeId(s) {
    return s.replace(/\s+/g, "_");
  }

  // Map Radiovaluess → Dateinamens-Segmente
  const StrengthLabel = {
    NORMAL: "Normal",
    GR_FETT: "GR_Fett",
    DE_FETT: "DE_Fett",
  };
  const ColorLabel = {
    COLOUR: "Colour",
    BLACK_WHITE: "BlackWhite",
  };
  const TagLabel = {
    TAGS: "Tag",
    NO_TAGS: "NoTags",
  };

  // Ermittelt, ob für (kind, author, work) Versmaß-Schalter gezeigt werden sollen
  // Heuristik: Poesie hat optional Versmaß; Prosa nie. Du kannst hier feiner per Autor/Werk steuern.
  function supportsMeter(kind, author, work) {
    if (kind !== "poesie") return false;
    // Feinsteuerung: Aischylos Der_gefesselte_Prometheus, Homer, Hesiod, ApolloniosRhodos, ggf. weitere
    const a = author.toLowerCase();
    const w = work.toLowerCase();
    if (a === "aischylos" && /prometheus|gefesselte/.test(w)) return true;
    if (a === "homer") return true;
    if (a === "hesiod") return true;
    if (a === "apolloniosrhodos") return true;
    // viele Sophokles-Stücke ohne Meter:
    return false;
  }

  function textPath(kind, author, work, variant) {
    // variant: "orig" => <work>.txt, "birk" => <work>_birkenbihl.txt
    const base = `texte/${kind}/${author}/${work}`;
    return variant === "birk" ? `${base}_birkenbihl.txt` : `${base}.txt`;
  }

  function pdfPath(kind, author, work, srcKind, strength, color, tag, meterOn) {
    const baseDir =
      srcKind === "original"
        ? `pdf/original_${kind}_pdf/${author}`
        : `pdf_drafts/draft_${kind}_pdf/${author}`;

    const fileCore =
      srcKind === "original"
        ? `${work}_${StrengthLabel[strength]}_${ColorLabel[color]}_${TagLabel[tag]}`
        : `${work}_DRAFT_LATEST_${StrengthLabel[strength]}_${ColorLabel[color]}_${TagLabel[tag]}`;

    const meter = meterOn ? "_Versmaß" : "";
    return `${baseDir}/${fileCore}${meter}.pdf`;
  }

  // ----------- Tag/Color-Filterung im Text (reine Anzeige → zerstört Original nicht) -----------
  // Grammatik-Tags sind Klammer-Token wie (N) (Aor) (Akt) usw. – optional selektiv später erweiterbar.
  const TAG_RE = /\(([A-Za-z/≈]+)\)/g;
  // Farbkürzel: führende # / + / - (deine Praxis im Text)
  const COLOR_PREFIX_RE = /(^|[\s\[])[#\+\-]([^\s\]\)]+)/g;

  function renderWithOptions(raw, { hideTags, hideColors }) {
    let s = raw || "";
    if (hideTags) {
      s = s.replace(TAG_RE, ""); // alle Klammer-Tags ausblenden
    }
    if (hideColors) {
      // nur Präfix (#|+|-) entfernen, Wort erhalten
      s = s.replace(COLOR_PREFIX_RE, (m, leading, word) => `${leading}${word}`);
    }
    return s;
  }

  // ----------- Größe/Scroll -----------
  function adjustFontSize(el, delta) {
    const cs = getComputedStyle(el);
    const cur = parseFloat(cs.fontSize || "16");
    const next = Math.max(10, Math.min(32, cur + delta));
    el.style.fontSize = next + "px";
  }
  function syncScroll(a, b, on) {
    if (!on) {
      a.onscroll = null;
      b.onscroll = null;
      return;
    }
    let lock = false;
    const link = (src, dst) => {
      src.addEventListener("scroll", () => {
        if (lock) return;
        lock = true;
        const r = src.scrollTop / (src.scrollHeight - src.clientHeight || 1);
        dst.scrollTop = r * (dst.scrollHeight - dst.clientHeight);
        lock = false;
      });
    };
    link(a, b);
    link(b, a);
  }

  // ----------- State -----------
  const state = {
    kind: "",
    author: "",
    work: "",
    meterEnabled: false,

    // Anzeigeoptionen für Previews/Editoren
    origHideTags: false,
    origHideColors: false,
    birkHideTags: false,
    birkHideColors: false,
    draftHideTags: false,
    draftHideColors: false,

    // Texte
    rawOrig: "",
    rawBirk: "",
    rawDraft: "",

    // PDF-Auswahl
    selectedSrc: "original", // original | draft
    selectedStrength: "NORMAL",
    selectedColor: "COLOUR",
    selectedTag: "TAGS",
    selectedMeter: "METER_OFF",
  };

  // ----------- Init ----------
  async function init() {
    const { kind, author, work } = getQS();
    if (!kind || !author || !work) {
      console.warn("URL-Parameter unvollständig. Erwartet ?kind=&author=&work=");
      return;
    }
    state.kind = kind;
    state.author = author;
    state.work = work;
    state.meterEnabled = supportsMeter(kind, author, work);

    // UI: Versmaß-Reihe sichtbar/unsichtbar
    const meterRow = $("#meterRow");
    if (meterRow) meterRow.style.display = state.meterEnabled ? "" : "none";

    // Titel (optional)
    const headTitle = $("#work-title");
    if (headTitle) {
      headTitle.textContent = `${author} — ${work.replace(/_/g, " ")}`;
    }

    // Texte laden
    await loadTexts(kind, author, work);

    // Controls binden
    bindControls();

    // Anfangs-PDF setzen
    updatePdf();

    // Scroll-Sync initial
    const origEl = $("#origSrc");
    const birkEl = $("#birkSrc");
    const syncCb = $("#syncScroll");
    if (origEl && birkEl && syncCb) {
      syncScroll(origEl, birkEl, syncCb.checked);
      syncCb.addEventListener("change", () =>
        syncScroll(origEl, birkEl, syncCb.checked)
      );
    }
  }

  async function loadTexts(kind, author, work) {
    const [origUrl, birkUrl] = [
      textPath(kind, author, work, "orig"),
      textPath(kind, author, work, "birk"),
    ];

    const loadOne = async (url) => {
      try {
        const r = await fetch(url, { cache: "no-store" });
        if (!r.ok) throw new Error(r.status + " " + r.statusText);
        return await r.text();
      } catch (e) {
        console.warn("Konnte Text nicht laden:", url, e);
        return ""; // leer anzeigen, aber UI bleibt bedienbar
      }
    };

    state.rawOrig = await loadOne(origUrl);
    state.rawBirk = await loadOne(birkUrl);

    // Draft initial = Birkenbihl (falls leer, dann orig)
    state.rawDraft = state.rawBirk || state.rawOrig;

    renderAllText();
  }

  function renderAllText() {
    // Original
    const origEl = $("#origSrc");
    if (origEl) {
      origEl.textContent = renderWithOptions(state.rawOrig, {
        hideTags: state.origHideTags,
        hideColors: state.origHideColors,
      });
    }
    // Birkenbihl
    const birkEl = $("#birkSrc");
    if (birkEl) {
      birkEl.textContent = renderWithOptions(state.rawBirk, {
        hideTags: state.birkHideTags,
        hideColors: state.birkHideColors,
      });
    }
    // Draft
    const draftTa = $("#draftEditor");
    if (draftTa) {
      // textarea zeigt IMMER Rohtext (Bearbeitung)
      draftTa.value = state.rawDraft || "";
      // separate Preview? Wenn ja, hier rendern.
    }
  }

  function bindControls() {
    // --- Original-Schalter
    const origTags = $("#origHideTags");
    if (origTags)
      origTags.addEventListener("change", () => {
        state.origHideTags = !!origTags.checked;
        renderAllText();
      });
    const origColors = $("#origHideColors");
    if (origColors)
      origColors.addEventListener("change", () => {
        state.origHideColors = !!origColors.checked;
        renderAllText();
      });
    const oMinus = $("#origSizeMinus");
    const oPlus = $("#origSizePlus");
    if (oMinus)
      oMinus.addEventListener("click", () => adjustFontSize($("#origSrc"), -1));
    if (oPlus)
      oPlus.addEventListener("click", () => adjustFontSize($("#origSrc"), +1));

    // --- Birkenbihl-Schalter
    const birkTags = $("#birkHideTags");
    if (birkTags)
      birkTags.addEventListener("change", () => {
        state.birkHideTags = !!birkTags.checked;
        renderAllText();
      });
    const birkColors = $("#birkHideColors");
    if (birkColors)
      birkColors.addEventListener("change", () => {
        state.birkHideColors = !!birkColors.checked;
        renderAllText();
      });
    const bMinus = $("#birkSizeMinus");
    const bPlus = $("#birkSizePlus");
    if (bMinus)
      bMinus.addEventListener("click", () => adjustFontSize($("#birkSrc"), -1));
    if (bPlus)
      bPlus.addEventListener("click", () => adjustFontSize($("#birkSrc"), +1));

    // --- Draft-Schalter
    const dTags = $("#draftHideTags");
    if (dTags)
      dTags.addEventListener("change", () => {
        state.draftHideTags = !!dTags.checked;
        // Draft-Preview wäre hier; Editor bleibt roh
      });
    const dColors = $("#draftHideColors");
    if (dColors)
      dColors.addEventListener("change", () => {
        state.draftHideColors = !!dColors.checked;
      });

    const draftTa = $("#draftEditor");
    if (draftTa) {
      draftTa.addEventListener("input", () => {
        state.rawDraft = draftTa.value;
        // lokale Speicherung (Session) möglich:
        // sessionStorage.setItem(draftKey(), state.rawDraft);
      });
    }

    const dMinus = $("#draftSizeMinus");
    const dPlus = $("#draftSizePlus");
    if (dMinus)
      dMinus.addEventListener("click", () =>
        adjustFontSize($("#draftEditor"), -1)
      );
    if (dPlus)
      dPlus.addEventListener("click", () =>
        adjustFontSize($("#draftEditor"), +1)
      );

    // Reset Draft (Warnmodal optional)
    const resetBtn = $("#resetDraftBtn");
    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        if (
          confirm(
            "Entwurf zurücksetzen? Ungespeicherte Änderungen gehen verloren."
          )
        ) {
          state.rawDraft = state.rawBirk || state.rawOrig || "";
          renderAllText();
        }
      });
    }

    // --- PDF-Radiogruppen (Quelle / Stärke / Farbe / Tags / Versmaß)
    bindRadioGroup("srcSel", (v) => {
      state.selectedSrc = v; // 'original' | 'draft'
      updatePdf();
    });
    bindRadioGroup("strengthSel", (v) => {
      state.selectedStrength = v; // NORMAL | GR_FETT | DE_FETT
      updatePdf();
    });
    bindRadioGroup("colorSel", (v) => {
      state.selectedColor = v; // COLOUR | BLACK_WHITE
      updatePdf();
    });
    bindRadioGroup("tagSel", (v) => {
      state.selectedTag = v; // TAGS | NO_TAGS
      updatePdf();
    });
    bindRadioGroup("meterSel", (v) => {
      state.selectedMeter = v; // METER_ON | METER_OFF
      updatePdf();
    });
  }

  function bindRadioGroup(name, onChange) {
    $$(`input[name="${name}"]`).forEach((input) => {
      input.addEventListener("change", () => {
        if (input.checked) onChange(input.value);
      });
    });
  }

  function updatePdf() {
    const frame = $("#pdfFrame");
    if (!frame) return;
    const meterOn =
      state.meterEnabled && state.selectedMeter === "METER_ON" ? true : false;

    const url = pdfPath(
      state.kind,
      state.author,
      state.work,
      state.selectedSrc,
      state.selectedStrength,
      state.selectedColor,
      state.selectedTag,
      meterOn
    );
    frame.src = url;

    const status = $("#pdfStatus");
    if (status) {
      status.textContent = `Quelle: ${
        state.selectedSrc === "original" ? "Original" : "Entwurf"
      } · ${StrengthLabel[state.selectedStrength]} · ${
        ColorLabel[state.selectedColor]
      } · ${TagLabel[state.selectedTag]}${
        meterOn ? " · Versmaß" : ""
      }`;
    }
  }

  // Run
  document.addEventListener("DOMContentLoaded", init);
})();
