import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Pickaxe } from "lucide-react";
import { eur, get } from "../api";
import { ErrorBox, Skeleton, StrengthMeter, VERDICT_HELP, VERDICT_LABEL, VerdictBadge, VerdictIcon, go } from "../components/common";
import type { MapData, MapStep, Verdict } from "../types";

const BANDS = [
  { id: "2020", label: "2020s", from: 2020, to: 2100 },
  { id: "2010", label: "2010s", from: 2010, to: 2019 },
  { id: "2000", label: "2000s", from: 2000, to: 2009 },
  { id: "1995", label: "1995 – 1999", from: 1995, to: 1999 },
  { id: "old", label: "≤ 1994", from: 0, to: 1994 },
];
const ROW = 34;
const PAD = 14;
const VERDICTS: Verdict[] = ["FOSSIL", "FENCE", "UNKNOWN", "ACTIVE"];

function stepYear(s: MapStep): number | null {
  if (s.first_seen) return Number(s.first_seen.slice(0, 4));
  return s.origin_year ?? null;
}

export default function MapPage() {
  const [data, setData] = useState<MapData | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [show, setShow] = useState<Record<string, boolean>>({ FOSSIL: true, FENCE: true, UNKNOWN: true, ACTIVE: true, PENDING: true });
  const [tip, setTip] = useState<{ s: MapStep; x: number; y: number; proc: string } | null>(null);

  useEffect(() => {
    get<MapData>("/api/map").then(setData, setErr);
  }, []);

  const layout = useMemo(() => {
    if (!data) return null;
    const cols = data.processes.map((p) => {
      const byBand: Record<string, MapStep[]> = {};
      BANDS.forEach((b) => (byBand[b.id] = []));
      p.steps.forEach((s) => {
        const y = stepYear(s);
        const band = BANDS.find((b) => y !== null && y >= b.from && y <= b.to) ?? BANDS[BANDS.length - 1];
        byBand[band.id].push(s);
      });
      Object.values(byBand).forEach((arr) => arr.sort((a, b) => (stepYear(b) ?? 0) - (stepYear(a) ?? 0) || a.seq - b.seq));
      return { p, byBand };
    });
    let top = 0;
    const bands = BANDS.map((b) => {
      const n = Math.max(1, ...cols.map((c) => c.byBand[b.id].length));
      const h = n * ROW + PAD * 2;
      const out = { ...b, top, h };
      top += h;
      return out;
    });
    return { cols, bands, height: top };
  }, [data]);

  if (err) return <ErrorBox error={err} />;
  if (!data || !layout)
    return (
      <div className="col gap-lg">
        <Skeleton h={60} w="60%" />
        <Skeleton h={110} />
        <Skeleton h={560} />
      </div>
    );

  const t = data.totals;
  const nSteps = data.processes.reduce((a, p) => a + p.steps.length, 0);
  const providers = data.computed_by.join(", ");

  return (
    <div>
      <div className="eyebrow">{data.plant.name} · {data.plant.site} · synthetic archive 1994 – 2026</div>
      <h1 className="h1" style={{ marginTop: 6 }}>Every factory runs on reasons nobody remembers.</h1>
      <p className="lead" style={{ marginTop: 8 }}>
        CROMO dug through the plant's own archive to recover why each of the {nSteps} steps in {data.processes.length} recipes and procedures exists.
        Fossils are waste whose reason is gone; fences look pointless but protect you.
      </p>

      <div className="kpis">
        <div className="kpi k-FOSSIL">
          <span className="ico c-FOSSIL"><VerdictIcon v="FOSSIL" size={26} /></span>
          <div className="big c-FOSSIL">{t.FOSSIL} fossils</div>
          <div className="label"><strong>{eur(data.fossil_annual_eur)}</strong> per year spent on steps whose reason is gone</div>
          <div className="sub">Removal only through a controlled trial with rollback</div>
        </div>
        <div className="kpi k-FENCE">
          <span className="ico c-FENCE"><VerdictIcon v="FENCE" size={24} /></span>
          <div className="big c-FENCE">{t.FENCE}</div>
          <div className="label">fences protected</div>
          <div className="sub">Look pointless, are load-bearing</div>
        </div>
        <div className="kpi k-UNKNOWN">
          <span className="ico c-UNKNOWN"><VerdictIcon v="UNKNOWN" size={24} /></span>
          <div className="big c-UNKNOWN">{t.UNKNOWN}</div>
          <div className="label">unknown → to a human</div>
          <div className="sub">No reliable reason found; CROMO never guesses</div>
        </div>
        <div className="kpi">
          <span className="ico c-ACTIVE"><VerdictIcon v="ACTIVE" size={24} /></span>
          <div className="big c-ACTIVE">{t.ACTIVE}</div>
          <div className="label">active</div>
          <div className="sub">Reason documented and still valid</div>
        </div>
      </div>

      <div className="filterbar">
        {VERDICTS.map((v) => (
          <button key={v} className={`toggle ${show[v] ? "on" : "off"}`} onClick={() => setShow({ ...show, [v]: !show[v] })} title={VERDICT_HELP[v]}>
            <span className={`c-${v}`}><VerdictIcon v={v} size={14} /></span>
            {VERDICT_LABEL[v]} <span className="muted mono">{t[v]}</span>
          </button>
        ))}
        <div className="grow" />
        <span className="tiny muted">
          Depth = when the step first appears in the archived recipes · verdicts by <span className="mono">{providers || "–"}</span>
        </span>
      </div>

      <div className="strata" role="figure" aria-label="Fossil map: process steps placed by the decade they first appeared, colored by verdict">
        <div className="strata-head" style={{ gridTemplateColumns: `120px repeat(${layout.cols.length}, 1fr)` }}>
          <div className="eyebrow" style={{ alignSelf: "end" }}>Stratum</div>
          {layout.cols.map(({ p }) => {
            const f = p.steps.filter((s) => s.verdict === "FOSSIL");
            return (
              <div key={p.id}>
                <div className="row" style={{ gap: 8 }}>
                  <strong className="mono">{p.code}</strong>
                  <span className="tiny muted">{p.revision}</span>
                </div>
                <div className="small muted" style={{ lineHeight: 1.3, marginTop: 2 }}>{p.name.replace(/^\S+\s/, "")}</div>
                <div className="tiny" style={{ marginTop: 4 }}>
                  <span className="c-FOSSIL">{f.length} fossil{f.length === 1 ? "" : "s"} · {eur(f.reduce((a, s) => a + s.annual_cost_eur, 0), true)}/yr</span>
                </div>
              </div>
            );
          })}
        </div>
        <div className="strata-body" style={{ gridTemplateColumns: `120px repeat(${layout.cols.length}, 1fr)`, height: layout.height }}>
          {layout.bands.map((b, i) => (
            <div
              key={b.id}
              style={{
                position: "absolute", left: 0, right: 0, top: b.top, height: b.h,
                background: `var(--stratum-${(i % 4) + 1})`, borderTop: i ? "1px dashed var(--border-strong)" : "none",
              }}
            >
              <span className="eyebrow" style={{ position: "absolute", left: 12, top: 12, maxWidth: 100 }}>{b.label}{b.id === "old" && <div className="tiny" style={{ textTransform: "none", letterSpacing: 0 }}>inherited before the archive</div>}</span>
            </div>
          ))}
          <div />
          {layout.cols.map(({ p, byBand }) => (
            <div key={p.id} className="core">
              {layout.bands.flatMap((b) =>
                byBand[b.id].map((s, k) => {
                  const y = stepYear(s);
                  const dim = !show[s.verdict];
                  return (
                    <button
                      key={s.id}
                      className={`specimen s-${s.verdict} ${dim ? "dim" : ""}`}
                      style={{ top: b.top + PAD + k * ROW, height: ROW - 6 }}
                      onClick={() => go(`/step/${s.id}`)}
                      onMouseEnter={(e) => setTip({ s, x: e.clientX, y: e.clientY, proc: p.code })}
                      onMouseMove={(e) => setTip((t0) => (t0 ? { ...t0, x: e.clientX, y: e.clientY } : t0))}
                      onMouseLeave={() => setTip(null)}
                      onFocus={(e) => {
                        const r = e.currentTarget.getBoundingClientRect();
                        setTip({ s, x: r.right, y: r.top, proc: p.code });
                      }}
                      onBlur={() => setTip(null)}
                      aria-label={`${s.id} ${VERDICT_LABEL[s.verdict]}: ${s.instruction}`}
                    >
                      <span className={`c-${s.verdict}`} style={{ display: "inline-flex" }}><VerdictIcon v={s.verdict} size={14} /></span>
                      <span className="sid">{s.id}</span>
                      <span className="txt">{s.instruction}</span>
                      {s.verdict === "FOSSIL" ? (
                        <span className="eur c-FOSSIL">{eur(s.annual_cost_eur, true)}</span>
                      ) : (
                        <span className="tiny muted mono">{y ?? ""}</span>
                      )}
                    </button>
                  );
                }),
              )}
            </div>
          ))}
        </div>
      </div>
      <div className="legend" style={{ marginTop: 12 }}>
        {VERDICTS.map((v) => (
          <span key={v} className="it">
            <span className={`c-${v}`}><VerdictIcon v={v} size={14} /></span> <strong>{VERDICT_LABEL[v]}</strong> <span className="muted">— {VERDICT_HELP[v]}</span>
          </span>
        ))}
      </div>

      {tip && (
        <div className="tooltip" style={{ left: Math.min(tip.x + 16, window.innerWidth - 380), top: tip.y + 14 }}>
          <div className="row" style={{ marginBottom: 6 }}>
            <VerdictBadge v={tip.s.verdict} />
            <span className="mono small">{tip.s.id}</span>
            <span className="grow" />
            <StrengthMeter grade={tip.s.strength} />
          </div>
          <div style={{ marginBottom: 6 }}>{tip.s.instruction}</div>
          {tip.s.reason && <div className="small muted">{tip.s.reason}</div>}
          <div className="small" style={{ marginTop: 6 }}>
            Annual cost of this step: <strong>{eur(tip.s.annual_cost_eur)}</strong>
            {tip.s.first_seen && <span className="muted"> · first seen {tip.s.first_seen.slice(0, 4)}</span>}
          </div>
          <div className="tiny muted" style={{ marginTop: 6 }}>Click to open the investigation</div>
        </div>
      )}

      <div style={{ marginTop: 28 }}>
        <div className="row" style={{ marginBottom: 10 }}>
          <Pickaxe size={18} />
          <h2 className="section-title" style={{ margin: 0 }}>Pick any step and watch CROMO dig</h2>
        </div>
        <div className="card" style={{ overflow: "hidden" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Step</th>
                <th>Instruction</th>
                <th>Verdict</th>
                <th>Evidence</th>
                <th className="num">Cost / yr</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.processes.flatMap((p) =>
                p.steps
                  .filter((s) => show[s.verdict])
                  .map((s) => (
                    <tr key={s.id} className="clickable" onClick={() => go(`/step/${s.id}`)}>
                      <td className="mono">{s.id}</td>
                      <td style={{ maxWidth: 560 }}>{s.instruction}</td>
                      <td><VerdictBadge v={s.verdict} /></td>
                      <td><StrengthMeter grade={s.strength} /></td>
                      <td className={`num mono ${s.verdict === "FOSSIL" ? "c-FOSSIL" : ""}`}>{eur(s.annual_cost_eur)}</td>
                      <td><ArrowRight size={15} className="muted" /></td>
                    </tr>
                  )),
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
