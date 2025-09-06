/* aias.js — Seitenlogik für Aias (ohne Draft-Vorschau; Scroll-Toggle im An/Aus-Stil) */
(function () {
  const CONF = {
    WORK: "Aias",
    LOCAL_KEY: "draft_Aias_birkenbihl",
    TXT_ORIG_PATH: "texte/Aias_birkenbihl.txt",
    PDF_DRAFT_BASE: "pdf_drafts/Aias_DRAFT_LATEST_", // + Normal/Fett[+Suffix].pdf
    PDF_OFFICIAL_BASE: "pdf/TragödieAias_",          // + Normal/Fett.pdf
    WORKER_URL: "https://birkenbihl-draft-01.klemp-tobias.workers.dev",
    FONT_KEY_LEFT:  "font_Aias_original_px",
    FONT_KEY_RIGHT: "font_Aias_draft_px",
    WAIT_ATTEMPTS: 24,
    WAIT_DELAY_MS: 5000,
  };

  const U = window.Utils || {};
  const byId = (id) => document.getElementById(id);

  // PDF oben
  const pdfFrame       = byId("pdf-frame");
  const pdfNormal      = byId("pdf-normal");
  const pdfFett        = byId("pdf-fett");
  const srcOriginal    = byId("src-original");
  const srcDraft       = byId("src-draft");
  const btnRefresh     = byId("pdf-refresh");
  const btnPdfDownload = byId("pdf-download");
  const btnPdfOpen     = byId("pdf-open");

  // Original (links)
  const origPre          = byId("bb-original-pre");
  const origToggleTags   = byId("orig-toggle-tags");
  const origToggleColors = byId("orig-toggle-colors");
  const origSzDec        = byId("orig-font-minus");
  const origSzInc        = byId("orig-font-plus");

  // Entwurf (rechts)
  const editor           = byId("bb-editor");
  const draftSzDec       = byId("draft-font-minus");
  const draftSzInc       = byId("draft-font-plus");
  const btnUploadDraft   = byId("bb-upload-draft");
  const btnDownloadDraft = byId("bb-download-draft");
  const btnReset         = byId("bb-reset");
  const btnGenerateOrig  = byId("bb-generate-original");
  const btnGenerateDraft = byId("bb-generate-draft");

  // Status / Save-UI
  const saveDot     = byId("save-dot");
  const saveText    = byId("save-text");
  const draftStatus = byId("draft-status");

  // Optionen-Modal
  const optBackdrop    = byId("opt-backdrop");
  const optClose       = byId("opt-close");
  const optCancel      = byId("opt-cancel");
  const optGenerate    = byId("opt-generate");
  const optColors      = byId("opt-colors");
  const optTags        = byId("opt-tags");
  const optAdv         = byId("opt-adv");
  const optColorN      = byId("opt-color-n");
  const optColorV      = byId("opt-color-v");
  const optColorAj     = byId("opt-color-aj");
  const tagAv          = byId("tag-Av");
  const tagPt          = byId("tag-Pt");
  const tagKo          = byId("tag-Ko");
  const tagArt         = byId("tag-Art");
  const tagAj          = byId("tag-Aj");
  const tagV           = byId("tag-V");
  const tagN           = byId("tag-N");
  const optContextNote = byId("opt-context-note");

  // Zurücksetzen-Modal
  const modalBackdrop = byId("confirm-backdrop");
  const modalClose    = byId("confirm-close");
  const modalCancel   = byId("confirm-cancel");
  const modalOk       = byId("confirm-ok");

  // Scroll-Kopplung (An/Aus-Toggle)
  const scrollToggle  = byId("scroll-link");

  let rawOriginal = "";
  let rawDraft    = "";
  let optContext  = "draft";
  let unlinkScroll = () => {};

  // PDF
  function currentPdfUrl(suffix = "") {
    const kind = (pdfFett && pdfFett.checked) ? "Fett" : "Normal";
    const useDraft = !!(srcDraft && srcDraft.checked);
    const base = useDraft ? CONF.PDF_DRAFT_BASE : CONF.PDF_OFFICIAL_BASE;
    return base + kind + (useDraft ? (suffix || "") : "") + ".pdf";
  }
  function refreshPdf(bust = false, suffix = "") {
    const url = currentPdfUrl(suffix);
    if (U.setPdfViewer) U.setPdfViewer(pdfFrame, btnPdfDownload, btnPdfOpen, url, bust);
  }

  // Init
  (async function init() {
    try { rawOriginal = U.fetchText ? await U.fetchText(CONF.TXT_ORIG_PATH) : ""; }
    catch { rawOriginal = "Konnte " + CONF.TXT_ORIG_PATH + " nicht laden. Liegt die Datei im Ordner texte/?"; }

    if (origPre) {
      U.updateToggleLabel && U.updateToggleLabel(origToggleTags, true);
      U.updateToggleLabel && U.updateToggleLabel(origToggleColors, true);
      origPre.textContent = U.renderWithFilters ? U.renderWithFilters(rawOriginal, false, false) : (rawOriginal || "");
    }

    rawDraft = (U.loadLocalDraft ? U.loadLocalDraft(CONF.LOCAL_KEY) : "") || rawOriginal || "";
    if (editor) editor.value = rawDraft;

    restoreFontSizes();
    setupCoupledScroll();
    refreshPdf(false);
  })();

  // Font-Größen
  function restoreFontSizes() {
    try {
      const leftPx  = parseFloat(localStorage.getItem(CONF.FONT_KEY_LEFT)  || "0");
      const rightPx = parseFloat(localStorage.getItem(CONF.FONT_KEY_RIGHT) || "0");
      if (origPre && leftPx  > 0 && U.setFontSize) U.setFontSize(origPre, leftPx);
      if (editor  && rightPx > 0 && U.setFontSize) U.setFontSize(editor,  rightPx);
    } catch {}
  }
  function bumpFont(elList, storageKey, deltaPx) {
    const tgt = elList.find(Boolean); if (!tgt) return;
    const base = U.getFontSize ? U.getFontSize(tgt) : parseFloat((getComputedStyle(tgt).fontSize||"14px"));
    const px = base + deltaPx;
    elList.forEach((el) => el && U.setFontSize && U.setFontSize(el, px));
    try { localStorage.setItem(storageKey, String(px)); } catch {}
  }
  origSzDec && origSzDec.addEventListener("click", () => bumpFont([origPre], CONF.FONT_KEY_LEFT, -1.0));
  origSzInc && origSzInc.addEventListener("click", () => bumpFont([origPre], CONF.FONT_KEY_LEFT, +1.0));
  draftSzDec && draftSzDec.addEventListener("click", () => bumpFont([editor],  CONF.FONT_KEY_RIGHT, -1.0));
  draftSzInc && draftSzInc.addEventListener("click", () => bumpFont([editor],  CONF.FONT_KEY_RIGHT, +1.0));

  // Scroll koppeln (An/Aus)
  function setupCoupledScroll() {
    unlinkScroll();
    const checked = !!(scrollToggle && scrollToggle.querySelector("input")?.checked);
    if (origPre && editor && U.coupleScroll && checked) {
      unlinkScroll = U.coupleScroll(origPre, editor, () => !!(scrollToggle && scrollToggle.querySelector("input")?.checked));
    } else {
      unlinkScroll = () => {};
    }
    // UI-Label aktualisieren
    if (U.updateToggleLabel && scrollToggle) {
      U.updateToggleLabel(scrollToggle, !!(scrollToggle.querySelector("input")?.checked));
    }
  }
  scrollToggle && scrollToggle.addEventListener("click", () => {
    const input = scrollToggle.querySelector("input");
    if (!input) return;
    input.checked = !input.checked;
    setupCoupledScroll();
  });

  // Original-Filter
  function currentOrigFilters() {
    const showTags   = !!(origToggleTags && origToggleTags.querySelector("input")?.checked);
    const showColors = !!(origToggleColors && origToggleColors.querySelector("input")?.checked);
    return { hideTags: !showTags, hideColors: !showColors };
  }
  function renderOriginal() {
    if (!origPre) return;
    const f = currentOrigFilters();
    origPre.textContent = U.renderWithFilters ? U.renderWithFilters(rawOriginal, f.hideTags, f.hideColors) : rawOriginal;
  }
  function bindToggle(toggleEl, handler) {
    if (!toggleEl) return;
    toggleEl.addEventListener("click", () => {
      const input = toggleEl.querySelector("input");
      if (!input) return;
      input.checked = !input.checked;
      U.updateToggleLabel && U.updateToggleLabel(toggleEl, input.checked);
      handler && handler();
    });
  }
  bindToggle(origToggleTags,   renderOriginal);
  bindToggle(origToggleColors, renderOriginal);

  // Editor + Autosave
  let saveTimer = null;
  editor && editor.addEventListener("input", () => {
    U.setSaveState && U.setSaveState(saveDot, saveText, "busy");
    rawDraft = editor.value || "";
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      U.saveLocalDraft && U.saveLocalDraft(CONF.LOCAL_KEY, rawDraft);
      U.setSaveState && U.setSaveState(saveDot, saveText, "ok", "Gespeichert");
    }, 250);
  });

  // Upload/Download/Reset
  btnUploadDraft && btnUploadDraft.addEventListener("click", () => {
    const inp = document.createElement("input");
    inp.type = "file"; inp.accept = ".txt,text/plain";
    inp.addEventListener("change", async () => {
      const file = inp.files && inp.files[0]; if (!file) return;
      try {
        const text = await file.text();
        rawDraft = text || ""; if (editor) editor.value = rawDraft;
        U.saveLocalDraft && U.saveLocalDraft(CONF.LOCAL_KEY, rawDraft);
        U.setSaveState && U.setSaveState(saveDot, saveText, "ok", "Entwurf geladen");
      } catch (e) { alert("Konnte Datei nicht lesen: " + e.message); }
    });
    inp.click();
  });

  btnDownloadDraft && btnDownloadDraft.addEventListener("click", async () => {
    const text = editor ? (editor.value || "") : (rawDraft || "");
    if (!text.trim()) { alert("Kein Entwurf vorhanden."); return; }
    try {
      const code = U.diffCode ? await U.diffCode(rawOriginal || "", text) : String(Date.now());
      const fname = `${CONF.WORK}_birkenbihl_ENTWURF_${code}.txt`;
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = fname; document.body.appendChild(a); a.click();
      setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1000);
    } catch (e) { alert("Konnte Entwurf nicht herunterladen: " + e.message); }
  });

  function openConfirm() {
    if (!modalBackdrop) return;
    modalBackdrop.style.display = "flex";
    modalBackdrop.setAttribute("aria-hidden", "false");
  }
  function closeConfirm() {
    if (!modalBackdrop) return;
    modalBackdrop.style.display = "none";
    modalBackdrop.setAttribute("aria-hidden", "true");
  }
  btnReset   && btnReset.addEventListener("click", openConfirm);
  modalClose && modalClose.addEventListener("click", closeConfirm);
  modalCancel&& modalCancel.addEventListener("click", closeConfirm);
  modalBackdrop && modalBackdrop.addEventListener("click", (e) => { if (e.target === modalBackdrop) closeConfirm(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && modalBackdrop && modalBackdrop.style.display === "flex") closeConfirm(); });
  modalOk && modalOk.addEventListener("click", () => {
    U.clearLocalDraft && U.clearLocalDraft(CONF.LOCAL_KEY);
    rawDraft = rawOriginal || "";
    if (editor) editor.value = rawDraft;
    U.setSaveState && U.setSaveState(saveDot, saveText, "ready", "Bereit");
    closeConfirm();
  });

  // PDF-Umschaltung
  ;[pdfNormal, pdfFett, srcOriginal, srcDraft].forEach((el) => {
    el && el.addEventListener("change", () => refreshPdf(true));
  });
  btnRefresh && btnRefresh.addEventListener("click", () => refreshPdf(true));

  // Optionen-Modal
  function openOptModal(context) {
    optContext = context;
    if (optContextNote) {
      optContextNote.textContent =
        context === "original"
          ? "Hinweis: Oben wird auf „Original“ umgeschaltet. Offizielle PDFs liegen im Ordner pdf/."
          : "Der Entwurf wird mit diesen Optionen gebaut und oben angezeigt.";
    }
    if (optBackdrop) {
      optBackdrop.style.display = "flex";
      optBackdrop.setAttribute("aria-hidden", "false");
    }
  }
  function closeOptModal() {
    if (!optBackdrop) return;
    optBackdrop.style.display = "none";
    optBackdrop.setAttribute("aria-hidden", "true");
  }
  btnGenerateOrig  && btnGenerateOrig.addEventListener("click", () => openOptModal("original"));
  btnGenerateDraft && btnGenerateDraft.addEventListener("click", () => openOptModal("draft"));
  optClose  && optClose.addEventListener("click", closeOptModal);
  optCancel && optCancel.addEventListener("click", closeOptModal);
  optBackdrop && optBackdrop.addEventListener("click", (e) => { if (e.target === optBackdrop) closeOptModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && optBackdrop && optBackdrop.style.display === "flex") closeOptModal(); });

  function suffixFromOptions() {
    let suffix = "";
    if (optColors && !optColors.checked) suffix += "_BW";
    if (optTags && !optTags.checked)     suffix += "_NoTags";
    if (optAdv && optAdv.open)           suffix += "_Custom";
    return suffix;
  }
  function collectOptionsPayload() {
    return {
      colors:   !!(optColors && optColors.checked),
      showTags: !!(optTags   && optTags.checked),
      custom: (optAdv && optAdv.open)
        ? {
            colorByPOS: { N: !!(optColorN&&optColorN.checked), V: !!(optColorV&&optColorV.checked), Aj: !!(optColorAj&&optColorAj.checked) },
            visibleTags:{ Av:!!(tagAv&&tagAv.checked), Pt:!!(tagPt&&tagPt.checked), Ko:!!(tagKo&&tagKo.checked),
                          Art:!!(tagArt&&tagArt.checked), Aj:!!(tagAj&&tagAj.checked), V:!!(tagV&&tagV.checked), N:!!(tagN&&tagN.checked) },
          }
        : null,
    };
  }

  const optGenerateHandler = async () => {
    const suffix = suffixFromOptions();

    if (optContext === "original") {
      if (srcOriginal) srcOriginal.checked = true;
      if (srcDraft)    srcDraft.checked = false;
      refreshPdf(true);
      draftStatus && (draftStatus.innerHTML = '<span class="small">Quelle auf <b>Original</b> umgestellt.</span>');
      closeOptModal();
      return;
    }

    const text = editor ? (editor.value || "") : (rawDraft || "");
    if (!text.trim()) { alert("Kein Entwurfstext vorhanden."); return; }

    try {
      draftStatus && (draftStatus.textContent = "⬆️ Entwurf wird an den Build-Dienst gesendet…");
      const opts = collectOptionsPayload();
      const res = await fetch(CONF.WORKER_URL + "/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ work: CONF.WORK, text, opts }),
      });
      const j = await res.json().catch(() => ({}));
      if (!res.ok || !j.ok) throw new Error(j.error || ("HTTP " + res.status));

      draftStatus && (draftStatus.textContent = "✅ Entwurf angenommen. Build startet…");

      if (srcDraft)    srcDraft.checked = true;
      if (srcOriginal) srcOriginal.checked = false;

      const kind = (pdfFett && pdfFett.checked) ? "Fett" : "Normal";
      const target = `${CONF.PDF_DRAFT_BASE}${kind}${suffix}.pdf`;

      const ok = U.waitForPdf
        ? await U.waitForPdf(target, CONF.WAIT_ATTEMPTS, CONF.WAIT_DELAY_MS)
        : true;

      refreshPdf(true, suffix);
      draftStatus && (draftStatus.innerHTML = ok
        ? "✅ Entwurfs-PDF aktualisiert."
        : '⚠️ PDF noch nicht bereit. Bitte später „PDF aktualisieren“ klicken.');
    } catch (e) {
      draftStatus && (draftStatus.innerHTML = '<span class="err">Fehler: ' + (e && e.message ? e.message : e) + "</span>");
    } finally {
      closeOptModal();
    }
  };
  optGenerate && optGenerate.addEventListener("click", optGenerateHandler);
})();
