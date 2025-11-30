export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const method = request.method.toUpperCase();

    // --------- CORS ---------
    const origin = request.headers.get("Origin") || "";
    const allowedList = (env.ALLOWED_ORIGIN || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    // WICHTIG: Bei credentials: 'include' darf KEIN Wildcard (*) verwendet werden!
    // Verwende immer den spezifischen Origin (wenn in allowedList oder leer)
    const allowOrigin =
      allowedList.length === 0
        ? origin || "*" // Fallback auf Origin, nur wenn leer dann *
        : allowedList.includes(origin)
        ? origin
        : allowedList[0];

    const CORS = {
      "Access-Control-Allow-Origin": allowOrigin,
      "Access-Control-Allow-Credentials": "true", // KRITISCH: Für Cookies!
      Vary: "Origin",
      "Access-Control-Allow-Methods": "GET, HEAD, POST, OPTIONS",
      "Access-Control-Allow-Headers": "content-type",
      "Access-Control-Max-Age": "86400",
    };

    // --------- OPTIONS / Preflight ---------
    if (method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    // --------- Healthcheck ---------
    if ((method === "GET" || method === "HEAD") && url.pathname === "/") {
      return new Response("OK antike-translinear-draft", {
        status: 200,
        headers: CORS,
      });
    }

    // --------- Release-Proxy (GET/HEAD) ---------
    if (
      (method === "GET" || method === "HEAD") &&
      url.pathname === "/release"
    ) {
      const tag = (url.searchParams.get("tag") || "").trim();
      const file = (url.searchParams.get("file") || "").trim();
      const modeRaw = (url.searchParams.get("mode") || "inline").toLowerCase();
      const mode = modeRaw === "attachment" ? "attachment" : "inline";
      const isDraft = url.searchParams.get("draft") === "true";

      // Für Draft-PDFs: Verwende raw.githubusercontent.com statt GitHub Releases
      if (isDraft) {
        if (!file) {
          return resp(
            {
              ok: false,
              error: "missing_params",
              message: "Query parameter 'file' is required for draft PDFs.",
            },
            400,
            CORS
          );
        }

        const owner = env.OWNER;
        const repo = env.REPO;
        if (!owner || !repo) {
          return resp(
            {
              ok: false,
              error: "misconfigured",
              message: "OWNER/REPO missing for draft proxy",
            },
            500,
            CORS
          );
        }

        // Draft-PDFs sind auf raw.githubusercontent.com/OWNER/REPO/main/pdf_drafts/...
        const draftUrl = `https://raw.githubusercontent.com/${owner}/${repo}/main/pdf_drafts/${file}`;
        const upstream = await fetch(draftUrl, {
          method: method === "HEAD" ? "HEAD" : "GET",
        });

        if (!upstream || !upstream.ok) {
          return resp(
            {
              ok: false,
              error: "upstream_error",
              status: upstream?.status || 404,
              message: `GitHub raw responded with ${upstream?.status || 404}`,
              url: draftUrl,
            },
            upstream?.status || 404,
            CORS
          );
        }

        // Content-Type für PDFs setzen
        let contentType = upstream.headers.get("content-type") || "";
        if (!contentType || contentType === "application/octet-stream") {
          if (file.toLowerCase().endsWith(".pdf")) {
            contentType = "application/pdf";
          } else if (file.toLowerCase().endsWith(".txt")) {
            contentType = "text/plain; charset=utf-8";
          }
        }

        // Content-Disposition Header für Download-Namen
        const baseName = file.split("/").pop() || "translinear.pdf";
        const disposition =
          mode === "attachment"
            ? `attachment; filename="${baseName}"`
            : `inline; filename="${baseName}"`;

        const headers = {
          ...CORS,
          "Content-Type": contentType,
          "Content-Disposition": disposition,
        };

        // WICHTIG: Content-Length vom Upstream kopieren, damit Browser die Dateigröße kennt
        const contentLength = upstream.headers.get("content-length");
        if (contentLength) {
          headers["Content-Length"] = contentLength;
        }

        if (method === "HEAD") {
          return new Response(null, { status: 200, headers });
        }

        return new Response(upstream.body, { status: 200, headers });
      }

      // Original Release-Proxy-Logik (für nicht-Draft PDFs)
      if (!tag || !file) {
        return resp(
          {
            ok: false,
            error: "missing_params",
            message: "Query parameters 'tag' and 'file' are required.",
          },
          400,
          CORS
        );
      }

      const owner = env.OWNER;
      const repo = env.REPO;
      if (!owner || !repo) {
        return resp(
          {
            ok: false,
            error: "misconfigured",
            message: "OWNER/REPO missing for release proxy",
          },
          500,
          CORS
        );
      }

      const filenameVariants = buildReleaseFilenameVariants(file);
      let upstream = null;
      let finalFileName = file;
      let lastStatus = 404;

      for (const candidate of filenameVariants) {
        const upstreamUrl = `https://github.com/${owner}/${repo}/releases/download/${encodeURIComponent(
          tag
        )}/${encodeURIComponent(candidate)}`;
        const attempt = await fetch(upstreamUrl, {
          method: method === "HEAD" ? "HEAD" : "GET",
        });
        if (attempt && attempt.ok) {
          upstream = attempt;
          finalFileName = candidate;
          break;
        }
        lastStatus = attempt?.status || 404;
      }

      if (!upstream || !upstream.ok) {
        return resp(
          {
            ok: false,
            error: "upstream_error",
            status: lastStatus,
            message: `GitHub responded with ${lastStatus}`,
            attempted: filenameVariants,
          },
          lastStatus,
          CORS
        );
      }

      // Content-Type sauber setzen:
      // - GitHub gibt für Release-Assets meist application/octet-stream zurück
      // - für *.pdf wollen wir explizit application/pdf,
      //   damit der Browser den eingebauten PDF-Viewer nutzt.
      let contentType = upstream.headers.get("content-type") || "";
      const lowerFile = finalFileName.toLowerCase();

      if (!contentType || contentType === "application/octet-stream") {
        if (lowerFile.endsWith(".pdf")) {
          contentType = "application/pdf";
        } else if (lowerFile.endsWith(".txt")) {
          contentType = "text/plain; charset=utf-8";
        } else {
          contentType = "application/octet-stream";
        }
      }

      const headers = new Headers({
        ...CORS,
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=3600",
      });

      // WICHTIG: Content-Length vom Upstream kopieren, damit Browser die Dateigröße kennt
      const contentLength = upstream.headers.get("content-length");
      if (contentLength) {
        headers.set("Content-Length", contentLength);
      }

      let desiredName = "";
      if (lowerFile.endsWith(".pdf")) {
        desiredName = "translinear.pdf";
      } else if (lowerFile.endsWith(".txt")) {
        desiredName = "translinear.txt";
      } else {
        desiredName = finalFileName;
      }

      if (desiredName) {
        const dispositionType = mode === "attachment" ? "attachment" : "inline";
        headers.set(
          "Content-Disposition",
          `${dispositionType}; filename="${desiredName}"`
        );
      }

      if (method === "HEAD") {
        return new Response(null, {
          status: upstream.status,
          headers,
        });
      }

      return new Response(upstream.body, {
        status: upstream.status,
        headers,
      });
    }

    // --------- Ab hier nur noch POST-basierte Draft-API ---------
    if (method !== "POST") {
      return resp(
        { ok: false, error: "method_not_allowed", message: "Use POST here." },
        405,
        CORS
      );
    }

    // --------- Payload lesen (JSON | text/plain | multipart/form-data) ---------
    let text = "";
    let work = "";
    let filename = "";
    let kind = "";
    let author = "";
    let language = "";
    let category = "";
    let workPath = "";
    let tagConfig = null;
    let releaseBase = "";
    let versmassFlag = "";
    let meterMode = "";
    let hidePipes = false;

    try {
      const ct = (request.headers.get("content-type") || "").toLowerCase();

      if (ct.includes("application/json")) {
        const data = await request.json();
        text = (data.text ?? "").toString();
        work = (data.work ?? "").toString().trim();
        filename = (data.filename ?? "").toString().trim();
        kind = (data.kind ?? "").toString().trim();
        author = (data.author ?? "").toString().trim();
        tagConfig = data.tag_config || null;
        language = (data.language ?? "").toString().trim();
        category = (data.category ?? "").toString().trim();
        workPath = (data.work_path ?? "").toString().trim();
        releaseBase = sanitizeReleaseBase(data.release_base);
        versmassFlag = (data.versmass ?? "").toString().trim();
        meterMode = (data.meter_mode ?? "").toString().trim();
        hidePipes = data.hide_pipes === true || data.hide_pipes === "true";
      } else if (ct.includes("text/plain")) {
        text = await request.text();
        work = (url.searchParams.get("work") || "").trim();
        filename = (url.searchParams.get("filename") || "").trim();
        kind = (url.searchParams.get("kind") || "").trim();
        author = (url.searchParams.get("author") || "").trim();
        language = (url.searchParams.get("language") || "").trim();
        category = (url.searchParams.get("category") || "").trim();
        workPath = (url.searchParams.get("work_path") || "").trim();
        releaseBase = sanitizeReleaseBase(url.searchParams.get("release_base"));
        versmassFlag = (url.searchParams.get("versmass") || "").trim();
        meterMode = (url.searchParams.get("meter_mode") || "").trim();
        hidePipes = url.searchParams.get("hide_pipes") === "true";
      } else if (ct.includes("multipart/form-data")) {
        const form = await request.formData();
        if (form.has("text")) {
          text = (form.get("text") || "").toString();
        } else if (form.has("file")) {
          const upFile = form.get("file");
          if (upFile && typeof upFile.text === "function") {
            text = await upFile.text();
            filename = upFile.name || filename;
          }
        }
        work = (form.get("work") || "").toString().trim();
        filename = (form.get("filename") || "").toString().trim();
        kind = (form.get("kind") || "").toString().trim();
        author = (form.get("author") || "").toString().trim();
        language = (form.get("language") || "").toString().trim();
        category = (form.get("category") || "").toString().trim();
        workPath = (form.get("work_path") || "").toString().trim();
        releaseBase = sanitizeReleaseBase(form.get("release_base"));
        versmassFlag = (form.get("versmass") || "").toString().trim();
        meterMode = (form.get("meter_mode") || "").toString().trim();
        hidePipes = form.get("hide_pipes") === "true";

        const tagConfigStr = form.get("tag_config");
        if (tagConfigStr) {
          try {
            tagConfig = JSON.parse(tagConfigStr.toString());
          } catch (e) {
            console.log("Fehler beim Parsen der Tag-Konfiguration:", e.message);
            tagConfig = null;
          }
        }
      } else {
        const data = await request.json();
        text = (data.text ?? "").toString();
        work = (data.work ?? "").toString().trim();
        filename = (data.filename ?? "").toString().trim();
        kind = (data.kind ?? "").toString().trim();
        author = (data.author ?? "").toString().trim();
        language = (data.language ?? "").toString().trim();
        category = (data.category ?? "").toString().trim();
        workPath = (data.work_path ?? "").toString().trim();
        releaseBase = sanitizeReleaseBase(data.release_base);
        versmassFlag = (data.versmass ?? "").toString().trim();
        meterMode = (data.meter_mode ?? "").toString().trim();
        hidePipes = data.hide_pipes === true || data.hide_pipes === "true";
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

    // Dateinamen-Strategie
    let baseName =
      filename && filename.endsWith(".txt")
        ? stripUnsafe(filename.replace(/\.txt$/i, ""))
        : "";
    if (!baseName) baseName = stripUnsafe(work) || "Entwurf";

    // Normalisiere Versmaß-Varianten zu "Versmass" (URL-sicher)
    baseName = baseName.replace(
      /_[Vv]ersm[aä][sß]{1,2}[a-zßA-Z]*/g,
      "_Versmass"
    );

    // Entferne "translinear" aus dem baseName, falls vorhanden (wird später wieder hinzugefügt)
    baseName = baseName
      .replace(/^translinear_?/i, "")
      .replace(/_translinear_?/gi, "_");
    if (!baseName) baseName = stripUnsafe(work) || "Entwurf";

    // WICHTIG: SESSION-ID aus Cookie lesen (oder generieren)
    // Format: SESSION_abc123def456 (16-stellige Hex-ID)
    const cookieHeader = request.headers.get("Cookie") || "";
    let sessionId = null;
    const sessionMatch = cookieHeader.match(
      /birkenbihl_session=([a-f0-9]{16})/
    );
    if (sessionMatch) {
      sessionId = sessionMatch[1];
    } else {
      // Neue Session generieren (16 hex chars = 64 bits Zufälligkeit)
      sessionId = Array.from({ length: 16 }, () =>
        Math.floor(Math.random() * 16).toString(16)
      ).join("");
    }

    const stamped = `${baseName}_translinear_SESSION_${sessionId}_DRAFT_${tsStamp()}.txt`;

    const kindSafe = sanitizePathSegment(kind) || "prosa";
    const authorSafe = sanitizePathSegment(author) || "Unsortiert";
    const workSafe = sanitizePathSegment(work) || "Unbenannt";
    const languageSafe =
      sanitizePathSegment(language) || stateLangFallback(kindSafe);
    const categorySafe = sanitizePathSegment(category);

    const providedWorkPathSegments = sanitizeWorkPath(workPath);
    const inferredSegments =
      providedWorkPathSegments.length >= 2
        ? providedWorkPathSegments
        : [
            languageSafe,
            kindSafe,
            ...(categorySafe ? [categorySafe] : []),
            authorSafe,
            workSafe,
          ];

    const path = ["texte_drafts", ...inferredSegments, stamped].join("/");

    let textWithConfig = text;
    const metadataHeaders = [];
    if (releaseBase) {
      metadataHeaders.push(`<!-- RELEASE_BASE:${releaseBase} -->`);
    }
    if (tagConfig) {
      metadataHeaders.push(`<!-- TAG_CONFIG:${JSON.stringify(tagConfig)} -->`);
      console.log("Tag-Konfiguration eingebettet:", Object.keys(tagConfig));
    }
    if (versmassFlag) {
      metadataHeaders.push(`<!-- VERSMASS:${versmassFlag} -->`);
    }
    if (meterMode) {
      metadataHeaders.push(`<!-- METER_MODE:${meterMode} -->`);
    }
    if (hidePipes) {
      metadataHeaders.push(`<!-- HIDE_PIPES:true -->`);
    }
    if (metadataHeaders.length) {
      textWithConfig = metadataHeaders.join("\n") + "\n" + text;
    }

    // --------- GitHub API: Datei anlegen ---------
    const owner = env.OWNER;
    const repo = env.REPO;
    const branch = env.BRANCH || "main";
    const token = env.GITHUB_PAT;

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
          message: "OWNER/REPO/GITHUB_PAT missing",
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
      content: toBase64Utf8(textWithConfig),
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

    console.log("Draft gespeichert, triggere GitHub Action für diese Datei...");

    // Trigger workflow_dispatch explizit für DIESE draft_file
    const workflowDispatchUrl = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/build-drafts.yml/dispatches`;
    const dispatchPayload = {
      ref: branch,
      inputs: {
        draft_file: path, // Nur diese Datei verarbeiten!
      },
    };

    console.log("workflow_dispatch URL:", workflowDispatchUrl);
    console.log(
      "workflow_dispatch payload:",
      JSON.stringify(dispatchPayload, null, 2)
    );

    const dispatchRes = await fetch(workflowDispatchUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "birkenbihl-worker/1.0",
      },
      body: JSON.stringify(dispatchPayload),
    });

    console.log("workflow_dispatch response status:", dispatchRes.status);

    let errorDetails = null;
    if (!dispatchRes.ok) {
      const errText = await dispatchRes.text().catch(() => "");
      errorDetails = `Status ${dispatchRes.status}: ${errText}`;
      console.error(`workflow_dispatch fehlgeschlagen:`, errorDetails);
    } else {
      console.log("workflow_dispatch erfolgreich getriggert für", path);
    }

    return resp(
      {
        ok: true,
        path,
        filename: stamped,
        size_bytes: textBytes.length,
        html_url: res.content?.html_url || null,
        workflow_triggered: dispatchRes.ok, // Nur true wenn Workflow erfolgreich getriggert
        workflow_error: errorDetails, // Detaillierter Fehler
        message: dispatchRes.ok
          ? "Text gespeichert und PDF-Generierung automatisch gestartet. PDFs werden in wenigen Minuten verfügbar sein."
          : `Text gespeichert, aber PDF-Generierung fehlgeschlagen: ${errorDetails}`,
        release_base: releaseBase || null,
        session_id: sessionId, // Session-ID zurückgeben
      },
      200,
      {
        ...CORS,
        "Set-Cookie": `birkenbihl_session=${sessionId}; Path=/; Max-Age=86400; SameSite=Lax; Secure`, // 24h Cookie
      }
    );
  },
};

// ---------- Hilfsfunktionen ----------
function resp(obj, status = 200, headers = {}) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...headers },
  });
}

function buildReleaseFilenameVariants(file) {
  const variants = [file];
  const umlautVariant = replaceGermanUmlauts(file);
  if (umlautVariant && umlautVariant !== file) variants.push(umlautVariant);
  const plainVariant = stripDiacritics(file);
  if (plainVariant && !variants.includes(plainVariant))
    variants.push(plainVariant);
  return [...new Set(variants)];
}

function replaceGermanUmlauts(str = "") {
  return str
    .replace(/Ä/g, "Ae")
    .replace(/ä/g, "ae")
    .replace(/Ö/g, "Oe")
    .replace(/ö/g, "oe")
    .replace(/Ü/g, "Ue")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss");
}

function stripDiacritics(str = "") {
  if (typeof str.normalize !== "function") return str;
  return str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function sanitizeReleaseBase(value) {
  if (!value) return "";
  let cleaned = value
    .toString()
    .replace(/[\r\n]/g, "")
    .trim();
  // Normalisiere Versmaß-Varianten zu "Versmass" (URL-sicher)
  cleaned = cleaned.replace(/_[Vv]ersm[aä][sß]{1,2}[a-zßA-Z]*/g, "_Versmass");
  if (cleaned && !cleaned.includes("_birkenbihl")) {
    cleaned += "_birkenbihl";
  }
  return cleaned;
}

function sanitizePathSegment(segment = "") {
  if (!segment) return "";
  let cleaned = segment
    .toString()
    .trim()
    .replace(/[\x00-\x1F<>:"|?*]/g, "_")
    .replace(/[\\]/g, "_")
    .replace(/\s+/g, "_")
    .replace(/\//g, "_");
  if (cleaned === "." || cleaned === "..") return "";
  return cleaned;
}

function sanitizeWorkPath(path = "") {
  if (!path) return [];
  return path
    .split("/")
    .map((seg) => sanitizePathSegment(seg))
    .filter(Boolean);
}

function stateLangFallback(kindSafe = "prosa") {
  if (kindSafe === "poesie") return "griechisch";
  if (kindSafe === "prosa") return "griechisch";
  return "griechisch";
}

function tsStamp(d = new Date()) {
  const p = (n) => n.toString().padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(
    d.getHours()
  )}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

function stripUnsafe(s = "") {
  if (!s) return "";
  const normalized = typeof s.normalize === "function" ? s.normalize("NFC") : s;
  let cleaned = normalized.replace(/[^\p{L}\p{N} _.\-]/gu, " ").trim();
  cleaned = cleaned.replace(/\s+/g, "_");
  return cleaned.slice(0, 64) || "";
}

function toBase64Utf8(str) {
  const bytes = new TextEncoder().encode(str || "");
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin);
}
