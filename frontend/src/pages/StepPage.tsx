import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowLeft, CircleX, ClipboardCheck, GitCompare, Play, RotateCcw, Scale, ShieldAlert, ShieldCheck, TriangleAlert } from "lucide-react";
import { eur, get, post, streamNdjson } from "../api";
import { ErrorBox, Skeleton, Spinner, StrengthMeter, VERDICT_LABEL, VerdictIcon, fmtDate, go, timeAgo, useApp } from "../components/common";
import type { Cost, Evidence, InvEvent, Verdict, VerdictData } from "../types";

interface StepInfo {
  step: { id: string; name?: string; instruction: string; process: string; process_name: string; process_code: string; seq: number };
  verdict: VerdictData | null;
  cost: Cost;
  has_recording: boolean;
}
interface Hop { n: number; kind: string; label: string; query?: string | null; detail?: string; documents?: string[]; found: number; running: boolean; compare?: { a: string; b: string } | null }
type Source = "stored" | "live" | "replay";

const HEADLINE: Record<Verdict, string> = {
  FOSSIL: "The reason for this step is gone.",
  FENCE: "It looks pointless - but it protects you.",
  UNKNOWN: "Nobody knows why. Ask a person.",
  ACTIVE: "Still needed, for a documented reason.",
  PENDING: "Not investigated yet.",
};
const TAG: Record<string, [string, string]> = {
  reason: ["reason", "Why it was introduced"],
  status: ["status", "Is it still true?"],
  counter: ["counter", "Warning sign"],
  context: ["context", "Context"],
};
const EXPECTED_HOPS = 9;

function parse(events: InvEvent[]) {
  const hops: Hop[] = [];
  const evidence: Evidence[] = [];
  const seen = new Set<string>();
  let verdict: VerdictData | null = null;
  let concluding = false;
  let meta: InvEvent | null = null;
  const ignored = new Set<string>();
  const warnings: string[] = [];
  for (const ev of events) {
    if (ev.type === "start" || ev.type === "replay") meta = { ...(meta ?? {}), ...ev };
    else if (ev.type === "hop_started") {
      hops.push({ n: ev.n!, kind: ev.kind!, label: ev.label!, query: ev.query, documents: ev.documents, found: 0, running: true });
    } else if (ev.type === "hop") {
      const items = ev.evidence ?? [];
      const h: Hop = {
        n: ev.n!, kind: ev.kind!, label: ev.label!, query: ev.query, detail: ev.detail, documents: ev.documents, found: items.length, running: false,
        compare: (ev as unknown as { compare?: { a: string; b: string } }).compare ?? null,
      };
      const i = hops.findIndex((x) => x.n === ev.n);
      if (i >= 0) hops[i] = h;
      else hops.push(h);
      (ev.ignored_injection ?? []).forEach((a) => ignored.add(a));
      for (const e of items) {
        const key = `${e.acc}|${e.quote.slice(0, 60)}`;
        if (seen.has(key)) continue;
        seen.add(key);
        if (e.suspicious) ignored.add(e.acc);
        else if (e.verified) evidence.push(e);
      }
    } else if (ev.type === "concluding") concluding = true;
    else if (ev.type === "verdict") {
      verdict = ev.verdict ?? null;
      concluding = false;
    } else if (ev.type === "warning" || ev.type === "error") warnings.push(ev.message ?? "");
  }
  evidence.sort((a, b) => (a.date ?? "9999").localeCompare(b.date ?? "9999"));
  return { hops, evidence, verdict, concluding, meta, ignored: [...ignored], warnings };
}

