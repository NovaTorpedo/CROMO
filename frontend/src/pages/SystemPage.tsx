import { useEffect, useState, type ReactNode } from "react";
import { Eye, FlaskConical, Search, ShieldCheck, Sparkles, Workflow } from "lucide-react";
import { get } from "../api";
import { ErrorBox, Skeleton } from "../components/common";

interface Role { configured: boolean; model: string | null; family?: string | null; endpoint_host: string | null }
interface VisSide { model: string; pages: number; failures: number; mean_cer: number | null; cer_by_kind: Record<string, number | null>; p50_ms: number | null }
interface VisCmp { A: VisSide; B: VisSide; verdict?: string; note: string; measured_at: number; hardware: string }
interface OcrRow extends VisSide { interface: string; mean_word_f1: number | null; pages_by_kind: Record<string, number>; word_f1_by_kind: Record<string, number | null> }
interface OcrCmp { models: OcrRow[]; ranking: string[]; note: string; measured_at: number; hardware: string; retried_failed_pages?: number | null }
interface RetrievalSide { steps: number; recall_at_5: number; recall_at_10: number; mrr: number }
interface Retrieval { without_expansion: RetrievalSide; with_expansion: RetrievalSide; metadata_source: string[]; note: string }
interface RsnSide { model: string | null; accuracy: number; fence_recall: number; false_fossil_rate: number; dangerous_errors: string[]; citation_precision: number | null }
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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  benchmark: Record<string, any> | null;
  eval: { amd: EvalRes | null; fixture: EvalRes | null };
  gpu: { source: string; data?: unknown; summary?: string } | null;
  evolus: { calls?: { endpoint: string; n: number; credits: number; ok: number }[]; credits_logged?: number; cached?: Record<string, number>; budget?: number; configured?: boolean };
  recordings: string[];
  vision_comparison?: VisCmp | null;
  ocr_comparison?: OcrCmp | null;
  retrieval_eval?: Retrieval | null;
  reasoner_comparison?: { primary: RsnSide | null; alternative: RsnSide | null } | null;
}

const FAMILY: Record<string, string> = { gemma: "Gemma 4 · Google DeepMind", qwen: "Qwen · Alibaba" };
const pct1 = (x: number | null | undefined) => (x === null || x === undefined ? "–" : `${(x * 100).toFixed(1)}%`);
const pct = (x: number | null | undefined) => (x === null || x === undefined ? "–" : `${Math.round(x * 100)}%`);
const CLASSES = ["FOSSIL", "FENCE", "ACTIVE", "UNKNOWN"];

function Acc({ title, sub, open = false, children }: { title: string; sub?: string; open?: boolean; children: ReactNode }) {
  return (
    <details className="card acc-section" open={open}>
      <summary>{title}{sub && <span className="small muted" style={{ fontWeight: 450, marginLeft: 6 }}>{sub}</span>}</summary>
      <div className="acc-body">{children}</div>
    </details>
  );
}

