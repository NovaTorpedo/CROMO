import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowLeft, CircleX, ClipboardCheck, FileSearch, GitCompare, Play, RotateCcw, Scale, ShieldAlert, ShieldCheck, TriangleAlert } from "lucide-react";
import { eur, get, post, streamNdjson } from "../api";
import VeteranCard from "../components/VeteranCard";
import { ErrorBox, Skeleton, Spinner, StrengthMeter, VERDICT_LABEL, VerdictIcon, fmtDate, go, timeAgo, useApp } from "../components/common";
import { keyEvidence, parseTrail, progress, type Hop } from "../lib/trail";
import type { Cost, Evidence, InvEvent, Verdict, VerdictData } from "../types";

interface StepInfo {
  step: { id: string; name?: string; instruction: string; process: string; process_name: string; process_code: string; seq: number };
  verdict: VerdictData | null;
  cost: Cost;
  has_recording: boolean;
}
type Source = "stored" | "live" | "replay";
type View = "key" | "dig";

const HEADLINE: Record<Verdict, string> = {
  FOSSIL: "The reason for this step is gone.",
  FENCE: "It looks pointless, but it protects you.",
  UNKNOWN: "Nobody wrote down why. Ask a person.",
  ACTIVE: "Still needed, for a documented reason.",
  PENDING: "Not investigated yet.",
};
const TAG: Record<string, [string, string]> = {
  reason: ["reason", "Why it was introduced"],
  status: ["status", "Is it still true?"],
  counter: ["counter", "Warning sign"],
  context: ["context", "Context"],
};

