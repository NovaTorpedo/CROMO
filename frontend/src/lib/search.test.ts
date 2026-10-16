import { test } from "node:test";
import assert from "node:assert/strict";
import { rank, score, terms } from "./search.ts";

const steps = [
  { id: "ALK-01", name: "Alkyd resin charge", instruction: "Charge 420 kg alkyd resin AR-55 to disperser D-2.", process: "AF-12" },
  { id: "ALK-04", name: "Ammonium chloride", instruction: "Add 1.6 kg ammonium chloride (RM-118) pre-dissolved in 4 L water; stir 10 min.", process: "AF-12" },
  { id: "SOL-02", name: "Bond and earth", instruction: "Bond and earth the drum before transferring solvent.", process: "SOP-07" },
  { id: "EPX-02", name: "Hot-box pre-heat", instruction: "Pre-heat the resin drums in hot box HB-1 at 50 °C for 12 h.", process: "EF-210" },
];

test("question words are dropped from the query", () => {
  assert.deepEqual(terms("Why do we add ammonium chloride?"), ["ammonium", "chloride"]);
  assert.deepEqual(terms("why"), ["why"]);
});

test("a natural question finds the step", () => {
  assert.equal(rank(steps, "why do we add ammonium chloride?")[0].id, "ALK-04");
  assert.equal(rank(steps, "earthing")[0]?.id, undefined); // prefix of a word only: "earthing" is not in the text
  assert.equal(rank(steps, "earth")[0].id, "SOL-02");
});

test("step ids match exactly and rank first", () => {
  assert.equal(score(steps[3], "epx-02"), 1000);
  assert.equal(rank(steps, "EPX-02")[0].id, "EPX-02");
});

test("every term must match; prefixes count", () => {
  assert.equal(rank(steps, "ammonium sulphate").length, 0);
  assert.equal(rank(steps, "hot pre")[0].id, "EPX-02");
});

test("process codes help but name matches rank higher", () => {
  const r = rank(steps, "resin");
  assert.equal(r[0].id, "ALK-01");
  assert.ok(r.some((s) => s.id === "EPX-02"));
});
