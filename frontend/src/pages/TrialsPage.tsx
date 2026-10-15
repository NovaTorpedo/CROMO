import { useCallback, useEffect, useState } from "react";
import { ClipboardCheck, RefreshCw, Send, Workflow } from "lucide-react";
import { eur, get, post } from "../api";
import { ErrorBox, Skeleton, Spinner, go, timeAgo } from "../components/common";

interface Trial {
  id: string; step_id: string; status: string; evolus_execution_id: string | null; created_at: number; updated_at: number;
  plan: {
    title: string; objective: string; scope: string; duration: string; measurements: string[]; acceptance_criteria: string[];
    rollback: string; risks: string[]; approvals: string[]; step: { id: string; instruction: string; process_code: string };
    strength: string; annual_saving_eur: number; evidence: { claim: string; sources: string[] }[]; drafted_by: string;
  };
  history: { status: string; note: string; source: string; ts: number; by?: string; execution_id?: string }[];
}

const STAGES = [
  ["draft", "Drafted"],
  ["submitted", "Sent to Evolus workflow"],
  ["awaiting_decision", "Awaiting engineer"],
  ["decided", "Decision"],
];

function stageIndex(s: string) {
  if (s === "draft") return 0;
  if (s === "submitted") return 1;
  if (s === "awaiting_decision") return 2;
  if (s === "approved" || s === "rejected") return 3;
  return 0;
}

