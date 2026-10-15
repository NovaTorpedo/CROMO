import { useEffect, useState } from "react";
import { eur, get } from "../api";
import { VerdictIcon } from "../components/common";
import type { MapData } from "../types";

/** 16:9 cover image for the submission (rendered by scripts/build_submission.py). */
export default function CoverPage() {
  const [d, setD] = useState<MapData | null>(null);
  useEffect(() => {
    get<MapData>("/api/map").then(setD).catch(() => {});
  }, []);
  if (!d) return null;
  const t = d.totals;
  return (
    <div style={{ width: 1600, height: 900, padding: "64px 72px", boxSizing: "border-box", background: "var(--bg)", display: "grid",
      gridTemplateColumns: "470px 1fr", gap: 50, overflow: "hidden" }}>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <div className="row" style={{ gap: 18 }}>
          <span className="logo-tile" style={{ width: 92, height: 92, fontSize: 44, borderRadius: 14 }}><small style={{ fontSize: 15, top: 6, left: 9 }}>24</small>Cr</span>
          <span className="logo-word" style={{ fontSize: 54, letterSpacing: 8 }}>CROMO</span>
        </div>
        <h1 className="hero-title" style={{ fontSize: 52, marginTop: 44 }}>Every factory runs on reasons nobody remembers.</h1>
        <p className="lead" style={{ fontSize: 21, marginTop: 22 }}>
          CROMO reads a plant's own archive and recovers why each process step exists - finding the waste and protecting the safeguards.
        </p>
        <div style={{ marginTop: "auto", display: "grid", gap: 12 }}>
          <div className="stat s-FOSSIL" style={{ paddingLeft: 16 }}><div className="n" style={{ fontSize: 40 }}>{eur(d.fossil_annual_eur)}/yr</div><div className="l" style={{ fontSize: 17 }}>in {t.FOSSIL} fossil steps whose reason is gone</div></div>
          <div className="row" style={{ gap: 30 }}>
            <div className="stat s-FENCE" style={{ paddingLeft: 16 }}><div className="n" style={{ fontSize: 34 }}>{t.FENCE} fences</div><div className="l" style={{ fontSize: 16 }}>protected</div></div>
            <div className="stat s-UNKNOWN" style={{ paddingLeft: 16 }}><div className="n" style={{ fontSize: 34 }}>{t.UNKNOWN} unknown</div><div className="l" style={{ fontSize: 16 }}>sent to a person</div></div>
          </div>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <div className="card" style={{ padding: "12px 22px" }}>
          {d.processes.map((p) => (
            <div key={p.id} className="prow" style={{ gridTemplateColumns: "118px 1fr", padding: "9px 0" }}>
              <div className="plabel" style={{ paddingTop: 4 }}><div className="code">{p.code}</div><div className="name" style={{ fontSize: 13 }}>{p.short}</div></div>
              <div className="tiles" style={{ gap: 4, flexWrap: "nowrap" }}>
                {p.steps.map((s) => (
                  <div key={s.id} className={`tile t-${s.verdict}`} style={{ width: 55, height: 70, padding: "5px 5px", cursor: "default" }}>
                    <span className="top" style={{ fontSize: 10 }}><span>{s.seq}</span>{s.verdict !== "ACTIVE" && <VerdictIcon v={s.verdict} size={12} />}</span>
                    <span className="nm" style={{ fontSize: 9.5, lineHeight: 1.15 }}>{s.name}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="row" style={{ marginTop: 22, gap: 22, fontSize: 16, color: "var(--text-2)", flexWrap: "wrap" }}>
          <span className="row" style={{ gap: 6 }}><span className="c-FOSSIL"><VerdictIcon v="FOSSIL" size={16} /></span> Fossil</span>
          <span className="row" style={{ gap: 6 }}><span className="c-FENCE"><VerdictIcon v="FENCE" size={16} /></span> Fence</span>
          <span className="row" style={{ gap: 6 }}><span className="c-UNKNOWN"><VerdictIcon v="UNKNOWN" size={16} /></span> Unknown</span>
          <span className="grow" />
          <span style={{ fontWeight: 600 }}>AMD Instinct MI300X · ROCm · vLLM · Evolus</span>
        </div>
      </div>
    </div>
  );
}
