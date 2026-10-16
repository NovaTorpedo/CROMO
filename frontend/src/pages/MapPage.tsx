import { useEffect, useState } from "react";
import { ArrowRight, Search } from "lucide-react";
import { eur, get } from "../api";
import { ErrorBox, Skeleton, VERDICT_LABEL, VerdictIcon, go } from "../components/common";
import type { MapData, MapStep, Verdict } from "../types";

const LEGEND: { v: Verdict; text: string }[] = [
  { v: "FOSSIL", text: "Fossil" },
  { v: "FENCE", text: "Fence" },
  { v: "UNKNOWN", text: "Unknown" },
  { v: "ACTIVE", text: "Active" },
];
const LEGEND_HELP: Record<string, string> = {
  FOSSIL: "the reason is gone: waste",
  FENCE: "looks pointless, protects you",
  UNKNOWN: "no documented reason: ask a person",
  ACTIVE: "still needed",
};

export function Tile({ s, dim, onHover }: { s: MapStep; dim: boolean; onHover?: (s: MapStep | null, r?: DOMRect) => void }) {
  return (
    <button
      className={`tile t-${s.verdict} ${dim ? "dim" : ""}`}
      onClick={() => go(`/step/${s.id}`)}
      onMouseEnter={(e) => onHover?.(s, e.currentTarget.getBoundingClientRect())}
      onMouseLeave={() => onHover?.(null)}
      onFocus={(e) => onHover?.(s, e.currentTarget.getBoundingClientRect())}
      onBlur={() => onHover?.(null)}
      aria-label={`Step ${s.id}, ${s.name}: ${VERDICT_LABEL[s.verdict]}`}
    >
      <span className="top">
        <span>{s.seq}</span>
        {s.verdict !== "ACTIVE" && <VerdictIcon v={s.verdict} size={14} />}
      </span>
      <span className="nm">{s.name}</span>
      <span className="bot">
        {s.verdict === "FOSSIL" ? `${eur(s.annual_cost_eur, true)}/yr` : s.verdict === "FENCE" ? "protects" : ""}
      </span>
    </button>
  );
}

