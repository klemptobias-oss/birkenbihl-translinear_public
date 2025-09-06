/* utils.js — gemeinsame Helfer (neutral) */
window.Utils = (function () {
  // ---------- Save-Status (kleiner Punkt + Text) ----------
  function setSaveState(dotEl, textEl, state, msg) {
    if (!dotEl || !textEl) return;
    dotEl.classList.remove("ok", "busy");
    if (state === "busy") dotEl.classList.add("busy");
    if (state === "ok") dotEl.classList.add("ok");
    textEl.textContent =
      msg || (state === "ok" ? "Gespeichert" : state === "busy" ? "Speichere…" : "Bereit");
  }

  // ---------- Lokaler Entwurf ----------
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
    // Cache-Busting, um GitHub-Pages-Cache zu umgehen
    const url = path + (path.includes("?") ? "&" : "?") + "t=" + Date.now();
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status + " beim Laden von " + path);
    return await r.text();
  }

  async function waitForPdf(url, attempts, delayMs) {
    for (let i = 0; i < attempts; i++) {
      try {
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

  // ---------- PDF-Viewer ----------
  function setPdfViewer(frameEl, downloadEl, openEl, url, bust = false) {
    if (!frameEl || !downloadEl || !openEl) return;
    const u = url + (bust ? (url.includes("?") ? "&" : "?") + "t=" + Date.now() : "");
    frameEl.setAttribute("data", u + "#view=FitH");
    downloadEl.setAttribute("href", url);
    openEl.setAttribute("href", url);
  }

  // ---------- Anzeige-Filter (nur Ansicht/Preview) ----------
  function stripGrammarTags(text) {
    // entfernt (…)-Tags
    return (text || "").replace(/\([^()\n]*\)/g, "");
  }
  function stripColorPrefixes(text) {
    // entfernt führende # + - vor Tokens (Farbcodes)
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

  // ---------- Font-Size (rem-basierend) ----------
  function getFontSize(el) {
    const s = window.getComputedStyle(el).fontSize || "0.95rem";
    return parseFloat(s);
  }
  function setFontSize(el, px) {
    el.style.fontSize = px + "px";
  }

  // ---------- SHA / Download-Code ----------
  async function sha256Hex(str) {
    const enc = new TextEncoder().encode(str);
    const buf = await crypto.subtle.digest("SHA-256", enc);
    return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
  }
  async function diffCode(original, draft) {
    const hex = await sha256Hex((original || "") + "|" + (draft || ""));
    return hex.slice(0, 8);
  }

  // ---------- Scroll-Kopplung (proportional) ----------
  function coupleScroll(a, b, enabledRef) {
    if (!a || !b) return () => {};
    let lock = false;
    function sync(from, to) {
      if (lock || !enabledRef()) return;
      lock = true;
      const ratio =
        from.scrollTop / Math.max(1, from.scrollHeight - from.clientHeight);
      to.scrollTop = ratio * (to.scrollHeight - to.clientHeight);
      lock = false;
    }
    const ha = () => sync(a, b);
    const hb = () => sync(b, a);
    a.addEventListener("scroll", ha);
    b.addEventListener("scroll", hb);
    return () => {
      a.removeEventListener("scroll", ha);
      b.removeEventListener("scroll", hb);
    };
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
    getFontSize,
    setFontSize,
    sha256Hex,
    diffCode,
    coupleScroll,
  };
})();
