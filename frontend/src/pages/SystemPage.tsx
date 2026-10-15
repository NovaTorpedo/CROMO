import { useEffect, useState } from "react";
import { Cpu, Database, FlaskConical, Gauge, ShieldCheck, Workflow } from "lucide-react";
import { get } from "../api";
import { ErrorBox, Section, Skeleton } from "../components/common";

interface Role { configured: boolean; model: string | null; endpoint_host: string | null }
interface Lat { stage: string; role: string; model: string; provider: string; calls: number; errors: number; p50_ms: number; p95_ms: number; tokens_in: number; tokens_out: number }
interface EvalRes {
  provider: string; label: string; models: Record<string, string>; hardware: string; evaluated_at: number; n_steps: number; accuracy: number;
  per_class: Record<string, { precision: number; recall: number; f1: number; support: number }>;
  confusion: Record<string, Record<string, number>>; fence_recall: number; false_fossil_rate: number; dangerous_errors: string[];
  citations: { precision: number | null; key_evidence_recall: number | null; quotes_rejected_by_verifier: number; note: string };
  tripwires: { recall: number | null; expected_effects: number; extra_alerts: number };
  change_checks: { accuracy: number }; injection: { passed: boolean; documents: string[] };
}
interface Sys {
  mode: "amd" | "fixture";
  config: { provider: string; amd_route: string; hardware: string; gpu_price_per_hour: number; gpu_price_source: string; roles: Record<string, Role>;
    evolus: Record<string, boolean>; write_protected: boolean };
  models_in_use: Record<string, string>;
  ingest: { documents: number; pages: number; scanned_pages: number; seconds: number; pages_per_min: number; provider: string } | null;
  latency: Lat[];
  benchmark: Record<string, any> | null;
  eval: { amd: EvalRes | null; fixture: EvalRes | null };
  gpu: { source: string; data?: unknown; summary?: string } | null;
  evolus: { calls?: { endpoint: string; n: number; credits: number; ok: number }[]; credits_logged?: number; cached?: Record<string, number>; budget?: number; configured?: boolean };
  recordings: string[];
}

const CLASSES = ["FOSSIL", "FENCE", "ACTIVE", "UNKNOWN"];
const pct = (x: number | null | undefined) => (x === null || x === undefined ? "–" : `${Math.round(x * 100)}%`);

