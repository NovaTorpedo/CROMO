import { useEffect, useState } from "react";
import { BellRing, Radar } from "lucide-react";
import { eur, get, post } from "../api";
import { ErrorBox, Skeleton, Spinner, VerdictBadge, fmtDate, go, useApp } from "../components/common";
import type { Evidence, Verdict } from "../types";

interface Ev { type: string; process?: string | null; from: string; to: string }
interface Alert {
  step_id: string; verdict: Verdict; instruction: string; process: string; effect: string; explanation: string;
  evidence: Evidence[]; annual_cost_eur: number;
}
interface Result { id: string; event: Ev; alerts: Alert[]; provider: string; duration_s: number; cached_at?: number }
interface Reg { step_id: string; verdict: Verdict; dependency: string; type: string; holds: boolean | null; instruction: string }
interface Data { registry: Reg[]; presets: { id: string; label: string; event: Ev }[]; recent: { id: string; event: Ev; created_at: number }[] }

export const EFFECT_LABEL: Record<string, string> = {
  fossil_reactivated: "Fossil reactivated - keep the step",
  fence_dependency_removed: "Fence may become a fossil - re-investigate",
  becomes_fossil: "Likely becomes a fossil",
  fence_still_required: "Fence still required",
  review_required: "Review this step",
};

