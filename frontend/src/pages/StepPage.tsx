import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft, BadgeCheck, CircleX, ClipboardCheck, FileSearch, GitCompare, Play, RotateCcw, ShieldAlert, ShieldCheck, TriangleAlert,
} from "lucide-react";
import { eur, get, post, streamNdjson } from "../api";
import {
  ErrorBox, Skeleton, Spinner, StrengthMeter, VERDICT_HELP, VERDICT_LABEL, VerdictBadge, VerdictIcon, fmtDate, go, timeAgo, useApp,
} from "../components/common";
import type { Cost, Evidence, InvEvent, VerdictData } from "../types";

interface StepInfo {
  step: { id: string; instruction: string; process: string; process_name: string; process_code: string; seq: number };
  verdict: VerdictData | null;
  cost: Cost;
  has_recording: boolean;
}

interface Hop {
  n: number;
  kind: string;
  label: string;
  query?: string | null;
  detail?: string;
  documents?: string[];
  evidence: Evidence[];
  ignored?: string[];
  running: boolean;
  compare?: { a: string; b: string } | null;
}

type Source = "stored" | "live" | "replay";

function hopsFrom(events: InvEvent[]): { hops: Hop[]; verdict: VerdictData | null; concluding: boolean; warnings: string[]; meta: InvEvent | null } {
  const hops: Hop[] = [];
  let verdict: VerdictData | null = null;
  let concluding = false;
  let meta: InvEvent | null = null;
  const warnings: string[] = [];
  for (const ev of events) {
    if (ev.type === "start" || ev.type === "replay") meta = { ...(meta ?? {}), ...ev };
    else if (ev.type === "hop_started") {
      hops.push({ n: ev.n!, kind: ev.kind!, label: ev.label!, query: ev.query, documents: ev.documents, evidence: [], running: true });
    } else if (ev.type === "hop") {
      const h: Hop = {
        n: ev.n!, kind: ev.kind!, label: ev.label!, query: ev.query, detail: ev.detail, documents: ev.documents, evidence: ev.evidence ?? [],
        ignored: ev.ignored_injection, running: false, compare: (ev as unknown as { compare?: { a: string; b: string } }).compare ?? null,
      };
      const i = hops.findIndex((x) => x.n === ev.n);
      if (i >= 0) hops[i] = h;
      else hops.push(h);
    } else if (ev.type === "concluding") concluding = true;
    else if (ev.type === "verdict") {
      verdict = ev.verdict ?? null;
      concluding = false;
    } else if (ev.type === "warning" || ev.type === "error") warnings.push(ev.message ?? "");
  }
  return { hops, verdict, concluding, warnings, meta };
}

