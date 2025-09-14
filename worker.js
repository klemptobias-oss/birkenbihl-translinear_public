export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // --------- CORS ---------
    const origin = request.headers.get("Origin") || "";
    const allowedList = (env.ALLOWED_ORIGIN || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const allowOrigin =
      allowedList.length === 0
        ? "*"
        : allowedList.includes(origin)
        ? origin
        : allowedList[0];

    const CORS = {
      "Access-Control-Allow-Origin": allowOrigin,
      Vary: "Origin",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "content-type",
      "Access-Control-Max-Age": "86400",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    // --------- Routen ---------
    const accepted = new Set([
      "/draft",
      "/render",
      "/api/render",
      "/generate",
      "/",
    ]);

    // Healthcheck
    if (request.method === "GET" && url.pathname === "/") {
      return new Response("OK birkenbihl-draft-01", {
        status: 200,
        headers: CORS,
      });
    }

    if (!accepted.has(url.pathname)) {
      return resp(
        { ok: false, error: "not_found", message: "Unknown route" },
        404,
        CORS
      );
    }
    if (request.method !== "POST") {
      return resp({ ok: false, error: "method_not_allowed" }, 405, CORS);
    }

    // --------- Payload lesen (JSON | text/plain | multipart/form-data) ---------
    let text = "";
    let work = "";
    let filename = "";
    let kind = "";
    let author = "";

    try {
      const ct = (request.headers.get("content-type") || "").toLowerCase();

      if (ct.includes("application/json")) {
        const data = await request.json();
        text = (data.text ?? "").toString();
        work = (data.work ?? "").toString().trim();
        filename = (data.filename ?? "").toString().trim();
        kind = (data.kind ?? "").toString().trim();
        author = (data.author ?? "").toString().trim();
      } else if (ct.includes("text/plain")) {
        text = await request.text();
        // optional: work/filename können via Queryparam kommen
        work = (url.searchParams.get("work") || "").trim();
        filename = (url.searchParams.get("filename") || "").trim();
        kind = (url.searchParams.get("kind") || "").trim();
        author = (url.searchParams.get("author") || "").trim();
      } else if (ct.includes("multipart/form-data")) {
        const form = await request.formData();
        // text kann als Textfeld oder als Datei kommen
        if (form.has("text")) {
          text = (form.get("text") || "").toString();
        } else if (form.has("file")) {
          const file = form.get("file");
          if (file && typeof file.text === "function") {
            text = await file.text();
            filename = file.name || filename;
          }
        }
        work = (form.get("work") || "").toString().trim();
        filename = (form.get("filename") || "").toString().trim();
        kind = (form.get("kind") || "").toString().trim();
        author = (form.get("author") || "").toString().trim();
      } else {
        // Fallback: versuchen als JSON
        const data = await request.json();
        text = (data.text ?? "").toString();
        work = (data.work ?? "").toString().trim();
        filename = (data.filename ?? "").toString().trim();
        kind = (data.kind ?? "").toString().trim();
        author = (data.author ?? "").toString().trim();
      }
    } catch (e) {
      return resp(
        {
          ok: false,
          error: "invalid_payload",
          message: "Payload could not be parsed",
        },
        400,
        CORS
      );
    }

    // --------- Validierung & Normalisierung ---------
    // Minimaler Schutz gegen zu große Texte (anpassbar)
    const BYTE_LIMIT = 1 * 1024 * 1024; // 1 MiB
    const textBytes = new TextEncoder().encode(text || "");
    if (!text) {
      return resp(
        { ok: false, error: "empty_text", message: "No text provided" },
        400,
        CORS
      );
    }
    if (textBytes.length > BYTE_LIMIT) {
      return resp(
        {
          ok: false,
          error: "too_large",
          message: `Text exceeds ${BYTE_LIMIT} bytes`,
        },
        413,
        CORS
      );
    }

    // Dateinamen-Strategie:
    // 1) bevorzugt 'filename' wenn .txt, sonst
    // 2) 'work' als Basis, sonst
    // 3) "Entwurf"
    let baseName =
      filename && filename.endsWith(".txt")
        ? stripUnsafe(filename.replace(/\.txt$/i, ""))
        : "";
    if (!baseName) baseName = stripUnsafe(work) || "Entwurf";

    // Endgültiger Name (zeitgestempelt, Kollisionen vermeiden)
    const stamped = `${baseName}_birkenbihl_DRAFT_${tsStamp()}.txt`;

    // Erstelle den korrekten Pfad basierend auf kind, author und work
    // Fallback falls Parameter fehlen
    const kindSafe = kind || "prosa"; // Standard zu prosa falls nicht angegeben
    const authorSafe = stripUnsafe(author) || "Unsortiert";
    const workSafe = stripUnsafe(work) || "Unbenannt";

    // Pfad: texte_drafts/{kind}_drafts/{author}/{work}/{filename}
    const path = `texte_drafts/${kindSafe}_drafts/${authorSafe}/${workSafe}/${stamped}`;

    // --------- GitHub API: Datei anlegen ---------
    const owner = env.OWNER;
    const repo = env.REPO;
    const branch = env.BRANCH || "main";
    const token = env.GITHUB_TOKEN;

    if (!owner || !repo || !token) {
      console.log("Missing environment variables:", {
        owner: !!owner,
        repo: !!repo,
        token: !!token,
      });
      return resp(
        {
          ok: false,
          error: "misconfigured",
          message: "OWNER/REPO/GITHUB_TOKEN missing",
        },
        500,
        CORS
      );
    }

    const apiUrl = `https://api.github.com/repos/${owner}/${repo}/contents/${encodeURI(
      path
    )}`;
    const body = {
      message: `draft: ${baseName} birkenbihl (${stamped})`,
      content: toBase64Utf8(text),
      branch,
    };

    const gh = await fetch(apiUrl, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "birkenbihl-worker/1.0",
      },
      body: JSON.stringify(body),
    });

    if (!gh.ok) {
      const errTxt = await gh.text().catch(() => "");
      return resp(
        {
          ok: false,
          error: "github_error",
          status: gh.status,
          details: errTxt.slice(0, 2000),
        },
        502,
        CORS
      );
    }

    const res = await gh.json();

    // GitHub Action wird automatisch durch den Push-Event ausgelöst
    // da die Action auf Push-Events in texte_drafts reagiert
    console.log("Draft gespeichert, GitHub Action wird automatisch ausgelöst");

    return resp(
      {
        ok: true,
        path,
        filename: stamped,
        size_bytes: textBytes.length,
        html_url: res.content?.html_url || null,
        workflow_triggered: true,
        message:
          "Text gespeichert und PDF-Generierung automatisch gestartet. PDFs werden in wenigen Minuten verfügbar sein.",
      },
      200,
      CORS
    );
  },
}; // <- WICHTIG: export-default Block wird hier geschlossen!

// ---------- Hilfsfunktionen ----------
function resp(obj, status = 200, headers = {}) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...headers },
  });
}

function tsStamp(d = new Date()) {
  const p = (n) => n.toString().padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(
    d.getHours()
  )}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

// Entfernt problematische Zeichen aus Dateinamenbasis
function stripUnsafe(s = "") {
  if (!s) return "";
  // erlaubt Buchstaben, Ziffern, Leerraum, Unterstrich, Minus, Punkt
  let cleaned = s.replace(/[^A-Za-z0-9 _.\-]/g, " ").trim();
  // stauche Mehrfach-Leerzeichen und ersetze sie durch Unterstriche
  cleaned = cleaned.replace(/\s+/g, "_");
  return cleaned.slice(0, 64) || "";
}

// RFC4648-Base64 ohne Zeilenumbrüche, UTF-8-sicher
function toBase64Utf8(str) {
  const bytes = new TextEncoder().encode(str || "");
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin);
}
