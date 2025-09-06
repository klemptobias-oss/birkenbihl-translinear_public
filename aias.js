/* aias.js — Seitenlogik für Aias (nutzt Utils) */
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
  };

  // ====== Kurz-Helper ======
  const U = window.Utils;

  // ====== Elemente: PDF oben ======
  const pdfFrame       = document.getElementById("pdf-frame");
  const pdfNormal      = document.getElementById("pdf-normal");
  const pdfFett        = document.getElementById("pdf-fett");
  const srcOriginal    = document.getElementById("src-original");
  const srcDraft       = document.getElementById("src-draft");
  const btnRefresh     = document.getElementById("pdf-refresh");
  const btnPdfDownload = document.getElementById("pdf-download");
  const btnPdfOpen     = document.getElementById("pdf-open");

  // ====== Elemente: Original (links) ======
  const origPre          = document.getElementById("bb-original-pre");
  const origToggleTags   = document.getElementById("orig-toggle-tags");
  const origToggleColors = document.getElementById("orig-toggle-colors");
  const origSzDec        = document.getElementById("orig-size-dec");
  const origSzInc        = document.getElementById("orig-size-inc");

  // ====== Elemente: Entwurf (rechts) ======
  const editor             = document.getElementById("bb-editor");         // immer sichtbar
  const draftPreview       = document.getElementById("bb-view-draft");     // gefilterte Vorschau
  const draftToggleTags    = document.getElementById("draft-toggle-tags");
  const draftToggleColors  = document.getElementById("draft-toggle-colors");
  const draftSzDec         = document.getElementById("draft-size-dec");
  const draftSzInc         = document.getElementById("draft-size-inc");
  const btnUploadDraft     = document.getElementById("bb-upload-draft");
  const btnDownloadDraft   = document.getElementById("bb-download-draft");
  const btnReset           = document.getElementById("bb-reset");
  const btnGenerateOrig    = document.getElementById("bb-generate-original");
  const btnGenerateDraft   = document.getElementById("bb-generate-draft");

  // ====== Status / Save-UI ======
  const saveDot     = document.getElementById("save-dot");
  const saveText    = document.getElementById("save-text");
  const draftStatus = document.getElementById("draft-status");

  // ====== Optionen-Modal ======
  const optBackdrop   = document.getElementById("opt-backdrop");
  const optClose      = document.getElementById("opt-close");
  const optCancel     = document.getElementById("opt-cancel");
  const optGenerate   = document.getElementById("opt-generate");
  const optColors     = document.getElementById("opt-colors");
  const optTags       = document.getElementById("opt-tags");
  const optAdv        = document.getElementById("opt-adv");
  const optColorN     = document.getElementById("opt-color-n");
  const optColorV     = document.getElementById("opt-color-v");
  const optColorAj    = document.getElementById("opt-color-aj");
  const tagAv         = document.getElementById("tag-Av");
  const tagPt         = document.getElementById("tag-Pt");
  const tagKo         = document.getElementById("tag-Ko");
  const tagArt        = document.getElementById("tag-Art");
  const tagAj         = document.getElementById("tag-Aj");
  const tagV          = document.getElementById("tag-V");
  const tagN          = document.getElementById("tag-N");
  const optContextNote= document.getElementById("opt-context-note");

  // ====== Zurücksetzen-Modal ======
  const modalBackdrop = document.getElementById("confirm-backdrop");
  const modalClose    = document.getElementById("confirm-close");
  const modalCancel   = document.getElementById("confirm-cancel");
  const modalOk       = document.getElementById("confirm-ok");

  // ====== Scroll-Kopplung ======
  const chkCouple = document.getElementById("link-scroll");

  // ====== State ======
  let rawOriginal = "";
  let rawDraft    = "";
  let optContext  = "draft"; // "draft" | "original"
  let unlinkScroll = () => {}; // cleanup-funktion

  // ====== PDF-URL bauen und anzeigen ======
  function currentPdfUrl(suffix = "") {
    const kind = pdfFett && pdfFett.checked ? "Fett" : "Normal";
    const base = srcDraft && srcDraft.checked ? CONF.PDF_DRAFT_BASE : CONF.PDF_OFFICIAL_BASE;
    return base + kind + (srcDraft && srcDraft.checked ? (suffix || "") : "") + ".pdf";
  }
  function refreshPdf(bust = false, suffix = "") {
    const url = currentPdfUrl(suffix);
    U.setPdfViewer(pdfFrame, btnPdfDownload, btnPdfOpen, url, bust);
  }

  // ====== Initial laden ======
  (async function init() {
    try {
      rawOriginal = await U.fetchText(CONF.TXT_ORIG_PATH);
    } catch (e) {
      rawOriginal = "Konnte " + CONF.TXT_ORIG_PATH + " nicht laden. Liegt die Datei im Ordner texte/?";
    }

    // Original anzeigen (Standard: Filter "An" ⇒ nichts ausblenden)
    if (origPre) {
      U.updateToggleLabel(origToggleTags, true);
      U.updateToggleLabel(origToggleColors, true);
      origPre.textContent = U.renderWithFilters(rawOriginal, false, false);
    }

    // Entwurf aus LocalStorage, sonst Original als Ausgangspunkt
    rawDraft = U.loadLocalDraft(CONF.LOCAL_KEY) || rawOriginal || "";
    if (editor) editor.value = rawDraft;

    // Entwurfs-Vorschau initial
    if (draftPreview) {
      U.updateToggleLabel(draftToggleTags, true);
      U.updateToggleLabel(draftToggleColors, true);
      draftPreview.textContent = U.renderWithFilters(rawDraft, false, false);
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
      if (origPre && leftPx  > 0) U.setFontSize(origPre, leftPx);
      if (editor  && rightPx > 0) U.setFontSize(editor,  rightPx);
      if (draftPreview && rightPx > 0) U.setFontSize(draftPreview, rightPx);
    } catch {}
  }
  function bumpFont(elList, storageKey, deltaPx) {
    const target = elList.find(Boolean);
    if (!target) return;
    const px = U.getFontSize(target) + deltaPx;
    elList.forEach((el) => el && U.setFontSize(el, px));
    try { localStorage.setItem(storageKey, String(px)); } catch {}
  }

  origSzDec && origSzDec.addEventListener("click", () => bumpFont([origPre], CONF.FONT_KEY_LEFT, -1.0));
  origSzInc && origSzInc.addEventListener("click", () => bumpFont([origPre], CONF.FONT_KEY_LEFT, +1.0));
  draftSzDec && draftSzDec.addEventListener("click", () => bumpFont([editor, draftPreview], CONF.FONT_KEY_RIGHT, -1.0));
  draftSzInc && draftSzInc.addEventListener("click", () => bumpFont([editor, draftPreview], CONF.FONT_KEY_RIGHT, +1.0));

  // ====== Scroll koppeln ======
  function setupCoupledScroll() {
    // zuerst alten Listener lösen
    unlinkScroll();
    // gekoppeltes Paar: Original-Pre ↔ Entwurf-Editor
    if (origPre && editor) {
      unlinkScroll = U.coupleScroll(origPre, editor, () => !!(chkCouple && chkCouple.checked));
    }
  }
  chkCouple && chkCouple.addEventListener("change", setupCoupledScroll);

  // ====== Filter-Schalter (Original) ======
  function currentOrigFilters() {
    const showTags   = !!(origToggleTags && origToggleTags.querySelector("input")?.checked);
    const showColors = !!(origToggleColors && origToggleColors.querySelector("input")?.checked);
    return { hideTags: !showTags, hideColors: !showColors, showTags, showColors };
  }
  origToggleTags && origToggleTags.addEventListener("click", () => {
    const input = origToggleTags.querySelector("input");
    if (!input) return;
    input.checked = !input.checked;
    U.updateToggleLabel(origToggleTags, input.checked);
    const f = currentOrigFilters();
    if (origPre) origPre.textContent = U.renderWithFilters(rawOriginal, f.hideTags, f.hideColors);
  });
  origToggleColors && origToggleColors.addEventListener("click", () => {
    const input = origToggleColors.querySelector("input");
    if (!input) return;
    input.checked = !input.checked;
    U.updateToggleLabel(origToggleColors, input.checked);
    const f = currentOrigFilters();
    if (origPre) origPre.textContent = U.renderWithFilters(rawOriginal, f.hideTags, f.hideColors);
  });

  // ====== Filter-Schalter (Entwurf-Preview) ======
  function currentDraftFilters() {
    const showTags   = !!(draftToggleTags && draftToggleTags.querySelector("input")?.checked);
    const showColors = !!(draftToggleColors && draftToggleColors.querySelector("input")?.checked);
    return { hideTags: !showTags, hideColors: !showColors, showTags, showColors };
  }
  function renderDraftPreview() {
    const f = currentDraftFilters();
    if (draftPreview) draftPreview.textContent = U.renderWithFilters(rawDraft, f.hideTags, f.hideColors);
  }
  draftToggleTags && draftToggleTags.addEventListener("click", () => {
    const input = draftToggleTags.querySelector("input");
    if (!input) return;
    input.checked = !input.checked;
    U.updateToggleLabel(draftToggleTags, input.checked);
    renderDraftPreview();
  });
  draftToggleColors && draftToggleColors.addEventListener("click", () => {
    const input = draftToggleColors.querySelector("input");
    if (!input) return;
    input.checked = !input.checked;
    U.updateToggleLabel(draftToggleColors, input.checked);
    renderDraftPreview();
  });

  // ====== Editor (immer aktiv) + Autosave + Live-Preview ======
  let saveTimer = null;
  editor && editor.addEventListener("input", () => {
    U.setSaveState(saveDot, saveText, "busy");
    rawDraft = editor.value || "";
    if (saveTimer) clearTimeout(saveTimer);
    // Live-Vorschau
    renderDraftPreview();
    // Autosave
    saveTimer = setTimeout(() => {
      U.saveLocalDraft(CONF.LOCAL_KEY, rawDraft);
      U.setSaveState(saveDot, saveText, "ok", "Gespeichert");
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
        U.saveLocalDraft(CONF.LOCAL_KEY, rawDraft);
        renderDraftPreview();
        U.setSaveState(saveDot, saveText, "ok", "Entwurf geladen");
      } catch (e) {
        alert("Konnte Datei nicht lesen: " + e.message);
      }
    });
    inp.click();
  });

  // ====== Download Entwurf.txt (mit Code) ======
  btnDownloadDraft && btnDownloadDraft.addEventListener("click", async () => {
    const text = editor ? (editor.value || "") : rawDraft || "";
    if (!text.trim()) {
      alert("Kein Entwurf vorhanden.");
      return;
    }
    try {
      const code = await U.diffCode(rawOriginal || "", text);
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
  btnReset && btnReset.addEventListener("click", openConfirm);
  modalClose && modalClose.addEventListener("click", closeConfirm);
  modalCancel && modalCancel.addEventListener("click", closeConfirm);
  modalBackdrop && modalBackdrop.addEventListener("click", (e) => { if (e.target === modalBackdrop) closeConfirm(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && modalBackdrop && modalBackdrop.style.display === "flex") closeConfirm(); });
  modalOk && modalOk.addEventListener("click", () => {
    U.clearLocalDraft(CONF.LOCAL_KEY);
    rawDraft = rawOriginal || "";
    if (editor) editor.value = rawDraft;
    renderDraftPreview();
    U.setSaveState(saveDot, saveText, "ready", "Bereit");
    closeConfirm();
  });

  // ====== PDF oben (Quelle & Kind & Refresh) ======
  ;[pdfNormal, pdfFett, srcOriginal, srcDraft].forEach((el) =>
    el && el.addEventListener("change", () => refreshPdf(true))
  );
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

    if (optContext === "original") {
      if (srcOriginal) srcOriginal.checked = true;
      if (srcDraft)    srcDraft.checked = false;
      refreshPdf(true);   // offizielle PDFs
      draftStatus && (draftStatus.innerHTML = '<span class="small">Quelle auf <b>Original</b> umgestellt.</span>');
      closeOptModal();
      return;
    }

    // Entwurf wirklich bauen (Worker)
    const text = editor ? (editor.value || "") : rawDraft || "";
    if (!text.trim()) {
      alert("Kein Entwurfstext vorhanden.");
      return;
    }

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

      const kind = pdfFett && pdfFett.checked ? "Fett" : "Normal";
      const target = `${CONF.PDF_DRAFT_BASE}${kind}${suffix}.pdf`;

      const ok = await U.waitForPdf(target, 24, 5000); // ~2 min
      refreshPdf(true, suffix);
      draftStatus && (draftStatus.innerHTML = ok
        ? "✅ Entwurfs-PDF aktualisiert."
        : '⚠️ PDF noch nicht bereit. Bitte später „PDF aktualisieren“ klicken.'
      );
    } catch (e) {
      draftStatus && (draftStatus.innerHTML = '<span class="err">Fehler: ' + e.message + "</span>");
    } finally {
      closeOptModal();
    }
  });
})();
