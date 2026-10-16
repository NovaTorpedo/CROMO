// Step search for the "Ask why" spotlight: rank plant steps against what the user typed.
// Pure functions (no React, no DOM) so they are unit-tested with `node --test`.

export interface Searchable { id: string; name: string; instruction: string; process?: string }

const norm = (s: string) => s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");
const words = (s: string) => norm(s).split(/[^a-z0-9]+/).filter(Boolean);
const STOP = new Set(["why", "do", "does", "we", "the", "a", "an", "is", "are", "of", "to", "in", "this", "step", "what", "for", "and", "it", "our", "us", "add"]);

/** Query terms that carry meaning ("why do we add ammonium chloride?" -> ["ammonium", "chloride"]). */
export function terms(query: string): string[] {
  const all = words(query);
  const kept = all.filter((w) => !STOP.has(w));
  return kept.length ? kept : all;
}

/** Score one step; 0 means "does not match". Every term must match a word prefix somewhere. */
export function score(step: Searchable, query: string): number {
  const q = query.trim();
  if (!q) return 0;
  if (norm(step.id) === norm(q)) return 1000;
  const ts = terms(q);
  if (!ts.length) return 0;
  const nameW = words(step.name);
  const instrW = words(step.instruction);
  const procW = words(step.process ?? "");
  const idW = words(step.id);
  let total = 0;
  for (const t of ts) {
    let best = 0;
    if (idW.some((w) => w === t)) best = 60;
    if (nameW.some((w) => w === t)) best = Math.max(best, 40);
    else if (nameW.some((w) => w.startsWith(t))) best = Math.max(best, 30);
    if (instrW.some((w) => w === t)) best = Math.max(best, 20);
    else if (instrW.some((w) => w.startsWith(t))) best = Math.max(best, 14);
    if (procW.some((w) => w.startsWith(t))) best = Math.max(best, 8);
    if (!best) return 0;
    total += best;
  }
  if (norm(step.name).startsWith(norm(q))) total += 25;
  return total;
}

/** Best matching steps, highest score first (ties keep the input order: the plant's process order). */
export function rank<T extends Searchable>(steps: T[], query: string, limit = 8): T[] {
  return steps
    .map((s, i) => ({ s, i, sc: score(s, query) }))
    .filter((x) => x.sc > 0)
    .sort((a, b) => b.sc - a.sc || a.i - b.i)
    .slice(0, limit)
    .map((x) => x.s);
}
