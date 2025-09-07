/* aias.js — PDF-Umschaltung + Draft-Preview; Editor bleibt immer sichtbar; PDF-Hinweis entdoppelt */
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
    LAST_DRAFT_URL_KEY: "Aias_last_draft_url",
  };

  const U = window.Utils || {};
  const $ = (id) => document.getElementById(id);

  // ===== PDF oben =====
  let pdfFrame      = $("pdf-frame");
  const btnRefresh  = $("pdf-refresh");
  const btnPdfDL    = $("pdf-download"); // optional
  const btnPdfOpen  = $("pdf-open");     // optional
  const pdfControls = document.querySelector(".pdf-controls");
  const pdfBusy     = $("pdf-busy");     // Overlay
  const pdfMeta     = $("pdf-meta");     // „Zuletzt gebaut“-Zeile
  const pdfHint     = $("pdf-hint");     // statische Hinweiszeile
  const DEFAULT_PDF_HINT = pdfHint ? pdfHint.textContent : "";

  // Persistenz für Auswahl
  const PDF_SRC_KEY  = "Aias_pdf_src";   // "original" | "draft"
  const PDF_KIND_KEY = "Aias_pdf_kind";  // "Normal"  | "Fett"

  // ===== Original (links) =====
  const origPre = $("bb-original-pre");
  const origToggleTags = $("orig-toggle-tags"), origToggleColors = $("orig-toggle-colors");
  const origSzDec = $("orig-font-minus"), origSzInc = $("orig-font-plus");

  // ===== Entwurf (rechts) =====
  const editor = $("bb-editor");
  const draftView = $("bb-draft-view");         // reine Ansicht (gefiltert)
  const draftViewNote = $("draft-view-note");   // kleiner Hinweistext unter der Ansicht
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

    // Hinweis oben NICHT doppeln: während „spinning“ blenden wir die statische Zeile aus
    if (pdfHint) {
      pdfHint.style.display = spinning ? "none" : "";
      if (!spinning) pdfHint.textContent = DEFAULT_PDF_HINT;
    }
  }
  function setPdfBusy(on) { if (pdfBusy) pdfBusy.style.display = on ? "flex" : "none"; }

  // ----- PDF-Meta (Last-Modified + Größe, per HEAD) -----
  function fmtSize(bytes) {
    if (!Number.isFinite(bytes) || bytes < 0) return "–";
    if (bytes < 1024) return bytes + " B";
    const kb = bytes / 1024;
    if (kb < 1024) return kb.toFixed(1) + " KB";
    const mb = kb / 1024;
    return mb.toFixed(2) + " MB";
  }
  async function updatePdfMeta(url) {
    if (!pdfMeta) return;
    try {
      const r = await fetch(url + (url.includes("?") ? "&" : "?") + "m=" + Date.now(), { method: "HEAD", cache: "no-store" });
      if (!r.ok) throw 0;
      const lm  = r.headers.get("Last-Modified");
      const len = parseInt(r.headers.get("Content-Length") || "0", 10);
      const when = lm ? new Date(lm).toLocaleString() : "unbekannt";
      pdfMeta.textContent = `Zuletzt gebaut: ${when} · Größe: ${fmtSize(len)}`;
    } catch {
      pdfMeta.textContent = "";
    }
  }

  // ===== Robustes Auslesen der PDF-UI =====
  function getPdfSrcKind() {
    const src = document.querySelector('input[name="pdfsrc"]:checked');
    const kind = document.querySelector('input[name="pdfkind"]:checked');
    const srcVal  = src ? src.value : "original"; // "original" | "draft"
    const kindVal = kind ? kind.value : "Normal"; // "Normal" | "Fett"
    return { srcVal, kindVal };
  }

  // ===== HEAD-Check mit Fallback auf Range-GET =====
  async function headOk(url) {
    try {
      const r = await fetch(url + (url.includes("?") ? "&" : "?") + "h=" + Date.now(), { method: "HEAD", cache: "no-store" });
      if (r.ok) return true;
    } catch {}
    try {
      const g = await fetch(url, { method: "GET", headers: { Range: "bytes=0-7" }, cache: "no-store" });
      if (g.ok || g.status === 206) {
        const buf = await g.arrayBuffer();
        const bytes = new Uint8Array(buf);
        const sig = Array.from(bytes).map(b=>String.fromCharCode(b)).join("");
        return sig.startsWith("%PDF-");
      }
    } catch {}
    return false;
  }

  // ===== Draft-URL automatisch ermitteln =====
  async function resolveDraftUrl(kind, suffix = "") {
    try {
      const last = localStorage.getItem(CONF.LAST_DRAFT_URL_KEY);
      if (last && last.includes(`_${kind}${suffix}.pdf`) && await headOk(last)) return last;
    } catch {}

    const candidates = [
      `pdf_drafts/Aias_DRAFT_LATEST_${kind}${suffix}.pdf`,
      `pdf/Aias_DRAFT_LATEST_${kind}${suffix}.pdf`,
      `pdf_drafts/Aias_DRAFT_${kind}${suffix}.pdf`,
      `pdf/Aias_DRAFT_${kind}${suffix}.pdf`,
    ];
    for (const url of candidates) {
      if (await headOk(url)) {
        try { localStorage.setItem(CONF.LAST_DRAFT_URL_KEY, url); } catch {}
        return url;
      }
    }
    return "";
  }

  // ===== Offizielle URL bauen =====
  function buildOfficialUrl(kind) {
    return `${CONF.PDF_OFFICIAL_BASE}${kind}.pdf`;
  }

  // ===== <object> hart neu laden + Links setzen =====
  function hardReloadPdf(url) {
    if (!pdfFrame) return;
    const bustUrl = url + (url.includes("?") ? "&" : "?") + "t=" + Date.now();

    if (btnPdfDL)   btnPdfDL.setAttribute("href", url);
    if (btnPdfOpen) btnPdfOpen.setAttribute("href", url);

    const clone = pdfFrame.cloneNode(true);
    clone.setAttribute("data", bustUrl + "#view=FitH");
    pdfFrame.replaceWith(clone);
    pdfFrame = $("pdf-frame");
    console.log("[PDF] geladen:", url);
    setStatus(`Aktuelles PDF: ${url}`, false);
    updatePdfMeta(url); // Meta (HEAD) nachladen
  }

  async function refreshPdf(_bust = true, suffix = "") {
    const { srcVal, kindVal } = getPdfSrcKind();
    if (srcVal === "draft") {
      setPdfBusy(true);
      const draftUrl = await resolveDraftUrl(kindVal, suffix);
      if (draftUrl) {
        hardReloadPdf(draftUrl);
        setPdfBusy(false);
        return;
      } else {
        setStatus("⚠️ Kein Entwurfs-PDF gefunden – zeige Original.", false);
        hardReloadPdf(buildOfficialUrl(kindVal));
        setPdfBusy(false);
        return;
      }
    }
    hardReloadPdf(buildOfficialUrl(kindVal));
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

  // ===== Verifikation (Signatur prüfen) =====
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

    // Entwurf initial
    rawDraft = (U.loadLocalDraft ? U.loadLocalDraft(CONF.LOCAL_KEY) : "") || rawOriginal || "";
    if (editor) editor.value = rawDraft;

    // Entwurfs-Schalter (persistiert)
    const tagsOn   = loadBool(CONF.DRAFT_TOGGLE_TAGS_KEY,   true);
    const colorsOn = loadBool(CONF.DRAFT_TOGGLE_COLORS_KEY, true);
    if (U.updateToggleLabel) {
      U.updateToggleLabel(draftToggleTags,   tagsOn);
      U.updateToggleLabel(draftToggleColors, colorsOn);
    }
    if (optTags)   optTags.checked   = tagsOn;
    if (optColors) optColors.checked = colorsOn;

    // Editor bleibt immer sichtbar – Ansicht je nach Filtern sichtbar/unsichtbar
    updateDraftViewMode();

    restoreFontSizes();
    setupCoupledScroll();

    // Auswahl aus localStorage wiederherstellen
    try {
      const savedSrc  = localStorage.getItem(PDF_SRC_KEY);
      const savedKind = localStorage.getItem(PDF_KIND_KEY);
      if (savedSrc) {
        const el = document.querySelector(`input[name="pdfsrc"][value="${savedSrc}"]`);
        if (el) el.checked = true;
      }
      if (savedKind) {
        const el = document.querySelector(`input[name="pdfkind"][value="${savedKind}"]`);
        if (el) el.checked = true;
      }
    } catch {}

    await refreshPdf(true);
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

  // ===== Entwurf: Editor bleibt sichtbar; Ansicht bei Filtern dazu =====
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
    const needPreview = f.hideTags || f.hideColors;
    // Editor NIE verstecken:
    if (editor) editor.style.display = "";

    // Vorschau nur ein-/ausblenden
    if (draftView) {
      draftView.style.display = needPreview ? "" : "none";
      if (needPreview) renderDraftView();
    }
    if (draftViewNote) draftViewNote.style.display = needPreview ? "" : "none";

    // Scrollkopplung neu, da Ziel sich ändert
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
    // Falls Vorschau sichtbar, koppeln wir daran; sonst an den Editor
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

  // ===== PDF: delegierte Events =====
  if (pdfControls) {
    pdfControls.addEventListener("change", async (ev) => {
      const t = ev.target;
      if (!(t instanceof HTMLInputElement)) return;
      if (t.name === "pdfsrc" || t.name === "pdfkind") {
        // Auswahl persistieren
        try {
          const src  = document.querySelector('input[name="pdfsrc"]:checked')?.value;
          const kind = document.querySelector('input[name="pdfkind"]:checked')?.value;
          if (src)  localStorage.setItem(PDF_SRC_KEY,  src);
          if (kind) localStorage.setItem(PDF_KIND_KEY, kind);
        } catch {}
        setPdfBusy(true);
        await refreshPdf(true);
        setPdfBusy(false);
      }
    });
  }
  btnRefresh && btnRefresh.addEventListener("click", async () => {
    setPdfBusy(true);
    await refreshPdf(true);
    setPdfBusy(false);
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
      const srcOrig = document.querySelector('input#src-original');
      const srcDraft = document.querySelector('input#src-draft');
      if (srcOrig) srcOrig.checked = true;
      if (srcDraft) srcDraft.checked = false;
      setPdfBusy(true);
      await refreshPdf(true);
      setPdfBusy(false);
      setStatus('Quelle auf „Original“ umgestellt.', false);
      closeOptModal();
      return;
    }

    const text = editor ? (editor.value || "") : (rawDraft || "");
    if (!text.trim()) { alert("Kein Entwurfstext vorhanden."); return; }

    try {
      setStatus('Pdf. wird aus dem Entwurf erstellt… Bitte warten. Sie können oben „PDF aktualisieren“ klicken.', true);
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
      const candidates = [
        `pdf_drafts/Aias_DRAFT_LATEST_${kindVal}${suffix}.pdf`,
        `pdf/Aias_DRAFT_LATEST_${kindVal}${suffix}.pdf`,
        `pdf_drafts/Aias_DRAFT_${kindVal}${suffix}.pdf`,
        `pdf/Aias_DRAFT_${kindVal}${suffix}.pdf`,
      ];

      let target = "";
      const t0 = Date.now();
      outer: for (const url of candidates) {
        const ok = await pollForPdf(url, CONF.WAIT_ATTEMPTS, CONF.WAIT_DELAY_MS, (i, max) => {
          const sec = Math.round((Date.now() - t0) / 1000);
          setStatus(`Pdf. wird generiert … (${sec}s, Versuch ${i}/${max}).`, true);
        });
        if (ok) { target = url; break outer; }
      }

      if (target) {
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
          try { localStorage.setItem(CONF.LAST_DRAFT_URL_KEY, target); } catch {}
          const srcOrig = document.querySelector('input#src-original');
          const srcDr   = document.querySelector('input#src-draft');
          if (srcDr)   srcDr.checked = true;
          if (srcOrig) srcOrig.checked = false;

          hardReloadPdf(target);
          setStatus("✅ Entwurfs-PDF bereit.", false);
          setPdfBusy(false);
        } else {
          setStatus('Pdf. wird aus dem Entwurf erstellt… Sie können oben „PDF aktualisieren“ klicken.', true);
        }
      } else {
        setStatus('Pdf. wird aus dem Entwurf erstellt… Sie können oben „PDF aktualisieren“ klicken.', true);
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
