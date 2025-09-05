// aias.js — Seitenlogik für Aias (nutzt Utils)
(function () {
  // ====== Konfiguration (werksbezogen) ======
  const CONF = {
    WORK: "Aias",
    LOCAL_KEY: "draft_Aias_birkenbihl",
    TXT_ORIG_PATH: "texte/Aias_birkenbihl.txt",
    PDF_DRAFT_BASE: "pdf_drafts/Aias_DRAFT_LATEST_",  // + Normal/Fett[+Suffix].pdf
    PDF_OFFICIAL_BASE: "pdf/TragödieAias_",            // + Normal/Fett.pdf
    WORKER_URL: "https://birkenbihl-draft-01.klemp-tobias.workers.dev",
    SIZE_KEY_ORIG: "size_Aias_original",
    SIZE_KEY_DRAFT:"size_Aias_draft",
    SYNC_KEY: "syncscroll_Aias",   // "on" | "off"
    SIZE_MIN: 0.78, SIZE_MAX: 1.35, SIZE_STEP: 0.05   // relative zu --mono-size Basis
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

  // Neue Steuerelemente: Schriftgröße +/- & Sync-Scroll
  const origMinus = document.getElementById("orig-font-minus");
  const origPlus  = document.getElementById("orig-font-plus");
  const origSizeChip = document.getElementById("orig-size-chip");
  const draftMinus = document.getElementById("draft-font-minus");
  const draftPlus  = document.getElementById("draft-font-plus");
  const draftSizeChip = document.getElementById("draft-size-chip");
  const syncToggle = document.getElementById("orig-sync-toggle");
  const syncState  = document.getElementById("orig-sync-state");

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
  let syncOn = false;       // Scroll-Kopplung aktiv?
  let syncing = false;      // Re-Entrancy-Guard

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

  // ====== Schriftgröße je Pane (lokal speichern) ======
  function getStoredSize(key, def = 1.0) {
    const v = localStorage.getItem(key);
    const n = v ? parseFloat(v) : NaN;
    return isFinite(n) && n > 0.4 && n < 2.0 ? n : def;
  }
  function applyPaneSize(el, baseRem, factor) {
    if (!el) return;
    el.style.fontSize = `calc(${baseRem} * ${factor.toFixed(2)})`;
  }
  function updateSizeChip(chip, factor) {
    if (chip) chip.textContent = `${Math.round(factor * 100)}%`;
  }
  function bumpSize(which, dir) {
    const key = which === "orig" ? CONF.SIZE_KEY_ORIG : CONF.SIZE_KEY_DRAFT;
    const el  = which === "orig" ? origPre : draftPre;
    const ed  = which === "orig" ? null    : editor;    // Editor nur rechts
    let f = getStoredSize(key, 1.0);
    f = Math.min(CONF.SIZE_MAX, Math.max(CONF.SIZE_MIN, f + (dir > 0 ? CONF.SIZE_STEP : -CONF.SIZE_STEP)));
    localStorage.setItem(key, String(f));
    applyPaneSize(el, "var(--mono-size)", f);
    if (ed) applyPaneSize(ed, "var(--mono-size)", f);
    updateSizeChip(which === "orig" ? origSizeChip : draftSizeChip, f);
  }

  // ====== Sync-Scroll an/aus ======
  function setSyncState(on) {
    syncOn = !!on;
    localStorage.setItem(CONF.SYNC_KEY, syncOn ? "on" : "off");
    if (syncState) {
      syncState.textContent = syncOn ? "An" : "Aus";
      syncState.classList.toggle("on", syncOn);
      syncState.classList.toggle("off", !syncOn);
    }
  }
  function handleScrollLink(src, dst) {
    if (!syncOn || !src || !dst) return;
    if (syncing) return;
    syncing = true;
    const ratio = src.scrollTop / Math.max(1, src.scrollHeight - src.clientHeight);
    dst.scrollTop = ratio * (dst.scrollHeight - dst.clientHeight);
    syncing = false;
  }

  // ====== Start: Texte laden (robust) ======
  (async function initTexts() {
    // 1) Original
    try {
      rawOriginal = await U.fetchText(CONF.TXT_ORIG_PATH);
      // Anzeige-Schalter initial: Tags & Farben sichtbar (An)
      U.updateToggleLabel(origToggleTags, true);
      U.updateToggleLabel(origToggleColors, true);
      origPre.textContent = U.renderWithFilters(rawOriginal, false, false);
    } catch (e) {
      origPre.textContent = "Konnte " + CONF.TXT_ORIG_PATH + " nicht laden ("
        + (e && e.message ? e.message : "Unbekannter Fehler") + "). Liegt die Datei im Ordner texte/?";
    }

    // 2) Entwurf (lokal)
    rawDraft = U.loadLocalDraft(CONF.LOCAL_KEY) || "";
    U.updateToggleLabel(draftToggleTags, true);
    U.updateToggleLabel(draftToggleColors, true);
    draftPre.textContent = U.renderWithFilters(rawDraft, false, false);

    // 3) Schriftgrößen anwenden
    const fOrig = getStoredSize(CONF.SIZE_KEY_ORIG, 1.0);
    const fDraft = getStoredSize(CONF.SIZE_KEY_DRAFT, 1.0);
    applyPaneSize(origPre, "var(--mono-size)", fOrig);
    applyPaneSize(draftPre, "var(--mono-size)", fDraft);
    applyPaneSize(editor,  "var(--mono-size)", fDraft);
    updateSizeChip(origSizeChip, fOrig);
    updateSizeChip(draftSizeChip, fDraft);

    // 4) Sync-Status herstellen
    setSyncState((localStorage.getItem(CONF.SYNC_KEY) || "off") === "on");
  })();

  // ====== Anzeige-Schalter ======
  // Original
  origToggleTags?.addEventListener("click", () => {
    const input = origToggleTags.querySelector("input");
    input.checked = !input.checked;
    const on = input.checked;
    U.updateToggleLabel(origToggleTags, on);
    const hideTags = !on;
    const hideColors = !(origToggleColors.querySelector("input").checked);
    origPre.textContent = U.renderWithFilters(rawOriginal, hideTags, hideColors);
  });
  origToggleColors?.addEventListener("click", () => {
    const input = origToggleColors.querySelector("input");
    input.checked = !input.checked;
    const on = input.checked;
    U.updateToggleLabel(origToggleColors, on);
    const hideColors = !on;
    const hideTags = !(origToggleTags.querySelector("input").checked);
    origPre.textContent = U.renderWithFilters(rawOriginal, hideTags, hideColors);
  });

  // Entwurf
  draftToggleTags?.addEventListener("click", () => {
    const input = draftToggleTags.querySelector("input");
    input.checked = !input.checked;
    const on = input.checked;
    U.updateToggleLabel(draftToggleTags, on);
    const hideTags = !on;
    const hideColors = !(draftToggleColors.querySelector("input").checked);
    draftPre.textContent = U.renderWithFilters(rawDraft, hideTags, hideColors);
  });
  draftToggleColors?.addEventListener("click", () => {
    const input = draftToggleColors.querySelector("input");
    input.checked = !input.checked;
    const on = input.checked;
    U.updateToggleLabel(draftToggleColors, on);
    const hideColors = !on;
    const hideTags = !(draftToggleTags.querySelector("input").checked);
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
    const hideTags = !(draftToggleTags.querySelector("input").checked);
    const hideColors = !(draftToggleColors.querySelector("input").checked);
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
      setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1000);
    } catch (e) {
      alert("Konnte Entwurf nicht herunterladen: " + e.message);
    }
  });

  // ====== Bestätigungs-Modal: Entwurf zurücksetzen ======
  function openConfirm() {
    modalBackdrop.style.display = "flex";
    modalBackdrop.setAttribute("aria-hidden", "false");
  }
  function closeConfirm() {
    modalBackdrop.style.display = "none";
    modalBackdrop.setAttribute("aria-hidden", "true");
  }
  btnReset?.addEventListener("click", openConfirm);
  modalClose?.addEventListener("click", closeConfirm);
  modalCancel?.addEventListener("click", closeConfirm);
  modalBackdrop?.addEventListener("click", (e) => { if (e.target === modalBackdrop) closeConfirm(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && modalBackdrop.style.display === "flex") closeConfirm(); });
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
  refreshPdf(false); // Initial

  // ====== Optionen-Modal (PDF generieren) ======
  const btnOpenOptsOriginal = document.getElementById("bb-generate-original");
  const btnOpenOptsDraft = document.getElementById("bb-generate-draft");

  function openOptModal(context) {
    optContext = context;
    optContextNote.textContent =
      context === "original"
        ? "Hinweis: Oben wird auf „Original“ umgeschaltet. Offizielle PDFs liegen im Ordner pdf/."
        : "Der Entwurf wird mit diesen Optionen gebaut und oben angezeigt.";
    optBackdrop.style.display = "flex";
    optBackdrop.setAttribute("aria-hidden", "false");
  }
  function closeOptModal() {
    optBackdrop.style.display = "none";
    optBackdrop.setAttribute("aria-hidden", "true");
  }
  btnOpenOptsOriginal?.addEventListener("click", () => openOptModal("original"));
  btnOpenOptsDraft?.addEventListener("click", () => openOptModal("draft"));
  optClose?.addEventListener("click", closeOptModal);
  optCancel?.addEventListener("click", closeOptModal);
  optBackdrop?.addEventListener("click", (e) => { if (e.target === optBackdrop) closeOptModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && optBackdrop.style.display === "flex") closeOptModal(); });

  function suffixFromOptions() {
    let suffix = "";
    if (!optColors.checked) suffix += "_BW";
    if (!optTags.checked) suffix += "_NoTags";
    if (optAdv.open) suffix += "_Custom";
    return suffix;
  }
  function collectOptionsPayload() {
    return {
      colors: !!optColors.checked,
      showTags: !!optTags.checked,
      custom: optAdv.open
        ? {
            colorByPOS: { N: !!optColorN.checked, V: !!optColorV.checked, Aj: !!optColorAj.checked },
            visibleTags: {
              Av: !!tagAv.checked, Pt: !!tagPt.checked, Ko: !!tagKo.checked,
              Art: !!tagArt.checked, Aj: !!tagAj.checked, V: !!tagV.checked, N: !!tagN.checked,
            },
          }
        : null,
    };
  }

  optGenerate?.addEventListener("click", async () => {
    const suffix = suffixFromOptions();

    if (optContext === "original") {
      srcOriginal.checked = true;
      srcDraft.checked = false;
      refreshPdf(true); // offizielle PDFs (ohne Suffix)
      draftStatus.innerHTML = '<span class="small">Quelle auf <b>Original</b> umgestellt.</span>';
      closeOptModal();
      return;
    }

    const text = editor.style.display !== "none" ? editor.value : rawDraft || "";
    if (!text.trim()) {
      alert("Kein Entwurfstext vorhanden. Bitte auf „Bearbeiten“ klicken, Text anpassen und speichern.");
      return;
    }

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

      srcDraft.checked = true;
      srcOriginal.checked = false;

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

  // ====== Schriftgröße-Buttons & Sync-Scroll verdrahten ======
  origMinus?.addEventListener("click", () => bumpSize("orig", -1));
  origPlus?.addEventListener("click",  () => bumpSize("orig", +1));
  draftMinus?.addEventListener("click", () => bumpSize("draft", -1));
  draftPlus?.addEventListener("click",  () => bumpSize("draft", +1));

  // Sync-Scroll Umschalter (nur links)
  if (syncToggle) {
    syncToggle.addEventListener("click", () => {
      setSyncState(!syncOn);
    });
  }
  // Scroll-Ereignisse koppeln
  origPre?.addEventListener("scroll", () => handleScrollLink(origPre, draftPre));
  draftPre?.addEventListener("scroll", () => handleScrollLink(draftPre, origPre));
})();