export default function StepPage({ stepId, query }: { stepId: string; query: URLSearchParams }) {
  const { mode, openDoc } = useApp();
  const [info, setInfo] = useState<StepInfo | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [events, setEvents] = useState<InvEvent[]>([]);
  const [source, setSource] = useState<Source>("stored");
  const [busy, setBusy] = useState(false);
  const queue = useRef<InvEvent[]>([]);
  const timer = useRef<number | null>(null);
  const abort = useRef<AbortController | null>(null);

  // reveal queued events at a readable pace (live events arrive at model speed anyway)
  const pump = useCallback(() => {
    if (timer.current !== null) return;
    const tick = () => {
      const ev = queue.current.shift();
      if (!ev) {
        timer.current = null;
        return;
      }
      setEvents((e) => [...e, ev]);
      const delay = ev.type === "hop" ? 420 : ev.type === "hop_started" ? 160 : 60;
      timer.current = window.setTimeout(tick, delay);
    };
    tick();
  }, []);

  const push = useCallback(
    (ev: InvEvent) => {
      if (ev.type === "heartbeat") return;
      queue.current.push(ev);
      pump();
    },
    [pump],
  );

  const reset = () => {
    abort.current?.abort();
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = null;
    queue.current = [];
    setEvents([]);
  };

  const showStored = useCallback(async () => {
    reset();
    setSource("stored");
    const r = await get<{ events: InvEvent[] }>(`/api/steps/${stepId}/events`);
    r.events.forEach(push);
  }, [stepId, push]);

  useEffect(() => {
    setInfo(null);
    setErr(null);
    reset();
    get<StepInfo>(`/api/steps/${stepId}`)
      .then((i) => {
        setInfo(i);
        if (query.get("live") === "1") run("live");
        else if (query.get("replay") === "1" && i.has_recording) run("replay");
        else if (i.verdict) showStored().catch(setErr);
      })
      .catch(setErr);
    return () => reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepId]);

  async function run(src: Source) {
    reset();
    setSource(src);
    setBusy(true);
    setErr(null);
    const ctl = new AbortController();
    abort.current = ctl;
    try {
      if (src === "live") await streamNdjson(`/api/steps/${stepId}/investigate`, "POST", push, ctl.signal);
      else await streamNdjson(`/api/steps/${stepId}/replay`, "GET", push, ctl.signal);
      if (src === "live") get<StepInfo>(`/api/steps/${stepId}`).then(setInfo).catch(() => {});
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) setErr(e);
    } finally {
      setBusy(false);
    }
  }

  if (err && !info) return <ErrorBox error={err} />;
  if (!info)
    return (
      <div className="col gap-lg">
        <Skeleton h={30} w="40%" />
        <Skeleton h={60} />
        <Skeleton h={400} />
      </div>
    );

  const { hops, verdict: streamed, concluding, warnings, meta } = hopsFrom(events);
  const v = streamed;
  const st = info.step;
  const running = busy || queue.current.length > 0 || (events.length > 0 && !v && source !== "stored");
  const evidenceById = v?.evidence ?? {};
  const cite = (id: string) => {
    const e = evidenceById[id];
    if (!e) return null;
    return (
      <button key={id} className="cite" title={`${e.acc} · ${e.doc_type ?? ""} · ${fmtDate(e.date)}`}
        onClick={() => openDoc({ acc: e.acc, page: e.page, quote: e.quote })}>
        {e.acc.replace("ACC-", "#")}
      </button>
    );
  };

  return (
    <div>
      <button className="btn ghost sm" onClick={() => go("/")} style={{ marginBottom: 10 }}>
        <ArrowLeft size={15} /> Fossil Map
      </button>
      <div className="eyebrow">
        {st.process_name} · step {st.seq} · <span className="mono">{st.id}</span>
      </div>
      <h1 className="h1" style={{ marginTop: 6, maxWidth: 1050 }}>{st.instruction}</h1>
      <div className="row wrap" style={{ marginTop: 14, gap: 8 }}>
        <span className="lead small" style={{ marginRight: 8 }}>Why does this step exist?</span>
        <button className="btn primary" disabled={running} onClick={() => run("live")}>
          {running && source === "live" ? <Spinner /> : <Play size={16} />}
          {mode === "amd" ? "Investigate live on AMD" : "Run investigation (offline fixture)"}
        </button>
        {info.has_recording && (
          <button className="btn" disabled={running} onClick={() => run("replay")}>
            <RotateCcw size={15} /> Replay recorded AMD run
          </button>
        )}
        {info.verdict && source !== "stored" && !running && (
          <button className="btn ghost" onClick={() => showStored()}>Show last stored result</button>
        )}
      </div>

      {source === "replay" && meta && (
        <div className="banner info small" style={{ marginTop: 14 }}>
          <RotateCcw size={18} />
          <div>
            <strong>Replay of a recorded run on AMD.</strong> Recorded {meta.recorded_at ? new Date(meta.recorded_at * 1000).toLocaleString() : ""}{" "}
            with <span className="mono">{meta.models?.reasoner}</span> on {meta.hardware}. Events are replayed with their original timing so the
            demo survives network or GPU failure; nothing is computed now.
          </div>
        </div>
      )}
      {mode === "fixture" && source !== "replay" && (
        <div className="banner warn small" style={{ marginTop: 14 }}>
          <TriangleAlert size={18} />
          <div>
            <strong>Offline fixture mode.</strong> No AMD model is connected: this trail was produced by CROMO's deterministic rule-based fixture
            provider (a heuristic baseline), not by an LLM. Scanned pages use recorded transcriptions. See System for measured AMD results.
          </div>
        </div>
      )}
      {source === "stored" && v && (
        <div className="tiny muted" style={{ marginTop: 10 }}>
          Showing the stored investigation from {timeAgo(v.created_at)} · {v.hops} hops · {v.duration_s}s · {v.provider === "amd" ? v.model : "fixture provider"}
        </div>
      )}
      <ErrorBox error={err} />

      <div className="inv-grid" style={{ marginTop: 18 }}>
        <div>
          <div className="row" style={{ marginBottom: 10 }}>
            <FileSearch size={18} />
            <h2 className="section-title" style={{ margin: 0 }}>Why-Trail</h2>
            <span className="small muted">every claim must cite an archive document</span>
          </div>
          {!events.length && !running && (
            <div className="card empty">
              <p>This step has not been investigated yet.</p>
              <button className="btn primary" onClick={() => run("live")}><Play size={16} /> Start digging</button>
            </div>
          )}
          <div className="trail">
            {hops.map((h) => (
              <HopCard key={h.n} h={h} />
            ))}
            {(concluding || (running && !hops.some((h) => h.running) && events.length > 0 && !v)) && (
              <div className="hop">
                <div className="hop-marker"><Spinner size={13} /></div>
                <div className="hop-card running small">
                  {concluding ? "Weighing the evidence and checking every citation…" : "Choosing the next lead…"}
                </div>
              </div>
            )}
            {v && (
              <div className="hop">
                <div className="hop-marker" style={{ borderColor: `var(--${v.verdict.toLowerCase()})` }}>
                  <span className={`c-${v.verdict}`} style={{ display: "inline-flex" }}><VerdictIcon v={v.verdict} size={14} /></span>
                </div>
                <div className="hop-card">
                  <div className="hop-head">
                    <span className="hop-kind">Verdict</span>
                    <VerdictBadge v={v.verdict} />
                    <span className="small muted">{v.reason}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
          {warnings.map((w, i) => (
            <div key={i} className="banner warn small" style={{ marginTop: 8 }}><TriangleAlert size={16} /> {w}</div>
          ))}
        </div>

        <div className="sticky">
          {v ? (
            <VerdictCard v={v} cite={cite} />
          ) : (
            <div className="verdict-card">
              <div className="verdict-top">
                <div className="eyebrow">Verdict</div>
                <div className="row" style={{ marginTop: 10 }}>
                  {running ? <Spinner /> : null}
                  <span className="muted">{running ? "Investigation in progress…" : "No verdict yet."}</span>
                </div>
              </div>
              <div className="vsec">
                <h4>Cost of this step</h4>
                <div className="money">{eur(info.cost.annual_eur)}<span className="small muted"> / year</span></div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function HopCard({ h }: { h: Hop }) {
  const { openDoc } = useApp();
  const [cmp, setCmp] = useState<{ loading: boolean; text?: string; err?: string; source?: string } | null>(null);
  const loadCompare = async () => {
    if (!h.compare) return;
    setCmp({ loading: true });
    try {
      const r = await get<{ source: string; result: { output: string } }>(`/api/compare?a=${h.compare.a}&b=${h.compare.b}`);
      setCmp({ loading: false, text: r.result.output, source: r.source });
    } catch (e) {
      setCmp({ loading: false, err: e instanceof Error ? e.message : String(e) });
    }
  };
  return (
    <div className="hop">
      <div className="hop-marker">{h.running ? <Spinner size={13} /> : h.n}</div>
      <div className={`hop-card ${h.running ? "running" : ""}`}>
        <div className="hop-head">
          <span className="hop-kind">{h.label}</span>
          {h.query && <span className="hop-query">{h.query}</span>}
        </div>
        {h.detail && <div className="small muted" style={{ marginTop: 4 }}>{h.detail}</div>}
        {h.documents && h.documents.length > 0 && (
          <div className="row wrap" style={{ gap: 5, marginTop: 8 }}>
            <span className="tiny muted">{h.running ? "Reading" : "Read"}</span>
            {h.documents.map((d) => (
              <button key={d} className="chip mono" onClick={() => openDoc({ acc: d })}>{d}</button>
            ))}
          </div>
        )}
        {h.ignored && h.ignored.length > 0 && (
          <div className="banner danger tiny" style={{ marginTop: 8, padding: "7px 10px" }}>
            <ShieldAlert size={15} /> Instruction-like text in {h.ignored.join(", ")} was treated as data and ignored.
          </div>
        )}
        {!h.running && h.evidence.length === 0 && h.kind !== "recipe" && (
          <div className="tiny muted" style={{ marginTop: 6 }}>Nothing relevant in these documents.</div>
        )}
        {h.evidence.length > 0 && (
          <div className="evidence">
            {h.evidence.map((e) => (
              <EvidenceItem key={e.id} e={e} />
            ))}
          </div>
        )}
        {h.compare && (
          <div style={{ marginTop: 10 }}>
            {!cmp ? (
              <button className="btn sm" onClick={loadCompare}><GitCompare size={14} /> What changed in that revision? (Evolus compare)</button>
            ) : cmp.loading ? (
              <span className="small muted"><Spinner size={13} /> Asking Evolus AI Tool “compare”…</span>
            ) : cmp.err ? (
              <span className="small muted">Evolus compare unavailable: {cmp.err}</span>
            ) : (
              <div className="card card-pad small" style={{ whiteSpace: "pre-wrap", maxHeight: 260, overflow: "auto" }}>
                <div className="eyebrow" style={{ marginBottom: 6 }}>{cmp.source}</div>
                {cmp.text}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function EvidenceItem({ e }: { e: Evidence }) {
  const { openDoc } = useApp();
  return (
    <div className={`ev st-${e.stance} ${e.suspicious ? "suspicious" : ""}`} onClick={() => openDoc({ acc: e.acc, page: e.page, quote: e.quote })}
      role="button" tabIndex={0} onKeyDown={(k) => k.key === "Enter" && openDoc({ acc: e.acc, page: e.page, quote: e.quote })}>
      <div className="ev-quote">“{e.quote}”</div>
      {e.claim && <div className="ev-claim">{e.claim}</div>}
      <div className="ev-meta">
        <span className={`stance ${e.stance}`}>{e.stance === "reason" ? "why introduced" : e.stance === "status" ? "still true?" : e.stance}</span>
        <span className="chip mono">{e.acc}</span>
        <span className="chip">{e.doc_type ?? "document"}</span>
        <span className="chip">{fmtDate(e.date)}</span>
        {e.verified ? (
          <span className="tiny" style={{ color: "var(--ok)", display: "inline-flex", gap: 4, alignItems: "center" }}><BadgeCheck size={13} /> quote verified</span>
        ) : (
          <span className="tiny" style={{ color: "var(--danger)" }}>quote not found in source · not used</span>
        )}
        {e.suspicious && <span className="tiny" style={{ color: "var(--danger)" }}>instruction-like text · ignored</span>}
      </div>
    </div>
  );
}

function VerdictCard({ v, cite }: { v: VerdictData; cite: (id: string) => React.ReactNode }) {
  const [showFormula, setShowFormula] = useState(false);
  const [showBreak, setShowBreak] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const draft = async () => {
    setDrafting(true);
    setErr(null);
    try {
      const t = await post<{ id: string }>("/api/trials", { step_id: v.step_id });
      go(`/trials?id=${t.id}`);
    } catch (e) {
      setErr(e);
    } finally {
      setDrafting(false);
    }
  };
  const costLabel = v.verdict === "FOSSIL" ? "Waste per year" : v.verdict === "FENCE" ? "Cost of protection per year" : "Cost of this step per year";
  return (
    <div className="verdict-card">
      <div className={`verdict-top vt-${v.verdict}`}>
        <div className="eyebrow">Verdict</div>
        <div className={`verdict-word c-${v.verdict}`} style={{ marginTop: 8 }}>
          <VerdictIcon v={v.verdict} size={34} /> {VERDICT_LABEL[v.verdict].toUpperCase()}
        </div>
        <div className="small" style={{ marginTop: 8, color: "var(--text-2)" }}>{VERDICT_HELP[v.verdict]}</div>
        {v.proposed_verdict !== v.verdict && (
          <div className="banner warn tiny" style={{ marginTop: 10, padding: "7px 10px" }}>
            <ShieldCheck size={15} /> Model proposed {v.proposed_verdict}; CROMO's guard rules changed it to {v.verdict}.
          </div>
        )}
        <div className="row" style={{ marginTop: 12 }}>
          <StrengthMeter grade={v.strength.grade} />
          <span className="tiny muted">{v.strength.score} pts · {v.strength.documents} documents</span>
          <span className="grow" />
          <button className="btn ghost sm" onClick={() => setShowBreak(!showBreak)}>{showBreak ? "Hide" : "How graded"}</button>
        </div>
        {showBreak && (
          <div className="small" style={{ marginTop: 8 }}>
            {v.strength.breakdown.map((b, i) => (
              <div key={i} className="row" style={{ justifyContent: "space-between" }}>
                <span>{b.label}</span>
                <span className="mono" style={{ color: b.points < 0 ? "var(--danger)" : "var(--ok)" }}>{b.points > 0 ? "+" : ""}{b.points}</span>
              </div>
            ))}
            <div className="tiny muted" style={{ marginTop: 4 }}>{v.strength.rule}</div>
          </div>
        )}
      </div>
      {v.reason && (
        <div className="vsec">
          <h4>Recovered reason</h4>
          <div>{v.reason}</div>
          {v.origin_year && <div className="small muted" style={{ marginTop: 4 }}>Introduced around {v.origin_year}{v.first_seen ? ` · first in recipes ${v.first_seen.slice(0, 4)}` : ""}</div>}
        </div>
      )}
      {v.chain.length > 0 && (
        <div className="vsec">
          <h4>Reasoning chain</h4>
          <ol className="chain">
            {v.chain.map((c, i) => (
              <li key={i}>{c.claim} {c.evidence.map(cite)}</li>
            ))}
          </ol>
        </div>
      )}
      {v.dependencies.length > 0 && (
        <div className="vsec">
          <h4>Depends on (tripwires)</h4>
          {v.dependencies.map((d, i) => (
            <div key={i} className="dep">
              {d.holds === true ? (
                <span title="still present" style={{ color: "var(--fence)" }}><ShieldCheck size={16} /></span>
              ) : d.holds === false ? (
                <span title="no longer present" style={{ color: "var(--fossil)" }}><CircleX size={16} /></span>
              ) : (
                <span title="unknown" className="muted"><TriangleAlert size={16} /></span>
              )}
              <div className="grow">
                <strong>{d.name}</strong>{" "}
                <span className="muted small">{d.holds === true ? "still present" : d.holds === false ? "no longer present" : "status unknown"}</span>{" "}
                {d.evidence.map(cite)}
                {d.note && <div className="tiny muted">{d.note}</div>}
              </div>
            </div>
          ))}
        </div>
      )}
      {v.counter_evidence.length > 0 && (
        <div className="vsec">
          <h4>Counter-evidence considered</h4>
          {v.counter_evidence.map((c, i) => (
            <div key={i} className="small" style={{ marginBottom: 6 }}>
              <span className={`stance ${c.resolved ? "context" : "counter"}`}>{c.resolved ? "resolved" : "unresolved"}</span> {c.claim} {c.evidence.map(cite)}
              {c.resolution && <div className="tiny muted">{c.resolution}</div>}
            </div>
          ))}
        </div>
      )}
      {v.open_questions.length > 0 && (
        <div className="vsec">
          <h4>Open questions for a human</h4>
          <ul className="chain">{v.open_questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
        </div>
      )}
      <div className="vsec">
        <h4>{costLabel}</h4>
        <div className={`money ${v.verdict === "FOSSIL" ? "c-FOSSIL" : ""}`}>{eur(v.cost.annual_eur)}</div>
        <div className="tiny muted">{v.cost.runs_per_year.toLocaleString()} runs/yr ({v.cost.basis}) × {eur(v.cost.per_run_eur)} per run</div>
        <button className="btn ghost sm" style={{ marginTop: 6, paddingLeft: 0 }} onClick={() => setShowFormula(!showFormula)}>
          {showFormula ? "Hide" : "Show"} formula and inputs
        </button>
        {showFormula && (
          <table className="table" style={{ marginTop: 4 }}>
            <tbody>
              {v.cost.lines.map((l, i) => (
                <tr key={i}>
                  <td>{l.label}<div className="tiny muted">{l.source}</div></td>
                  <td className="num mono tiny">{l.qty.toLocaleString(undefined, { maximumFractionDigits: 2 })} {l.unit} × €{l.unit_cost}</td>
                  <td className="num mono">€{l.amount.toFixed(2)}</td>
                </tr>
              ))}
              <tr><td colSpan={3} className="tiny muted">{v.cost.formula}</td></tr>
            </tbody>
          </table>
        )}
      </div>
      {v.guards.length > 0 && (
        <div className="vsec">
          <h4>Safety checks applied</h4>
          {v.guards.map((g, i) => (
            <div key={i} className="tiny row" style={{ alignItems: "flex-start", marginBottom: 4 }}><ShieldCheck size={13} style={{ flexShrink: 0, marginTop: 2 }} /> {g}</div>
          ))}
        </div>
      )}
      <div className="vsec">
        <div className="row wrap">
          {v.verdict === "FOSSIL" && (
            <button className="btn primary" onClick={draft} disabled={drafting}>
              {drafting ? <Spinner /> : <ClipboardCheck size={16} />} Draft a safe trial
            </button>
          )}
          <button className="btn" onClick={() => go(`/change?p=${encodeURIComponent(`Remove step ${v.step_id}`)}`)}>Before you change…</button>
        </div>
        <ErrorBox error={err} />
        <div className="tiny muted" style={{ marginTop: 10 }}>
          {v.provider === "amd" ? <>Computed on AMD by <span className="mono">{v.model}</span></> : <>Computed by the offline fixture provider (heuristic baseline)</>} ·{" "}
          {v.hops} hops · {v.duration_s}s
          {v.stats ? <> · {v.stats.unverified_quotes} quote(s) rejected by the verifier</> : null}
        </div>
      </div>
    </div>
  );
}
