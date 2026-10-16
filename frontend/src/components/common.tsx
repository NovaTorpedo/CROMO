import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { CircleCheck, CircleQuestionMark, Fence, LoaderCircle, Shell } from "lucide-react";
import type { Verdict } from "../types";

// ---------------------------------------------------------------- routing (hash based, no dependency)
export interface Route { path: string[]; query: URLSearchParams }

function parse(): Route {
  const h = window.location.hash.replace(/^#/, "") || "/";
  const [p, q] = h.split("?");
  return { path: p.split("/").filter(Boolean), query: new URLSearchParams(q || "") };
}

export function useRoute(): Route {
  const [r, setR] = useState<Route>(parse);
  useEffect(() => {
    const f = () => {
      setR(parse());
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  return r;
}

export const go = (to: string) => {
  window.location.hash = to;
};

// ---------------------------------------------------------------- verdict visuals
export const VERDICT_LABEL: Record<Verdict, string> = {
  FOSSIL: "Fossil",
  FENCE: "Fence",
  ACTIVE: "Active",
  UNKNOWN: "Unknown",
  PENDING: "Pending",
};

export const VERDICT_HELP: Record<Verdict, string> = {
  FOSSIL: "The original reason no longer applies. Waste - remove only through a controlled trial.",
  FENCE: "Looks pointless but is load-bearing (safety, quality, compliance). Protected.",
  ACTIVE: "The reason exists and is obviously still valid.",
  UNKNOWN: "No reliable reason found. Routed to a human - CROMO never guesses.",
  PENDING: "Not investigated yet.",
};

export function VerdictIcon({ v, size = 16 }: { v: Verdict; size?: number }) {
  const p = { size, strokeWidth: 2 };
  if (v === "FOSSIL") return <Shell {...p} />;
  if (v === "FENCE") return <Fence {...p} />;
  if (v === "ACTIVE") return <CircleCheck {...p} />;
  return <CircleQuestionMark {...p} />;
}

export function VerdictBadge({ v, size = "md" }: { v: Verdict; size?: "md" | "lg" }) {
  return (
    <span className={`badge v-${v}`} style={size === "lg" ? { fontSize: 14, padding: "5px 13px 5px 10px" } : undefined} title={VERDICT_HELP[v]}>
      <VerdictIcon v={v} size={size === "lg" ? 17 : 13} />
      {VERDICT_LABEL[v]}
    </span>
  );
}

export function StrengthMeter({ grade }: { grade: string | null | undefined }) {
  const n = grade === "Strong" ? 3 : grade === "Moderate" ? 2 : grade === "Weak" ? 1 : 0;
  return (
    <span className="strength" title={`Evidence strength: ${grade ?? "n/a"}`}>
      <span className="meter">
        {[1, 2, 3].map((i) => (
          <i key={i} className={i <= n ? "on" : ""} />
        ))}
      </span>
      <span className="small" style={{ fontWeight: 600 }}>{grade ?? "–"}</span>
    </span>
  );
}

export function Spinner({ size = 16 }: { size?: number }) {
  return <LoaderCircle size={size} className="spin" />;
}

export function Skeleton({ h = 18, w = "100%" }: { h?: number; w?: number | string }) {
  return <div className="skeleton" style={{ height: h, width: w }} />;
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="note danger small" role="alert">
      <strong>Something went wrong.</strong> <span>{msg}</span>
    </div>
  );
}

// ---------------------------------------------------------------- app context (mode, document drawer)
export interface DocTarget { acc: string; page?: number; quote?: string; line_start?: number; line_end?: number }
export interface Ctx {
  mode: "amd" | "fixture";
  modelLabel: string;
  openDoc: (t: DocTarget) => void;
  /** demo mode: investigations replay the recorded AMD run instead of calling the models */
  demo: boolean;
  /** "tokenfactory" | "vllm": where the AMD models are served */
  amdRoute?: string;
  /** an Evolus plant agent is connected (it runs on our own model) */
  evolusAgent?: boolean;
}
export const AppCtx = createContext<Ctx>({ mode: "fixture", modelLabel: "", openDoc: () => {}, demo: false, amdRoute: "" });
export const useApp = () => useContext(AppCtx);

export function Section({ title, eyebrow, children, right }: { title: string; eyebrow?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section style={{ marginBottom: 26 }}>
      <div className="row" style={{ marginBottom: 12, alignItems: "flex-end" }}>
        <div className="grow">
          {eyebrow && <div className="eyebrow">{eyebrow}</div>}
          <h2 className="section-title">{title}</h2>
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

export function fmtDate(d: string | null | undefined) {
  if (!d) return "undated";
  const [y, m, day] = d.split("-");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${Number(day)} ${months[Number(m) - 1] ?? ""} ${y}`;
}

export function timeAgo(ts: number | null | undefined) {
  if (!ts) return "";
  const s = Date.now() / 1000 - ts;
  if (s < 90) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return new Date(ts * 1000).toLocaleDateString();
}
