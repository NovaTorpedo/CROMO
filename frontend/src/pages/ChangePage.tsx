import { useEffect, useState, type ReactNode } from "react";
import { Ban, CircleCheck, Scale, TriangleAlert } from "lucide-react";
import { eur, post } from "../api";
import { ErrorBox, Spinner, VerdictBadge, fmtDate, go, useApp } from "../components/common";
import type { Evidence, Verdict } from "../types";

interface Finding {
  step_id: string | null; verdict?: Verdict; strength?: string; decision: string; why: string; instruction?: string;
  evidence?: Evidence[]; annual_cost_eur?: number; effect?: string;
}
interface Res { proposal: string; decision: string; findings: Finding[]; parsed: { targets: string[]; action: string; subject: string }; provider: string; duration_s: number; policy: string; cached_at?: number }

const EXAMPLES = [
  "Remove step SOL-02 (bonding and earthing) to save time",
  "Remove the ammonium chloride addition from AF-12",
  "Shorten the cooling hold before letdown in AF-12 from 30 to 5 minutes",
  "Drop the second acetone rinse in SOP-07",
  "Switch the epoxy resin to a cheaper standard grade resin",
  "Reduce the wait after cleaning from 60 to 15 minutes",
];

const DECISION: Record<string, { word: string; icon: ReactNode; sub: string }> = {
  blocked: { word: "BLOCKED", icon: <Ban size={34} />, sub: "This change would tear down a fence." },
  caution: { word: "CAUTION", icon: <TriangleAlert size={34} />, sub: "Not enough certainty, or the change affects a protected reason. A human must review." },
  allowed_with_trial: { word: "ALLOWED WITH TRIAL", icon: <CircleCheck size={34} />, sub: "The reason is gone. Proceed through a controlled trial with rollback - never a direct deletion." },
  allowed_with_review: { word: "ALLOWED WITH REVIEW", icon: <CircleCheck size={34} />, sub: "No fence is affected; review the steps listed." },
  allowed: { word: "ALLOWED", icon: <CircleCheck size={34} />, sub: "No recovered reason is affected." },
};

export default function ChangePage({ initial }: { initial: string }) {
  const { openDoc } = useApp();
  const [p, setP] = useState(initial);
  const [res, setRes] = useState<Res | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  async function check(text: string) {
    if (text.trim().length < 5) return;
    setBusy(true);
    setErr(null);
    setRes(null);
    try {
      setRes(await post<Res>("/api/v1/change-check", { proposal: text }));
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (initial) check(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial]);

  const d = res ? DECISION[res.decision] ?? DECISION.caution : null;
  return (
    <div style={{ maxWidth: 1100 }}>
      <p className="lead" style={{ marginTop: 0 }}>
        The tool that tells AI optimizers which fences not to tear down. Propose a change in plain language, or call the REST endpoint from an
        optimization tool. CROMO answers <strong>blocked</strong>, <strong>caution</strong> or <strong>allowed</strong> with the fences and
        evidence involved. Auditable rules decide; the model only maps your words to steps.
      </p>
      <form className="askbar glass" style={{ marginTop: 18 }} onSubmit={(e) => { e.preventDefault(); check(p); }}>
        <Scale size={18} />
        <input className="input" value={p} onChange={(e) => setP(e.target.value)} placeholder="e.g. Remove step SOL-02 to save time" aria-label="Proposed change" />
        <button className="btn primary" disabled={busy}>{busy ? <Spinner /> : null} Check</button>
      </form>
      <div className="row wrap" style={{ gap: 6, marginTop: 12 }}>
        {EXAMPLES.map((x) => <button key={x} className="chip" onClick={() => { setP(x); check(x); }}>{x}</button>)}
      </div>
      <div style={{ marginTop: 20 }} className="col">
        <ErrorBox error={err} />
        {res && d && (
          <>
            <div className={`decision d-${res.decision}`}>
              {d.icon}
              <div>
                <div className="word">{d.word}</div>
                <div className="small" style={{ color: "var(--text-2)" }}>{d.sub}</div>
              </div>
            </div>
            {res.findings.map((f, i) => (
              <div key={i} className="card card-pad">
                <div className="row wrap">
                  {f.step_id && <button className="chip mono" onClick={() => go(`/step/${f.step_id}`)}>{f.step_id}</button>}
                  {f.verdict && <VerdictBadge v={f.verdict} />}
                  {f.strength && <span className="tiny muted">{f.strength} evidence</span>}
                  <span className="grow" />
                  <span className={`effect ${f.decision === "blocked" ? "e-fossil_reactivated" : f.decision === "caution" ? "e-fence_dependency_removed" : f.decision === "info" ? "e-review_required" : "e-fence_still_required"}`}>
                    {f.decision.replace(/_/g, " ")}
                  </span>
                </div>
                {f.instruction && <div style={{ marginTop: 8 }}>{f.instruction}</div>}
                <div className="small" style={{ marginTop: 6, color: "var(--text-2)" }}>{f.why}</div>
                {f.evidence?.map((e) => (
                  <div key={e.id + e.acc} className="tl-card" style={{ marginTop: 8 }} onClick={() => openDoc({ acc: e.acc, page: e.page, quote: e.quote })}>
                    <div className="quote" style={{ fontSize: 14 }}>“{e.quote}”</div>
                    <div className="tl-meta"><span className="chip mono">{e.acc}</span><span className="chip">{e.doc_type}</span><span className="chip">{fmtDate(e.date)}</span></div>
                  </div>
                ))}
                {f.verdict === "FOSSIL" && f.annual_cost_eur ? <div className="tiny c-FOSSIL" style={{ marginTop: 6 }}>Potential saving {eur(f.annual_cost_eur)}/yr</div> : null}
              </div>
            ))}
            <div className="tiny muted">Policy: {res.policy} · mapped to {res.parsed.targets.join(", ") || res.parsed.subject || "nothing"} ({res.parsed.action}) · {res.duration_s}s
              {res.cached_at ? ` · stored answer from ${new Date(res.cached_at * 1000).toLocaleString()}` : ""}</div>
          </>
        )}
      </div>
      <details className="card acc-section" style={{ marginTop: 26 }}>
        <summary>REST API for optimization tools</summary>
        <div className="acc-body">
        <pre className="code">{`curl -X POST $CROMO_URL/api/v1/change-check \\
  -H "Content-Type: application/json" \\
  -H "X-Access-Token: $CROMO_ACCESS_TOKEN" \\
  -d '{"proposal": "Shorten the AF-12 cooling hold from 30 to 5 minutes"}'

# -> {"decision": "blocked", "findings": [{"step_id": "ALK-07", "verdict": "FENCE", "why": "...", "evidence": [...]}]}`}</pre>
        </div>
      </details>
    </div>
  );
}