export default function MapPage({ onAsk }: { onAsk: () => void }) {
  const [data, setData] = useState<MapData | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [focus, setFocus] = useState<Verdict | null>(null);
  const [tip, setTip] = useState<{ s: MapStep; r: DOMRect } | null>(null);

  useEffect(() => {
    get<MapData>("/api/map").then(setData, setErr);
  }, []);

  if (err) return <ErrorBox error={err} />;
  if (!data)
    return (
      <div className="col" style={{ gap: 18 }}>
        <Skeleton h={56} w="60%" />
        <Skeleton h={60} w="50%" />
        <Skeleton h={560} />
      </div>
    );

  const t = data.totals;
  const steps = data.processes.flatMap((p) => p.steps);
  const levi = steps.find((s) => s.id === "ALK-04");
  const examples = [
    levi && levi.verdict === "FOSSIL" ? levi : steps.find((s) => s.verdict === "FOSSIL"),
    steps.find((s) => s.verdict === "FENCE"),
    steps.find((s) => s.verdict === "UNKNOWN"),
  ].filter(Boolean) as MapStep[];

  return (
    <div>
      <section className="home-hero fade-in">
        <div>
          <div className="eyebrow">{data.plant.name.replace(" S.p.A.", "")} · a fictional paint plant · 30 years of paperwork</div>
          <h1 className="hero-title" style={{ marginTop: 10 }}>Every factory runs on reasons nobody remembers.</h1>
          <p className="lead">
            CROMO read the plant's archive and worked out why each of its {steps.length} process steps exists. Some are pure waste.
            Some look pointless but keep people safe.
          </p>
        </div>
        <div className="metrics" style={{ flexDirection: "column" }}>
          <div className="metric card m-FOSSIL">
            <span className="ic"><VerdictIcon v="FOSSIL" size={17} /></span>
            <span><div className="n">{eur(data.fossil_annual_eur)}<span style={{ fontSize: 14, fontWeight: 600 }}> /yr</span></div>
              <div className="l">spent on {t.FOSSIL} fossil steps whose reason is gone</div></span>
          </div>
          <div className="metric card m-FENCE">
            <span className="ic"><VerdictIcon v="FENCE" size={17} /></span>
            <span><div className="n">{t.FENCE} fences</div><div className="l">look pointless, guard safety or quality: blocked from removal</div></span>
          </div>
          <div className="metric card m-UNKNOWN">
            <span className="ic"><VerdictIcon v="UNKNOWN" size={17} /></span>
            <span><div className="n">{t.UNKNOWN} unknown</div><div className="l">no reliable reason on file: sent to a person, never guessed</div></span>
          </div>
        </div>
      </section>

      <button className="askbar glass" onClick={onAsk} style={{ width: "100%", cursor: "text", textAlign: "left", border: "1px solid var(--glass-border)" }}
        aria-label="Ask why about any step">
        <Search size={19} />
        <span className="grow muted" style={{ fontSize: 16.5, padding: "9px 4px" }}>Ask why about any step… e.g. “why do we add ammonium chloride?”</span>
        <span className="btn primary sm">Ask why</span>
      </button>

      <section className="panel map-panel">
        <div className="map-head">
          <h2 className="section-title" style={{ margin: 0 }}>The periodic table of the plant</h2>
          <span className="grow" />
          <div className="legend" role="group" aria-label="Highlight a verdict">
            {LEGEND.map(({ v, text }) => (
              <button key={v} className={focus === v ? "on" : focus ? "off" : ""} onClick={() => setFocus(focus === v ? null : v)}
                title={`${text}: ${LEGEND_HELP[v]}. Click to highlight.`} aria-pressed={focus === v}>
                <span className={`sw t-${v}`} /> {text} <span className="muted num-tab">{t[v]}</span>
              </button>
            ))}
          </div>
        </div>
        {data.processes.map((p) => {
          const fossils = p.steps.filter((s) => s.verdict === "FOSSIL");
          return (
            <div key={p.id} className="prow">
              <div className="plabel">
                <div className="code">{p.code}</div>
                <div className="name">{p.short}</div>
                {fossils.length > 0 && <div className="sum c-FOSSIL">{eur(fossils.reduce((a, s) => a + s.annual_cost_eur, 0), true)}/yr waste</div>}
              </div>
              <div className="tiles">
                {p.steps.map((s) => (
                  <Tile key={s.id} s={s} dim={!!focus && s.verdict !== focus} onHover={(st, r) => setTip(st && r ? { s: st, r } : null)} />
                ))}
              </div>
            </div>
          );
        })}
        <div className="tiny muted" style={{ padding: "8px 0 10px" }}>
          Each tile is one step of a current recipe or procedure, in order. Open any tile to see the paper trail behind its verdict.
        </div>
      </section>

      {examples.length > 0 && (
        <section style={{ marginTop: 34 }}>
          <div className="eyebrow">Start here</div>
          <div className="try">
            {examples.map((s) => (
              <button key={s.id} className="card card-pad" onClick={() => go(`/step/${s.id}`)}>
                <span className={`badge v-${s.verdict}`}><VerdictIcon v={s.verdict} size={13} /> {VERDICT_LABEL[s.verdict]}</span>
                <div className="h2" style={{ fontSize: 19, marginTop: 10 }}>{s.name}</div>
                <div className="small muted" style={{ marginTop: 4 }}>{s.instruction}</div>
                <div className="row small" style={{ marginTop: 12, fontWeight: 600, color: "var(--accent)" }}>See why <ArrowRight size={15} /></div>
              </button>
            ))}
          </div>
        </section>
      )}

      {tip && (
        <div className="tooltip glass" style={{ left: Math.min(tip.r.left, window.innerWidth - 360), top: tip.r.bottom + 10 }}>
          <div className="row" style={{ marginBottom: 6 }}>
            <span className={`badge v-${tip.s.verdict}`}><VerdictIcon v={tip.s.verdict} size={13} /> {VERDICT_LABEL[tip.s.verdict]}</span>
            <span className="tiny muted">{tip.s.id}</span>
          </div>
          <div style={{ fontWeight: 560 }}>{tip.s.instruction}</div>
          {tip.s.reason && <div className="small muted" style={{ marginTop: 6 }}>{tip.s.reason}</div>}
          <div className="small" style={{ marginTop: 8 }}>Costs <strong>{eur(tip.s.annual_cost_eur)}</strong> a year</div>
        </div>
      )}
    </div>
  );
}