export default function TrialsPage({ focus }: { focus: string }) {
  const [list, setList] = useState<Trial[] | null>(null);
  const [wf, setWf] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [sel, setSel] = useState<string>(focus);
  const [busy, setBusy] = useState(false);
  const [by, setBy] = useState("D. Morra (Process Engineering)");

  const load = useCallback(async () => {
    const r = await get<{ trials: Trial[]; workflow_configured: boolean }>("/api/trials");
    setList(r.trials);
    setWf(r.workflow_configured);
    if (!sel && r.trials.length) setSel(r.trials[0].id);
  }, [sel]);

  useEffect(() => {
    load().catch(setErr);
  }, [load]);

  const t = list?.find((x) => x.id === sel) ?? null;

  useEffect(() => {
    if (!t || !["submitted", "awaiting_decision"].includes(t.status) || !t.evolus_execution_id) return;
    const id = window.setInterval(() => {
      post<Trial>(`/api/trials/${t.id}/refresh`).then((nt) => setList((l) => l?.map((x) => (x.id === nt.id ? nt : x)) ?? null)).catch(() => {});
    }, 8000);
    return () => window.clearInterval(id);
  }, [t?.id, t?.status, t?.evolus_execution_id]);

  async function act(fn: () => Promise<Trial>) {
    setBusy(true);
    setErr(null);
    try {
      const nt = await fn();
      setList((l) => l?.map((x) => (x.id === nt.id ? nt : x)) ?? [nt]);
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="eyebrow">Safe trial plans · Evolus workflow approval</div>
      <h1 className="h1" style={{ marginTop: 6 }}>CROMO never deletes a step.</h1>
      <p className="lead">
        For a fossil it drafts a controlled trial - scope, measurements, acceptance criteria, rollback - and sends it to an engineer for approval
        through an Evolus workflow. The status comes back here.
      </p>
      {!wf && (
        <div className="note warn small" style={{ marginTop: 12 }}>
          <Workflow size={18} />
          <div>The Evolus approval workflow is not connected in this deployment: submissions are simulated locally and labelled “offline”.</div>
        </div>
      )}
      <ErrorBox error={err} />
      <div className="grid-2" style={{ gridTemplateColumns: "340px 1fr", marginTop: 18, alignItems: "start" }}>
        <div className="col">
          {!list ? <Skeleton h={200} /> : list.length === 0 ? (
            <div className="card empty">
              <ClipboardCheck size={22} />
              <p>No trials yet. Open a fossil on the map and choose “Draft a safe trial”.</p>
              <button className="btn" onClick={() => go("/step/ALK-04")}>Open the ammonium chloride fossil</button>
            </div>
          ) : (
            list.map((x) => (
              <button key={x.id} className="card card-pad" style={{ textAlign: "left", cursor: "pointer", borderColor: x.id === sel ? "var(--chrome)" : undefined }} onClick={() => setSel(x.id)}>
                <div className="row"><span className="mono small">{x.id}</span><span className="grow" /><span className="chip">{x.status.replace(/_/g, " ")}</span></div>
                <div style={{ marginTop: 4, fontWeight: 500 }}>{x.plan.step.id} · {x.plan.step.instruction}</div>
                <div className="tiny muted" style={{ marginTop: 4 }}>saves {eur(x.plan.annual_saving_eur)}/yr · {timeAgo(x.updated_at)}</div>
              </button>
            ))
          )}
        </div>
        {t && (
          <div className="card">
            <div className="card-pad" style={{ borderBottom: "1px solid var(--border)" }}>
              <div className="steps-flow">
                {STAGES.map(([k, label], i) => {
                  const idx = stageIndex(t.status);
                  const cls = i < idx ? "done" : i === idx ? "now" : "";
                  const lab = k === "decided" && (t.status === "approved" || t.status === "rejected") ? t.status.toUpperCase() : label;
                  return <span key={k} className={`s ${cls}`}>{lab}</span>;
                })}
              </div>
              <h2 className="h2" style={{ marginTop: 14 }}>{t.plan.title}</h2>
              <div className="small muted" style={{ marginTop: 4 }}>
                {t.plan.step.process_code} · FOSSIL ({t.plan.strength} evidence) · potential saving <strong className="c-FOSSIL">{eur(t.plan.annual_saving_eur)}/yr</strong> · drafted by <span className="mono">{t.plan.drafted_by}</span>
              </div>
            </div>
            <div className="card-pad grid-2" style={{ gap: 18 }}>
              <div className="col small">
                <div><strong>Objective.</strong> {t.plan.objective}</div>
                <div><strong>Scope.</strong> {t.plan.scope}</div>
                <div><strong>Duration.</strong> {t.plan.duration}</div>
                <div><strong>Rollback.</strong> {t.plan.rollback}</div>
                <div><strong>Approvals.</strong> {t.plan.approvals.join(", ")}</div>
              </div>
              <div className="col small">
                <div><strong>Measurements</strong><ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{t.plan.measurements.map((m, i) => <li key={i}>{m}</li>)}</ul></div>
                <div><strong>Acceptance criteria</strong><ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{t.plan.acceptance_criteria.map((m, i) => <li key={i}>{m}</li>)}</ul></div>
                <div><strong>Risks</strong><ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{t.plan.risks.map((m, i) => <li key={i}>{m}</li>)}</ul></div>
              </div>
            </div>
            <div className="card-pad" style={{ borderTop: "1px solid var(--border)" }}>
              <div className="row wrap">
                {(t.status === "draft" || t.status === "failed") && (
                  <button className="btn primary" disabled={busy} onClick={() => act(() => post<Trial>(`/api/trials/${t.id}/submit`))}>
                    {busy ? <Spinner /> : <Send size={16} />} Send for approval via Evolus workflow
                  </button>
                )}
                {["submitted", "awaiting_decision"].includes(t.status) && (
                  <>
                    {t.evolus_execution_id && (
                      <button className="btn" disabled={busy} onClick={() => act(() => post<Trial>(`/api/trials/${t.id}/refresh`))}>
                        <RefreshCw size={15} /> Refresh Evolus status
                      </button>
                    )}
                    <input className="input" style={{ width: 260 }} value={by} onChange={(e) => setBy(e.target.value)} aria-label="Approver name" />
                    <button className="btn okb" disabled={busy} onClick={() => act(() => post<Trial>(`/api/trials/${t.id}/decision`, { approved: true, by }))}>Approve</button>
                    <button className="btn danger" disabled={busy} onClick={() => act(() => post<Trial>(`/api/trials/${t.id}/decision`, { approved: false, by }))}>Reject</button>
                  </>
                )}
                <button className="btn ghost" onClick={() => go(`/step/${t.step_id}`)}>Open investigation</button>
              </div>
              <div className="eyebrow" style={{ marginTop: 16, marginBottom: 6 }}>History</div>
              {t.history.map((h, i) => (
                <div key={i} className="small row" style={{ alignItems: "flex-start", marginBottom: 4 }}>
                  <span className="mono tiny muted" style={{ width: 120, flexShrink: 0 }}>{new Date(h.ts * 1000).toLocaleTimeString()}</span>
                  <span className="chip">{h.source}</span>
                  <span>{h.note}{h.by ? ` - ${h.by}` : ""}{h.execution_id ? <span className="tiny muted mono"> · execution {h.execution_id}</span> : null}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
