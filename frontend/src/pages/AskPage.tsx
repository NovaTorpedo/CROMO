import { useEffect, useState } from "react";
import { ArrowRight, MessageSquareText, Search } from "lucide-react";
import { post } from "../api";
import { ErrorBox, Spinner, fmtDate, go, useApp } from "../components/common";

interface Source { acc: string; page: number; date: string | null; doc_type: string | null; title: string | null; text: string }
interface Answer {
  type: "answer" | "step";
  step_id?: string;
  answer?: string;
  claims?: { text: string; sources: Source[] }[];
  insufficient_evidence?: boolean;
  related_steps?: string[];
  provider?: string;
  model?: string;
  duration_s?: number;
  evolus_agent?: { answer?: string; model?: string; latency_ms?: number; error?: string };
}

const EXAMPLES = [
  "Why do we add ammonium chloride to AF-12?",
  "Why do we pre-heat the epoxy drums in the hot box?",
  "Why must the vessel be bonded and earthed before solvent transfer?",
  "Why are TL-5 cans dried in the oven?",
  "What happened with the flash fire at D-2 in 2001?",
  "Which supplier delivered the chromate pigment and when did it stop?",
];

export default function AskPage({ initial }: { initial: string }) {
  const { openDoc } = useApp();
  const [q, setQ] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<Answer | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [agent, setAgent] = useState(false);

  async function ask(question: string) {
    if (!question.trim()) return;
    setBusy(true);
    setErr(null);
    setRes(null);
    try {
      const r = await post<Answer>("/api/ask", { question, use_evolus_agent: agent });
      if (r.type === "step" && r.step_id) {
        go(`/step/${r.step_id}?live=1`);
        return;
      }
      setRes(r);
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (initial) ask(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial]);

  return (
    <div style={{ maxWidth: 980 }}>
      <div className="eyebrow">Ask about any step</div>
      <h1 className="h1" style={{ marginTop: 6 }}>Pick any step. Ask why.</h1>
      <p className="lead">
        Questions about a specific step open a live investigation. Other questions about the plant are answered from the archive, with every
        claim tied to a document.
      </p>
      <form
        className="ask-hero"
        onSubmit={(e) => {
          e.preventDefault();
          ask(q);
        }}
      >
        <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Why do we add ammonium chloride to AF-12?" aria-label="Question" />
        <button className="btn primary" disabled={busy}>{busy ? <Spinner /> : <Search size={16} />} Ask</button>
      </form>
      <label className="row small muted" style={{ marginTop: 8, gap: 6 }}>
        <input type="checkbox" checked={agent} onChange={(e) => setAgent(e.target.checked)} />
        Also ask the Evolus plant agent (runs on our AMD-hosted model, grounded in the Evolus knowledge library)
      </label>
      <div className="row wrap" style={{ gap: 6, marginTop: 14 }}>
        {EXAMPLES.map((x) => (
          <button key={x} className="chip" onClick={() => { setQ(x); ask(x); }}>{x}</button>
        ))}
      </div>
      <div style={{ marginTop: 22 }}>
        <ErrorBox error={err} />
        {busy && <div className="card card-pad row"><Spinner /> Searching the archive…</div>}
        {res && (
          <div className="card">
            <div className="card-pad" style={{ borderBottom: "1px solid var(--border)" }}>
              <div className="eyebrow">Evidence brief</div>
              <div style={{ fontSize: 17, marginTop: 6 }}>{res.answer}</div>
              {res.insufficient_evidence && <div className="small c-UNKNOWN" style={{ marginTop: 6 }}>Not enough evidence in the archive: CROMO does not guess.</div>}
            </div>
            {res.claims && res.claims.length > 0 && (
              <div className="card-pad col">
                {res.claims.map((c, i) => (
                  <div key={i}>
                    <div style={{ fontWeight: 500 }}>{c.text}</div>
                    <div className="row wrap" style={{ gap: 6, marginTop: 4 }}>
                      {c.sources.map((s, j) => (
                        <button key={j} className="chip" onClick={() => openDoc({ acc: s.acc, page: s.page, quote: c.text })}>
                          <span className="mono">{s.acc}</span> · {s.doc_type} · {fmtDate(s.date)}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {res.related_steps && res.related_steps.length > 0 && (
              <div className="card-pad row wrap" style={{ borderTop: "1px solid var(--border)" }}>
                <span className="small muted">Related steps:</span>
                {res.related_steps.map((s) => (
                  <button key={s} className="btn sm" onClick={() => go(`/step/${s}`)}>{s} <ArrowRight size={13} /></button>
                ))}
              </div>
            )}
            <div className="card-pad tiny muted" style={{ borderTop: "1px solid var(--border)" }}>
              {res.provider === "amd" ? <>Answered on AMD by <span className="mono">{res.model}</span></> : "Offline fixture provider (heuristic)"} · {res.duration_s}s
            </div>
          </div>
        )}
        {res?.evolus_agent && (
          <div className="card card-pad" style={{ marginTop: 14 }}>
            <div className="row" style={{ marginBottom: 6 }}>
              <MessageSquareText size={16} />
              <strong>Evolus plant agent</strong>
              <span className="tiny muted mono">{res.evolus_agent.model}</span>
            </div>
            {res.evolus_agent.error ? (
              <div className="small muted">Not available: {res.evolus_agent.error}</div>
            ) : (
              <div style={{ whiteSpace: "pre-wrap" }}>{res.evolus_agent.answer}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
