<!-- aias.js -->
<script>
(function () {
  // ====== Werks-Konfiguration ======
  const CONF = {
    WORK: "Aias",
    LOCAL_KEY: "draft_Aias_birkenbihl",
    TXT_ORIG_PATH: "texte/Aias_birkenbihl.txt",
    PDF_DRAFT_BASE: "pdf_drafts/Aias_DRAFT_LATEST_",   // + Normal/Fett[+Suffix].pdf
    PDF_OFFICIAL_BASE: "pdf/TragödieAias_",            // + Normal/Fett.pdf
    WORKER_URL: "https://birkenbihl-draft-01.klemp-tobias.workers.dev",
  };
  const U = window.Utils;

  // ====== Elemente ======
  // PDF oben
  const pdfFrame = document.getElementById("pdf-frame");
  const pdfNormal = document.getElementById("pdf-normal");
  const pdfFett = document.getElementById("pdf-fett");
  const srcOriginal = document.getElementById("src-original");
  const srcDraft = document.getElementById("src-draft");
  const btnRefresh = document.getElementById("pdf-refresh");
  const btnPdfDownload = document.getElementById("pdf-download");
  const btnPdfOpen = document.getElementById("pdf-open");

  // Original-Pane
  const origPre = document.getElementById("bb-original-pre");
  const origToggleTags = document.getElementById("orig-toggle-tags");
  const origToggleColors = document.getElementById("orig-toggle-colors");
  const origFontMinus = document.getElementById("orig-font-minus");
  const origFontPlus  = document.getElementById("orig-font-plus");
  const scrollLinkChk = document.getElementById("scroll-link");

  // Draft-Pane
  const draftEditor = document.getElementById("bb-editor");        // immer sichtbar/editierbar
  const draftPreview = document.getElementById("bb-draft-preview"); // gefilterte Vorschau
  const draftToggleTags = document.getElementById("draft-toggle-tags");
  const draftToggleColors = document.getElementById("draft-toggle-colors");
  const draftFontMinus = document.getElementById("draft-font-minus");
  const draftFontPlus  = document.getElementById("draft-font-plus");
  const btnDownloadDraft = document.getElementById("bb-download-draft");
  const btnUploadDraft = document.getElementById("bb-upload-draft");
  const fileDraft = document.getElementById("bb-upload-file");
  const btnReset = document.getElementById("bb-reset");
  const btnGenerateOrig = document.getElementById("bb-generate-original");
  const btnGenerateDraft = document.getElementById("bb-generate-draft");

  // Status
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
  const tagV  = document.getElementById("tag-V");
  const tagN  = document.getElementById("tag-N");
  const optContextNote = document.getElementById("opt-context-note");

  // Confirm-Modal (Reset)
  const modalBackdrop = document.getElementById("confirm-backdrop");
  const modalClose = document.getElementById("confirm-close");
  const modalCancel = document.getElementById("confirm-cancel");
  const modalOk = document.getElementById("confirm-ok");

  // ====== State ======
  let rawOriginal = "";
  let rawDraft = "";

  function pdfUrl(suffix = "") {
    const kind = pdfFett?.checked ? "Fett" : "Normal";
    const base = srcDraft?.checked ? CONF.PDF_DRAFT_BASE : CONF.PDF_OFFICIAL_BASE;
    return base + kind + (srcDraft?.checked ? (suffix || "") : "") + ".pdf";
  }
  function refreshPdf(bust = false, suffix = "") {
    U.setPdfViewer(pdfFrame, btnPdfDownload, btnPdfOpen, pdfUrl(suffix), bust);
  }

  // ====== Init: Texte laden & Draft initial füllen ======
  (async function init() {
    try {
      rawOriginal = await U.fetchText(CONF.TXT_ORIG_PATH);
    } catch (e) {
      rawOriginal = "Konnte " + CONF.TXT_ORIG_PATH + " nicht laden. Liegt die Datei im Ordner texte/?";
    }
    // Original anzeigen (Start: Filter "An" -> nichts ausblenden)
    U.updateToggleLabel(origToggleTags, true);
    U.updateToggleLabel(origToggleColors, true);
    origPre.textContent = U.renderWithFilters(rawOriginal, false, false);

    // Draft aus localStorage, sonst Kopie des Originals
    const stored = U.loadLocalDraft(CONF.LOCAL_KEY);
    rawDraft = stored || rawOriginal;
    draftEditor.value = rawDraft;

    // Draft-Preview initial
    U.updateToggleLabel(draftToggleTags, true);
    U.updateToggleLabel(draftToggleColors, true);
    draftPreview.textContent = U.renderWithFilters(rawDraft, false, false);

    // PDF initial
    refreshPdf(false);

    // Scroll-Sync: Original -> Draft (Preview + Editor), steuerbar per Checkbox
    U.attachScrollSync(origPre, [draftPreview, draftEditor], () => !!scrollLinkChk?.checked);
  })();

  // ====== Filter-Schalter: ORIGINAL ======
  function applyOriginalView() {
    const hideTags = !(origToggleTags.querySelector("input")?.checked);
    const hideColors = !(origToggleColors.querySelector("input")?.checked);
    origPre.textContent = U.renderWithFilters(rawOriginal, hideTags, hideColors);
  }
  origToggleTags?.addEventListener("click", () => {
    const inp = origToggleTags.querySelector("input");
    inp.checked = !inp.checked;
    U.updateToggleLabel(origToggleTags, inp.checked);
    applyOriginalView();
  });
  origToggleColors?.addEventListener("click", () => {
    const inp = origToggleColors.querySelector("input");
    inp.checked = !inp.checked;
    U.updateToggleLabel(origToggleColors, inp.checked);
    applyOriginalView();
  });

  // ====== Filter-Schalter: DRAFT (wirken auf Preview) ======
  function applyDraftPreview() {
    const hideTags = !(draftToggleTags.querySelector("input")?.checked);
    const hideColors = !(draftToggleColors.querySelector("input")?.checked);
    draftPreview.textContent = U.renderWithFilters(rawDraft, hideTags, hideColors);
  }
  draftToggleTags?.addEventListener("click", () => {
    const inp = draftToggleTags.querySelector("input");
    inp.checked = !inp.checked;
    U.updateToggleLabel(draftToggleTags, inp.checked);
    applyDraftPreview();
  });
  draftToggleColors?.addEventListener("click", () => {
    const inp = draftToggleColors.querySelector("input");
    inp.checked = !inp.checked;
    U.updateToggleLabel(draftToggleColors, inp.checked);
    applyDraftPreview();
  });

  // ====== Draft-Editor: live speichern & Preview updaten ======
  let saveTimer = null;
  draftEditor?.addEventListener("input", () => {
    U.setSaveState(saveDot, saveText, "busy");
    rawDraft = draftEditor.value || "";
    applyDraftPreview();
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      U.saveLocalDraft(CONF.LOCAL_KEY, rawDraft);
      U.setSaveState(saveDot, saveText, "ok", "Gespeichert");
    }, 250);
  });

  // ====== Font-Regler ======
  origFontMinus?.addEventListener("click", () => U.nudgeFont(origPre, -1));
  origFontPlus ?.addEventListener("click", () => U.nudgeFont(origPre, +1));
  draftFontMinus?.addEventListener("click", () => {
    U.nudgeFont(draftEditor, -1);
    U.nudgeFont(draftPreview, -1);
  });
  draftFontPlus ?.addEventListener("click", () => {
    U.nudgeFont(draftEditor, +1);
    U.nudgeFont(draftPreview, +1);
  });

  // ====== Entwurf herunterladen (mit Code) ======
  btnDownloadDraft?.addEventListener("click", async () => {
    const text = draftEditor.value || rawDraft || "";
    if (!text.trim()) { alert("Kein Entwurf vorhanden."); return; }
    try {
      const code = await U.diffCode(rawOriginal || "", text);
      const fname = `${CONF.WORK}_birkenbihl_ENTWURF_${code}.txt`;
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = fname; document.body.appendChild(a); a.click();
      setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 800);
    } catch (e) {
      alert("Konnte Entwurf nicht herunterladen: " + e.message);
    }
  });

  // ====== Entwurf HOCHLADEN (lokale TXT in Editor laden) ======
  btnUploadDraft?.addEventListener("click", () => fileDraft?.click());
  fileDraft?.addEventListener("change", async (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    try {
      const txt = await f.text();
      draftEditor.value = txt;
      rawDraft = txt;
      applyDraftPreview();
      U.saveLocalDraft(CONF.LOCAL_KEY, rawDraft);
      U.setSaveState(saveDot, saveText, "ok", "Entwurf importiert");
      draftStatus.innerHTML = '<span class="ok">Entwurf geladen.</span>';
    } catch (err) {
      alert("Konnte Datei nicht lesen: " + err.message);
    } finally {
      fileDraft.value = "";
    }
  });

  // ====== Entwurf zurücksetzen (nur lokal) ======
  function openConfirm() { modalBackdrop.style.display = "flex"; modalBackdrop.setAttribute("aria-hidden", "false"); }
  function closeConfirm(){ modalBackdrop.style.display = "none"; modalBackdrop.setAttribute("aria-hidden", "true"); }
  btnReset?.addEventListener("click", openConfirm);
  modalClose?.addEventListener("click", closeConfirm);
  modalCancel?.addEventListener("click", closeConfirm);
  modalBackdrop?.addEventListener("click", (e) => { if (e.target === modalBackdrop) closeConfirm(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && modalBackdrop.style.display === "flex") closeConfirm(); });

  modalOk?.addEventListener("click", () => {
    U.clearLocalDraft(CONF.LOCAL_KEY);
    rawDraft = rawOriginal || "";
    draftEditor.value = rawDraft;
    applyDraftPreview();
    draftStatus.innerHTML = '<span class="ok">Entwurf auf Original zurückgesetzt.</span>';
    U.setSaveState(saveDot, saveText, "ready", "Bereit");
    closeConfirm();
  });

  // ====== PDF-Panel oben ======
  ;[pdfNormal, pdfFett, srcOriginal, srcDraft].forEach((el) => el && el.addEventListener("change", () => refreshPdf(true)));
  btnRefresh?.addEventListener("click", () => refreshPdf(true));
  refreshPdf(false);

  // ====== PDF-Optionen-Modal ======
  let optContext = "draft"; // "original" | "draft"
  function openOptModal(ctx) {
    optContext = ctx;
    optContextNote.textContent =
      ctx === "original"
        ? "Hinweis: Oben wird auf „Original“ umgeschaltet. Offizielle PDFs liegen im Ordner pdf/."
        : "Der Entwurf wird mit diesen Optionen gebaut und oben angezeigt.";
    optBackdrop.style.display = "flex";
    optBackdrop.setAttribute("aria-hidden", "false");
  }
  function closeOptModal() { optBackdrop.style.display = "none"; optBackdrop.setAttribute("aria-hidden", "true"); }
  btnGenerateOrig?.addEventListener("click", () => openOptModal("original"));
  btnGenerateDraft?.addEventListener("click", () => openOptModal("draft"));
  optClose?.addEventListener("click", closeOptModal);
  optCancel?.addEventListener("click", closeOptModal);
  optBackdrop?.addEventListener("click", (e) => { if (e.target === optBackdrop) closeOptModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && optBackdrop.style.display === "flex") closeOptModal(); });

  function suffixFromOptions() {
    let s = "";
    if (!optColors.checked) s += "_BW";
    if (!optTags.checked) s += "_NoTags";
    if (optAdv.open) s += "_Custom";
    return s;
  }
  function collectOptionsPayload() {
    return {
      colors: !!optColors.checked,
      showTags: !!optTags.checked,
      custom: optAdv.open
        ? {
            colorByPOS: { N: !!optColorN.checked, V: !!optColorV.checked, Aj: !!optColorAj.checked },
            visibleTags: {
              Av: !!tagAv.checked, Pt: !!tagPt.checked, Ko: !!tagKo.checked, Art: !!tagArt.checked,
              Aj: !!tagAj.checked, V: !!tagV.checked, N: !!tagN.checked,
            },
          }
        : null,
    };
  }

  optGenerate?.addEventListener("click", async () => {
    const suffix = suffixFromOptions();

    if (optContext === "original") {
      srcOriginal.checked = true; srcDraft.checked = false;
      refreshPdf(true); // offizielle PDFs
      draftStatus.innerHTML = '<span class="small">Quelle auf <b>Original</b> umgestellt.</span>';
      closeOptModal();
      return;
    }

    // Entwurf bauen via Worker
    const text = draftEditor.value || rawDraft || "";
    if (!text.trim()) { alert("Kein Entwurfstext vorhanden."); return; }

    try {
      draftStatus.textContent = "⬆️ Entwurf wird an den Build-Dienst gesendet…";
      const opts = collectOptionsPayload();
      const res = await fetch(CONF.WORKER_URL + "/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ work: CONF.WORK, text, opts }),
      });
      const j = await res.json().catch(() => ({}));
      if (!res.ok || !j.ok) throw new Error(j.error || "HTTP " + res.status);

      draftStatus.textContent = "✅ Entwurf angenommen. Build startet…";
      srcDraft.checked = true; srcOriginal.checked = false;

      const kind = pdfFett.checked ? "Fett" : "Normal";
      const target = `${CONF.PDF_DRAFT_BASE}${kind}${suffix}.pdf`;
      const ok = await U.waitForPdf(target, 24, 5000); // ~2 min

      refreshPdf(true, suffix);
      draftStatus.innerHTML = ok
        ? "✅ Entwurfs-PDF aktualisiert."
        : '⚠️ PDF noch nicht bereit. Bitte später „PDF aktualisieren“ klicken.';
    } catch (e) {
      draftStatus.innerHTML = '<span class="err">Fehler: ' + e.message + "</span>";
    } finally {
      closeOptModal();
    }
  });
})();
</script>