function EvalCard({ e, title }: { e: EvalRes; title: string }) {
  return (
    <div className="card card-pad">
      <div className="row wrap">
        <strong>{title}</strong>
        <span className={`pill ${e.provider === "amd" ? "amd" : "fixture"}`}>{e.provider === "amd" ? "measured on AMD" : "heuristic baseline · no LLM"}</span>
      </div>
      <div className="tiny muted" style={{ marginTop: 4 }}>{e.label} · {e.hardware} · {new Date(e.evaluated_at * 1000).toLocaleString()}</div>
      <div className="grid-3" style={{ marginTop: 14 }}>
        <div><div className="eyebrow">FENCE recall</div><div className="big-n c-FENCE">{pct(e.fence_recall)}</div><div className="tiny muted">missing a fence is the dangerous error</div></div>
        <div><div className="eyebrow">False-FOSSIL rate</div><div className="big-n c-FOSSIL">{pct(e.false_fossil_rate)}</div><div className="tiny muted">non-fossils wrongly called waste</div></div>
        <div><div className="eyebrow">Accuracy (4 classes)</div><div className="big-n">{pct(e.accuracy)}</div><div className="tiny muted">{e.n_steps} steps</div></div>
      </div>
      {e.dangerous_errors.length > 0 && <div className="small" style={{ color: "var(--danger)", marginTop: 6 }}>Fences called fossils: {e.dangerous_errors.join(", ")}</div>}
      <div className="grid-2" style={{ marginTop: 14 }}>
        <table className="table">
          <thead><tr><th>Class</th><th className="num">P</th><th className="num">R</th><th className="num">F1</th><th className="num">n</th></tr></thead>
          <tbody>
            {CLASSES.map((c) => (
              <tr key={c}><td className={`c-${c} mono`}>{c}</td><td className="num">{pct(e.per_class[c]?.precision)}</td><td className="num">{pct(e.per_class[c]?.recall)}</td><td className="num">{pct(e.per_class[c]?.f1)}</td><td className="num">{e.per_class[c]?.support}</td></tr>
            ))}
          </tbody>
        </table>
        <table className="table confusion">
          <thead><tr><th>truth ↓ / pred →</th>{CLASSES.map((c) => <th key={c}>{c.slice(0, 3)}</th>)}</tr></thead>
          <tbody>
            {CLASSES.map((t) => (
              <tr key={t}><th className="mono">{t.slice(0, 3)}</th>
                {CLASSES.map((p) => {
                  const n = e.confusion[t]?.[p] ?? 0;
                  const bad = t === "FENCE" && p === "FOSSIL" && n > 0;
                  return <td key={p} className={t === p ? "diag" : bad ? "bad" : ""}>{n || ""}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid-3 small" style={{ marginTop: 12 }}>
        <div><strong>Citations</strong><div className="muted">precision {pct(e.citations.precision)} · key-evidence recall {pct(e.citations.key_evidence_recall)} · {e.citations.quotes_rejected_by_verifier} quotes rejected</div></div>
        <div><strong>Tripwires</strong><div className="muted">recall {pct(e.tripwires.recall)} of {e.tripwires.expected_effects} planted effects · {e.tripwires.extra_alerts} extra alerts</div></div>
        <div><strong>Before-you-change</strong><div className="muted">{pct(e.change_checks.accuracy)} decisions correct · prompt-injection test {e.injection.passed ? "passed" : "FAILED"}</div></div>
      </div>
    </div>
  );
}

export default function SystemPage() {
  const [s, setS] = useState<Sys | null>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => {
    get<Sys>("/api/system").then(setS, setErr);
  }, []);
  if (err) return <ErrorBox error={err} />;
  if (!s) return <Skeleton h={500} />;
  const b = s.benchmark;
  const live = s.mode === "amd";
  return (
    <div>
      <div className="eyebrow">System · where CROMO runs</div>
      <h1 className="h1" style={{ marginTop: 6 }}>{live ? "Running on AMD." : "Offline fixture mode."}</h1>
      <p className="lead">
        {live
          ? `Every model call goes to OpenAI-compatible endpoints served on AMD (${s.config.amd_route === "tokenfactory" ? "AMD Token Factory" : "vLLM on AMD Developer Cloud"}).`
          : "No AMD endpoint is configured in this deployment. A deterministic fixture provider stands in for the models so the product runs end to end; its numbers are labelled as a heuristic baseline. Measured AMD numbers appear below once the benchmark has been run."}
      </p>

      <Section title="Models and hardware" eyebrow="Roles">
        <div className="card">
          <table className="table">
            <thead><tr><th>Role</th><th>Model in use</th><th>Endpoint</th><th>Runs on</th></tr></thead>
            <tbody>
              {(["reasoner", "vision", "embeddings", "speech"] as const).map((r) => {
                const role = s.config.roles[r];
                return (
                  <tr key={r}>
                    <td className="mono">{r.toUpperCase()}</td>
                    <td className="mono">{role?.configured ? role.model : r === "speech" ? "not used" : s.models_in_use[r] ?? "–"}</td>
                    <td>{role?.configured ? role.endpoint_host : <span className="muted">not configured</span>}</td>
                    <td>{role?.configured ? s.config.hardware : <span className="c-FOSSIL">offline fixture (CPU)</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Measured performance" eyebrow={b ? `AMD benchmark · ${new Date((b.finished_at ?? 0) * 1000).toLocaleString()}` : "AMD benchmark"}>
        {b ? (
          <div className="grid-3">
            <div className="card card-pad"><span className="muted" style={{ float: "right" }}><Gauge size={20} /></span><div className="big-n">{b.ingest?.pages_per_min ?? "–"}</div><div className="small" style={{ marginTop: 8 }}>pages / min ingested (all pages)</div><div className="tiny muted">{b.ingest?.scanned_pages_per_min ?? "–"} scanned pages/min read by the VLM</div></div>
            <div className="card card-pad"><span className="muted" style={{ float: "right" }}><Cpu size={20} /></span><div className="big-n">{b.investigation?.p50_s ?? "–"}s</div><div className="small" style={{ marginTop: 8 }}>median investigation (multi-hop)</div><div className="tiny muted">p95 {b.investigation?.p95_s ?? "–"}s · {b.investigation?.calls_per_step ?? "–"} model calls/step</div></div>
            <div className="card card-pad"><span className="muted" style={{ float: "right" }}><Database size={20} /></span><div className="big-n">${b.cost?.per_plant_audit_usd ?? "–"}</div><div className="small" style={{ marginTop: 8 }}>cost per full plant audit</div><div className="tiny muted">{b.cost?.gpu_hours ?? "–"} GPU-h at ${b.cost?.price_per_gpu_hour}/h · {s.config.gpu_price_source}</div></div>
          </div>
        ) : (
          <div className="note warn small"><FlaskConical size={18} /><div><strong>Not measured yet.</strong> Run <span className="mono">scripts/benchmark_amd.py</span> once AMD is linked; CROMO never shows invented numbers.</div></div>
        )}
        {s.gpu && (
          <div className="card card-pad small" style={{ marginTop: 12 }}>
            <strong>GPU memory</strong> <span className="muted">({s.gpu.source})</span>
            <pre className="code" style={{ marginTop: 8, maxHeight: 200 }}>{s.gpu.summary ?? JSON.stringify(s.gpu.data, null, 1)}</pre>
          </div>
        )}
      </Section>

      <Section title="Latency per stage (this server)" eyebrow={live ? "live metrics" : "fixture metrics - not model latency"}>
        <div className="card" style={{ maxHeight: 360, overflow: "auto" }}>
          <table className="table">
            <thead><tr><th>Stage</th><th>Role</th><th>Model</th><th className="num">Calls</th><th className="num">p50 ms</th><th className="num">p95 ms</th><th className="num">Tokens in/out</th></tr></thead>
            <tbody>
              {s.latency.filter((l) => l.provider === (live ? "amd" : "fixture")).map((l, i) => (
                <tr key={i}><td className="mono">{l.stage}</td><td>{l.role}</td><td className="mono tiny">{l.model}</td><td className="num">{l.calls}</td><td className="num">{l.p50_ms}</td><td className="num">{l.p95_ms}</td><td className="num tiny">{l.tokens_in.toLocaleString()} / {l.tokens_out.toLocaleString()}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        {s.ingest && <div className="tiny muted" style={{ marginTop: 6 }}>Last ingestion: {s.ingest.documents} documents, {s.ingest.pages} pages ({s.ingest.scanned_pages} scanned) in {s.ingest.seconds}s · provider {s.ingest.provider}</div>}
      </Section>

      <Section title="Evaluation against planted ground truth" eyebrow="49 steps · 12 fossils · 9 fences · 22 active · 6 unknown">
        <div className="col">
          {s.eval.amd ? <EvalCard e={s.eval.amd} title="CROMO on AMD" /> : (
            <div className="note warn small"><FlaskConical size={18} /><div><strong>AMD evaluation pending.</strong> Run <span className="mono">python eval/run_eval.py --rerun</span> with the AMD endpoints configured.</div></div>
          )}
          {s.eval.fixture && <EvalCard e={s.eval.fixture} title="Rule-based heuristic baseline (offline fixture provider)" />}
          <div className="small muted">
            The archive is synthetic and the ground truth is stored in <span className="mono">eval/ground_truth.json</span>, which the product never reads (enforced by tests).
            Results on a synthetic archive do not guarantee results on a real plant.
          </div>
        </div>
      </Section>

      <Section title="Evolus building blocks" eyebrow="Partner integration">
        <div className="grid-2">
          <div className="card card-pad small col">
            {[
              ["Document extractor", s.config.evolus.extractor, "archive documents → structured records"],
              ["Workflow", s.config.evolus.trial_workflow, "trial plan → engineer approval"],
              ["AI Tool: compare", s.config.evolus.configured, "what changed between recipe revisions"],
              ["Knowledge library", s.config.evolus.library, "archive for the Evolus plant agent"],
              ["Agent (on AMD vLLM)", s.config.evolus.agent, "ask the plant agent"],
            ].map(([n, on, d]) => (
              <div key={String(n)} className="row"><Workflow size={15} /><strong>{n}</strong><span className="muted grow">{d}</span><span className={on ? "c-FENCE" : "muted"}>{on ? "connected" : "not configured"}</span></div>
            ))}
          </div>
          <div className="card card-pad small">
            <strong>Usage</strong>
            {s.evolus.calls ? (
              <>
                <div className="muted" style={{ marginTop: 4 }}>{s.evolus.credits_logged} credits logged of {s.evolus.budget?.toLocaleString()} · cached results: {Object.entries(s.evolus.cached ?? {}).map(([k, v]) => `${k} ${v}`).join(", ")}</div>
                <table className="table" style={{ marginTop: 6 }}>
                  <tbody>{s.evolus.calls.map((c) => <tr key={c.endpoint}><td className="mono tiny">{c.endpoint}</td><td className="num">{c.n} calls</td><td className="num">{c.credits.toFixed(1)} cr</td></tr>)}</tbody>
                </table>
              </>
            ) : <div className="muted">Evolus not configured in this deployment.</div>}
          </div>
        </div>
      </Section>

      <Section title="Security" eyebrow="Public demo">
        <div className="card card-pad small col">
          <div className="row"><ShieldCheck size={15} /> Model and Evolus keys are server-side only; the browser never sees them.</div>
          <div className="row"><ShieldCheck size={15} /> Write and GPU/credit-spending endpoints {s.config.write_protected ? "require the demo passcode and are rate limited" : "are rate limited (set CROMO_ACCESS_TOKEN when public)"}.</div>
          <div className="row"><ShieldCheck size={15} /> Archive text is untrusted data: delimited in prompts, quotes verified verbatim, instruction-like text flagged and excluded.</div>
          <div className="row"><ShieldCheck size={15} /> Recorded AMD runs available for replay: {s.recordings.length} steps.</div>
        </div>
      </Section>
    </div>
  );
}
