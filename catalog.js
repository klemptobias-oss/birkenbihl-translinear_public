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

// NEU: Gibt die Kategorien für eine gegebene Sprache und Gattung zurück.
// z.B. ["Epos", "Drama", "Lyrik"] für Poesie oder ["Philosophie_Rhetorik", "Historie"] für Prosa
export function listCategoriesByKind(cat, language, kind) {
  const kindNode = cat?.Sprachen?.[language]?.[kind] || {};
  return Object.keys(kindNode).sort((a, b) => a.localeCompare(b, "de"));
}

export async function getWorkEntry(language, kind, category, author, work) {
  const catalog = await loadCatalog();
  return (
    catalog.Sprachen?.[language]?.[kind]?.[category]?.[author]?.[work] || null
  );
}

// Gibt die Autoren für eine gegebene Sprache, Gattung und Kategorie zurück.
// Rückgabe-Element: { author: "Aischylos", display: "Aischylos" }
export function listAuthors(cat, language, kind, category) {
  const categoryNode = cat?.Sprachen?.[language]?.[kind]?.[category] || {};
  return Object.keys(categoryNode)
    .map((a) => ({ author: a, display: categoryNode[a].display || a })) // Annahme: display-Name ist optional
    .sort((x, y) => x.display.localeCompare(y.display, "de"));
}

// Gibt die Werke für einen gegebenen Pfad (Sprache, Gattung, Kategorie, Autor) zurück.
// Rückgabe-Element: { id: "Der_gefesselte_Prometheus", title: "Der gefesselte Prometheus", versmass: true, path: "..." }
export function listWorks(cat, language, kind, category, author) {
  const authorNode =
    cat?.Sprachen?.[language]?.[kind]?.[category]?.[author] || {};
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
export function getWorkMeta(cat, language, kind, category, author, workId) {
  const works = listWorks(cat, language, kind, category, author);
  const w = works.find((x) => x.id === workId);
  if (!w) return null;

  // Bestimme den Anzeigenamen des Autors (falls vorhanden, sonst Fallback)
  const authorNode =
    cat?.Sprachen?.[language]?.[kind]?.[category]?.[author] || {};
  const author_display = authorNode.display || author;

  return {
    language,
    kind,
    category,
    author,
    author_display,
    ...w,
  };
}
