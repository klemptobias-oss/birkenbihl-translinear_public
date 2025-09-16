// catalog.js – API zur Navigation durch die hierarchische Werk-Datenbank (catalog.json)
// Nutzung: import { loadCatalog, ... } from './catalog.js';

let _cache = null;

export async function loadCatalog() {
  if (_cache) return _cache;
  const res = await fetch("./catalog.json", { cache: "no-store" });
  if (!res.ok) throw new Error("catalog.json konnte nicht geladen werden");
  _cache = await res.json();
  return _cache;
}

// Gibt alle verfügbaren Sprachen zurück.
// z.B. ["Griechisch", "Latein"]
export function listLanguages(cat) {
  return Object.keys(cat?.Sprachen || {});
}

// Gibt die Gattungen für eine gegebene Sprache zurück.
// z.B. ["Poesie", "Prosa"]
export function listKindsByLanguage(cat, language) {
  const langNode = cat?.Sprachen?.[language] || {};
  return Object.keys(langNode);
}

// Gibt die Autoren für eine gegebene Sprache und Gattung zurück.
// Rückgabe-Element: { author: "Aischylos", display: "Aischylos" }
export function listAuthors(cat, language, kind) {
  const kindNode = cat?.Sprachen?.[language]?.[kind] || {};
  return Object.keys(kindNode)
    .map((a) => ({ author: a, display: kindNode[a].display || a })) // Annahme: display-Name ist optional
    .sort((x, y) => x.display.localeCompare(y.display, "de"));
}

// Gibt die Werke für einen gegebenen Pfad (Sprache, Gattung, Autor) zurück.
// Rückgabe-Element: { id: "Der_gefesselte_Prometheus", title: "Der gefesselte Prometheus", versmass: true, path: "..." }
export function listWorks(cat, language, kind, author) {
  const authorNode = cat?.Sprachen?.[language]?.[kind]?.[author] || {};
  return Object.keys(authorNode)
    .map((workId) => {
      const workData = authorNode[workId];
      return {
        id: workId,
        title: workId.replace(/_/g, " "), // Erzeuge einen lesbaren Titel aus der ID
        ...workData, // Enthält "path" und "versmass"
      };
    })
    .sort((x, y) => x.title.localeCompare(y.title, "de"));
}

// Ruft die vollständigen Metadaten eines Werks ab.
export function getWorkMeta(cat, language, kind, author, workId) {
  const works = listWorks(cat, language, kind, author);
  const w = works.find((x) => x.id === workId);
  if (!w) return null;

  // Bestimme den Anzeigenamen des Autors (falls vorhanden, sonst Fallback)
  const authorNode = cat?.Sprachen?.[language]?.[kind]?.[author] || {};
  const author_display = authorNode.display || author;

  return {
    language,
    kind,
    author,
    author_display,
    ...w,
  };
}
