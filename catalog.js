// catalog.js – minimale Katalog-API für Start- und Werkseiten
// Nutzung: import { loadCatalog, listKinds, listAuthorsByKind, listWorks, getWorkMeta } from './catalog.js';

let _cache = null;

export async function loadCatalog() {
  if (_cache) return _cache;
  const res = await fetch('./catalog.json', { cache: 'no-store' });
  if (!res.ok) throw new Error('catalog.json konnte nicht geladen werden');
  _cache = await res.json();
  return _cache;
}

// "poesie" | "prosa"
export function listKinds(cat) {
  return Object.keys(cat);
}

// Autorenobjekte je Kind, sortiert nach display
// Rückgabe-Element: { author: "Aischylos", display: "Aischylos" }
export function listAuthorsByKind(cat, kind) {
  const node = cat[kind] || {};
  return Object.keys(node)
    .map(a => ({ author: a, display: node[a].display || a }))
    .sort((x, y) => x.display.localeCompare(y.display, 'de'));
}

// Werke je (kind, author), sortiert nach title
// Rückgabe-Element: { id: "Der_gefesselte_Prometheus", title: "...", meter_capable: true|false }
export function listWorks(cat, kind, author) {
  const a = cat[kind]?.[author];
  if (!a) return [];
  return (a.works || []).slice().sort((x, y) => x.title.localeCompare(y.title, 'de'));
}

// Vollständige Metadaten eines Werks
export function getWorkMeta(cat, kind, author, workId) {
  const works = listWorks(cat, kind, author);
  const w = works.find(x => x.id === workId);
  if (!w) return null;
  return {
    kind,
    author,
    author_display: cat[kind]?.[author]?.display || author,
    ...w
  };
}

// Hilfsfunktion: Dateipfade zu den .txts gemäß unserer Ordnerkonvention
// - Original:   texte/<kind>/<author>/<work>.txt
// - Birkenbihl: texte/<kind>/<author>/<work>_birkenbihl.txt
export function txtPaths(kind, author, workId) {
  const base = `texte/${kind}/${author}/${workId}`;
  return {
    original: `${base}.txt`,
    birkenbihl: `${base}_birkenbihl.txt`
  };
}
