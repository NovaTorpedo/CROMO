import { useEffect, useMemo, useRef, useState } from "react";
import { CornerDownLeft, MessageSquareText, Search } from "lucide-react";
import { get } from "../api";
import { rank } from "../lib/search";
import type { MapData, MapStep } from "../types";
import { VERDICT_LABEL, VerdictIcon, go } from "./common";

interface Item { kind: "step"; step: MapStep & { process: string } }
interface AskItem { kind: "ask"; q: string }

/** "Ask why" spotlight: jump straight to any step's investigation, or ask the archive a free question. */
export default function Palette({ onClose }: { onClose: () => void }) {
  const [q, setQ] = useState("");
  const [steps, setSteps] = useState<(MapStep & { process: string })[]>([]);
  const [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    input.current?.focus();
    get<MapData>("/api/map")
      .then((d) => setSteps(d.processes.flatMap((p) => p.steps.map((s) => ({ ...s, process: p.code })))))
      .catch(() => {});
  }, []);

  const items: (Item | AskItem)[] = useMemo(() => {
    const found: (Item | AskItem)[] = q.trim()
      ? rank(steps, q, 7).map((s) => ({ kind: "step" as const, step: s }))
      : steps.filter((s) => ["ALK-04", "SOL-02", "EPX-02", "ALK-07"].includes(s.id)).map((s) => ({ kind: "step" as const, step: s }));
    if (q.trim().length > 2) found.push({ kind: "ask", q: q.trim() });
    return found;
  }, [q, steps]);

  useEffect(() => setSel(0), [q]);

  const choose = (it: Item | AskItem) => {
    onClose();
    if (it.kind === "step") go(`/step/${it.step.id}`);
    else go(`/ask?q=${encodeURIComponent(it.q)}`);
  };

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div className="palette glass" role="dialog" aria-modal="true" aria-label="Ask why about any step">
        <div className="palette-in">
          <Search size={19} className="muted" />
          <input
            ref={input}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Ask why about any step… e.g. ammonium chloride"
            aria-label="Search steps"
            onKeyDown={(e) => {
              if (e.key === "Escape") onClose();
              else if (e.key === "ArrowDown") {
                e.preventDefault();
                setSel((s) => Math.min(items.length - 1, s + 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setSel((s) => Math.max(0, s - 1));
              } else if (e.key === "Enter" && items[sel]) choose(items[sel]);
            }}
          />
          <span className="kbd">Esc</span>
        </div>
        <div className="palette-list" role="listbox">
          {!q.trim() && <div className="tiny muted" style={{ padding: "6px 12px" }}>Start with these</div>}
          {items.map((it, i) =>
            it.kind === "step" ? (
              <button key={it.step.id} role="option" aria-selected={i === sel} className={`palette-item ${i === sel ? "sel" : ""}`}
                onMouseEnter={() => setSel(i)} onClick={() => choose(it)}>
                <span className={`ic v-${it.step.verdict}`}><VerdictIcon v={it.step.verdict} size={16} /></span>
                <span className="grow">
                  <span className="t">{it.step.name}</span> <span className="tiny muted">{it.step.process} · {it.step.id} · {VERDICT_LABEL[it.step.verdict]}</span>
                  <div className="s">{it.step.instruction}</div>
                </span>
                {i === sel && <CornerDownLeft size={15} className="muted" />}
              </button>
            ) : (
              <button key="ask" role="option" aria-selected={i === sel} className={`palette-item ${i === sel ? "sel" : ""}`}
                onMouseEnter={() => setSel(i)} onClick={() => choose(it)}>
                <span className="ic" style={{ background: "var(--accent-soft)", color: "var(--accent)" }}><MessageSquareText size={16} /></span>
                <span className="grow">
                  <span className="t">Ask the archive</span>
                  <div className="s">“{it.q}” — answered from the documents, every claim cited</div>
                </span>
                {i === sel && <CornerDownLeft size={15} className="muted" />}
              </button>
            ),
          )}
          {q.trim() && items.length === 0 && <div className="empty small">No step matches. Try a material, a piece of equipment or a step id.</div>}
        </div>
        <div className="palette-foot"><span>↑↓ to move</span><span>↵ to open</span><span className="grow" /><span>Ctrl K anywhere</span></div>
      </div>
    </>
  );
}
