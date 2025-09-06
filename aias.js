/* aias.js — Seitenlogik für Aias (robust gegen ID-Varianten; nutzt window.Utils) */
(function () {
  // ====== Konfiguration (werksbezogen) ======
  const CONF = {
    WORK: "Aias",
    LOCAL_KEY: "draft_Aias_birkenbihl",
    TXT_ORIG_PATH: "texte/Aias_birkenbihl.txt",
    PDF_DRAFT_BASE: "pdf_drafts/Aias_DRAFT_LATEST_", // + Normal/Fett[+Suffix].pdf
    PDF_OFFICIAL_BASE: "pdf/TragödieAias_",          // + Normal/Fett.pdf
    WORKER_URL: "https://birkenbihl-draft-01.klemp-tobias.workers.dev",
    FONT_KEY_LEFT:  "font_Aias_original_px",
    FONT_KEY_RIGHT: "font_Aias_draft_px",
    WAIT_ATTEMPTS: 24,   // ~2 min bei 5 s Polling
    WAIT_DELAY_MS: 5000,
  };

  // ====== Kurz-Helper ======
  const U = window.Utils || {};
  const byId = (...ids) => {
    for (const id of ids) {
      const el = document.getElementById(id);
      if (el) return el;
    }
    return null;
  };

  // ====== Elemente: PDF oben ======
  const pdfFrame       = byId("pdf-frame");
  const pdfNormal      = byId("pdf-normal");
  const pdfFett        = byId("pdf-fett");
  const srcOriginal    = byId("src-original");
  const srcDraft       = byId("src-draft");
  const btnRefresh     = byId("pdf-refresh");
  const btnPdfDownload = byId("pdf-download");
  const btnPdfOpen     = byId("pdf-open");

  // ====== Elemente: Original (links) ======
  const origPre          = byId("bb-original-pre");
  const origToggleTags   = byId("orig-toggle-tags");
  const origToggleColors = byId("orig-toggle-colors");
  // Tolerant: alte vs. neue IDs
  const origSzDec        = byId("orig-size-dec", "orig-font-minus");
  const origSzInc        = byId("orig-size-inc", "orig-font-plus");

  // ====== Elemente: Entwurf (rechts) ======
  const editor             = byId("bb-editor");                       // immer sichtbar
  const draftPreview       = byId("bb-view-draft", "bb-draft-preview"); // gefilterte Vorschau (tolerant)
  const draftToggleTags    = byId("draft-toggle-tags");
  const draftToggleColors  = byId("draft-toggle-colors");
  const draftSzDec         = byId("draft-size-dec", "draft-font-minus");
  const draftSzInc         = byId("draft-size-inc", "draft-font-plus");
  const btnUploadDraft     = byId("bb-upload-draft");
  const btnDownloadDraft   = byId("bb-download-draft");
  const btnReset           = byId("bb-reset");
  const btnGenerateOrig    = byId("bb-generate-original");
  const btnGenerateDraft   = byId("bb-generate-draft");

  // ====== Status / Save-UI ======
  const saveDot     = byId("save-dot");
  const saveText    = byId("save-text");
  const draftStatus = byId("draft-status");

  // ====== Optionen-Modal ======
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

  // ====== Zurücksetzen-Modal ======
  const modalBackdrop = byId("confirm-backdrop");
  const modalClose    = byId("confirm-close");
  const modalCancel   = byId("confirm-cancel");
  const modalOk       = byId("confirm-ok");

  // ====== Scroll-Kopplung ======
  const chkCouple = byId("link-scroll", "scroll-link"); // tolerant

  // ====== State ======
  let rawOriginal = "";
  let rawDraft    = "";
  let optContext  = "draft"; // "draft" | "original"
  let unlinkScroll = () => {};

  // ====== PDF-URL bauen und anzeigen ======
  function currentPdfUrl(suffix = "") {
    const kind = (pdfFett && pdfFett.checked) ? "Fett" : "Normal";
    const useDraft = !!(srcDraft && srcDraft.checked);
    const base = useDraft ? CONF.PDF_DRAFT_BASE : CONF.PDF_OFFICIAL_BASE;
    // Nur für Entwurf wird ein Suffix (z. B. _BW/_NoTags/_Custom) genutzt
    return base + kind + (useDraft ? (suffix || "") : "") + ".pdf";
  }
  function refreshPdf(bust = false, suffix = "") {
    const url = currentPdfUrl(suffix);
    if (U.setPdfViewer) {
      U.setPdfViewer(pdfFrame, btnPdfDownload, btnPdfOpen, url, bust);
    } else {
      // sehr defensiv, falls Utils fehlt
      if (pdfFrame) pdfFrame.setAttribute("data", url + (bust ? ("?t=" + Date.now()) : "") + "#view=FitH");
      if (btnPdfDownload) btnPdfDownload.setAttribute("href", url);
      if (btnPdfOpen) btnPdfOpen.setAttribute("href", url);
    }
  }

  // ====== Initial laden ======
  (async function init() {
    try {
      rawOriginal = U.fetchText ? await U.fetchText(CONF.TXT_ORIG_PATH) : "";
    } catch (e) {
      rawOriginal = "Konnte " + CONF.TXT_ORIG_PATH + " nicht laden. Liegt die Datei im Ordner texte/?";
    }

    // Original anzeigen (Standard: Filter „An“ ⇒ nichts ausblenden)
    if (origPre) {
      U.updateToggleLabel && U.updateToggleLabel(origToggleTags, true);
      U.updateToggleLabel && U.updateToggleLabel(origToggleColors, true);
      origPre.textContent = U.renderWithFilters ? U.renderWithFilters(rawOriginal, false, false) : (rawOriginal || "");
    }

    // Entwurf aus LocalStorage, sonst Original als Ausgangspunkt
    rawDraft = (U.loadLocalDraft ? U.loadLocalDraft(CONF.LOCAL_KEY) : "") || rawOriginal || "";
    if (editor) editor.value = rawDraft;

    // Entwurfs-Vorschau initial
    if (draftPreview) {
      U.updateToggleLabel && U.updateToggleLabel(draftToggleTags, true);
      U.updateToggleLabel && U.updateToggleLabel(draftToggleColors, true);
      draftPreview.textContent = U.renderWithFilters ? U.renderWithFilters(rawDraft, false, false) : (rawDraft || "");
    }

    // Font-Größen wiederherstellen
    restoreFontSizes();

    // Scroll-Kopplung
    setupCoupledScroll();

    // PDF initial
    refreshPdf(false);
  })();

  // ====== Font-Size Steuerung ======
  function restoreFontSizes() {
    try {
      const leftPx  = parseFloat(localStorage.getItem(CONF.FONT_KEY_LEFT)  || "0");
      const rightPx = parseFloat(localStorage.getItem(CONF.FONT_KEY_RIGHT) || "0");
      if (origPre && leftPx  > 0 && U.setFontSize) U.setFontSize(origPre, leftPx);
      if (editor  && rightPx > 0 && U.setFontSize) U.setFontSize(editor,  rightPx);
      if (draftPreview && rightPx > 0 && U.setFontSize) U.setFontSize(draftPreview, rightPx);
    } catch {}
  }
  function bumpFont(elList, storageKey, deltaPx) {
    const target = elList.find(Boolean);
    if (!target) return;
    const base = U.getFontSize ? U.getFontSize(target) : parseFloat((window.getComputedStyle(target).fontSize || "14px"));
    const px = base + deltaPx;
    elList.forEach((el) => el && U.setFontSize && U.setFontSize(el, px));
    try { localStorage.setItem(storageKey, String(px)); } catch {}
  }

  origSzDec && origSzDec.addEventListener("click", () => bumpFont([origPre], CONF.FONT_KEY_LEFT, -1.0));
  origSzInc && origSzInc.addEventListener("click", () => bumpFont([origPre], CONF.FONT_KEY_LEFT, +1.0));
  draftSzDec && draftSzDec.addEventListener("click", () => bumpFont([editor, draftPreview], CONF.FONT_KEY_RIGHT, -1.0));
  draftSzInc && draftSzInc.addEventListener("click", () => bumpFont([editor, draftPreview], CONF.FONT_KEY_RIGHT, +1.0));

  // ====== Scroll koppeln ======
  function setupCoupledScroll() {
    unlinkScroll();
    if (origPre && editor && U.coupleScroll) {
      unlinkScroll = U.coupleScroll(origPre, editor, () => !!(chkCouple && chkCouple.checked));
    } else {
      unlinkScroll = () => {};
    }
  }
  chkCouple && chkCouple.addEventListener("change", setupCoupledScroll);

  // ====== Filter-Schalter (Original) ======
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

  // ====== Filter-Schalter (Entwurf-Preview) ======
  function currentDraftFilters() {
    const showTags   = !!(draftToggleTags && draftToggleTags.querySelector("input")?.checked);
    const showColors = !!(draftToggleColors && draftToggleColors.querySelector("input")?.checked);
    return { hideTags: !showTags, hideColors: !showColors };
  }
  function renderDraftPreview() {
    if (!draftPreview) return;
    const f = currentDraftFilters();
    draftPreview.textContent = U.renderWithFilters ? U.renderWithFilters(rawDraft, f.hideTags, f.hideColors) : rawDraft;
  }
  bindToggle(draftToggleTags,   renderDraftPreview);
  bindToggle(draftToggleColors, renderDraftPreview);

  // ====== Editor (immer aktiv) + Autosave + Live-Preview ======
  let saveTimer = null;
  editor && editor.addEventListener("input", () => {
    U.setSaveState && U.setSaveState(saveDot, saveText, "busy");
    rawDraft = editor.value || "";
    if (saveTimer) clearTimeout(saveTimer);
    renderDraftPreview();
    saveTimer = setTimeout(() => {
      U.saveLocalDraft && U.saveLocalDraft(CONF.LOCAL_KEY, rawDraft);
      U.setSaveState && U.setSaveState(saveDot, saveText, "ok", "Gespeichert");
    }, 250);
  });

  // ====== Upload Entwurf.txt ======
  btnUploadDraft && btnUploadDraft.addEventListener("click", () => {
    const inp = document.createElement("input");
    inp.type = "file";
    inp.accept = ".txt,text/plain";
    inp.addEventListener("change", async () => {
      const file = inp.files && inp.files[0];
      if (!file) return;
      try {
        const text = await file.text();
        rawDraft = text || "";
        if (editor) editor.value = rawDraft;
        U.saveLocalDraft && U.saveLocalDraft(CONF.LOCAL_KEY, rawDraft);
        renderDraftPreview();
        U.setSaveState && U.setSaveState(saveDot, saveText, "ok", "Entwurf geladen");
      } catch (e) {
        alert("Konnte Datei nicht lesen: " + e.message);
      }
    });
    inp.click();
  });

  // ====== Download Entwurf.txt ======
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
    } catch (e) {
      alert("Konnte Entwurf nicht herunterladen: " + e.message);
    }
  });

  // ====== Entwurf zurücksetzen (Modal) ======
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
    renderDraftPreview();
    U.setSaveState && U.setSaveState(saveDot, saveText, "ready", "Bereit");
    closeConfirm();
  });

  // ====== PDF oben (Quelle & Kind & Refresh) ======
  ;[pdfNormal, pdfFett, srcOriginal, srcDraft].forEach((el) => {
    el && el.addEventListener("change", () => refreshPdf(true));
  });
  btnRefresh && btnRefresh.addEventListener("click", () => refreshPdf(true));

  // ====== Optionen-Modal für „PDF generieren“ ======
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
            colorByPOS: {
              N:  !!(optColorN && optColorN.checked),
              V:  !!(optColorV && optColorV.checked),
              Aj: !!(optColorAj && optColorAj.checked),
            },
            visibleTags: {
              Av:  !!(tagAv  && tagAv.checked),
              Pt:  !!(tagPt  && tagPt.checked),
              Ko:  !!(tagKo  && tagKo.checked),
              Art: !!(tagArt && tagArt.checked),
              Aj:  !!(tagAj  && tagAj.checked),
              V:   !!(tagV   && tagV.checked),
              N:   !!(tagN   && tagN.checked),
            },
          }
        : null,
    };
  }

  optGenerate && optGenerate.addEventListener("click", async () => {
    const suffix = suffixFromOptions();

    // Fall A: Nutzer wählt „Original“
    if (optContext === "original") {
      if (srcOriginal) srcOriginal.checked = true;
      if (srcDraft)    srcDraft.checked = false;
      refreshPdf(true); // offizielle PDFs
      draftStatus && (draftStatus.innerHTML = '<span class="small">Quelle auf <b>Original</b> umgestellt.</span>');
      closeOptModal();
      return;
    }

    // Fall B: Entwurf bauen (Worker)
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
        : true; // falls Utils fehlt, nicht blockieren

      refreshPdf(true, suffix);
      draftStatus && (draftStatus.innerHTML = ok
        ? "✅ Entwurfs-PDF aktualisiert."
        : '⚠️ PDF noch nicht bereit. Bitte später „PDF aktualisieren“ klicken.'
      );
    } catch (e) {
      draftStatus && (draftStatus.innerHTML = '<span class="err">Fehler: ' + (e && e.message ? e.message : e) + "</span>");
    } finally {
      closeOptModal();
    }
  });
})();
