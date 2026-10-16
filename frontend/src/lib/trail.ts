// Turn an investigation's event stream into what the Why-Trail shows: hops (in dig order, each with the evidence
// it found), the verified key evidence (by date), the verdict, and warnings. Pure, so it is unit-tested.
import type { Evidence, InvEvent, VerdictData } from "../types";

export interface Hop {
  n: number;
  kind: string;
  label: string;
  query?: string | null;
  detail?: string;
  documents?: string[];
  found: number;
  running: boolean;
  evidence: Evidence[];
  compare?: { a: string; b: string } | null;
}

export interface Trail {
  hops: Hop[];
  evidence: Evidence[];
  verdict: VerdictData | null;
  concluding: boolean;
  meta: InvEvent | null;
  ignored: string[];
  warnings: string[];
}

const key = (e: Evidence) => `${e.acc}|${e.quote.slice(0, 60)}`;

export function parseTrail(events: InvEvent[]): Trail {
  const hops: Hop[] = [];
  const evidence: Evidence[] = [];
  const seen = new Set<string>();
  let verdict: VerdictData | null = null;
  let concluding = false;
  let meta: InvEvent | null = null;
  const ignored = new Set<string>();
  const warnings: string[] = [];
  for (const ev of events) {
    if (ev.type === "start" || ev.type === "replay") meta = { ...(meta ?? {}), ...ev };
    else if (ev.type === "hop_started") {
      if (!hops.some((h) => h.n === ev.n))
        hops.push({ n: ev.n!, kind: ev.kind!, label: ev.label!, query: ev.query, documents: ev.documents, found: 0, running: true, evidence: [] });
    } else if (ev.type === "hop") {
      const items = ev.evidence ?? [];
      const own: Evidence[] = [];
      (ev.ignored_injection ?? []).forEach((a) => ignored.add(a));
      for (const e of items) {
        if (e.suspicious) {
          ignored.add(e.acc);
          continue;
        }
        if (!e.verified) continue;
        own.push(e);
        if (!seen.has(key(e))) {
          seen.add(key(e));
          evidence.push(e);
        }
      }
      const h: Hop = {
        n: ev.n!, kind: ev.kind!, label: ev.label!, query: ev.query, detail: ev.detail, documents: ev.documents, found: items.length,
        running: false, evidence: own, compare: (ev as unknown as { compare?: { a: string; b: string } }).compare ?? null,
      };
      const i = hops.findIndex((x) => x.n === ev.n);
      if (i >= 0) hops[i] = h;
      else hops.push(h);
    } else if (ev.type === "concluding") concluding = true;
    else if (ev.type === "verdict") {
      verdict = ev.verdict ?? null;
      concluding = false;
    } else if (ev.type === "warning" || ev.type === "error") warnings.push(ev.message ?? "");
  }
  hops.sort((a, b) => a.n - b.n);
  evidence.sort((a, b) => (a.date ?? "9999").localeCompare(b.date ?? "9999"));
  return { hops, evidence, verdict, concluding, meta, ignored: [...ignored], warnings };
}

/** Evidence the verdict relies on (cited), plus recipe context lines; everything when there is no verdict yet. */
export function keyEvidence(t: Trail): Evidence[] {
  if (!t.verdict) return t.evidence;
  const cited = new Set(t.verdict.strength.cited);
  return t.evidence.filter((e) => cited.has(e.id) || e.doc_type === "recipe");
}

/** Progress of a live dig, 0-100 (the scheduler runs at most `expected` hops, then concludes). */
export function progress(t: Trail, expected = 9): number {
  if (t.verdict) return 100;
  return Math.min(95, Math.round((t.hops.length / expected) * 90) + (t.concluding ? 5 : 0));
}