export default function TripwiresPage({ preset = "" }: { preset?: string }) {
  const { openDoc } = useApp();
  const [data, setData] = useState<Data | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [ev, setEv] = useState<Ev>({ type: "material_substitution", process: "ALK", from: "white spirit D40", to: "high-flash isoparaffin solvent (flash point 62 °C)" });
  const [res, setRes] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    get<Data>("/api/tripwires")
      .then((d) => {
        setData(d);
        const p = d.presets.find((x) => x.id === preset);
        if (p) {
          setEv(p.event);
          simulate(p.event);
        }
      })
      .catch(setErr);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset]);

  async function simulate(e: Ev) {
    setBusy(true);
    setErr(null);
    setRes(null);
    try {
      setRes(await post<Result>("/api/tripwires/simulate", e));
    } catch (x) {
      setErr(x);
    } finally {
      setBusy(false);
    }
  }

  const watched = data?.registry ?? [];
  return (
    <div>
      <p className="lead" style={{ marginTop: 0 }}>
        Every recovered reason records what it depends on: suppliers, materials, equipment, regulations. These are <strong>tripwires</strong>.
        Simulate a change and CROMO says which steps just became fossils, which fences are affected, and which old fossils come back to life.
      </p>
      <div className="grid-2" style={{ marginTop: 18, alignItems: "start" }}>
        <div className="card card-pad col">
          <div className="row"><Radar size={18} /><strong>Simulate a change event</strong></div>
          <div className="col" style={{ gap: 6 }}>
            {data?.presets.map((p) => (
              <button key={p.id} className="btn ghost" style={{ justifyContent: "flex-start", textAlign: "left" }} onClick={() => { setEv(p.event); simulate(p.event); }}>
                <BellRing size={15} /> {p.label}
              </button>
            )) ?? <Skeleton h={160} />}
          </div>
          <div className="eyebrow" style={{ marginTop: 8 }}>Or describe your own</div>
          <div className="grid-2" style={{ gap: 8 }}>
            <select className="select" value={ev.type} onChange={(e) => setEv({ ...ev, type: e.target.value })} aria-label="Change type">
              <option value="material_substitution">Material substitution</option>
              <option value="supplier_switch">Supplier switch</option>
              <option value="equipment_replacement">Equipment replacement</option>
              <option value="regulation_change">Regulation change</option>
              <option value="step_removal">Step removal</option>
            </select>
            <select className="select" value={ev.process ?? ""} onChange={(e) => setEv({ ...ev, process: e.target.value || null })} aria-label="Process">
              <option value="">Any process</option>
              <option value="ALK">AF-12</option><option value="EPX">EF-210</option><option value="SOL">SOP-07</option>
              <option value="TNK">TL-5</option><option value="QC">QP-02</option>
            </select>
          </div>
          <input className="input" value={ev.from} onChange={(e) => setEv({ ...ev, from: e.target.value })} placeholder="From (what changes)" aria-label="From" />
          <input className="input" value={ev.to} onChange={(e) => setEv({ ...ev, to: e.target.value })} placeholder="To (the new situation)" aria-label="To" />
          <button className="btn primary" onClick={() => simulate(ev)} disabled={busy || ev.from.length < 2}>{busy ? <Spinner /> : <BellRing size={16} />} Check tripwires</button>
        </div>
        <div>
          <ErrorBox error={err} />
          {busy && <div className="card card-pad row"><Spinner /> Checking {watched.length} watched dependencies…</div>}
          {!busy && !res && <div className="card empty">Choose a change event to see its consequences.</div>}
          {res && (
            <div className="col">
              <div className="small muted">
                {res.alerts.length} alert{res.alerts.length === 1 ? "" : "s"} for <strong>{res.event.from}</strong> → <strong>{res.event.to}</strong> · {res.duration_s}s ·{" "}
                {res.provider === "amd" ? "reviewed by the AMD-hosted model" : "rule-based (offline)"}
                {res.cached_at ? ` · stored answer from ${new Date(res.cached_at * 1000).toLocaleString()}` : ""}
              </div>
              {res.alerts.length === 0 && <div className="card empty">No recovered reason depends on this item.</div>}
              {res.alerts.map((a) => (
                <div key={a.step_id} className="card card-pad">
                  <div className="row wrap">
                    <span className={`effect e-${a.effect}`}>{EFFECT_LABEL[a.effect] ?? a.effect}</span>
                    <span className="grow" />
                    <VerdictBadge v={a.verdict} />
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <button className="chip mono" onClick={() => go(`/step/${a.step_id}`)}>{a.step_id}</button> {a.instruction}
                  </div>
                  <div className="small" style={{ marginTop: 6, color: "var(--text-2)" }}>{a.explanation}</div>
                  {a.evidence.map((e) => (
                    <div key={e.id} className="tl-card" style={{ marginTop: 8 }} onClick={() => openDoc({ acc: e.acc, page: e.page, quote: e.quote })}>
                      <div className="quote" style={{ fontSize: 14 }}>“{e.quote}”</div>
                      <div className="tl-meta"><span className="chip mono">{e.acc}</span><span className="chip">{fmtDate(e.date)}</span></div>
                    </div>
                  ))}
                  {a.effect === "fossil_reactivated" && <div className="tiny" style={{ marginTop: 6, color: "var(--danger)" }}>Do not remove this step under the new conditions.</div>}
                  {a.verdict === "FOSSIL" && a.effect !== "fossil_reactivated" && <div className="tiny muted" style={{ marginTop: 6 }}>Current waste: {eur(a.annual_cost_eur)}/yr</div>}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <details className="card acc-section" style={{ marginTop: 26 }}>
        <summary>Watched dependencies · {watched.length} tripwires</summary>
        <div className="acc-body">
          <div style={{ maxHeight: 420, overflow: "auto" }}>
            <table className="table">
              <thead><tr><th>Step</th><th>Verdict</th><th>Depends on</th><th>Type</th><th>Still present?</th></tr></thead>
              <tbody>
                {watched.map((r, i) => (
                  <tr key={i} className="clickable" onClick={() => go(`/step/${r.step_id}`)}>
                    <td className="mono">{r.step_id}</td>
                    <td><VerdictBadge v={r.verdict} /></td>
                    <td>{r.dependency}</td>
                    <td className="muted">{r.type}</td>
                    <td>{r.holds === true ? <span className="c-FENCE">yes</span> : r.holds === false ? <span className="c-FOSSIL">no - ended</span> : <span className="muted">unknown</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </details>
    </div>
  );
}
