// aias.js — Seitenlogik für Aias (nutzt Utils)
(function () {
  // ====== Konfiguration (werksbezogen) ======
  const CONF = {
    WORK: "Aias",
    LOCAL_KEY: "draft_Aias_birkenbihl",
    TXT_ORIG_PATH: "texte/Aias_birkenbihl.txt",
    PDF_DRAFT_BASE: "pdf_drafts/Aias_DRAFT_LATEST_",       // + Normal/Fett[+Suffix].pdf
    PDF_OFFICIAL_BASE: "pdf/TragödieAias_",                 // + Normal/Fett.pdf
    WORKER_URL: "https://birkenbihl-draft-01.klemp-tobias.workers.dev",
  };

  // ====== Element-Handles ======
  // Oben (PDF)
  const pdfFrame = document.getElementById("pdf-frame");
  const pdfNormal = document.getElementById("pdf-normal");
  const pdfFett = document.getElementById("pdf-fett");
  const srcOriginal = document.getElementById("src-original");
  const srcDraft = document.getElementById("src-draft");
  const btnRefresh = document.getElementById("pdf-refresh");
  const btnPdfDownload = document.getElementById("pdf-download");
  const btnPdfOpen = document.getElementById("pdf-open");

  // Unten (Original & Entwurf)
  const origPre = document.getElementById("bb-original-pre");
  const draftPre = document.getElementById("bb-view-draft");
  const editor = document.getElementById("bb-editor");

  const btnEdit = document.getElementById("bb-edit");
  const btnCancel = document.getElementById("bb-cancel");
  const btnDownloadDraft = document.getElementById("bb-download-draft");
  const btnGenerateOrig = document.getElementById("bb-generate-original");
  const btnGenerateDraft = document.getElementById("bb-generate-draft");
  const btnReset = document.getElementById("bb-reset");

  const origToggleTags = document.getElementById("orig-toggle-tags");
  const origToggleColors = document.getElementById("orig-toggle-colors");
  const draftToggleTags = document.getElementById("draft-toggle-tags");
  const draftToggleColors = document.getElementById("draft-toggle-colors");

  // Save/Status
  const saveDot = document.getElementById("save-dot");
  const saveText = document.getElementById("save-text");
  const draftStatus = document.getElementById("draft-status");

  // Optionen-Modal
  const optBackdrop = document.getElementById("opt-backdrop");
  const optClose = document.getElementById("opt-close");
  const optCancel = document.getElementById("opt-cancel");
  const optGenerate = document.getElementById("opt-generate");
  const optColors = document.getElementById("opt-colors");
  const optTags = document.getElementById("opt-tags");
  const optAdv = document.getElementById("opt-adv");
  const optColorN = document.getElementById("opt-color-n");
  const optColorV = document.getElementById("opt-color-v");
  const optColorAj = document.getElementById("opt-color-aj");
  const tagAv = document.getElementById("tag-Av");
  const tagPt = document.getElementById("tag-Pt");
  const tagKo = document.getElementById("tag-Ko");
  const tagArt = document.getElementById("tag-Art");
  const tagAj = document.getElementById("tag-Aj");
  const tagV = document.getElementById("tag-V");
  const tagN = document.getElementById("tag-N");
  const optContextNote = document.getElementById("opt-context-note");

  // Bestätigungs-Modal (Zurücksetzen)
  const modalBackdrop = document.getElementById("confirm-backdrop");
  const modalClose = document.getElementById("confirm-close");
  const modalCancel = document.getElementById("confirm-cancel");
  const modalOk = document.getElementById("confirm-ok");

  // ====== State ======
  let rawOriginal = "";
  let rawDraft = "";
  let optContext = "draft"; // "draft" | "original"

  // ====== Kurz-Helper (aus Utils) ======
  const U = window.Utils;

  // ====== PDF-URL bauen und anzeigen ======
  function currentPdfUrl(suffix = "") {
    const kind = pdfFett?.checked ? "Fett" : "Normal";
    const base = srcDraft?.checked ? CONF.PDF_DRAFT_BASE : CONF.PDF_OFFICIAL_BASE;
    return base + kind + (srcDraft?.checked ? (suffix || "") : "") + ".pdf";
  }
  function refreshPdf(bust = false, suffix = "") {
    const url = currentPdfUrl(suffix);
    U.setPdfViewer(pdfFrame, btnPdfDownload, btnPdfOpen, url, bust);
  }

  // ====== Start: Texte laden + Schalter initialisieren ======
  (async function initTexts() {
    try {
      rawOriginal = await U.fetchText(CONF.TXT_ORIG_PATH);
    } catch (e) {
      rawOriginal = "Konnte " + CONF.TXT_ORIG_PATH + " nicht laden. Liegt die Datei im Ordner texte/?";
    }

    // Beide Schalter-Gruppen **synchron** auf "An" setzen (Checkbox + Label!)
    U.setToggle(origToggleTags, true);
    U.setToggle(origToggleColors, true);
    U.setToggle(draftToggleTags, true);
    U.setToggle(draftToggleColors, true);

    // Erstansicht rendern (nichts ausblenden)
    origPre.textContent  = U.renderWithFilters(rawOriginal, false, false);

    rawDraft = U.loadLocalDraft(CONF.LOCAL_KEY) || "";
    draftPre.textContent = U.renderWithFilters(rawDraft, false, false);
  })();

  // ====== Anzeige-Schalter ======
  // Original: Grammatik-Tags
  origToggleTags?.addEventListener("click", () => {
    const nowOn = !U.getToggleValue(origToggleTags);     // umschalten
    U.setToggle(origToggleTags, nowOn);
    const hideTags = !nowOn;
    const hideColors = !U.getToggleValue(origToggleColors);
    origPre.textContent = U.renderWithFilters(rawOriginal, hideTags, hideColors);
  });

  // Original: Farb-Kürzel
  origToggleColors?.addEventListener("click", () => {
    const nowOn = !U.getToggleValue(origToggleColors);   // umschalten
    U.setToggle(origToggleColors, nowOn);
    const hideColors = !nowOn;
    const hideTags = !U.getToggleValue(origToggleTags);
    origPre.textContent = U.renderWithFilters(rawOriginal, hideTags, hideColors);
  });

  // Entwurf: Grammatik-Tags
  draftToggleTags?.addEventListener("click", () => {
    const nowOn = !U.getToggleValue(draftToggleTags);
    U.setToggle(draftToggleTags, nowOn);
    const hideTags = !nowOn;
    const hideColors = !U.getToggleValue(draftToggleColors);
    draftPre.textContent = U.renderWithFilters(rawDraft, hideTags, hideColors);
  });

  // Entwurf: Farb-Kürzel
  draftToggleColors?.addEventListener("click", () => {
    const nowOn = !U.getToggleValue(draftToggleColors);
    U.setToggle(draftToggleColors, nowOn);
    const hideColors = !nowOn;
    const hideTags = !U.getToggleValue(draftToggleTags);
    draftPre.textContent = U.renderWithFilters(rawDraft, hideTags, hideColors);
  });

  // ====== Editor ======
  function showEditor(text) {
    editor.value = text || "";
    editor.style.display = "block";
    draftPre.style.display = "none";
    btnCancel.style.display = "inline-block";
    U.setSaveState(saveDot, saveText, "ready", "Im Editor");
  }
  function hideEditor() {
    editor.style.display = "none";
    draftPre.style.display = "block";
    btnCancel.style.display = "none";
    U.setSaveState(saveDot, saveText, "ready", "Bereit");
  }

  btnEdit?.addEventListener("click", async () => {
    U.setSaveState(saveDot, saveText, "busy");
    try {
      const draft = U.loadLocalDraft(CONF.LOCAL_KEY);
      const text = draft || rawOriginal || (await U.fetchText(CONF.TXT_ORIG_PATH));
      showEditor(text);
      U.setSaveState(saveDot, saveText, "ready", draft ? "Entwurf bearbeiten" : "Original bearbeiten");
    } catch (e) {
      U.setSaveState(saveDot, saveText, "ready");
      alert("Konnte Text nicht laden: " + e.message);
    }
  });
  btnCancel?.addEventListener("click", hideEditor);

  let saveTimer = null;
  editor?.addEventListener("input", () => {
    U.setSaveState(saveDot, saveText, "busy");
    rawDraft = editor.value;
    const hideTags = !U.getToggleValue(draftToggleTags);
    const hideColors = !U.getToggleValue(draftToggleColors);
    draftPre.textContent = U.renderWithFilters(rawDraft, hideTags, hideColors);
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      U.saveLocalDraft(CONF.LOCAL_KEY, rawDraft);
      U.setSaveState(saveDot, saveText, "ok", "Gespeichert");
    }, 300);
  });

  // ====== Download Entwurf (mit Code) ======
  btnDownloadDraft?.addEventListener("click", async () => {
    const text = editor.style.display !== "none" ? editor.value || "" : rawDraft || "";
    if (!text.trim()) {
      alert("Kein Entwurf vorhanden. Bitte auf „Bearbeiten“ klicken, Text anpassen und speichern.");
      return;
    }
    try {
      const code = await U.diffCode(rawOriginal || "", text);
      const fname = `${CONF.WORK}_birkenbihl_ENTWURF_${code}.txt`;
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fname;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        URL.revokeObjectURL(url);
        a.remove();
      }, 1000);
    } catch (e) {
      alert("Konnte Entwurf nicht herunterladen: " + e.message);
    }
  });

  // ====== Bestätigungs-Modal: Entwurf zurücksetzen ======
  function openConfirm() {
    modalBackdrop?.setAttribute("style", "display:flex");
    modalBackdrop?.setAttribute("aria-hidden", "false");
  }
  function closeConfirm() {
    modalBackdrop?.setAttribute("style", "display:none");
    modalBackdrop?.setAttribute("aria-hidden", "true");
  }
  btnReset?.addEventListener("click", openConfirm);
  modalClose?.addEventListener("click", closeConfirm);
  modalCancel?.addEventListener("click", closeConfirm);
  modalBackdrop?.addEventListener("click", (e) => {
    if (e.target === modalBackdrop) closeConfirm();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modalBackdrop && modalBackdrop.style.display === "flex") closeConfirm();
  });
  modalOk?.addEventListener("click", () => {
    U.clearLocalDraft(CONF.LOCAL_KEY);
    rawDraft = "";
    draftPre.textContent = "";
    if (editor.style.display !== "none") editor.value = "";
    draftStatus.innerHTML = '<span class="ok">Lokaler Entwurf gelöscht.</span>';
    U.setSaveState(saveDot, saveText, "ready", "Bereit");
    closeConfirm();
  });

  // ====== PDF oben (Quelle & Kind & Refresh) ======
  [pdfNormal, pdfFett, srcOriginal, srcDraft].forEach((el) => el && el.addEventListener("change", () => refreshPdf(true)));
  btnRefresh?.addEventListener("click", () => refreshPdf(true));
  // Initial
  refreshPdf(false);

  // ====== Optionen-Modal (PDF generieren) ======
  const btnOpenOptsOriginal = document.getElementById("bb-generate-original");
  const btnOpenOptsDraft = document.getElementById("bb-generate-draft");

  function openOptModal(context) {
    optContext = context;
    if (optContextNote) {
      optContextNote.textContent =
        context === "original"
          ? "Hinweis: Oben wird auf „Original“ umgeschaltet. Offizielle PDFs liegen im Ordner pdf/."
          : "Der Entwurf wird mit diesen Optionen gebaut und oben angezeigt.";
    }
    optBackdrop?.setAttribute("style", "display:flex");
    optBackdrop?.setAttribute("aria-hidden", "false");
  }
  function closeOptModal() {
    optBackdrop?.setAttribute("style", "display:none");
    optBackdrop?.setAttribute("aria-hidden", "true");
  }
  btnOpenOptsOriginal?.addEventListener("click", () => openOptModal("original"));
  btnOpenOptsDraft?.addEventListener("click", () => openOptModal("draft"));
  optClose?.addEventListener("click", closeOptModal);
  optCancel?.addEventListener("click", closeOptModal);
  optBackdrop?.addEventListener("click", (e) => {
    if (e.target === optBackdrop) closeOptModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && optBackdrop && optBackdrop.style.display === "flex") closeOptModal();
  });

  function suffixFromOptions() {
    let suffix = "";
    if (optColors && !optColors.checked) suffix += "_BW";
    if (optTags && !optTags.checked) suffix += "_NoTags";
    if (optAdv && optAdv.open) suffix += "_Custom";
    return suffix;
  }
  function collectOptionsPayload() {
    return {
      colors: !!(optColors && optColors.checked),
      showTags: !!(optTags && optTags.checked),
      custom: optAdv && optAdv.open
        ? {
            colorByPOS: { N: !!(optColorN && optColorN.checked), V: !!(optColorV && optColorV.checked), Aj: !!(optColorAj && optColorAj.checked) },
            visibleTags: {
              Av: !!(tagAv && tagAv.checked),
              Pt: !!(tagPt && tagPt.checked),
              Ko: !!(tagKo && tagKo.checked),
              Art: !!(tagArt && tagArt.checked),
              Aj: !!(tagAj && tagAj.checked),
              V:  !!(tagV  && tagV.checked),
              N:  !!(tagN  && tagN.checked),
            },
          }
        : null,
    };
  }

  optGenerate?.addEventListener("click", async () => {
    const suffix = suffixFromOptions();

    if (optContext === "original") {
      // Nur Anzeige umschalten
      if (srcOriginal && srcDraft) {
        srcOriginal.checked = true;
        srcDraft.checked = false;
      }
      refreshPdf(true); // ohne Suffix (offizielle PDFs)
      if (draftStatus) draftStatus.innerHTML = '<span class="small">Quelle auf <b>Original</b> umgestellt.</span>';
      closeOptModal();
      return;
    }

    // Entwurf wirklich bauen über Worker
    const text = editor.style.display !== "none" ? editor.value : rawDraft || "";
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
      const j = await res.json().catch(() => ({}));
      if (!res.ok || !j.ok) throw new Error(j.error || "HTTP " + res.status);

      if (draftStatus) draftStatus.textContent = "✅ Entwurf angenommen. Build startet…";

      if (srcDraft && srcOriginal) {
        srcDraft.checked = true;
        srcOriginal.checked = false;
      }

      const kind = pdfFett && pdfFett.checked ? "Fett" : "Normal";
      const target = `${CONF.PDF_DRAFT_BASE}${kind}${suffix}.pdf`;

      const ok = await U.waitForPdf(target, 24, 5000); // ~2 min
      refreshPdf(true, suffix);
      if (draftStatus) {
        draftStatus.innerHTML = ok
          ? "✅ Entwurfs-PDF aktualisiert."
          : '⚠️ PDF noch nicht bereit. Bitte später „PDF aktualisieren“ klicken.';
      }
    } catch (e) {
      if (draftStatus) draftStatus.innerHTML = '<span class="err">Fehler: ' + e.message + "</span>";
    } finally {
      closeOptModal();
    }
  });
})();
