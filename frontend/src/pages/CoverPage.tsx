import { useEffect, useState } from "react";
import { eur, get } from "../api";
import { VerdictIcon } from "../components/common";
import type { MapData } from "../types";

interface SysLite { config: { amd_route: string; roles: { reasoner: { model: string | null } } }; benchmark: { route?: string; models?: Record<string, string> } | null }

/** 16:9 cover image and first video frame (rendered by scripts/build_submission.py). */
export default function CoverPage() {
  const [d, setD] = useState<MapData | null>(null);
  const [sys, setSys] = useState<SysLite | null>(null);
  useEffect(() => {
    get<MapData>("/api/map").then(setD).catch(() => {});
    get<SysLite>("/api/system").then(setSys).catch(() => {});
  }, []);
  if (!d) return null;
  const t = d.totals;
  const route = sys?.benchmark?.route ?? sys?.config.amd_route;
  const model = sys?.benchmark?.models?.reasoner ?? sys?.config.roles.reasoner.model ?? "";
  const stack = route === "tokenfactory"
    ? `${/gemma/i.test(model) ? "Google Gemma 4" : model} on the AMD Token Factory · Evolus`
    : `${/gemma/i.test(model) ? "Google Gemma 4" : "Open models"} on AMD Instinct MI300X · ROCm · vLLM · Evolus`;
  return (
    <div className="cover" style={{ width: 1600, height: 900, padding: "60px 64px", boxSizing: "border-box", display: "grid",
      gridTemplateColumns: "500px 1fr", gap: 44, overflow: "hidden", position: "relative" }}>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <div className="row" style={{ gap: 16 }}>
          <span className="logo-tile" style={{ width: 76, height: 76, fontSize: 34, borderRadius: 22 }}><small style={{ fontSize: 12, top: 6, left: 9 }}>24</small>Cr</span>
          <span className="logo-word" style={{ fontSize: 40 }}>CROMO</span>
        </div>
        <h1 className="hero-title" style={{ fontSize: 58, marginTop: 46 }}>Every factory runs on reasons nobody remembers.</h1>
        <p className="lead" style={{ fontSize: 21, marginTop: 20 }}>
          CROMO reads a plant's own archive and recovers why each process step exists: it finds the waste and protects the safeguards.
        </p>
        <div style={{ marginTop: "auto", display: "grid", gap: 10 }}>
          <div className="metric card m-FOSSIL" style={{ padding: "16px 20px" }}>
            <span className="ic" style={{ width: 44, height: 44 }}><VerdictIcon v="FOSSIL" size={22} /></span>
            <span><div className="n" style={{ fontSize: 32 }}>{eur(d.fossil_annual_eur)}<span style={{ fontSize: 18 }}> /yr</span></div><div className="l" style={{ fontSize: 15 }}>in {t.FOSSIL} fossil steps whose reason is gone</div></span>
          </div>
          <div className="row" style={{ gap: 10 }}>
            <div className="metric card m-FENCE grow" style={{ padding: "14px 18px" }}>
              <span className="ic"><VerdictIcon v="FENCE" size={18} /></span><span><div className="n" style={{ fontSize: 26 }}>{t.FENCE} fences</div><div className="l" style={{ fontSize: 14 }}>protected</div></span>
            </div>
            <div className="metric card m-UNKNOWN grow" style={{ padding: "14px 18px" }}>
              <span className="ic"><VerdictIcon v="UNKNOWN" size={18} /></span><span><div className="n" style={{ fontSize: 26 }}>{t.UNKNOWN} unknown</div><div className="l" style={{ fontSize: 14 }}>sent to a person</div></span>
            </div>
          </div>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <div className="panel" style={{ padding: "10px 24px" }}>
          {d.processes.map((p) => (
            <div key={p.id} className="prow" style={{ gridTemplateColumns: "104px 1fr", padding: "11px 0", gap: 14 }}>
              <div className="plabel" style={{ paddingTop: 6 }}><div className="code">{p.code}</div><div className="name" style={{ fontSize: 12.5 }}>{p.short}</div></div>
              <div className="tiles" style={{ gap: 5, flexWrap: "nowrap" }}>
                {p.steps.map((s) => (
                  <div key={s.id} className={`tile t-${s.verdict}`} style={{ width: 66, height: 112, padding: "7px 7px", cursor: "default", borderRadius: 14 }}>
                    <span className="top" style={{ fontSize: 10.5 }}><span>{s.seq}</span>{s.verdict !== "ACTIVE" && <VerdictIcon v={s.verdict} size={12} />}</span>
                    <span className="nm" style={{ fontSize: 10, lineHeight: 1.15, letterSpacing: "-0.015em" }}>{s.name}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="row" style={{ marginTop: "auto", gap: 18, fontSize: 16, color: "var(--text-2)", flexWrap: "wrap" }}>
          <span className="row" style={{ gap: 6 }}><span className="c-FOSSIL"><VerdictIcon v="FOSSIL" size={16} /></span> Fossil</span>
          <span className="row" style={{ gap: 6 }}><span className="c-FENCE"><VerdictIcon v="FENCE" size={16} /></span> Fence</span>
          <span className="row" style={{ gap: 6 }}><span className="c-UNKNOWN"><VerdictIcon v="UNKNOWN" size={16} /></span> Unknown</span>
          <span className="grow" />
          <span className="pill" style={{ fontSize: 15, padding: "8px 16px", fontWeight: 600, color: "var(--text)" }}><span className="dot" style={{ background: "var(--ok)" }} />{stack}</span>
        </div>
      </div>
    </div>
  );
}
