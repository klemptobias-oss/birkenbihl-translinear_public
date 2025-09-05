<!-- aias.js -->
<script>
(function () {
  // ====== Konfiguration (werksbezogen) ======
  const CONF = {
    WORK: "Aias",
    LOCAL_KEY: "draft_Aias_birkenbihl",
    TXT_ORIG_PATH: "texte/Aias_birkenbihl.txt",
    PDF_DRAFT_BASE: "pdf_drafts/Aias_DRAFT_LATEST_",   // + Normal/Fett[+Suffix].pdf
    PDF_OFFICIAL_BASE: "pdf/TragödieAias_",             // + Normal/Fett.pdf
    WORKER_URL: "https://birkenbihl-draft-01.klemp-tobias.workers.dev",
  };

  // Kurzhilfe für getElementById
  const $ = (id) => document.getElementById(id) || null;

  // ====== Element-Handles ======
  // Oben (PDF)
  const pdfFrame       = $("pdf-frame");
  const pdfNormal      = $("pdf-normal");
  const pdfFett        = $("pdf-fett");
  const srcOriginal    = $("src-original");
  const srcDraft       = $("src-draft");
  const btnRefresh     = $("pdf-refresh");
  const btnPdfDownload = $("pdf-download");
  const btnPdfOpen     = $("pdf-open");

  // Unten (Original & Entwurf)
  const origPre            = $("bb-original-pre");
  const draftPre           = $("bb-view-draft");
  const editor             = $("bb-editor");
  const btnEdit            = $("bb-edit");
  const btnCancel          = $("bb-cancel");
  const btnDownloadDraft   = $("bb-download-draft");
  const btnGenerateOrig    = $("bb-generate-original");
  const btnGenerateDraft   = $("bb-generate-draft");
  const btnReset           = $("bb-reset");

  const origToggleTags     = $("orig-toggle-tags");
  const origToggleColors   = $("orig-toggle-colors");
  const draftToggleTags    = $("draft-toggle-tags");
  const draftToggleColors  = $("draft-toggle-colors");

  // Save/Status
  const saveDot      = $("save-dot");
  const saveText     = $("save-text");
  const draftStatus  = $("draft-status");

  // Optionen-Modal
  const optBackdrop   = $("opt-backdrop");
  const optClose      = $("opt-close");
  const optCancel     = $("opt-cancel");
  const optGenerate   = $("opt-generate");
  const optColors     = $("opt-colors");
  const optTags       = $("opt-tags");
  const optAdv        = $("opt-adv");
  const optColorN     = $("opt-color-n");
  const optColorV     = $("opt-color-v");
  const optColorAj    = $("opt-color-aj");
  const tagAv         = $("tag-Av");
  const tagPt         = $("tag-Pt");
  const tagKo         = $("tag-Ko");
  const tagArt        = $("tag-Art");
  const tagAj         = $("tag-Aj");
  const tagV          = $("tag-V");
  const tagN          = $("tag-N");
  const optContextNote= $("opt-context-note");

  // Bestätigungs-Modal (Zurücksetzen)
  const modalBackdrop = $("confirm-backdrop");
  const modalClose    = $("confirm-close");
  const modalCancel   = $("confirm-cancel");
  const modalOk       = $("confirm-ok");

  // ====== State ======
  let rawOriginal = "";
  let rawDraft = "";
  let optContext = "draft"; // "draft" | "original"

  // ====== Utils ======
  const U = window.Utils || {
    // Falls utils.js nicht geladen wäre, verhindern wir harte Fehler:
    setSaveState: ()=>{}, loadLocalDraft:()=>"", saveLocalDraft:()=>{},
    clearLocalDraft:()=>{}, fetchText: async()=>{ throw new Error("utils.js fehlt") },
    waitForPdf: async()=>false, setPdfViewer: ()=>{},
    renderWithFilters: (t)=>t, updateToggleLabel: ()=>{},
    diffCode: async()=>String(Date.now()).slice(-8),
  };

  // ====== PDF-URL bauen und anzeigen ======
  function currentPdfUrl(suffix = "") {
    const kind = (pdfFett && pdfFett.checked) ? "Fett" : "Normal";
    const useDraft = !!(srcDraft && srcDraft.checked);
    const base = useDraft ? CONF.PDF_DRAFT_BASE : CONF.PDF_OFFICIAL_BASE;
    return base + kind + (useDraft ? (suffix || "") : "") + ".pdf";
  }
  function refreshPdf(bust = false, suffix = "") {
    const url = currentPdfUrl(suffix);
    U.setPdfViewer?.(pdfFrame, btnPdfDownload, btnPdfOpen, url, bust);
  }

  // ====== Start: Texte laden ======
  (async function initTexts() {
    // Original laden
    try {
      rawOriginal = await U.fetchText?.(CONF.TXT_ORIG_PATH);
    } catch (e) {
      rawOriginal = `Konnte ${CONF.TXT_ORIG_PATH} nicht laden. Liegt die Datei im Ordner texte/?`;
    }
    // Default: Anzeige-Schalter = An (keine Filter → beide An)
    U.updateToggleLabel?.(origToggleTags,   true);
    U.updateToggleLabel?.(origToggleColors, true);
    if (origPre) origPre.textContent = U.renderWithFilters?.(rawOriginal, false, false) ?? rawOriginal;

    // Entwurf laden
    rawDraft = U.loadLocalDraft?.(CONF.LOCAL_KEY) || "";
    U.updateToggleLabel?.(draftToggleTags,   true);
    U.updateToggleLabel?.(draftToggleColors, true);
    if (draftPre) {
      draftPre.textContent = rawDraft
        ? U.renderWithFilters?.(rawDraft, false, false) ?? rawDraft
        : "Noch kein Entwurf vorhanden. Klicke auf „Bearbeiten“, um einen Entwurf zu starten.";
    }
  })();

  // ====== Anzeige-Schalter ======
  function isOn(toggleEl){ return !!(toggleEl && toggleEl.querySelector && toggleEl.querySelector("input")?.checked); }

  // Original
  origToggleTags?.addEventListener("click", () => {
    const input = origToggleTags.querySelector("input"); if (!input) return;
    input.checked = !input.checked;
    U.updateToggleLabel?.(origToggleTags, input.checked);
    const hideTags   = !input.checked;
    const hideColors = !isOn(origToggleColors);
    if (origPre) origPre.textContent = U.renderWithFilters?.(rawOriginal, hideTags, hideColors) ?? rawOriginal;
  });
  origToggleColors?.addEventListener("click", () => {
    const input = origToggleColors.querySelector("input"); if (!input) return;
    input.checked = !input.checked;
    U.updateToggleLabel?.(origToggleColors, input.checked);
    const hideColors = !input.checked;
    const hideTags   = !isOn(origToggleTags);
    if (origPre) origPre.textContent = U.renderWithFilters?.(rawOriginal, hideTags, hideColors) ?? rawOriginal;
  });

  // Entwurf
  draftToggleTags?.addEventListener("click", () => {
    const input = draftToggleTags.querySelector("input"); if (!input) return;
    input.checked = !input.checked;
    U.updateToggleLabel?.(draftToggleTags, input.checked);
    const hideTags   = !input.checked;
    const hideColors = !isOn(draftToggleColors);
    if (draftPre) draftPre.textContent = U.renderWithFilters?.(rawDraft, hideTags, hideColors) ?? rawDraft;
  });
  draftToggleColors?.addEventListener("click", () => {
    const input = draftToggleColors.querySelector("input"); if (!input) return;
    input.checked = !input.checked;
    U.updateToggleLabel?.(draftToggleColors, input.checked);
    const hideColors = !input.checked;
    const hideTags   = !isOn(draftToggleTags);
    if (draftPre) draftPre.textContent = U.renderWithFilters?.(rawDraft, hideTags, hideColors) ?? rawDraft;
  });

  // ====== Editor ======
  function showEditor(text) {
    if (!editor || !draftPre) return;
    editor.value = text || "";
    editor.style.display = "block";
    draftPre.style.display = "none";
    if (btnCancel) btnCancel.style.display = "inline-block";
    U.setSaveState?.(saveDot, saveText, "ready", "Im Editor");
  }
  function hideEditor() {
    if (!editor || !draftPre) return;
    editor.style.display = "none";
    draftPre.style.display = "block";
    if (btnCancel) btnCancel.style.display = "none";
    U.setSaveState?.(saveDot, saveText, "ready", "Bereit");
  }

  btnEdit?.addEventListener("click", async () => {
    U.setSaveState?.(saveDot, saveText, "busy");
    try {
      const draft = U.loadLocalDraft?.(CONF.LOCAL_KEY);
      const base  = rawOriginal || (await U.fetchText?.(CONF.TXT_ORIG_PATH));
      showEditor(draft || base || "");
      U.setSaveState?.(saveDot, saveText, "ready", draft ? "Entwurf bearbeiten" : "Original bearbeiten");
    } catch (e) {
      U.setSaveState?.(saveDot, saveText, "ready");
      alert("Konnte Text nicht laden: " + (e?.message || e));
    }
  });
  btnCancel?.addEventListener("click", hideEditor);

  let saveTimer = null;
  editor?.addEventListener("input", () => {
    U.setSaveState?.(saveDot, saveText, "busy");
    rawDraft = editor.value;
    const hideTags   = !isOn(draftToggleTags);
    const hideColors = !isOn(draftToggleColors);
    if (draftPre) draftPre.textContent = U.renderWithFilters?.(rawDraft, hideTags, hideColors) ?? rawDraft;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      U.saveLocalDraft?.(CONF.LOCAL_KEY, rawDraft);
      U.setSaveState?.(saveDot, saveText, "ok", "Gespeichert");
    }, 300);
  });

  // ====== Download Entwurf (mit Code) ======
  btnDownloadDraft?.addEventListener("click", async () => {
    const text = (editor && editor.style.display !== "none") ? (editor.value || "") : (rawDraft || "");
    if (!text.trim()) {
      alert("Kein Entwurf vorhanden. Bitte auf „Bearbeiten“ klicken, Text anpassen und speichern.");
      return;
    }
    try {
      const code = await U.diffCode?.(rawOriginal || "", text);
      const fname = `${CONF.WORK}_birkenbihl_ENTWURF_${code || Date.now()}.txt`;
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      const url  = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = fname; document.body.appendChild(a); a.click();
      setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1000);
    } catch (e) {
      alert("Konnte Entwurf nicht herunterladen: " + (e?.message || e));
    }
  });

  // ====== Bestätigungs-Modal: Entwurf zurücksetzen ======
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
  btnReset?.addEventListener("click", openConfirm);
  modalClose?.addEventListener("click", closeConfirm);
  modalCancel?.addEventListener("click", closeConfirm);
  modalBackdrop?.addEventListener("click", (e) => { if (e.target === modalBackdrop) closeConfirm(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && modalBackdrop && modalBackdrop.style.display === "flex") closeConfirm(); });
  modalOk?.addEventListener("click", () => {
    U.clearLocalDraft?.(CONF.LOCAL_KEY);
    rawDraft = "";
    if (draftPre) draftPre.textContent = "Entwurf zurückgesetzt. (Tipp: „Bearbeiten“ starten, um erneut zu arbeiten.)";
    if (editor && editor.style.display !== "none") editor.value = "";
    if (draftStatus) draftStatus.innerHTML = '<span class="ok">Lokaler Entwurf gelöscht.</span>';
    U.setSaveState?.(saveDot, saveText, "ready", "Bereit");
    closeConfirm();
  });

  // ====== PDF oben (Quelle & Kind & Refresh) ======
  [pdfNormal, pdfFett, srcOriginal, srcDraft].forEach((el) => el?.addEventListener("change", () => refreshPdf(true)));
  btnRefresh?.addEventListener("click", () => refreshPdf(true));
  // Initial
  refreshPdf(false);

  // ====== Optionen-Modal (PDF generieren) ======
  const btnOpenOptsOriginal = btnGenerateOrig;
  const btnOpenOptsDraft    = btnGenerateDraft;

  function openOptModal(context) {
    if (!optBackdrop || !optContextNote) return;
    optContext = context;
    optContextNote.textContent =
      context === "original"
        ? "Hinweis: Oben wird auf „Original“ umgeschaltet. Offizielle PDFs liegen im Ordner pdf/."
        : "Der Entwurf wird mit diesen Optionen gebaut und oben angezeigt.";
    optBackdrop.style.display = "flex";
    optBackdrop.setAttribute("aria-hidden", "false");
  }
  function closeOptModal() {
    if (!optBackdrop) return;
    optBackdrop.style.display = "none";
    optBackdrop.setAttribute("aria-hidden", "true");
  }
  btnOpenOptsOriginal?.addEventListener("click", () => openOptModal("original"));
  btnOpenOptsDraft?.addEventListener("click", () => openOptModal("draft"));
  optClose?.addEventListener("click", closeOptModal);
  optCancel?.addEventListener("click", closeOptModal);
  optBackdrop?.addEventListener("click", (e) => { if (e.target === optBackdrop) closeOptModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && optBackdrop && optBackdrop.style.display === "flex") closeOptModal(); });

  function suffixFromOptions() {
    let suffix = "";
    if (optColors && !optColors.checked) suffix += "_BW";
    if (optTags   && !optTags.checked)   suffix += "_NoTags";
    if (optAdv    &&  optAdv.open)       suffix += "_Custom";
    return suffix;
  }
  function collectOptionsPayload() {
    return {
      colors:   !!(optColors?.checked),
      showTags: !!(optTags?.checked),
      custom: (optAdv && optAdv.open) ? {
        colorByPOS: {
          N:  !!(optColorN?.checked),
          V:  !!(optColorV?.checked),
          Aj: !!(optColorAj?.checked),
        },
        visibleTags: {
          Av:  !!(tagAv?.checked),
          Pt:  !!(tagPt?.checked),
          Ko:  !!(tagKo?.checked),
          Art: !!(tagArt?.checked),
          Aj:  !!(tagAj?.checked),
          V:   !!(tagV?.checked),
          N:   !!(tagN?.checked),
        },
      } : null,
    };
  }

  optGenerate?.addEventListener("click", async () => {
    const suffix = suffixFromOptions();

    if (optContext === "original") {
      // Nur Anzeige umschalten
      if (srcOriginal && srcDraft) { srcOriginal.checked = true; srcDraft.checked = false; }
      refreshPdf(true); // offizielle PDFs (ohne Suffix)
      if (draftStatus) draftStatus.innerHTML = '<span class="small">Quelle auf <b>Original</b> umgestellt.</span>';
      closeOptModal();
      return;
    }

    // Entwurf wirklich bauen über Worker
    const text = (editor && editor.style.display !== "none") ? editor.value : (rawDraft || "");
    if (!text.trim()) {
      alert("Kein Entwurfstext vorhanden. Bitte auf „Bearbeiten“ klicken, Text anpassen und speichern.");
      return;
    }

    try {
      if (draftStatus) draftStatus.textContent = "⬆️ Entwurf wird an den Build-Dienst gesendet…";
      const opts = collectOptionsPayload();
      const res = await fetch(CONF.WORKER_URL + "/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ work: CONF.WORK, text, opts }),
      });
      let j = {};
      try { j = await res.json(); } catch {}
      if (!res.ok || !j.ok) throw new Error(j.error || ("HTTP " + res.status));

      if (draftStatus) draftStatus.textContent = "✅ Entwurf angenommen. Build startet…";

      if (srcDraft && srcOriginal) { srcDraft.checked = true; srcOriginal.checked = false; }

      const kind   = (pdfFett && pdfFett.checked) ? "Fett" : "Normal";
      const target = `${CONF.PDF_DRAFT_BASE}${kind}${suffix}.pdf`;

      const ok = await U.waitForPdf?.(target, 24, 5000); // ~2 min
      refreshPdf(true, suffix);
      if (draftStatus) {
        draftStatus.innerHTML = ok
          ? "✅ Entwurfs-PDF aktualisiert."
          : '⚠️ PDF noch nicht bereit. Bitte später „PDF aktualisieren“ klicken.';
      }
    } catch (e) {
      if (draftStatus) draftStatus.innerHTML = '<span class="err">Fehler: ' + (e?.message || e) + "</span>";
    } finally {
      closeOptModal();
    }
  });
})();
</script>
