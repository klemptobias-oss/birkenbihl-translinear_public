// utils.js — gemeinsame Helfer, defensiv & wiederverwendbar
(function () {
  // Mini-Guard: sichere Objektpfade ohne Fehler
  const has = (obj, k) => Object.prototype.hasOwnProperty.call(obj || {}, k);

  // ---- Save-Status UI (kleiner Punkt + Text) ----
  function setSaveState(dotEl, textEl, state, msg) {
    if (!dotEl || !textEl) return;
    dotEl.classList.remove("ok", "busy");
    if (state === "busy") dotEl.classList.add("busy");
    if (state === "ok") dotEl.classList.add("ok");
    textEl.textContent =
      msg || (state === "ok" ? "Gespeichert" : state === "busy" ? "Speichere…" : "Bereit");
  }

  // ---- lokaler Entwurf (localStorage) ----
  function loadLocalDraft(key) {
    try { return localStorage.getItem(key) || ""; } catch { return ""; }
  }
  function saveLocalDraft(key, text) {
    try { localStorage.setItem(key, text || ""); } catch {}
  }
  function clearLocalDraft(key) {
    try { localStorage.removeItem(key); } catch {}
  }

  // ---- Netz & Timing ----
  async function fetchText(path) {
    const r = await fetch(path, { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return await r.text();
  }

  async function waitForPdf(url, attempts, delayMs) {
    for (let i = 0; i < attempts; i++) {
      try {
        const r = await fetch(url + "?check=" + Date.now(), {
          method: "HEAD",
          cache: "no-store",
        });
        if (r.ok) return true;
      } catch {}
      await new Promise((res) => setTimeout(res, delayMs));
    }
    return false;
  }

  // ---- PDF-Viewer-Helfer ----
  function setPdfViewer(frameEl, downloadEl, openEl, url, bust = false) {
    if (!frameEl || !downloadEl || !openEl || !url) return;
    const u = url + (bust ? "?t=" + Date.now() : "");
    // Wichtig: <object> nutzt "data"
    frameEl.setAttribute("data", u + "#view=FitH");
    downloadEl.setAttribute("href", url);
    openEl.setAttribute("href", url);
  }

  // ---- Anzeige-Filter (nur Ansicht, nicht Editor) ----
  // (1) Grammatik-Tags in runden Klammern ausblenden: (…)
  function stripGrammarTags(text) {
    if (!text) return "";
    return text.replace(/\([^()\n]*\)/g, "");
  }
  // (2) Farbkürzel (#, +, -) am Tokenanfang entfernen
  function stripColorPrefixes(text) {
    if (!text) return "";
    return text
      .split("\n")
      .map((line) =>
        line
          .split(/\s+/)
          .map((tok) => {
            if (!tok) return tok;
            const f = tok.charAt(0);
            return f === "#" || f === "+" || f === "-" ? tok.slice(1) : tok;
          })
          .join(" ")
      )
      .join("\n");
  }
  // Kombinierte Renderer-Funktion
  function renderWithFilters(rawText, hideTags, hideColors) {
    let out = rawText || "";
    if (hideTags) out = stripGrammarTags(out);
    if (hideColors) out = stripColorPrefixes(out);
    return out;
  }

  // ---- Anzeige: Toggle-Label (An/Aus) pflegen ----
  function updateToggleLabel(toggleEl, isOn) {
    if (!toggleEl) return;
    const state = toggleEl.querySelector(".state");
    if (!state) return;
    state.textContent = isOn ? state.dataset.on || "An" : state.dataset.off || "Aus";
    state.classList.toggle("on", isOn);
    state.classList.toggle("off", !isOn);
  }

  // ---- Dateiname (Entwurf) stabilisieren: kurzer Diff-Code ----
  async function sha256Hex(str) {
    const enc = new TextEncoder().encode(str || "");
    const buf = await crypto.subtle.digest("SHA-256", enc);
    return Array.from(new Uint8Array(buf))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }
  async function diffCode(original, draft) {
    const hex = await sha256Hex(String(original || "") + "|" + String(draft || ""));
    return hex.slice(0, 8);
  }

  // ---- Export in globalen Namensraum ----
  window.Utils = {
    setSaveState,
    loadLocalDraft,
    saveLocalDraft,
    clearLocalDraft,
    fetchText,
    waitForPdf,
    setPdfViewer,
    stripGrammarTags,
    stripColorPrefixes,
    renderWithFilters,
    updateToggleLabel,
    sha256Hex,
    diffCode,
  };
})();
