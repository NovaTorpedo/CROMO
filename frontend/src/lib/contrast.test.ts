// WCAG 2.1 contrast of the design tokens in styles.css (light and dark), measured on the surfaces they are used on.
// Translucent surfaces are composited over the page background first (worst case: no ambient tint).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../styles.css", import.meta.url), "utf8");
const block = (sel: string) => css.slice(css.indexOf(sel + " {"), css.indexOf("\n}", css.indexOf(sel + " {")));
const vars = (b: string) => Object.fromEntries([...b.matchAll(/--([\w-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]));
const light = vars(block(":root"));
const dark = { ...light, ...vars(block(':root[data-theme="dark"]')) };

type RGBA = [number, number, number, number];
function parse(c: string): RGBA {
  const h = c.match(/^#([0-9a-f]{6})$/i);
  if (h) return [0, 2, 4].map((i) => parseInt(h[1].slice(i, i + 2), 16)).concat(1) as RGBA;
  const r = c.match(/rgba?\(([^)]+)\)/);
  if (r) {
    const p = r[1].split(",").map((x) => parseFloat(x));
    return [p[0], p[1], p[2], p[3] ?? 1];
  }
  throw new Error("unparsed colour " + c);
}
const over = (top: RGBA, bottom: RGBA): RGBA => [0, 1, 2].map((i) => top[i] * top[3] + bottom[i] * (1 - top[3])).concat(1) as RGBA;
const lum = (c: RGBA) => {
  const [r, g, b] = c.slice(0, 3).map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a: RGBA, b: RGBA) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};
/** first colour stop of a tile gradient, or the colour itself */
const firstStop = (v: string) => (v.match(/#[0-9a-f]{6}|rgba?\([^)]+\)/i) ?? [v])[0];

for (const [name, t] of [["light", light], ["dark", dark]] as const) {
  const bg = parse(t.bg);
  const surface = over(parse(t.surface), bg);
  const glass = over(parse(t.glass), bg);
  const check = (fg: string, on: RGBA, min: number, what: string) => {
    const r = ratio(over(parse(fg), on), on);
    assert.ok(r >= min, `${name}: ${what} contrast ${r.toFixed(2)} < ${min}`);
  };
  test(`${name}: body text, secondary text and muted labels meet AA on surfaces and glass`, () => {
    for (const [on, where] of [[surface, "surface"], [glass, "glass"], [bg, "page"]] as const) {
      check(t.text, on, 7, `text on ${where}`);
      check(t["text-2"], on, 4.5, `text-2 on ${where}`);
      check(t.muted, on, 4.5, `muted on ${where}`);
    }
  });
  test(`${name}: verdict colours are readable as text on surfaces`, () => {
    for (const v of ["fossil", "fence", "unknown", "danger", "ok", "accent"]) check(t[v], surface, 4.5, `${v} on surface`);
  });
  test(`${name}: tile ink on verdict tiles meets AA`, () => {
    for (const v of ["fossil", "fence", "unknown", "active"]) {
      const tile = over(parse(firstStop(t[`${v}-tile`])), surface);
      check(t[`${v}-ink`], tile, 4.5, `${v}-ink on ${v} tile`);
    }
  });
  test(`${name}: verdict badges (colour on its tinted pill)`, () => {
    for (const v of ["fossil", "fence", "unknown", "danger", "info"]) {
      const pill = over(parse(t[`${v}-soft`]), surface);
      check(t[v], pill, 4.5, `${v} badge`);
    }
  });
  test(`${name}: primary and accent buttons`, () => {
    check(t["accent-ink"], parse(t.accent), 4.5, "accent button label");
    check(t.bg, parse(t.text), 7, "primary button label");
  });
}
