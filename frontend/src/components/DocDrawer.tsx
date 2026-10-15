import { useEffect, useMemo, useState } from "react";
import { FileText, ShieldAlert, X } from "lucide-react";
import { get, pageUrl } from "../api";
import type { DocData } from "../types";
import { ErrorBox, Skeleton, fmtDate, type DocTarget } from "./common";

function norm(s: string) {
  return s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9%]+/g, " ").trim();
}

/** Which lines of the page contain the quoted passage (tolerant to line breaks and OCR noise). */
function matchLines(lines: { text: string }[], quote?: string): Set<number> {
  const hit = new Set<number>();
  if (!quote) return hit;
  const q = norm(quote);
  const qWords = q.split(" ").filter((w) => w.length > 2);
  if (!qWords.length) return hit;
  const nl = lines.map((l) => norm(l.text));
  // windows of 1-4 consecutive lines whose joined text contains most of the quote
  for (let i = 0; i < nl.length; i++) {
    for (let k = 1; k <= 4 && i + k <= nl.length; k++) {
      const joined = nl.slice(i, i + k).join(" ");
      const found = qWords.filter((w) => joined.includes(w)).length;
      if (joined.includes(q) || found / qWords.length >= 0.85) {
        for (let j = i; j < i + k; j++) {
          // keep only the lines that actually share words with the quote
          if (qWords.some((w) => nl[j].includes(w))) hit.add(j);
        }
        return hit;
      }
    }
  }
  return hit;
}

export default function DocDrawer({ target, onClose }: { target: DocTarget; onClose: () => void }) {
  const [doc, setDoc] = useState<DocData | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [page, setPage] = useState(target.page ?? 1);

  useEffect(() => {
    setDoc(null);
    setErr(null);
    setPage(target.page ?? 1);
    get<DocData>(`/api/docs/${encodeURIComponent(target.acc)}`).then(setDoc, setErr);
  }, [target.acc, target.page]);

  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);

  const pg = doc?.pages_data.find((p) => p.page === page);
  const hits = useMemo(() => (pg ? matchLines(pg.lines, target.quote) : new Set<number>()), [pg, target.quote]);
  const digital = pg?.source === "text_layer";
  const testimony = pg?.source === "testimony";

  return (
    <>
      <div className="drawer-back" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={`Archive document ${target.acc}`}>
        <div className="drawer-head">
          <FileText size={20} />
          <div className="grow">
            <div className="row wrap" style={{ gap: 8 }}>
              <strong className="mono">{target.acc}</strong>
              {doc && <span className="chip">{doc.doc_type}</span>}
              {doc && <span className="chip">{fmtDate(doc.date)}</span>}
              {doc && <span className="chip">{doc.lang === "it" ? "Italiano" : "English"}</span>}
            </div>
            <div className="small muted" style={{ marginTop: 2 }}>{doc?.title || doc?.summary || "Archive document"}</div>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close document">
            <X size={18} />
          </button>
        </div>
        {err ? (
          <div style={{ padding: 18 }}>
            <ErrorBox error={err} />
          </div>
        ) : !doc ? (
          <div style={{ padding: 18 }} className="col">
            <Skeleton h={500} />
          </div>
        ) : (
          <div className="drawer-body">
            <div className="col">
              {doc.pages > 1 && (
                <div className="row">
                  {Array.from({ length: doc.pages }, (_, i) => (
                    <button key={i} className={`btn sm ${page === i + 1 ? "primary" : ""}`} onClick={() => setPage(i + 1)}>
                      Page {i + 1}
                    </button>
                  ))}
                </div>
              )}
              {testimony ? (
                <div className="card card-pad small">Interview record captured in CROMO (no scanned page). The transcript is on the right.</div>
              ) : (
              <div className="page-wrap">
                <img src={pageUrl(doc.acc, page)} alt={`Page ${page} of archive document ${doc.acc}`} />
                {digital && pg &&
                  [...hits].map((i) => {
                    const b = pg.lines[i]?.bbox;
                    if (!b) return null;
                    return (
                      <div
                        key={i}
                        className="hl"
                        style={{
                          left: `${(b[0] / pg.width) * 100 - 0.6}%`,
                          top: `${(b[1] / pg.height) * 100 - 0.2}%`,
                          width: `${((b[2] - b[0]) / pg.width) * 100 + 1.2}%`,
                          height: `${((b[3] - b[1]) / pg.height) * 100 + 0.4}%`,
                        }}
                      />
                    );
                  })}
              </div>
              )}
              <div className="tiny muted">
                Synthetic archive page (fictional plant). {digital ? "Born-digital: highlight placed from the embedded text layer." : "Scanned: text below was read from the image."}
              </div>
            </div>
            <div className="col">
              {doc.injection_flag ? (
                <div className="note danger small">
                  <ShieldAlert size={18} />
                  <div>
                    <strong>Instruction-like text detected.</strong> This document contains text that tries to instruct an AI system. CROMO treats
                    archive content strictly as data: it was excluded from verdicts.
                  </div>
                </div>
              ) : null}
              <div className="card card-pad small">
                <div className="eyebrow" style={{ marginBottom: 6 }}>How this page was read</div>
                <div>
                  {testimony ? (
                    <>Testimony recorded in CROMO ({doc.text_source === "voice" ? "transcribed from a voice recording" : "typed"}).</>
                  ) : digital ? (
                    <>Text layer of a born-digital document (no model needed).</>
                  ) : pg?.source === "vision" ? (
                    <>
                      Transcribed by vision model <span className="mono">{pg.model}</span> on AMD.
                    </>
                  ) : (
                    <>
                      <strong className="c-FOSSIL">Offline fixture mode:</strong> recorded transcription, not a live model reading.
                    </>
                  )}
                </div>
                <div className="muted" style={{ marginTop: 4 }}>
                  Metadata: <span className="mono">{doc.meta_source}</span>
                  {doc.refs?.own?.length ? <> · Ref {doc.refs.own.join(", ")}</> : null}
                  {doc.refs?.cited?.length ? <> · cites {doc.refs.cited.join(", ")}</> : null}
                </div>
              </div>
              {target.quote && (
                <div className="card card-pad">
                  <div className="eyebrow" style={{ marginBottom: 6 }}>Cited passage</div>
                  <div className="quote">“{target.quote}”</div>
                  {!hits.size && <div className="tiny muted" style={{ marginTop: 6 }}>Passage is on another page or spans a page break.</div>}
                </div>
              )}
              <div className="transcript" aria-label="Page text">
                {pg?.lines.map((l, i) => (
                  <span key={i} className={`ln ${hits.has(i) ? "on" : ""}`}>
                    {l.text}
                    {"\n"}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </aside>
    </>
  );
}