export default function StepPage({ stepId, query }: { stepId: string; query: URLSearchParams }) {
  const { mode, demo, amdRoute } = useApp();
  const [info, setInfo] = useState<StepInfo | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [events, setEvents] = useState<InvEvent[]>([]);
  const [source, setSource] = useState<Source>("stored");
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<View>("key");
  const queue = useRef<InvEvent[]>([]);
  const timer = useRef<number | null>(null);
  const abort = useRef<AbortController | null>(null);

  const pump = useCallback(() => {
    if (timer.current !== null) return;
    const tick = () => {
      const ev = queue.current.shift();
      if (!ev) {
        timer.current = null;
        return;
      }
      setEvents((e) => [...e, ev]);
      timer.current = window.setTimeout(tick, ev.type === "hop" ? 380 : ev.type === "hop_started" ? 140 : 40);
    };
    tick();
  }, []);
  const push = useCallback((ev: InvEvent) => {
    if (ev.type === "heartbeat") return;
    queue.current.push(ev);
    pump();
  }, [pump]);
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
    setView("key");
    const r = await get<{ events: InvEvent[] }>(`/api/steps/${stepId}/events`);
    setEvents(r.events.filter((e) => e.type !== "heartbeat")); // stored results appear at once
  }, [stepId]);

  async function run(src: Source) {
    if (src === "live" && demo && info?.has_recording) src = "replay";
    reset();
    setSource(src);
    setView("dig");
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

  function runReplayFor(i: StepInfo) {
    setInfo(i);
    run("replay");
  }

  useEffect(() => {
    setInfo(null);
    setErr(null);
    reset();
    get<StepInfo>(`/api/steps/${stepId}`)
      .then((i) => {
        setInfo(i);
        if (query.get("live") === "1") (demo && i.has_recording ? runReplayFor(i) : run("live"));
        else if (query.get("replay") === "1" && i.has_recording) run("replay");
        else if (i.verdict) showStored().catch(setErr);
      })
      .catch(setErr);
    return () => reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepId]);

  if (err && !info) return <ErrorBox error={err} />;
  if (!info)
    return (
      <div className="col" style={{ gap: 18 }}>
        <Skeleton h={40} w="45%" />
        <Skeleton h={170} />
        <Skeleton h={400} />
      </div>
    );

  const trail = parseTrail(events);
  const { hops, verdict: v, concluding, meta, ignored, warnings } = trail;
  const key = keyEvidence(trail);
  const st = info.step;
  const running = busy || (events.length > 0 && !v && source !== "stored");
  const shown: Verdict = v?.verdict ?? "PENDING";
  const docsRead = new Set(hops.flatMap((h) => h.documents ?? [])).size;
  const current = [...hops].reverse().find((h) => h.running) ?? hops[hops.length - 1];
  const where = amdRoute === "tokenfactory" ? "the AMD Token Factory" : "AMD";
  const effView: View = running ? "dig" : view;

  return (
    <div>
      <button className="crumb" onClick={() => go("/")}><ArrowLeft size={15} /> Plant map</button>
      <div className="step-head">
        <div className="eyebrow">{st.process_code} {st.process_name.replace(/^\S+\s/, "")} · step {st.seq} · {st.id}</div>
        <h1 className="h1" style={{ marginTop: 6 }}>{st.name ?? st.id}</h1>
        <div className="instr">“{st.instruction}”</div>
      </div>

      {/* ------------------------------------------------ verdict hero */}
      <div className={`verdict-hero panel h-${shown} fade-in`}>
        <div className={`vtile t-${shown}`}>
          {running && !v ? <Spinner size={28} /> : <VerdictIcon v={shown} size={32} />}
          <span>{running && !v ? "DIGGING" : VERDICT_LABEL[shown].toUpperCase()}</span>
        </div>
        <div>
          {v ? (
            <>
              <div className="v-headline">{HEADLINE[v.verdict]}</div>
              {v.reason && <div className="v-reason">{v.reason}</div>}
              <div className="v-facts">
                {v.origin_year && <span className="fact">Introduced <strong>{v.origin_year}</strong></span>}
                <span className="fact">Evidence <StrengthMeter grade={v.strength.grade} /> <span className="muted">{v.strength.documents} documents</span></span>
                {v.proposed_verdict !== v.verdict && <span className="fact c-UNKNOWN">A safety rule changed the model's {v.proposed_verdict} to {v.verdict}</span>}
              </div>
            </>
          ) : running ? (
            <>
              <div className="v-headline">Digging through the archive…</div>
              <div className="v-reason">{current ? `${current.label}${current.query ? ": " + current.query.replace(/^Search: /, "") : ""}` : "Opening the recipe history"}</div>
            </>
          ) : (
            <>
              <div className="v-headline">Why does this step exist?</div>
              <div className="v-reason">CROMO will search the plant archive, follow the references it finds, and cite every claim.</div>
            </>
          )}
        </div>
        <div style={{ textAlign: "right" }}>
          <div className={`money ${shown === "FOSSIL" ? "c-FOSSIL" : ""}`}>{eur((v?.cost ?? info.cost).annual_eur)}</div>
          <div className="small muted">{shown === "FOSSIL" ? "wasted per year" : shown === "FENCE" ? "cost of protection / yr" : "cost per year"}</div>
          <div className="row" style={{ justifyContent: "flex-end", marginTop: 14, gap: 8 }}>
            {v?.verdict === "FOSSIL" && <DraftTrial stepId={st.id} />}
            {v && <button className="btn sm" onClick={() => go(`/change?p=${encodeURIComponent(`Remove step ${st.id}`)}`)}><Scale size={14} /> Check a change</button>}
            {!v && !running && <button className="btn accent" onClick={() => run("live")}><Play size={15} /> Investigate</button>}
          </div>
        </div>
      </div>

      {/* ------------------------------------------------ provenance */}
      <div className="provenance">
        {source === "replay" && meta ? (
          <span className="note info" style={{ padding: "5px 12px" }}>
            <RotateCcw size={14} /> Replay of a run recorded on AMD {meta.recorded_at ? new Date(meta.recorded_at * 1000).toLocaleDateString() : ""} ·{" "}
            {meta.models?.reasoner} · {meta.hardware}
          </span>
        ) : mode === "fixture" && v?.provider !== "amd" ? (
          <span>Offline mode: this result comes from CROMO's rule-based fixture provider, not from an AI model.</span>
        ) : v ? (
          <span>Computed on {v.provider === "amd" ? where : "this machine"} by {v.model} · {v.hops} hops · {fmtDur(v.duration_s)}</span>
        ) : null}
        {v && source === "stored" && <span>· {timeAgo(v.created_at)}</span>}
        <span className="grow" />
        {!running && v && (
          <button className="btn ghost sm" onClick={() => run("live")}><Play size={14} /> Investigate again{mode === "fixture" ? " (offline)" : ""}</button>
        )}
        {!running && info.has_recording && <button className="btn ghost sm" onClick={() => run("replay")}><RotateCcw size={14} /> Replay AMD run</button>}
      </div>
      <ErrorBox error={err} />

      {running && (
        <div className="progress glass fade-in" style={{ marginTop: 18 }}>
          <Spinner />
          <div className="grow">
            <div className="row small"><strong>Hop {hops.length || 1}</strong><span className="muted">· {docsRead} documents read · {trail.evidence.length} verified quotes</span></div>
            <div className="bar" style={{ marginTop: 8 }}><i style={{ width: `${progress(trail)}%` }} /></div>
          </div>
        </div>
      )}

      <div className="inv-grid">
        <div>
          <div className="row wrap" style={{ alignItems: "flex-end" }}>
            <div className="grow">
              <h2 className="section-title">The Why-Trail</h2>
              <div className="small muted">Every claim is a quote verified in an archive document. Open any card to see the page.</div>
            </div>
            {hops.length > 0 && (
              <div className="seg" role="tablist" aria-label="Trail view">
                <button role="tab" aria-selected={effView === "key"} className={effView === "key" ? "on" : ""} disabled={running} onClick={() => setView("key")}>Key evidence</button>
                <button role="tab" aria-selected={effView === "dig"} className={effView === "dig" ? "on" : ""} onClick={() => setView("dig")}>Full dig · {hops.length} hops</button>
              </div>
            )}
          </div>

          {hops.length === 0 && !running && (
            <div className="card empty" style={{ marginTop: 16 }}>No evidence yet. Press <strong>Investigate</strong> to start digging.</div>
          )}

          {effView === "key" ? (
            <div className="timeline">
              {key.map((e) => <TimelineItem key={e.id + e.acc} e={e} />)}
              {v && key.length < trail.evidence.length && (
                <button className="btn ghost sm" style={{ marginLeft: 80 }} onClick={() => setView("dig")}>
                  <FileSearch size={14} /> {trail.evidence.length - key.length} more quote{trail.evidence.length - key.length === 1 ? "" : "s"} CROMO read but did not rely on
                </button>
              )}
            </div>
          ) : (
            <div className="trail">
              {hops.map((h) => <HopItem key={h.n} h={h} />)}
              {concluding && (
                <div className="hop running fade-in"><div className="hop-n"><Spinner size={14} /></div>
                  <div className="hop-body"><div className="hop-title"><strong>Weighing the evidence</strong><span className="q">the model proposes a verdict; the rules decide what may be removed</span></div></div></div>
              )}
            </div>
          )}

          {ignored.length > 0 && (
            <div className="note danger" style={{ marginTop: 10 }}>
              <ShieldAlert size={18} style={{ flexShrink: 0 }} />
              <div><strong>Ignored instruction-like text</strong> in {ignored.join(", ")}. Archive content is treated as data, never as instructions.</div>
            </div>
          )}
          {warnings.map((w, i) => <div key={i} className="note warn" style={{ marginTop: 8 }}><TriangleAlert size={16} /> {w}</div>)}
          {v && !running && (v.verdict === "UNKNOWN" || v.strength.grade === "Weak") && (
            <VeteranCard stepId={st.id} onRecorded={() => run("live")} />
          )}
        </div>

        <aside className="side panel sticky">{v ? <Side v={v} /> : <div className="small muted" style={{ padding: "14px 0" }}>Details appear when the investigation is complete.</div>}</aside>
      </div>
    </div>
  );
}

/** "42s", "6 min", "58 min" */
export function fmtDur(s: number) {
  return s < 120 ? `${Math.round(s)}s` : `${Math.round(s / 60)} min`;
}

function sameText(claim: string, quote: string) {
  const n = (x: string) => x.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  return n(claim).includes(n(quote).slice(0, 40));
}

function EvidenceCard({ e, compact = false }: { e: Evidence; compact?: boolean }) {
  const { openDoc } = useApp();
  const [cls, label] = TAG[e.stance] ?? TAG.context;
  const open = () => openDoc({ acc: e.acc, page: e.page, quote: e.quote });
  return (
    <div className={`tl-card ${e.suspicious ? "suspicious" : ""}`} onClick={open} role="button" tabIndex={0}
      onKeyDown={(k) => (k.key === "Enter" || k.key === " ") && open()} aria-label={`Open ${e.acc}`}>
      <div className="tl-meta">
        <span className={`tl-tag ${cls}`}>{e.doc_type === "recipe" && e.stance === "context" ? "Recipe" : e.doc_type === "interview record" ? "Testimony" : label}</span>
        <span style={{ textTransform: "capitalize" }}>{e.doc_type ?? "document"}</span>
        <span>· {fmtDate(e.date)}</span>
        <span>· {e.acc}</span>
      </div>
      <div className="quote" style={compact ? { fontSize: 14.5 } : undefined}>“{e.quote}”</div>
      {e.claim && e.stance !== "context" && !sameText(e.claim, e.quote) && <div className="claim">{e.claim}</div>}
    </div>
  );
}

function TimelineItem({ e }: { e: Evidence }) {
  return (
    <div className="tl-item fade-in">
      <div className="tl-year">{e.date ? e.date.slice(0, 4) : "–"}</div>
      <div className={`tl-dot st-${e.stance}`} />
      <EvidenceCard e={e} />
    </div>
  );
}

function HopItem({ h }: { h: Hop }) {
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
  const what = h.query ? h.query.replace(/^Search: /, "") : h.detail;
  return (
    <div className={`hop k-${h.kind} ${h.running ? "running" : ""} fade-in`}>
      <div className="hop-n">{h.running ? <Spinner size={14} /> : h.n}</div>
      <div className="hop-body">
        <div className="hop-title">
          <strong>{h.label}</strong>
          {what && <span className="q">{what}</span>}
          <span className="tiny muted">· {h.running ? "reading…" : `${h.evidence.length} verified of ${h.found}`}</span>
        </div>
        {h.evidence.length > 0 && <div className="hop-ev">{h.evidence.map((e) => <EvidenceCard key={e.id + e.acc} e={e} compact />)}</div>}
        {h.compare && (
          <div style={{ marginTop: 10 }}>
            {!cmp ? (
              <button className="btn sm" onClick={loadCompare}><GitCompare size={14} /> What changed when this step was added? (Evolus AI Tool)</button>
            ) : cmp.loading ? (
              <span className="small muted"><Spinner size={13} /> Asking the Evolus “compare” tool…</span>
            ) : cmp.err ? (
              <span className="small muted">Evolus compare unavailable: {cmp.err}</span>
            ) : (
              <div className="card small" style={{ whiteSpace: "pre-wrap", maxHeight: 300, overflow: "auto", padding: 14 }}>
                <div className="tiny muted" style={{ marginBottom: 6 }}>{cmp.source}</div>
                {cmp.text}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Side({ v }: { v: VerdictData }) {
  const { openDoc } = useApp();
  const cite = (id: string): ReactNode => {
    const e = v.evidence[id];
    if (!e) return null;
    return <button key={id} className="cite" title={`${e.doc_type ?? ""} · ${fmtDate(e.date)}`} onClick={() => openDoc({ acc: e.acc, page: e.page, quote: e.quote })}>{e.date?.slice(0, 4) ?? e.acc}</button>;
  };
  return (
    <>
      {v.dependencies.length > 0 && (
        <div className="blk">
          <h4>What the reason depends on</h4>
          {v.dependencies.map((d, i) => (
            <div key={i} className="dep">
              {d.holds === true ? <span style={{ color: "var(--fence)" }}><ShieldCheck size={17} /></span>
                : d.holds === false ? <span style={{ color: "var(--fossil)" }}><CircleX size={17} /></span>
                : <span className="muted"><TriangleAlert size={17} /></span>}
              <div>
                <div><strong>{d.name}</strong></div>
                <div className="small muted">{d.holds === true ? "still present" : d.holds === false ? "no longer present" : "status unknown"} {d.evidence.map(cite)}</div>
              </div>
            </div>
          ))}
          <div className="tiny muted" style={{ marginTop: 6 }}>CROMO watches these. If one changes, What if → Change the plant raises an alert.</div>
        </div>
      )}
      <div className="blk">
        <h4>How sure are we?</h4>
        <div className="row"><StrengthMeter grade={v.strength.grade} /><span className="small muted">{v.strength.score} points · {v.strength.documents} documents</span></div>
        <details style={{ marginTop: 8 }}>
          <summary>Scoring rules</summary>
          <div className="small" style={{ marginTop: 6 }}>
            {v.strength.breakdown.map((b, i) => (
              <div key={i} className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                <span>{b.label}</span><span style={{ color: b.points < 0 ? "var(--danger)" : "var(--ok)", fontWeight: 650 }}>{b.points > 0 ? "+" : ""}{b.points}</span>
              </div>
            ))}
            <div className="tiny muted" style={{ marginTop: 4 }}>{v.strength.rule}</div>
          </div>
        </details>
      </div>
      {v.counter_evidence.length > 0 && (
        <div className="blk">
          <details>
            <summary><h4 style={{ margin: 0 }}>Counter-evidence considered ({v.counter_evidence.length})</h4></summary>
            {v.counter_evidence.map((c, i) => (
              <div key={i} className="small" style={{ margin: "8px 0" }}>
                <span className={`tl-tag ${c.resolved ? "context" : "counter"}`}>{c.resolved ? "resolved" : "open"}</span> {c.claim} {c.evidence.map(cite)}
                {c.resolution && <div className="tiny muted">{c.resolution}</div>}
              </div>
            ))}
          </details>
        </div>
      )}
      {v.open_questions.length > 0 && (
        <div className="blk">
          <h4>Questions for a person</h4>
          {v.open_questions.map((q, i) => <div key={i} className="small" style={{ marginBottom: 4 }}>{q}</div>)}
        </div>
      )}
      <div className="blk">
        <h4>Cost</h4>
        <div className="small">{v.cost.runs_per_year.toLocaleString()} runs a year × {eur(v.cost.per_run_eur)} = <strong>{eur(v.cost.annual_eur)}</strong></div>
        <details style={{ marginTop: 8 }}>
          <summary>Inputs</summary>
          <table className="table" style={{ marginTop: 4 }}>
            <tbody>
              {v.cost.lines.map((l, i) => (
                <tr key={i}><td style={{ paddingLeft: 0 }}>{l.label}<div className="tiny muted">{l.source}</div></td><td className="num small">€{l.amount.toFixed(2)}</td></tr>
              ))}
            </tbody>
          </table>
          <div className="tiny muted">{v.cost.formula}</div>
        </details>
      </div>
      {v.guards.length > 0 && (
        <div className="blk">
          <details>
            <summary><h4 style={{ margin: 0 }}>Safety checks · {v.guards.length} rule{v.guards.length === 1 ? "" : "s"} applied</h4></summary>
            {v.guards.map((g, i) => <div key={i} className="tiny" style={{ marginTop: 6 }}><ShieldCheck size={12} /> {g}</div>)}
          </details>
        </div>
      )}
      <div className="blk tiny muted">
        {v.provider === "amd" ? `Computed on AMD by ${v.model}` : "Computed offline by the rule-based fixture provider"} · {v.hops} hops · {fmtDur(v.duration_s)}
        {v.stats ? ` · ${v.stats.unverified_quotes} unverifiable quote(s) rejected` : ""}
      </div>
    </>
  );
}

function DraftTrial({ stepId }: { stepId: string }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  return (
    <>
      <button className="btn accent sm" disabled={busy} onClick={async () => {
        setBusy(true);
        setErr(null);
        try {
          const t = await post<{ id: string }>("/api/trials", { step_id: stepId });
          go(`/trials?id=${t.id}`);
        } catch (e) {
          setErr(e);
        } finally {
          setBusy(false);
        }
      }}>
        {busy ? <Spinner size={14} /> : <ClipboardCheck size={14} />} Plan a safe trial
      </button>
      {err ? <ErrorBox error={err} /> : null}
    </>
  );
}
