import { useState } from "react";
import { Mic, UserRound } from "lucide-react";
import { ApiError, STATIC, getToken, post } from "../api";
import { ErrorBox, Spinner } from "./common";

interface Q { questions: string[]; who: string[]; provider: string }

/** Veteran interview mode: questions for experienced staff, answer recorded as dated testimony, then re-investigate. */
export default function VeteranCard({ stepId, onRecorded }: { stepId: string; onRecorded: (acc: string) => void }) {
  const [q, setQ] = useState<Q | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [answer, setAnswer] = useState("");
  const [audio, setAudio] = useState<File | null>(null);

  async function load() {
    setBusy(true);
    setErr(null);
    try {
      setQ(await post<Q>(`/api/steps/${stepId}/veteran-questions`));
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      const fd = new FormData();
      fd.append("name", name);
      fd.append("role", role);
      fd.append("answer", answer);
      if (audio) fd.append("audio", audio);
      const h: Record<string, string> = {};
      const t = getToken();
      if (t) h["X-Access-Token"] = t;
      const r = await fetch(`/api/steps/${stepId}/testimony`, { method: "POST", body: fd, headers: h });
      if (!r.ok) {
        let msg = `${r.status}`;
        try {
          msg = (await r.json()).detail ?? msg;
        } catch {
          /* not json */
        }
        throw new ApiError(r.status, typeof msg === "string" ? msg : JSON.stringify(msg));
      }
      const j = await r.json();
      onRecorded(j.acc);
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card card-pad" style={{ marginTop: 22, background: "var(--unknown-soft)", borderColor: "transparent" }}>
      <div className="row" style={{ alignItems: "flex-start" }}>
        <UserRound size={22} style={{ color: "var(--unknown)", flexShrink: 0, marginTop: 2 }} />
        <div className="grow">
          <div style={{ fontWeight: 600, fontSize: 17 }}>Ask a veteran before the knowledge retires</div>
          <div className="small" style={{ color: "var(--text-2)", marginTop: 2 }}>
            The archive does not explain this step reliably. CROMO prepares questions for experienced staff, records the answer as dated
            testimony and investigates again. Testimony alone never counts as strong evidence.
          </div>
          {!q && (
            <button className="btn sm" style={{ marginTop: 12 }} onClick={load} disabled={busy || STATIC}>
              {busy ? <Spinner size={14} /> : null} Prepare interview questions
            </button>
          )}
          {STATIC && <div className="tiny muted" style={{ marginTop: 8 }}>Available in the full app (not in the read-only public demo).</div>}
          {q && (
            <div style={{ marginTop: 14 }}>
              <ol className="small" style={{ margin: "0 0 10px", paddingLeft: 20, display: "grid", gap: 4 }}>
                {q.questions.map((x, i) => <li key={i}>{x}</li>)}
              </ol>
              {q.who.length > 0 && <div className="tiny muted" style={{ marginBottom: 12 }}>Who might know: {q.who.join(", ")}</div>}
              <div className="row wrap" style={{ gap: 8 }}>
                <input className="input" style={{ maxWidth: 240 }} placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} aria-label="Interviewee name" />
                <input className="input" style={{ maxWidth: 320 }} placeholder="Role and years (e.g. shift foreman 1985-2016)" value={role} onChange={(e) => setRole(e.target.value)} aria-label="Interviewee role" />
              </div>
              <textarea className="textarea input" style={{ marginTop: 8 }} placeholder="Their answer, in their words…" value={answer} onChange={(e) => setAnswer(e.target.value)} aria-label="Answer" />
              <div className="row wrap" style={{ marginTop: 8 }}>
                <label className="btn sm ghost" style={{ cursor: "pointer" }}>
                  <Mic size={14} /> {audio ? audio.name : "or attach a voice recording"}
                  <input type="file" accept="audio/*" style={{ display: "none" }} onChange={(e) => setAudio(e.target.files?.[0] ?? null)} />
                </label>
                <span className="grow" />
                <button className="btn primary sm" disabled={busy || name.trim().length < 2 || (answer.trim().length < 20 && !audio)} onClick={submit}>
                  {busy ? <Spinner size={14} /> : null} Record testimony and investigate again
                </button>
              </div>
            </div>
          )}
          <ErrorBox error={err} />
        </div>
      </div>
    </div>
  );
}