function OcrTable({ o }: { o: OcrCmp }) {
  const kinds = Array.from(new Set(o.models.flatMap((m) => Object.keys(m.cer_by_kind))));
  const best = o.ranking[0];
  return (
    <>
      <div style={{ overflowX: "auto" }}>
        <table className="table">
          <thead>
            <tr><th>Model</th><th className="num">Strict CER</th><th className="num">Word F1</th>
              {kinds.map((k) => <th key={k} className="num">{k} <span className="muted">(n={o.models[0]?.pages_by_kind?.[k] ?? "?"})</span></th>)}
              <th className="num">p50 / page</th><th className="num">Failures</th></tr>
          </thead>
          <tbody>
            {o.models.map((m) => (
              <tr key={m.model} className={m.model === best ? "best" : ""}>
                <td><span className="mono">{m.model}</span>{/gemma/i.test(m.model) && <span className="pill amd" style={{ marginLeft: 8, padding: "2px 9px" }}><span className="dot" />used by CROMO</span>}
                  <div className="tiny muted">{m.interface}</div></td>
                <td className="num"><strong>{pct1(m.mean_cer)}</strong></td>
                <td className="num">{pct1(m.mean_word_f1)}</td>
                {kinds.map((k) => <td key={k} className="num">{pct1(m.cer_by_kind[k])}</td>)}
                <td className="num">{m.p50_ms != null ? `${(m.p50_ms / 1000).toFixed(1)} s` : "–"}</td>
                <td className="num">{m.failures}/{m.pages}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="tiny muted" style={{ marginTop: 8 }}>{o.note}{o.retried_failed_pages ? ` Pages that failed with a transient server error were retried once (${o.retried_failed_pages}).` : ""} Measured {new Date(o.measured_at * 1000).toLocaleString()}.</div>
    </>
  );
}

function VisionAB({ v }: { v: VisCmp }) {
  const kinds = Array.from(new Set([...Object.keys(v.A.cer_by_kind), ...Object.keys(v.B.cer_by_kind)]));
  return (
    <>
      <table className="table">
        <thead><tr><th>Vision model</th><th>Mean CER</th>{kinds.map((k) => <th key={k}>{k}</th>)}<th>p50</th><th>Failures</th></tr></thead>
        <tbody>
          {(["A", "B"] as const).map((t) => (
            <tr key={t}>
              <td className="mono">{v[t].model}</td><td><strong>{pct1(v[t].mean_cer)}</strong></td>
              {kinds.map((k) => <td key={k}>{pct1(v[t].cer_by_kind[k])}</td>)}
              <td>{v[t].p50_ms != null ? `${v[t].p50_ms} ms` : "–"}</td><td>{v[t].failures}/{v[t].pages}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="small" style={{ marginTop: 8 }}>{v.verdict ?? "No verdict: a model failed on every page."} <span className="muted tiny">{v.note} {v.hardware}</span></div>
    </>
  );
}

function EvalCard({ e, title }: { e: EvalRes; title: string }) {
  return (
    <div className="card card-pad">
      <div className="row wrap">
        <strong>{title}</strong>
        <span className={`pill ${e.provider === "amd" ? "amd" : "fixture"}`}><span className="dot" />{e.provider === "amd" ? "measured on AMD" : "heuristic baseline · no LLM"}</span>
      </div>
      <div className="tiny muted" style={{ marginTop: 4 }}>{e.label} · {e.hardware} · {new Date(e.evaluated_at * 1000).toLocaleString()}</div>
      <div className="grid-3" style={{ marginTop: 14 }}>
        <div><div className="eyebrow">FENCE recall</div><div className="big-n c-FENCE">{pct(e.fence_recall)}</div><div className="tiny muted">missing a fence is the dangerous error</div></div>
        <div><div className="eyebrow">False-FOSSIL rate</div><div className="big-n c-FOSSIL">{pct(e.false_fossil_rate)}</div><div className="tiny muted">non-fossils wrongly called waste</div></div>
        <div><div className="eyebrow">Accuracy · 4 classes</div><div className="big-n">{pct(e.accuracy)}</div><div className="tiny muted">{e.n_steps} steps</div></div>
      </div>
      {e.dangerous_errors.length > 0 && <div className="small" style={{ color: "var(--danger)", marginTop: 8 }}>Fences called fossils: {e.dangerous_errors.join(", ")}</div>}
      <details style={{ marginTop: 12 }}>
        <summary>Per class, confusion matrix, citations, tripwires, change checks</summary>
        <div className="grid-2" style={{ marginTop: 10 }}>
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
          <div><strong>Before you change</strong><div className="muted">{pct(e.change_checks.accuracy)} decisions correct · prompt-injection test {e.injection.passed ? "passed" : "FAILED"}</div></div>
        </div>
      </details>
    </div>
  );
}

function WhereCard({ icon, role, model, family, where, note }: { icon: ReactNode; role: string; model: string; family?: string | null; where: string; note: string }) {
  return (
    <div className="card">
      <div className="row"><span className="muted">{icon}</span><span className="role">{role}</span></div>
      <div className="model">{model}</div>
      {family && FAMILY[family] && <div style={{ marginTop: 6 }}><span className={`pill ${family === "gemma" ? "amd" : ""}`} style={{ padding: "2px 10px" }}><span className="dot" />{FAMILY[family]}</span></div>}
      <div className="small" style={{ marginTop: 10 }}>{where}</div>
      <div className="tiny muted" style={{ marginTop: 4 }}>{note}</div>
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
  const tf = (b?.route ?? s.config.amd_route) === "tokenfactory";
  const endpoint = tf ? "AMD Token Factory · shared endpoints on AMD GPUs" : s.config.hardware;
  const roles = s.config.roles;
  const benchModels = (b?.models ?? {}) as Record<string, string>;
  // only what runs here (live) or what the recorded benchmark measured; configured-but-offline names are not shown
  const reasoner = live && roles.reasoner?.configured ? roles.reasoner.model! : benchModels.reasoner ?? "offline fixture (no model)";
  const vision = live && roles.vision?.configured ? roles.vision.model! : b?.vision_accuracy?.mean_cer != null ? benchModels.vision : "recorded transcriptions";
  const embeddings = live && roles.embeddings?.configured ? roles.embeddings.model! : b && !/local|fixture/.test(benchModels.embeddings ?? "local") ? benchModels.embeddings : null;
  const family = (m: string) => (/gemma/i.test(m) ? "gemma" : /qwen/i.test(m) ? "qwen" : null);
  const evalAmd = s.eval.amd;
  const usage = b?.tokenfactory_usage;
  const readP50 = ((b?.latency ?? []) as Lat[]).find((l) => l.stage === "investigate.read")?.p50_ms;
  const dur = (s: number) => (s < 120 ? `${Math.round(s)}s` : `${Math.round(s / 60)} min`);
  const r = s.retrieval_eval;

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">System · where CROMO runs</div>
        <h1 className="h1" style={{ marginTop: 6 }}>{live ? "Running on AMD." : b ? "Measured on AMD. Showing recorded results." : "Offline fixture mode."}</h1>
        <p className="lead">
          {live || b
            ? tf
              ? "Every model call goes to the AMD Token Factory: OpenAI-compatible endpoints served on AMD GPUs. Google DeepMind's open Gemma 4 reads the scanned pages and does all the reasoning."
              : "Every model call goes to vLLM on ROCm on an AMD Instinct MI300X."
            : "No AMD endpoint is configured here. A deterministic fixture provider stands in for the models so the product runs end to end; its numbers are labelled as a heuristic baseline."}
        </p>
      </div>

      <div className="where">
        <WhereCard icon={<Sparkles size={16} />} role="Reasoner" model={reasoner} family={family(reasoner)} where={live || b ? endpoint : "not connected: offline fixture"}
          note="Reads passages, proposes leads and verdicts, parses change proposals; native tool calling for agents." />
        <WhereCard icon={<Eye size={16} />} role="Vision" model={vision} family={family(vision)} where={(live && roles.vision?.configured) || b?.vision_accuracy?.mean_cer != null ? endpoint : "not connected: recorded transcriptions"}
          note="Transcribes every scanned, faxed and handwritten page of the archive." />
        <WhereCard icon={<Search size={16} />} role="Retrieval" model={embeddings ?? "BM25 + n-grams + Gemma keywords"} family={null}
          where={embeddings ? endpoint : live || b ? "Index on the CROMO server (CPU); keywords written by the reasoner on AMD" : "Index on the CROMO server (CPU)"}
          note={embeddings ? "Multilingual embeddings." : "The Token Factory serves no embedding model: lexical hybrid retrieval, made bilingual by Gemma's English + Italian keywords per document."} />
      </div>

      <div className="kpis" style={{ marginTop: 14 }}>
        <div className="card kpi">
          <div className="big-n">{b?.investigation?.p50_s != null ? dur(b.investigation.p50_s) : "–"}</div>
          <div className="l">median investigation</div>
          <div className="s">{b?.investigation ? `p95 ${dur(b.investigation.p95_s)} · ${b.investigation.calls_per_step ?? "–"} model calls per step${readP50 ? `, ${Math.round(readP50 / 1000)} s each at the median` : ""} · ${b.investigation.concurrency} at a time` : "not measured yet"}</div>
        </div>
        <div className="card kpi">
          <div className="big-n">{b?.ingest?.pages_per_min ?? "–"}</div>
          <div className="l">archive pages / minute ingested</div>
          <div className="s">{b?.vision_accuracy?.mean_cer != null ? `${b.ingest?.scanned_pages} scanned pages read by the vision model · CER ${pct1(b.vision_accuracy.mean_cer)}` : "not measured yet"}</div>
        </div>
        <div className="card kpi">
          <div className="big-n c-FENCE">{evalAmd ? pct(evalAmd.fence_recall) : "–"}</div>
          <div className="l">FENCE recall on the planted truth</div>
          <div className="s">{evalAmd ? `accuracy ${pct(evalAmd.accuracy)} · false-FOSSIL ${pct(evalAmd.false_fossil_rate)} · ${evalAmd.n_steps} steps` : "AMD evaluation pending"}</div>
        </div>
        <div className="card kpi">
          <div className="big-n">{usage ? `$${usage.metered_usd.toFixed(2)}` : b?.cost?.per_plant_audit_usd != null ? `$${b.cost.per_plant_audit_usd}` : "–"}</div>
          <div className="l">{usage ? "metered for a full plant audit" : "GPU cost per full plant audit"}</div>
          <div className="s">{usage ? `${usage.requests} requests · ${(usage.tokens / 1e6).toFixed(2)}M tokens · Token Factory meter (free during the event)` : b?.cost?.basis ?? "not measured yet"}</div>
        </div>
      </div>
      {b?.complete === false && (
        <div className="note warn small" style={{ marginTop: 12 }}><FlaskConical size={18} /><div><strong>Partial run.</strong> {b.note ?? `${b.investigation?.steps} of ${b.investigation?.of_steps} steps measured on AMD.`}</div></div>
      )}
      {!b && <div className="note warn small" style={{ marginTop: 12 }}><FlaskConical size={18} /><div><strong>Not measured yet.</strong> Run <span className="mono">scripts/benchmark_amd.py</span> once AMD is linked; CROMO never shows invented numbers.</div></div>}
      {b?.ingest?.note && <div className="tiny muted" style={{ marginTop: 8 }}>{b.ingest.note}</div>}

      <div style={{ marginTop: 26 }}>
        <Acc title="Which model reads the archive best?" sub={s.ocr_comparison ? `${s.ocr_comparison.models.length} AMD-hosted models on ${s.ocr_comparison.models[0]?.pages} scanned pages` : "pending"} open>
          {s.ocr_comparison ? <OcrTable o={s.ocr_comparison} /> : <div className="small muted">Run <span className="mono">scripts/compare_models.py ocr</span>. No numbers are shown until they are measured.</div>}
          {s.vision_comparison && <div style={{ marginTop: 16 }}><div className="eyebrow" style={{ marginBottom: 6 }}>Own vLLM A/B</div><VisionAB v={s.vision_comparison} /></div>}
        </Acc>
        <Acc title="Evaluation against the planted ground truth" sub="49 steps · 12 fossils · 9 fences · 22 active · 6 unknown">
          <div className="col">
            {evalAmd ? <EvalCard e={evalAmd} title="CROMO on AMD" /> : <div className="note warn small"><FlaskConical size={18} /><div><strong>AMD evaluation pending.</strong></div></div>}
            {s.reasoner_comparison?.primary && s.reasoner_comparison.alternative && (
              <div className="card card-pad small">Reasoner A/B: {[s.reasoner_comparison.primary, s.reasoner_comparison.alternative].map((x) => `${x!.model}: accuracy ${pct(x!.accuracy)}, FENCE recall ${pct(x!.fence_recall)}`).join(" · ")}</div>
            )}
            {s.eval.fixture && <EvalCard e={s.eval.fixture} title="Rule-based heuristic baseline (offline fixture provider)" />}
            <div className="small muted">The archive is synthetic. The ground truth lives in <span className="mono">eval/ground_truth.json</span>, which the product never reads (enforced by tests). Results on a synthetic archive do not guarantee results on a real plant.</div>
          </div>
        </Acc>
        {r && (
          <Acc title="Retrieval without an embedding model" sub={`first key document ranked higher with Gemma's keywords: MRR ${r.without_expansion.mrr.toFixed(2)} → ${r.with_expansion.mrr.toFixed(2)}`}>
            <table className="table">
              <thead><tr><th>Index</th><th className="num">Recall@5</th><th className="num">Recall@10</th><th className="num">MRR</th></tr></thead>
              <tbody>
                <tr><td>BM25 + local hashed n-grams</td><td className="num">{pct(r.without_expansion.recall_at_5)}</td><td className="num">{pct(r.without_expansion.recall_at_10)}</td><td className="num">{r.without_expansion.mrr}</td></tr>
                <tr><td>+ bilingual keywords and summary from the reasoner</td><td className="num"><strong>{pct(r.with_expansion.recall_at_5)}</strong></td><td className="num"><strong>{pct(r.with_expansion.recall_at_10)}</strong></td><td className="num"><strong>{r.with_expansion.mrr}</strong></td></tr>
              </tbody>
            </table>
            <div className="tiny muted" style={{ marginTop: 8 }}>{r.note} Query: each step's instruction; target: its key documents in the planted truth ({r.with_expansion.steps} steps).</div>
          </Acc>
        )}
        <Acc title="Latency per stage" sub={live ? "this server, live metrics" : "metrics stored on this server"}>
          <div style={{ maxHeight: 360, overflow: "auto" }}>
            <table className="table">
              <thead><tr><th>Stage</th><th>Model</th><th className="num">Calls</th><th className="num">p50 ms</th><th className="num">p95 ms</th><th className="num">Tokens in / out</th></tr></thead>
              <tbody>
                {(b?.latency ?? s.latency.filter((l) => l.provider === (live ? "amd" : "fixture"))).map((l: Lat, i: number) => (
                  <tr key={i}><td className="mono">{l.stage}</td><td className="mono tiny">{l.model}</td><td className="num">{l.calls}</td><td className="num">{Math.round(l.p50_ms).toLocaleString()}</td><td className="num">{Math.round(l.p95_ms).toLocaleString()}</td><td className="num tiny">{l.tokens_in.toLocaleString()} / {l.tokens_out.toLocaleString()}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="tiny muted" style={{ marginTop: 6 }}>Latency is the duration of each successful request; time spent queueing behind CROMO's own rate limiter is not counted.{tf ? " The Token Factory is shared by every event participant, so latency depends on its load." : ""}</div>
          {s.gpu && <pre className="code" style={{ marginTop: 10, maxHeight: 200 }}>{s.gpu.summary ?? JSON.stringify(s.gpu.data, null, 1)}</pre>}
        </Acc>
        <Acc title="Evolus building blocks" sub="driven through the Evolus REST API">
          <div className="grid-2">
            <div className="col small">
              {[
                ["Workflow", s.config.evolus.trial_workflow, "trial plan → engineer approval"],
                ["AI Tool: compare", s.config.evolus.configured, "what changed between recipe revisions"],
                ["Knowledge library", s.config.evolus.library, "the archive for the Evolus plant agent"],
                ["Document extractor", s.config.evolus.extractor, "archive documents → structured records"],
                ["Agent", s.config.evolus.agent, "plant agent on our own AMD model"],
              ].map(([n, on, d]) => (
                <div key={String(n)} className="row"><Workflow size={15} /><strong>{n}</strong><span className="muted grow">{d}</span><span className={on ? "c-FENCE" : "muted"}>{on ? "connected" : "not configured"}</span></div>
              ))}
            </div>
            <div className="small">
              {s.evolus.calls ? (
                <>
                  <div className="muted">{s.evolus.credits_logged} credits logged of {s.evolus.budget?.toLocaleString()} · cached results: {Object.entries(s.evolus.cached ?? {}).map(([k, v]) => `${k} ${v}`).join(", ")}</div>
                  <table className="table" style={{ marginTop: 6 }}>
                    <tbody>{s.evolus.calls.map((c) => <tr key={c.endpoint}><td className="mono tiny">{c.endpoint}</td><td className="num">{c.n} calls</td><td className="num">{c.credits.toFixed(1)} cr</td></tr>)}</tbody>
                  </table>
                </>
              ) : <div className="muted">Evolus usage is shown on a deployment with Evolus configured.</div>}
            </div>
          </div>
        </Acc>
        <Acc title="Security">
          <div className="col small">
            <div className="row"><ShieldCheck size={15} /> Model and Evolus keys are server-side only; the browser never sees them.</div>
            <div className="row"><ShieldCheck size={15} /> Write and model/credit-spending endpoints {s.config.write_protected ? "require the demo passcode and are rate limited" : "are rate limited (set CROMO_ACCESS_TOKEN when public)"}.</div>
            <div className="row"><ShieldCheck size={15} /> Archive text is untrusted data: delimited in prompts, quotes verified verbatim, instruction-like text flagged and excluded.</div>
            <div className="row"><ShieldCheck size={15} /> Recorded AMD runs available for replay: {s.recordings.length} steps.</div>
          </div>
        </Acc>
      </div>
    </div>
  );
}
