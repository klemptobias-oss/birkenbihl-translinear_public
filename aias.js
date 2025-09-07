/* aias.js — robuste PDF-Umschaltung + Editor/Entwurf-Logik + Status */
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
    DRAFT_TOGGLE_TAGS_KEY:   "Aias_draft_toggle_tags",
    DRAFT_TOGGLE_COLORS_KEY: "Aias_draft_toggle_colors",
    WAIT_ATTEMPTS: 24,
    WAIT_DELAY_MS: 5000,
  };

  const U = window.Utils || {};
  const $ = (id) => document.getElementById(id);

  // ===== PDF oben =====
  const pdfFrame    = $("pdf-frame");
  const btnRefresh  = $("pdf-refresh");
  const btnPdfDL    = $("pdf-download");
  const btnPdfOpen  = $("pdf-open");
  const pdfControls = document.querySelector(".pdf-controls");
  const pdfBusy     = $("pdf-busy"); // optionales Overlay

  // ===== Original (links) =====
  const origPre = $("bb-original-pre");
  const origToggleTags = $("orig-toggle-tags"), origToggleColors = $("orig-toggle-colors");
  const origSzDec = $("orig-font-minus"), origSzInc = $("orig-font-plus");

  // ===== Entwurf (rechts) =====
  const editor = $("bb-editor");
  const draftView = $("bb-draft-view");
  const draftViewNote = $("draft-view-note");
  const draftSzDec = $("draft-font-minus"), draftSzInc = $("draft-font-plus");
  const btnUploadDraft = $("bb-upload-draft"), btnDownloadDraft = $("bb-download-draft"), btnReset = $("bb-reset");
  const btnGenerateOrig = $("bb-generate-original"), btnGenerateDraft = $("bb-generate-draft");
  const draftToggleTags = $("draft-toggle-tags");
  const draftToggleColors = $("draft-toggle-colors");

  // ===== Status / Save-UI =====
  const saveDot = $("save-dot"), saveText = $("save-text"), draftStatus = $("draft-status");

  // ===== Optionen-Modal =====
  const optBackdrop = $("opt-backdrop"), optClose = $("opt-close"), optCancel = $("opt-cancel"), optGenerate = $("opt-generate");
  const optColors = $("opt-colors"), optTags = $("opt-tags"), optAdv = $("opt-adv");
  const optColorN = $("opt-color-n"), optColorV = $("opt-color-v"), optColorAj = $("opt-color-aj");
  const tagAv = $("tag-Av"), tagPt = $("tag-Pt"), tagKo = $("tag-Ko"), tagArt = $("tag-Art"), tagAj = $("tag-Aj"), tagV = $("tag-V"), tagN = $("tag-N");
  const optContextNote = $("opt-context-note");

  // ===== Zurücksetzen-Modal =====
  const modalBackdrop = $("confirm-backdrop"), modalClose = $("confirm-close");
  const modalCancel = $("confirm-cancel"), modalOk = $("confirm-ok");

  // ===== Scroll-Kopplung =====
  const scrollToggle = $("scroll-link");

  // ===== State =====
  let rawOriginal = "", rawDraft = "", optContext = "draft", unlinkScroll = () => {};

  // ===== Status-/Overlay-Helfer =====
  function setStatus(text, spinning) {
    if (!draftStatus) return;
    let spin = draftStatus.querySelector(".spinner");
    let sTxt = draftStatus.querySelector(".status-text");
    if (!spin) {
      spin = document.createElement("span");
      spin.className = "spinner";
      spin.setAttribute("aria-hidden", "true");
      draftStatus.appendChild(spin);
    }
    if (!sTxt) {
      sTxt = document.createElement("span");
      sTxt.className = "status-text";
      draftStatus.appendChild(sTxt);
    }
    sTxt.textContent = text || "";
    spin.style.display = spinning ? "inline-block" : "none";
  }
  function setPdfBusy(on) { if (pdfBusy) pdfBusy.style.display = on ? "flex" : "none"; }

  // ===== Robustes Auslesen der PDF-UI =====
  function getPdfSrcKind() {
    const src = document.querySelector('input[name="pdfsrc"]:checked');
    const kind = document.querySelector('input[name="pdfkind"]:checked');
    const srcVal  = src ? src.value : "original"; // "original" | "draft"
    const kindVal = kind ? kind.value : "Normal"; // "Normal" | "Fett"
    return { srcVal, kindVal };
  }

  // ===== PDF-URL bauen =====
  function buildPdfUrl(suffix="") {
    const { srcVal, kindVal } = getPdfSrcKind();
    const useDraft = srcVal === "draft";
    const base = useDraft ? CONF.PDF_DRAFT_BASE : CONF.PDF_OFFICIAL_BASE;
    // Draft bekommt ggf. Suffix (BW/NoTags/Custom). Hier: Standard ohne Suffix.
    return base + kindVal + (useDraft ? (suffix || "") : "") + ".pdf";
  }

  // ===== PDF wirklich neu laden (Klon-Trick) + Links setzen =====
  function hardReloadPdf(url, bust=false) {
    if (!pdfFrame || !btnPdfDL || !btnPdfOpen) return;
    const finalUrl = url + (bust ? (url.includes("?") ? "&" : "?") + "t=" + Date.now() : "");
    // Download/Open ohne Bust (sauberer Dateiname)
    btnPdfDL.setAttribute("href", url);
    btnPdfOpen.setAttribute("href", url);

    // <object> neu aufbauen (einige Browser ignorieren data-Änderung sonst)
    const clone = pdfFrame.cloneNode(true);
    clone.setAttribute("data", finalUrl + "#view=FitH");
    pdfFrame.replaceWith(clone);
    // Referenz aktualisieren
    const newRef = $("pdf-frame"); // gleiche ID, frisches Element
    // nichts weiter nötig – Browser lädt das Objekt neu
  }

  function refreshPdf(bust=false, suffix="") {
    const url = buildPdfUrl(suffix);
    hardReloadPdf(url, bust);
  }

  // ===== Live-Polling (HEAD) =====
  async function pollForPdf(url, attempts, delayMs, onTick) {
    for (let i = 1; i <= attempts; i++) {
      try {
        onTick && onTick(i, attempts);
        const r = await fetch(url + (url.includes("?") ? "&" : "?") + "check=" + Date.now(), {
          method: "HEAD",
          cache: "no-store",
        });
        if (r.ok) return true;
      } catch {}
      await new Promise((res) => setTimeout(res, delayMs));
    }
    return false;
  }

  // ===== Verifikation: HEAD + Range-GET (PDF-Signatur) =====
  async function verifyPdf(url) {
    try {
      const head = await fetch(url + (url.includes("?") ? "&" : "?") + "vcheck=" + Date.now(), {
        method: "HEAD",
        cache: "no-store",
      });
      if (!head.ok) return false;
      const ct = (head.headers.get("Content-Type") || "").toLowerCase();
      const len = parseInt(head.headers.get("Content-Length") || "0", 10);
      if (!ct.includes("pdf")) return false;
      if (isFinite(len) && len > 0 && len < 500) return false;

      const rng = await fetch(url, { method: "GET", headers: { Range: "bytes=0-7" }, cache: "no-store" });
      if (!rng.ok && rng.status !== 206 && rng.status !== 200) return false;
      const buf = await rng.arrayBuffer();
      const bytes = new Uint8Array(buf);
      const txt = Array.from(bytes).map((b) => String.fromCharCode(b)).join("");
      return txt.startsWith("%PDF-");
    } catch { return false; }
  }

  // ===== Init =====
  (async function init() {
    try {
      rawOriginal = U.fetchText ? await U.fetchText(CONF.TXT_ORIG_PATH) : "";
    } catch (e) {
      console.error("Fehler beim Laden:", e);
      rawOriginal = "Konnte " + CONF.TXT_ORIG_PATH + " nicht laden. Liegt die Datei im Ordner texte/?";
    }

    if (origPre) {
      U.updateToggleLabel && U.updateToggleLabel(origToggleTags, true);
      U.updateToggleLabel && U.updateToggleLabel(origToggleColors, true);
      renderOriginal();
    }

    rawDraft = (U.loadLocalDraft ? U.loadLocalDraft(CONF.LOCAL_KEY) : "") || rawOriginal || "";
    if (editor) editor.value = rawDraft;

    const tagsOn   = loadBool(CONF.DRAFT_TOGGLE_TAGS_KEY,   true);
    const colorsOn = loadBool(CONF.DRAFT_TOGGLE_COLORS_KEY, true);
    if (U.updateToggleLabel) {
      U.updateToggleLabel(draftToggleTags,   tagsOn);
      U.updateToggleLabel(draftToggleColors, colorsOn);
    }
    if (optTags)   optTags.checked   = tagsOn;
    if (optColors) optColors.checked = colorsOn;

    updateDraftViewMode();

    restoreFontSizes();
    setupCoupledScroll();

    // Initial PDF entsprechend aktueller Radios laden (auch falls HTML Default nicht passt)
    refreshPdf(true);
  })();

  // ===== persistente Booleans =====
  function loadBool(key, fallback) {
    try { const v = localStorage.getItem(key); return v === null ? fallback : v === "1"; }
    catch { return fallback; }
  }
  function saveBool(key, value) { try { localStorage.setItem(key, value ? "1" : "0"); } catch {} }

  // ===== Original-Filter =====
  function currentOrigFilters() {
    const showTags   = !!(origToggleTags && origToggleTags.querySelector("input")?.checked);
    const showColors = !!(origToggleColors && origToggleColors.querySelector("input")?.checked);
    return { hideTags: !showTags, hideColors: !showColors };
  }
  function renderOriginal() {
    if (!origPre) return;
    const f = currentOrigFilters();
    const text = U.renderWithFilters ? U.renderWithFilters(rawOriginal, f.hideTags, f.hideColors) : rawOriginal;
    origPre.textContent = text || "— (leer) —";
  }
  function bindToggle(toggleEl, onChange) {
    if (!toggleEl) return;
    toggleEl.addEventListener("click", () => {
      const input = toggleEl.querySelector("input");
      if (!input) return;
      input.checked = !input.checked;
      U.updateToggleLabel && U.updateToggleLabel(toggleEl, input.checked);
      onChange && onChange(input.checked);
    });
  }
  bindToggle(origToggleTags,   () => renderOriginal());
  bindToggle(origToggleColors, () => renderOriginal());

  // ===== Entwurf: View/Editor umschalten =====
  function currentDraftFilters() {
    const showTags   = !!(draftToggleTags && draftToggleTags.querySelector("input")?.checked);
    const showColors = !!(draftToggleColors && draftToggleColors.querySelector("input")?.checked);
    return { hideTags: !showTags, hideColors: !showColors, showTags, showColors };
  }
  function renderDraftView() {
    if (!draftView) return;
    const f = currentDraftFilters();
    const text = editor ? (editor.value || "") : (rawDraft || "");
    draftView.textContent = U.renderWithFilters ? U.renderWithFilters(text, f.hideTags, f.hideColors) : text;
  }
  function updateDraftViewMode() {
    const f = currentDraftFilters();
    const useView = f.hideTags || f.hideColors;
    if (useView) {
      if (editor) editor.style.display = "none";
      if (draftView) { draftView.style.display = ""; renderDraftView(); }
      if (draftViewNote) draftViewNote.style.display = "";
    } else {
      if (draftView) draftView.style.display = "none";
      if (editor) editor.style.display = "";
      if (draftViewNote) draftViewNote.style.display = "none";
    }
    setupCoupledScroll();
  }

  bindToggle(draftToggleTags, (isOn) => {
    saveBool(CONF.DRAFT_TOGGLE_TAGS_KEY, isOn);
    if (optTags) optTags.checked = isOn;
    updateDraftViewMode();
  });
  bindToggle(draftToggleColors, (isOn) => {
    saveBool(CONF.DRAFT_TOGGLE_COLORS_KEY, isOn);
    if (optColors) optColors.checked = isOn;
    updateDraftViewMode();
  });

  // ===== Font-Größen =====
  function restoreFontSizes() {
    try {
      const leftPx  = parseFloat(localStorage.getItem(CONF.FONT_KEY_LEFT)  || "0");
      const rightPx = parseFloat(localStorage.getItem(CONF.FONT_KEY_RIGHT) || "0");
      if (origPre && leftPx  > 0 && U.setFontSize) U.setFontSize(origPre, leftPx);
      if (editor  && rightPx > 0 && U.setFontSize) U.setFontSize(editor,  rightPx);
      if (draftView && rightPx > 0 && U.setFontSize) U.setFontSize(draftView, rightPx);
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
  draftSzDec && draftSzDec.addEventListener("click", () => bumpFont([visibleDraftScrollEl()], CONF.FONT_KEY_RIGHT, -1.0));
  draftSzInc && draftSzInc.addEventListener("click", () => bumpFont([visibleDraftScrollEl()], CONF.FONT_KEY_RIGHT, +1.0));

  // ===== Scroll koppeln =====
  function visibleDraftScrollEl() {
    const viewVisible = draftView && draftView.style.display !== "none";
    return viewVisible ? draftView : editor;
  }
  function setupCoupledScroll() {
    unlinkScroll();
    const checked = !!(scrollToggle && scrollToggle.querySelector("input")?.checked);
    const rightPane = visibleDraftScrollEl();
    if (origPre && rightPane && U.coupleScroll && checked) {
      unlinkScroll = U.coupleScroll(origPre, rightPane, () => !!(scrollToggle && scrollToggle.querySelector("input")?.checked));
    } else {
      unlinkScroll = () => {};
    }
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

  // ===== Editor + Autosave =====
  let saveTimer = null;
  editor && editor.addEventListener("input", () => {
    U.setSaveState && U.setSaveState(saveDot, saveText, "busy");
    rawDraft = editor.value || "";
    if (saveTimer) clearTimeout(saveTimer);
    if (draftView && draftView.style.display !== "none") renderDraftView();
    saveTimer = setTimeout(() => {
      U.saveLocalDraft && U.saveLocalDraft(CONF.LOCAL_KEY, rawDraft);
      U.setSaveState && U.setSaveState(saveDot, saveText, "ok", "Gespeichert");
    }, 250);
  });

  // ===== Upload/Download/Reset =====
  btnUploadDraft && btnUploadDraft.addEventListener("click", () => {
    const inp = document.createElement("input");
    inp.type = "file"; inp.accept = ".txt,text/plain";
    inp.addEventListener("change", async () => {
      const file = inp.files && inp.files[0]; if (!file) return;
      try {
        const text = await file.text();
        rawDraft = text || ""; if (editor) editor.value = rawDraft;
        U.saveLocalDraft && U.saveLocalDraft(CONF.LOCAL_KEY, rawDraft);
        if (draftView && draftView.style.display !== "none") renderDraftView();
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

  function openConfirm() { if (!modalBackdrop) return; modalBackdrop.style.display = "flex"; modalBackdrop.setAttribute("aria-hidden", "false"); }
  function closeConfirm() { if (!modalBackdrop) return; modalBackdrop.style.display = "none"; modalBackdrop.setAttribute("aria-hidden", "true"); }
  btnReset && btnReset.addEventListener("click", openConfirm);
  modalClose && modalClose.addEventListener("click", closeConfirm);
  modalCancel&& modalCancel.addEventListener("click", closeConfirm);
  modalBackdrop && modalBackdrop.addEventListener("click", (e) => { if (e.target === modalBackdrop) closeConfirm(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && modalBackdrop && modalBackdrop.style.display === "flex") closeConfirm(); });
  modalOk && modalOk.addEventListener("click", () => {
    U.clearLocalDraft && U.clearLocalDraft(CONF.LOCAL_KEY);
    rawDraft = rawOriginal || "";
    if (editor) editor.value = rawDraft;
    if (draftView && draftView.style.display !== "none") renderDraftView();
    U.setSaveState && U.setSaveState(saveDot, saveText, "ready", "Bereit");
    closeConfirm();
  });

  // ===== PDF: delegierte Events auf dem Container (resistent gegen Duplikate) =====
  if (pdfControls) {
    pdfControls.addEventListener("change", (ev) => {
      const t = ev.target;
      if (!(t instanceof HTMLInputElement)) return;
      if (t.name === "pdfsrc" || t.name === "pdfkind") {
        setPdfBusy(true);
        refreshPdf(true);
        setTimeout(() => setPdfBusy(false), 400);
      }
    });
  }
  btnRefresh && btnRefresh.addEventListener("click", () => {
    setPdfBusy(true);
    refreshPdf(true);
    setTimeout(() => setPdfBusy(false), 400);
  });

  // ===== Optionen-Modal & Build =====
  function openOptModal(context) {
    optContext = context;
    if (optContextNote) {
      optContextNote.textContent =
        context === "original"
          ? "Hinweis: Oben wird auf „Original“ umgeschaltet. Offizielle PDFs liegen im Ordner pdf/."
          : "Der Entwurf wird mit diesen Optionen gebaut und oben angezeigt.";
    }
    const f = currentDraftFilters();
    if (optTags)   optTags.checked   = !f.hideTags;
    if (optColors) optColors.checked = !f.hideColors;

    if (optBackdrop) { optBackdrop.style.display = "flex"; optBackdrop.setAttribute("aria-hidden", "false"); }
  }
  function closeOptModal() { if (!optBackdrop) return; optBackdrop.style.display = "none"; optBackdrop.setAttribute("aria-hidden", "true"); }

  btnGenerateOrig  && btnGenerateOrig.addEventListener("click", () => openOptModal("original"));
  btnGenerateDraft && btnGenerateDraft.addEventListener("click", () => openOptModal("draft"));
  optClose && optClose.addEventListener("click", closeOptModal);
  optCancel&& optCancel.addEventListener("click", closeOptModal);
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
      // Nur Quelle umschalten + reload
      const srcOrig = document.querySelector('input#src-original');
      const srcDraft = document.querySelector('input#src-draft');
      if (srcOrig) srcOrig.checked = true;
      if (srcDraft) srcDraft.checked = false;
      setPdfBusy(true);
      refreshPdf(true);
      setTimeout(() => setPdfBusy(false), 400);
      setStatus('Quelle auf „Original“ umgestellt.', false);
      closeOptModal();
      return;
    }

    const text = editor ? (editor.value || "") : (rawDraft || "");
    if (!text.trim()) { alert("Kein Entwurfstext vorhanden."); return; }

    try {
      setStatus('Pdf. wird aus dem Entwurf erstellt. Dies kann bis zu zwei Minuten in Anspruch nehmen. Klicken Sie regelmäßig auf „Pdf aktualisieren“ um den aktuellen Stand zu überprüfen.', true);
      setPdfBusy(true);

      const opts = collectOptionsPayload();
      const res = await fetch(CONF.WORKER_URL + "/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ work: CONF.WORK, text, opts }),
      });
      const j = await res.json().catch(() => ({}));
      if (!res.ok || !j.ok) throw new Error(j.error || ("HTTP " + res.status));

      const { kindVal } = getPdfSrcKind();
      const target = `${CONF.PDF_DRAFT_BASE}${kindVal}${suffix}.pdf`;

      const t0 = Date.now();
      const ok = await pollForPdf(target, CONF.WAIT_ATTEMPTS, CONF.WAIT_DELAY_MS, (i, max) => {
        const sec = Math.round((Date.now() - t0) / 1000);
        setStatus(`Pdf. wird generiert … (${sec}s, Versuch ${i}/${max}). Sie können oben „Pdf aktualisieren“ klicken – ich lade automatisch, sobald es fertig ist.`, true);
      });

      if (ok) {
        setStatus("Verifiziere fertiges Pdf…", true);
        let verified = await verifyPdf(target);

        if (!verified) {
          const t1 = Date.now();
          const ok2 = await pollForPdf(target, 6, 5000, (i, max) => {
            const sec = Math.round((Date.now() - t1) / 1000);
            setStatus(`Verifiziere Pdf … (${sec}s, Versuch ${i}/${max}).`, true);
          });
          if (ok2) verified = await verifyPdf(target);
        }

        if (verified) {
          // Quelle auf Entwurf umschalten
          const srcOrig = document.querySelector('input#src-original');
          const srcDr   = document.querySelector('input#src-draft');
          if (srcDr)   srcDr.checked = true;
          if (srcOrig) srcOrig.checked = false;

          refreshPdf(true, suffix);
          setStatus("✅ Entwurfs-PDF bereit.", false);
          setPdfBusy(false);
        } else {
          setStatus('Pdf. wird aus dem Entwurf erstellt. Dies kann bis zu zwei Minuten in Anspruch nehmen. Klicken Sie regelmäßig auf „Pdf aktualisieren“ um den aktuellen Stand zu überprüfen.', true);
          // Overlay bleibt sichtbar, Nutzer kann manuell prüfen
        }
      } else {
        setStatus('Pdf. wird aus dem Entwurf erstellt. Dies kann bis zu zwei Minuten in Anspruch nehmen. Klicken Sie regelmäßig auf „Pdf aktualisieren“ um den aktuellen Stand zu überprüfen.', true);
      }
    } catch (e) {
      setStatus('Fehler: ' + (e && e.message ? e.message : e), false);
      setPdfBusy(false);
    } finally {
      closeOptModal();
    }
  };
  optGenerate && optGenerate.addEventListener("click", optGenerateHandler);
})();
