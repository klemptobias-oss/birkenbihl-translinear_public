<!-- utils.js -->
<script>
window.Utils = (function () {
  // ---------- Save-Status ----------
  function setSaveState(dotEl, textEl, state, msg) {
    if (!dotEl || !textEl) return;
    dotEl.classList.remove("ok", "busy");
    if (state === "busy") dotEl.classList.add("busy");
    if (state === "ok") dotEl.classList.add("ok");
    textEl.textContent =
      msg || (state === "ok" ? "Gespeichert" : state === "busy" ? "Speichere…" : "Bereit");
  }

  // ---------- lokaler Entwurf ----------
  function loadLocalDraft(key) {
    try { return localStorage.getItem(key) || ""; } catch { return ""; }
  }
  function saveLocalDraft(key, text) {
    try { localStorage.setItem(key, text || ""); } catch {}
  }
  function clearLocalDraft(key) {
    try { localStorage.removeItem(key); } catch {}
  }

  // ---------- Netz & Timing ----------
  async function fetchText(path) {
    const r = await fetch(path, { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return await r.text();
  }
  async function waitForPdf(url, attempts, delayMs) {
    for (let i = 0; i < attempts; i++) {
      try {
        const r = await fetch(url + "?check=" + Date.now(), { method: "HEAD", cache: "no-store" });
        if (r.ok) return true;
      } catch {}
      await new Promise((res) => setTimeout(res, delayMs));
    }
    return false;
  }

  // ---------- PDF-Viewer ----------
  function setPdfViewer(frameEl, downloadEl, openEl, url, bust = false) {
    if (!frameEl || !downloadEl || !openEl) return;
    const u = url + (bust ? "?t=" + Date.now() : "");
    frameEl.setAttribute("data", u + "#view=FitH");
    downloadEl.setAttribute("href", url);
    openEl.setAttribute("href", url);
  }

  // ---------- Anzeige-Filter (nur Ansicht/Preview) ----------
  function stripGrammarTags(text) {
    return (text || "").replace(/\([^()\n]*\)/g, "");
  }
  function stripColorPrefixes(text) {
    return (text || "")
      .split(/\n/)
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
  function renderWithFilters(rawText, hideTags, hideColors) {
    let out = rawText || "";
    if (hideTags) out = stripGrammarTags(out);
    if (hideColors) out = stripColorPrefixes(out);
    return out;
  }
  function updateToggleLabel(toggleEl, isOn) {
    if (!toggleEl) return;
    const state = toggleEl.querySelector(".state");
    if (!state) return;
    state.textContent = isOn ? state.dataset.on || "An" : state.dataset.off || "Aus";
    state.classList.toggle("on", isOn);
    state.classList.toggle("off", !isOn);
  }

  // ---------- Hash/Code für Dateinamen ----------
  async function sha256Hex(str) {
    const enc = new TextEncoder().encode(str);
    const buf = await crypto.subtle.digest("SHA-256", enc);
    return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
  }
  async function diffCode(original, draft) {
    const hex = await sha256Hex((original || "") + "|" + (draft || ""));
    return hex.slice(0, 8);
  }

  // ---------- Scroll-Sync ----------
  // Quelle -> Ziel(e), prozentualer Abgleich; aktiv nur wenn getter() true liefert.
  function attachScrollSync(sourceEl, targetEls, enabledGetter) {
    if (!sourceEl || !targetEls?.length) return;
    sourceEl.addEventListener("scroll", () => {
      if (!enabledGetter || !enabledGetter()) return;
      const max = sourceEl.scrollHeight - sourceEl.clientHeight;
      const p = max > 0 ? sourceEl.scrollTop / max : 0;
      targetEls.forEach((t) => {
        if (!t) return;
        const tMax = t.scrollHeight - t.clientHeight;
        t.scrollTop = p * (tMax > 0 ? tMax : 0);
      });
    }, { passive: true });
  }

  // ---------- Font-Regler ----------
  function getFontSize(el) {
    const c = getComputedStyle(el);
    const px = parseFloat(c.fontSize || "14");
    return isNaN(px) ? 14 : px;
  }
  function setFontSize(el, px) {
    if (el) el.style.fontSize = px + "px";
  }
  function nudgeFont(el, deltaPx, minPx = 10, maxPx = 24) {
    if (!el) return;
    const cur = getFontSize(el);
    const next = Math.max(minPx, Math.min(maxPx, cur + deltaPx));
    setFontSize(el, next);
  }

  return {
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
    attachScrollSync,
    getFontSize,
    setFontSize,
    nudgeFont,
  };
})();
</script>
