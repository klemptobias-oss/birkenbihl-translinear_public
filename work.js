/* ==========================================================
   Allgemeines Werk-Script für Original + Birkenbihl + PDF
   ----------------------------------------------------------
   URL-Parameter:
     ?kind=poesie|prosa&author=<Autor>&work=<Werk>

   Datenquellen:
     - Original (oben links):
       texte/<kind>/<Autor>/<Werk>.txt
     - Birkenbihl (unten links):
       texte/<kind>/<Autor>/<Werk>_birkenbihl.txt
     - PDF (oben rechts, Viewer):
       Poesie: pdf/original_poesie_pdf/<Autor>/<pdfStem>_<Strength>_<Color>_<Tags>[ _Versmaß].pdf
       Prosa : pdf/original_prosa_pdf/<Autor>/<pdfStem>_<Strength>_<Color>_<Tags>.pdf

   pdfStem: pro Werk konfigurierbar, falls Generator andere Basis nutzt.
   Beispiele unten in CONFIG.WORKS.

   Drafts (unten rechts):
     - Hier nur UI (Editor + Buttons). Der eigentliche PDF-Build läuft
       wie gehabt über eure Adapter, nicht im Browser.

   ========================================================== */

(function () {
  // ---------- Konfiguration (bestehende Werke als Beispiele) ----------
  const CONFIG = {
    // Sichtbare Labels optional; technisch maßgeblich sind author/work/kind
    WORKS: [
      {
        // Poesie mit Versmaß
        label: "Aischylos – Der gefesselte Prometheus",
        kind: "poesie",
        author: "Aischylos",
        work: "Der_gefesselte_Prometheus",
        // PDFs heißen typischerweise wie das Work (wenn ihr so generiert)
        pdfStem: "Der_gefesselte_Prometheus",
        supportsMeter: true
      },
      {
        // Poesie ohne Versmaß
        label: "Sophokles – Aias",
        kind: "poesie",
        author: "Sophokles",
        work: "Aias",
        pdfStem: "Aias",
        supportsMeter: false
      },
      {
        // Prosa ohne Versmaß; Prosa-PDFs nutzen oft Autor+Werk als Basis
        label: "Platon – Menon",
        kind: "prosa",
        author: "Platon",
        work: "Menon",
        pdfStem: "PlatonMenon",
        supportsMeter: false
      }
    ]
  };

  // ---------- URL-Parameter auslesen ----------
  const params = new URLSearchParams(location.search);
  const kind = (params.get("kind") || "").toLowerCase();      // "poesie" | "prosa"
  const author = params.get("author") || "";
  const work = params.get("work") || "";

  // passendes Werk-Profil ermitteln (oder Fallback aus URL bauen)
  const profile =
    CONFIG.WORKS.find(
      w =>
        w.kind.toLowerCase() === kind &&
        w.author === author &&
        w.work === work
    ) ||
    {
      // Fallback: funktioniert, wenn Verzeichnis/Dateinamen exakt stimmen
      label: `${author} – ${work}`.replaceAll("_", " "),
      kind,
      author,
      work,
      pdfStem:
        kind === "prosa"
          ? `${author}${work}` // z.B. PlatonMenon
          : work, // z.B. Der_gefesselte_Prometheus
      supportsMeter: kind === "poesie" // bei Poesie standardmäßig anzeigen
    };

  // ---------- Titel setzen ----------
  const pageTitle = document.getElementById("page-title");
  if (pageTitle) pageTitle.textContent = `Originaltext + Birkenbihl — ${profile.label}`;

  // ---------- DOM-Refs ----------
  const origBox = document.getElementById("orig-src");
  const bbBox = document.getElementById("bb-src");
  const pdfObj = document.getElementById("pdf-view");
  const pdfBusy = document.getElementById("pdf-busy");
  const meterRow = document.getElementById("meter-row");
  const draftEditor = document.getElementById("draft-editor");
  const draftSpinner = document.getElementById("draft-spinner");
  const draftStatus = document.querySelector("#draft-status .status-text");

  // Zeige/Verstecke Versmaß-Reihe
  meterRow.style.display = profile.supportsMeter ? "" : "none";

  // ---------- Hilfsfunktionen ----------
  function pathText(kind, author, work, isBirkenbihl) {
    const base = `texte/${kind}/${author}/${work}`;
    return isBirkenbihl ? `${base}_birkenbihl.txt` : `${base}.txt`;
  }

  function pdfBaseDir(kind, author) {
    return kind === "poesie"
      ? `pdf/original_poesie_pdf/${author}`
      : `pdf/original_prosa_pdf/${author}`;
  }

  function currentRadio(name) {
    const el = document.querySelector(`input[name="${name}"]:checked`);
    return el ? el.value : null;
  }

  function pdfName(stem, strength, color, tags, withMeter) {
    // Beispiel: Aias_Normal_Colour_Tag[_Versmaß].pdf
    const meterPart = withMeter ? "_Versmaß" : "";
    return `${stem}_${strength}_${color}_${tags}${meterPart}.pdf`;
  }

  function setPDF(src) {
    if (!pdfObj) return;
    pdfBusy.style.display = "flex";
    pdfObj.data = ""; // reset
    // Preload via Image-Workaround geht bei PDF nicht sauber; wir setzen direkt.
    pdfObj.addEventListener(
      "load",
      () => {
        pdfBusy.style.display = "none";
      },
      { once: true }
    );
    // onerror greift bei <object> nicht immer; wir geben einfach aus.
    pdfObj.data = src;
  }

  async function fetchText(url) {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return await res.text();
  }

  // ---------- Initiale Texte laden ----------
  (async function loadTexts() {
    try {
      const origPath = pathText(profile.kind, profile.author, profile.work, false);
      const bbPath = pathText(profile.kind, profile.author, profile.work, true);

      origBox.textContent = "Lade Original…";
      bbBox.textContent = "Lade Birkenbihl…";

      const [orig, bb] = await Promise.all([
        fetchText(origPath).catch(() => "(Kein Original gefunden)"),
        fetchText(bbPath).catch(() => "(Keine Birkenbihl-Datei gefunden)")
      ]);

      origBox.textContent = orig;
      bbBox.textContent = bb;
    } catch (e) {
      origBox.textContent = "(Fehler beim Laden der Texte)";
      bbBox.textContent = "(Fehler beim Laden der Texte)";
    }
  })();

  // ---------- PDF-Kombination anwenden ----------
  function updatePDFFromControls() {
    const which = currentRadio("which") || "original"; // "original" | "draft"
    const strength = currentRadio("strength") || "Normal";
    const color = currentRadio("color") || "Colour";
    const tags = currentRadio("tags") || "Tag";
    const meterVal = currentRadio("meter") || "without";
    const withMeter = profile.supportsMeter && meterVal === "with";

    // Drafts hätten später eigenen Speicherort; hier nutzen wir weiterhin "original"
    const baseDir = pdfBaseDir(profile.kind, profile.author);
    const fileName = pdfName(profile.pdfStem, strength, color, tags, withMeter);
    const full = `${baseDir}/${fileName}`;

    setPDF(full);
    const hint = document.getElementById("pdf-hint");
    if (hint) hint.textContent = `Quelle: ${full}`;
  }

  // Initial setzen
  updatePDFFromControls();

  // ---------- Listener auf alle Radios ----------
  document.querySelectorAll('input[type="radio"]').forEach((el) => {
    el.addEventListener("change", updatePDFFromControls);
  });

  // ---------- Draft-Bedienelemente (UI-Stub wie gehabt) ----------
  document.getElementById("btn-load-draft")?.addEventListener("click", () => {
    draftSpinner.style.display = "inline-block";
    draftStatus.textContent = "lade letzten Entwurf…";
    // Hier könnt ihr ggf. AJAX an euren Server hängen. Wir stubben:
    setTimeout(() => {
      draftSpinner.style.display = "none";
      draftStatus.textContent = "bereit";
      // Keine Änderung am Editor in diesem Stub.
    }, 600);
  });

  document.getElementById("btn-generate")?.addEventListener("click", () => {
    draftSpinner.style.display = "inline-block";
    draftStatus.textContent = "PDF wird erzeugt…";
    // Hier würde man euren Adapter (serverseitig) triggern.
    setTimeout(() => {
      draftSpinner.style.display = "none";
      draftStatus.textContent = "fertig (siehe Viewer oben rechts)";
      // Optional: Nach Build könntet ihr updatePDFFromControls() erneut aufrufen.
    }, 1200);
  });
})();
