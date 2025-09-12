// catalog.js
// Lädt den Katalog und bietet kleine Helfer.

export async function loadCatalog() {
  const res = await fetch('catalog.json', { cache: 'no-store' });
  if (!res.ok) throw new Error('Katalog konnte nicht geladen werden.');
  const json = await res.json();
  return json;
}

export function findAuthorEntry(cat, kind, author) {
  return cat.entries.find(e => e.kind === kind && e.author === author) || null;
}

export function findWork(cat, kind, author, workId) {
  const a = findAuthorEntry(cat, kind, author);
  if (!a) return null;
  return a.works.find(w => w.id === workId) || null;
}

export function listKinds(cat) {
  // Nur die im Katalog vorhandenen Arten zurückgeben (Stabil gegen Tippfehler)
  const ks = new Set(cat.entries.map(e => e.kind));
  return Array.from(ks);
}

export function listAuthorsByKind(cat, kind) {
  return cat.entries
    .filter(e => e.kind === kind)
    .map(e => ({ author: e.author, display: e.author_display }));
}

export function listWorks(cat, kind, author) {
  const a = findAuthorEntry(cat, kind, author);
  return a ? a.works.slice() : [];
}
