import { useEffect, useState } from "react";
import { ArrowRight, Search } from "lucide-react";
import { eur, get } from "../api";
import { ErrorBox, Skeleton, VERDICT_LABEL, VerdictIcon, go } from "../components/common";
import type { MapData, MapStep, Verdict } from "../types";

const LEGEND: { v: Verdict; text: string }[] = [
  { v: "FOSSIL", text: "Fossil · reason is gone" },
  { v: "FENCE", text: "Fence · looks pointless, protects you" },
  { v: "UNKNOWN", text: "Unknown · ask a person" },
  { v: "ACTIVE", text: "Active · still needed" },
];

function Tile({ s, dim, onHover }: { s: MapStep; dim: boolean; onHover: (s: MapStep | null, r?: DOMRect) => void }) {
  return (
    <button
      className={`tile t-${s.verdict} ${dim ? "dim" : ""}`}
      onClick={() => go(`/step/${s.id}`)}
      onMouseEnter={(e) => onHover(s, e.currentTarget.getBoundingClientRect())}
      onMouseLeave={() => onHover(null)}
      onFocus={(e) => onHover(s, e.currentTarget.getBoundingClientRect())}
      onBlur={() => onHover(null)}
      aria-label={`Step ${s.id}, ${s.name}: ${VERDICT_LABEL[s.verdict]}`}
    >
      <span className="top">
        <span>{s.seq}</span>
        {s.verdict !== "ACTIVE" && <VerdictIcon v={s.verdict} size={15} />}
      </span>
      <span className="nm">{s.name}</span>
      <span className="bot">
        {s.verdict === "FOSSIL" ? `${eur(s.annual_cost_eur, true)}/yr` : s.verdict === "FENCE" ? "protects" : ""}
      </span>
    </button>
  );
}

export default function MapPage() {
  const [data, setData] = useState<MapData | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [focus, setFocus] = useState<Verdict | null>(null);
  const [tip, setTip] = useState<{ s: MapStep; r: DOMRect } | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    get<MapData>("/api/map").then(setData, setErr);
  }, []);

  if (err) return <ErrorBox error={err} />;
  if (!data)
    return (
      <div className="col" style={{ gap: 18, marginTop: 30 }}>
        <Skeleton h={56} w="70%" />
        <Skeleton h={90} />
        <Skeleton h={480} />
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
      <section className="home-hero">
        <h1 className="hero-title">Every factory runs on reasons nobody remembers.</h1>
        <p className="lead">
          CROMO read 30 years of paperwork from {data.plant.name.replace(" S.p.A.", "")}, a fictional paint plant, and worked out why each of its{" "}
          {steps.length} process steps exists. Some are pure waste. Some look pointless but keep people safe.
        </p>
      </section>

      <div className="stats">
        <div className="stat s-FOSSIL">
          <div className="n">{eur(data.fossil_annual_eur)}</div>
          <div className="l">spent every year on <strong>{t.FOSSIL} fossil steps</strong> whose original reason is gone</div>
        </div>
        <div className="stat s-FENCE">
          <div className="n">{t.FENCE} fences</div>
          <div className="l">look pointless but guard safety or quality - CROMO blocks their removal</div>
        </div>
        <div className="stat s-UNKNOWN">
          <div className="n">{t.UNKNOWN} unknown</div>
          <div className="l">no reliable reason in the archive - sent to a person, never guessed</div>
        </div>
      </div>

      <form
        className="askbar"
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) go(`/ask?q=${encodeURIComponent(q.trim())}`);
        }}
      >
        <input className="input" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Ask why any step exists - e.g. “why do we add ammonium chloride?”" aria-label="Ask why a step exists" />
        <button className="btn primary"><Search size={16} /> Ask</button>
      </form>

      <section className="ptable">
        <div className="ptable-head">
          <h2 className="section-title" style={{ margin: 0 }}>The periodic table of the plant</h2>
          <div className="legend">
            {LEGEND.map(({ v, text }) => (
              <button
                key={v}
                className="it"
                style={{ background: "none", border: "none", cursor: "pointer", padding: 0, opacity: focus && focus !== v ? 0.45 : 1 }}
                onClick={() => setFocus(focus === v ? null : v)}
                title="Click to highlight"
              >
                <span className={`sw tile t-${v}`} style={{ width: 14, height: 14, padding: 0, borderRadius: 4 }} />
                {text}
              </button>
            ))}
          </div>
        </div>
        <div className="card" style={{ padding: "8px 22px" }}>
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
        </div>
        <div className="tiny muted" style={{ marginTop: 10 }}>
          Each tile is one step of a current recipe or procedure, in order. Click any tile to see the evidence behind it.
        </div>
      </section>

      {examples.length > 0 && (
        <section style={{ marginTop: 40 }}>
          <h2 className="section-title">Start here</h2>
          <div className="try">
            {examples.map((s) => (
              <button key={s.id} className="card card-pad" onClick={() => go(`/step/${s.id}`)}>
                <span className={`badge v-${s.verdict}`}><VerdictIcon v={s.verdict} size={13} /> {VERDICT_LABEL[s.verdict]}</span>
                <div className="h2" style={{ fontSize: 21, marginTop: 10 }}>{s.name}</div>
                <div className="small muted" style={{ marginTop: 4 }}>{s.instruction}</div>
                <div className="row small" style={{ marginTop: 12, fontWeight: 500 }}>See why <ArrowRight size={15} /></div>
              </button>
            ))}
          </div>
        </section>
      )}

      {tip && (
        <div className="tooltip" style={{ left: Math.min(tip.r.left, window.innerWidth - 360), top: tip.r.bottom + 10 }}>
          <div className="row" style={{ marginBottom: 6 }}>
            <span className={`badge v-${tip.s.verdict}`}><VerdictIcon v={tip.s.verdict} size={13} /> {VERDICT_LABEL[tip.s.verdict]}</span>
            <span className="tiny muted">{tip.s.id}</span>
          </div>
          <div style={{ fontWeight: 500 }}>{tip.s.instruction}</div>
          {tip.s.reason && <div className="small muted" style={{ marginTop: 6 }}>{tip.s.reason}</div>}
          <div className="small" style={{ marginTop: 8 }}>Costs <strong>{eur(tip.s.annual_cost_eur)}</strong> a year</div>
        </div>
      )}
    </div>
  );
}
