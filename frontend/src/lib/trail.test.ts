import { test } from "node:test";
import assert from "node:assert/strict";
import { keyEvidence, parseTrail, progress } from "./trail.ts";

const ev = (id: string, acc: string, date: string, extra: Record<string, unknown> = {}) => ({
  id, acc, page: 1, line_start: 0, line_end: 1, chunk: `${acc}#0`, date, doc_type: "change request", title: null,
  stance: "reason", claim: "", quote: `quote ${id} from ${acc}`, entities: [], verified: true, suspicious: false, ...extra,
});

const events = [
  { type: "start" },
  { type: "hop_started", n: 1, kind: "recipe", label: "Recipe history" },
  { type: "hop", n: 1, kind: "recipe", label: "Recipe history", evidence: [ev("E1", "ACC-0050", "1996-01-22", { doc_type: "recipe", stance: "context" })] },
  { type: "hop_started", n: 2, kind: "origin", label: "Origin", query: "Follow reference CR-1995-009" },
  { type: "hop", n: 2, kind: "origin", label: "Origin", evidence: [
    ev("E2", "ACC-0074", "1995-12-05"),
    ev("E3", "ACC-0099", "2001-01-01", { verified: false }),
    ev("E4", "ACC-0177", "2020-01-01", { suspicious: true }),
  ] },
  { type: "hop_started", n: 3, kind: "status", label: "Dependency status" },
] as never[];

test("hops keep dig order and their own verified evidence", () => {
  const t = parseTrail(events);
  assert.deepEqual(t.hops.map((h) => [h.n, h.running]), [[1, false], [2, false], [3, true]]);
  assert.deepEqual(t.hops[1].evidence.map((e) => e.id), ["E2"]);
  assert.equal(t.hops[1].found, 3);
});

test("evidence is verified only, de-duplicated and sorted by date; injected text is reported", () => {
  const t = parseTrail([...events, events[4]]);
  assert.deepEqual(t.evidence.map((e) => e.id), ["E2", "E1"]);
  assert.deepEqual(t.ignored, ["ACC-0177"]);
});

test("key evidence keeps cited items and recipe lines once a verdict exists", () => {
  const verdict = { strength: { cited: ["E2"] } };
  const t = parseTrail([...events, { type: "verdict", verdict } as never]);
  assert.deepEqual(keyEvidence(t).map((e) => e.id), ["E2", "E1"]);
  assert.equal(progress(t), 100);
  const live = parseTrail(events);
  assert.equal(keyEvidence(live).length, 2);
  assert.equal(progress(live), 30);
});