export default function StepPage({ stepId, query }: { stepId: string; query: URLSearchParams }) {
  const { mode } = useApp();
  const [info, setInfo] = useState<StepInfo | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [events, setEvents] = useState<InvEvent[]>([]);
  const [source, setSource] = useState<Source>("stored");
  const [busy, setBusy] = useState(false);
  const [showAll, setShowAll] = useState(false);
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
    const r = await get<{ events: InvEvent[] }>(`/api/steps/${stepId}/events`);
    setEvents(r.events.filter((e) => e.type !== "heartbeat")); // stored results appear at once
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

  if (err && !info) return <ErrorBox error={err} />;
  if (!info)
    return (
      <div className="col" style={{ gap: 18, marginTop: 20 }}>
        <Skeleton h={40} w="45%" />
        <Skeleton h={160} />
        <Skeleton h={400} />
      </div>
    );

  const { hops, evidence: allEvidence, verdict: v, concluding, meta, ignored, warnings } = parse(events);
  const cited = v ? new Set(v.strength.cited) : null;
  const evidence = v && !showAll ? allEvidence.filter((e) => cited!.has(e.id) || e.doc_type === "recipe") : allEvidence;
  const hidden = allEvidence.length - evidence.length;
  const st = info.step;
  const running = busy || (events.length > 0 && !v && source !== "stored");
  const shown: Verdict = v?.verdict ?? "PENDING";
  const docsRead = new Set(hops.flatMap((h) => h.documents ?? [])).size;
  const progress = v ? 100 : Math.min(95, Math.round((hops.length / EXPECTED_HOPS) * 90) + (concluding ? 5 : 0));
  const current = [...hops].reverse().find((h) => h.running) ?? hops[hops.length - 1];

  return (
    <div>
      <button className="crumb" onClick={() => go("/")}><ArrowLeft size={15} /> Plant map</button>
      <div className="eyebrow" style={{ marginTop: 18 }}>{st.process_code} {st.process_name.replace(/^\S+\s/, "")} · step {st.seq}</div>
      <h1 className="h1" style={{ marginTop: 4 }}>{st.name ?? st.id}</h1>
      <div className="lead" style={{ marginTop: 6, fontSize: 17 }}>“{st.instruction}”</div>

      {/* ------------------------------------------------ verdict hero */}
      <div className={`verdict-hero h-${shown} fade-in`} style={{ marginTop: 24 }}>
        <div className={`vtile t-${shown}`}>
          {running && !v ? <Spinner size={28} /> : <VerdictIcon v={shown} size={34} />}
          <span>{running && !v ? "DIGGING" : VERDICT_LABEL[shown].toUpperCase()}</span>
        </div>
        <div>
          {v ? (
            <>
              <div className="v-headline">{HEADLINE[v.verdict]}</div>
              {v.reason && <div className="v-reason">{v.reason}</div>}
              <div className="v-facts">
                {v.origin_year && <span>Introduced <strong>{v.origin_year}</strong></span>}
                <span>Evidence <StrengthMeter grade={v.strength.grade} /> <span className="muted">({v.strength.documents} documents)</span></span>
                {v.proposed_verdict !== v.verdict && <span className="c-UNKNOWN">Safety rule changed the model's {v.proposed_verdict} to {v.verdict}</span>}
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
            {!v && !running && <button className="btn brand" onClick={() => run("live")}><Play size={15} /> Investigate</button>}
          </div>
        </div>
      </div>

      {/* ------------------------------------------------ mode / provenance line */}
      <div className="row wrap small muted" style={{ marginTop: 12, gap: 14 }}>
        {source === "replay" && meta ? (
          <span className="note info" style={{ padding: "6px 12px" }}>
            <RotateCcw size={15} /> Replay of a run recorded on AMD {meta.recorded_at ? new Date(meta.recorded_at * 1000).toLocaleDateString() : ""} ·{" "}
            {meta.models?.reasoner} · {meta.hardware}
          </span>
        ) : mode === "fixture" ? (
          <span>Offline mode: this result comes from CROMO's rule-based fixture provider, not from an AI model.</span>
        ) : v ? (
          <span>Computed on AMD by {v.model}</span>
        ) : null}
        {v && source === "stored" && <span>· last run {timeAgo(v.created_at)}</span>}
        <span className="grow" />
        {!running && v && (
          <button className="btn ghost sm" onClick={() => run("live")}><Play size={14} /> Investigate again{mode === "fixture" ? " (offline)" : " live"}</button>
        )}
        {!running && info.has_recording && <button className="btn ghost sm" onClick={() => run("replay")}><RotateCcw size={14} /> Replay AMD run</button>}
      </div>
      <ErrorBox error={err} />

      {/* ------------------------------------------------ live progress */}
      {running && (
        <div className="progress fade-in" style={{ marginTop: 20 }}>
          <Spinner />
          <div className="grow">
            <div className="row small"><strong>Step {hops.length || 1} of the dig</strong><span className="muted">· {docsRead} documents read · {evidence.length} pieces of evidence</span></div>
            <div className="bar" style={{ marginTop: 8 }}><i style={{ width: `${progress}%` }} /></div>
          </div>
        </div>
      )}

      <div className="inv-grid">
        {/* ------------------------------------------------ paper trail */}
        <div>
          <h2 className="section-title">The paper trail</h2>
          <div className="small muted">Every claim is tied to a document in the archive. Click any entry to open the page.</div>
          {evidence.length === 0 && !running && (
            <div className="card empty" style={{ marginTop: 16 }}>No evidence yet. Press <strong>Investigate</strong> to start digging.</div>
          )}
          <div className="timeline">
            {evidence.map((e) => <TimelineItem key={e.id + e.acc} e={e} />)}
            {running && <div className="tl-item"><div className="tl-year" /><div className="tl-dot" /><div className="small muted" style={{ paddingTop: 8 }}><Spinner size={13} /> reading…</div></div>}
          </div>
          {v && (hidden > 0 || showAll) && (
            <button className="btn ghost sm" onClick={() => setShowAll(!showAll)}>
              {showAll ? "Show only the evidence used in the verdict" : `Show ${hidden} more passage${hidden === 1 ? "" : "s"} CROMO read but did not rely on`}
            </button>
          )}
          {ignored.length > 0 && (
            <div className="note danger" style={{ marginTop: 10 }}>
              <ShieldAlert size={18} style={{ flexShrink: 0 }} />
              <div>
                <strong>Ignored instruction-like text</strong> in {ignored.join(", ")}. Archive content is treated as data, never as instructions.
              </div>
            </div>
          )}
          {warnings.map((w, i) => <div key={i} className="note warn" style={{ marginTop: 8 }}><TriangleAlert size={16} /> {w}</div>)}
          {hops.length > 0 && <DigLog hops={hops} docsRead={docsRead} open={running} />}
        </div>

        {/* ------------------------------------------------ side panel */}
        <aside className="side sticky">{v ? <Side v={v} /> : <div className="small muted">Details appear when the investigation is complete.</div>}</aside>
      </div>
    </div>
  );
}

function sameText(claim: string, quote: string) {
  const n = (x: string) => x.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  return n(claim).includes(n(quote).slice(0, 40));
}

function TimelineItem({ e }: { e: Evidence }) {
  const { openDoc } = useApp();
  const [cls, label] = TAG[e.stance] ?? TAG.context;
  const open = () => openDoc({ acc: e.acc, page: e.page, quote: e.quote });
  return (
    <div className="tl-item fade-in">
      <div className="tl-year">{e.date ? e.date.slice(0, 4) : "–"}</div>
      <div className={`tl-dot st-${e.stance}`} />
      <div className={`tl-card ${e.suspicious ? "suspicious" : ""}`} onClick={open} role="button" tabIndex={0} onKeyDown={(k) => k.key === "Enter" && open()}>
        <div className="tl-meta">
          <span className={`tl-tag ${cls}`}>{e.doc_type === "recipe" && e.stance === "context" ? "Recipe" : label}</span>
          <span style={{ textTransform: "capitalize" }}>{e.doc_type ?? "document"}</span>
          <span>· {fmtDate(e.date)}</span>
          <span>· {e.acc}</span>
        </div>
        <div className="quote">“{e.quote}”</div>
        {e.claim && e.stance !== "context" && !sameText(e.claim, e.quote) && <div className="claim">{e.claim}</div>}
      </div>
    </div>
  );
}

function DigLog({ hops, docsRead, open }: { hops: Hop[]; docsRead: number; open: boolean }) {
  const [cmp, setCmp] = useState<{ loading: boolean; text?: string; err?: string; source?: string } | null>(null);
  const recipeHop = hops.find((h) => h.compare);
  const loadCompare = async () => {
    if (!recipeHop?.compare) return;
    setCmp({ loading: true });
    try {
      const r = await get<{ source: string; result: { output: string } }>(`/api/compare?a=${recipeHop.compare.a}&b=${recipeHop.compare.b}`);
      setCmp({ loading: false, text: r.result.output, source: r.source });
    } catch (e) {
      setCmp({ loading: false, err: e instanceof Error ? e.message : String(e) });
    }
  };
  return (
    <details className="card card-pad" style={{ marginTop: 22 }} open={open}>
      <summary>How CROMO dug: {hops.length} steps, {docsRead} documents read</summary>
      <ol className="diglog">
        {hops.map((h) => (
          <li key={h.n}>
            <span className="k">{h.n}.</span>
            <span>
              <strong>{h.label}</strong>
              {h.query ? <span className="muted"> - {h.query}</span> : h.detail ? <span className="muted"> - {h.detail}</span> : null}
              <span className="muted"> · {h.running ? "reading…" : `${h.found} found`}</span>
            </span>
          </li>
        ))}
      </ol>
      {recipeHop?.compare && (
        <div style={{ marginTop: 12 }}>
          {!cmp ? (
            <button className="btn sm" onClick={loadCompare}><GitCompare size={14} /> What changed when this step was added? (Evolus AI Tool)</button>
          ) : cmp.loading ? (
            <span className="small muted"><Spinner size={13} /> Asking the Evolus “compare” tool…</span>
          ) : cmp.err ? (
            <span className="small muted">Evolus compare unavailable: {cmp.err}</span>
          ) : (
            <div className="small" style={{ whiteSpace: "pre-wrap", maxHeight: 300, overflow: "auto", background: "var(--surface-2)", padding: 14, borderRadius: 12 }}>
              <div className="tiny muted" style={{ marginBottom: 6 }}>{cmp.source}</div>
              {cmp.text}
            </div>
          )}
        </div>
      )}
    </details>
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
          <div className="tiny muted" style={{ marginTop: 6 }}>CROMO watches these. If one changes, the Tripwires page raises an alert.</div>
        </div>
      )}
      {v.counter_evidence.length > 0 && (
        <div className="blk">
          <h4>Counter-evidence considered</h4>
          {v.counter_evidence.map((c, i) => (
            <div key={i} className="small" style={{ marginBottom: 8 }}>
              <span className={`tl-tag ${c.resolved ? "context" : "counter"}`}>{c.resolved ? "resolved" : "open"}</span> {c.claim} {c.evidence.map(cite)}
              {c.resolution && <div className="tiny muted">{c.resolution}</div>}
            </div>
          ))}
        </div>
      )}
      {v.open_questions.length > 0 && (
        <div className="blk">
          <h4>Questions for a person</h4>
          {v.open_questions.map((q, i) => <div key={i} className="small" style={{ marginBottom: 4 }}>{q}</div>)}
        </div>
      )}
      <div className="blk">
        <h4>How sure are we?</h4>
        <div className="row"><StrengthMeter grade={v.strength.grade} /><span className="small muted">{v.strength.score} points</span></div>
        <details style={{ marginTop: 8 }}>
          <summary>Scoring rules</summary>
          <div className="small" style={{ marginTop: 6 }}>
            {v.strength.breakdown.map((b, i) => (
              <div key={i} className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                <span>{b.label}</span><span style={{ color: b.points < 0 ? "var(--danger)" : "var(--ok)", fontWeight: 600 }}>{b.points > 0 ? "+" : ""}{b.points}</span>
              </div>
            ))}
            <div className="tiny muted" style={{ marginTop: 4 }}>{v.strength.rule}</div>
          </div>
        </details>
      </div>
      <div className="blk">
        <h4>Cost</h4>
        <div className="small">{v.cost.runs_per_year.toLocaleString()} runs a year × {eur(v.cost.per_run_eur)} = <strong>{eur(v.cost.annual_eur)}</strong></div>
        <details style={{ marginTop: 8 }}>
          <summary>Inputs</summary>
          <table className="table" style={{ marginTop: 4 }}>
            <tbody>
              {v.cost.lines.map((l, i) => (
                <tr key={i}><td>{l.label}<div className="tiny muted">{l.source}</div></td><td className="num small">€{l.amount.toFixed(2)}</td></tr>
              ))}
            </tbody>
          </table>
          <div className="tiny muted">{v.cost.formula}</div>
        </details>
      </div>
      {v.guards.length > 0 && (
        <div className="blk">
          <h4>Safety checks</h4>
          <details>
            <summary>{v.guards.length} rule{v.guards.length === 1 ? "" : "s"} applied</summary>
            {v.guards.map((g, i) => <div key={i} className="tiny" style={{ marginTop: 6 }}><ShieldCheck size={12} /> {g}</div>)}
          </details>
        </div>
      )}
      <div className="blk tiny muted">
        {v.provider === "amd" ? `Computed on AMD by ${v.model}` : "Computed offline by the rule-based fixture provider"} · {v.hops} steps · {v.duration_s}s
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
      <button className="btn brand sm" disabled={busy} onClick={async () => {
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
