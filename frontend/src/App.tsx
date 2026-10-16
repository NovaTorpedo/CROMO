import { useCallback, useEffect, useState } from "react";
import { ClipboardCheck, Cpu, GitBranch, LayoutGrid, Lock, Moon, Search, Sun } from "lucide-react";
import { STATIC, get, onAuthRequired, setToken } from "./api";
import { AppCtx, useRoute, type DocTarget } from "./components/common";
import DocDrawer from "./components/DocDrawer";
import Palette from "./components/Palette";
import MapPage from "./pages/MapPage";
import StepPage from "./pages/StepPage";
import AskPage from "./pages/AskPage";
import WhatIfPage from "./pages/WhatIfPage";
import TrialsPage from "./pages/TrialsPage";
import SystemPage from "./pages/SystemPage";
import CoverPage from "./pages/CoverPage";

interface Health { ok: boolean; mode: "amd" | "fixture"; results?: { provider: string; model: string } | null }
interface SysLite { config: { amd_route: string; roles: { reasoner: { model: string | null } } }; recordings: string[] }

const NAV: { p: string; label: string; icon: typeof LayoutGrid; also?: string[] }[] = [
  { p: "", label: "Plant", icon: LayoutGrid, also: ["step", "ask"] },
  { p: "whatif", label: "What if", icon: GitBranch, also: ["change", "tripwires"] },
  { p: "trials", label: "Trials", icon: ClipboardCheck },
  { p: "system", label: "System", icon: Cpu },
];

function initialTheme(): string {
  try {
    const q = new URLSearchParams(window.location.hash.split("?")[1] || "").get("theme");
    return q || localStorage.getItem("cromo.theme") || "light";
  } catch {
    return "light";
  }
}

export default function App() {
  const route = useRoute();
  const [theme, setTheme] = useState(initialTheme);
  const [mode, setMode] = useState<"amd" | "fixture">("fixture");
  const [modelLabel, setModelLabel] = useState("");
  const [route_, setRoute_] = useState("");
  const [recorded, setRecorded] = useState<string | null>(null);
  const [hasRecordings, setHasRecordings] = useState(false);
  const [palette, setPalette] = useState(false);
  const [demo, setDemo] = useState<boolean>(() => {
    try {
      return localStorage.getItem("cromo.demo") === "1";
    } catch {
      return false;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem("cromo.demo", demo ? "1" : "0");
    } catch {
      /* storage unavailable */
    }
  }, [demo]);
  const [doc, setDoc] = useState<DocTarget | null>(null);
  const [needPass, setNeedPass] = useState(false);
  const [pass, setPass] = useState("");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("cromo.theme", theme);
    } catch {
      /* storage unavailable */
    }
  }, [theme]);

  useEffect(() => {
    get<Health>("/api/health")
      .then((h) => {
        setMode(h.mode);
        if (h.mode === "fixture" && h.results?.provider === "amd") setRecorded(h.results.model);
      })
      .catch(() => {});
    get<SysLite>("/api/system")
      .then((s) => {
        setModelLabel(s.config.roles.reasoner.model ?? "");
        setRoute_(s.config.amd_route);
        setHasRecordings((s.recordings ?? []).length > 0);
      })
      .catch(() => {});
    return onAuthRequired(() => setNeedPass(true));
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLElement && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName);
      if ((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !typing)) {
        e.preventDefault();
        setPalette(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const openDoc = useCallback((t: DocTarget) => setDoc(t), []);
  const page = route.path[0] ?? "";
  if (page === "cover") return <CoverPage />;

  let content;
  if (page === "step" && route.path[1]) content = <StepPage stepId={route.path[1].toUpperCase()} query={route.query} />;
  else if (page === "ask") content = <AskPage initial={route.query.get("q") ?? ""} />;
  else if (page === "whatif" || page === "change" || page === "tripwires")
    content = <WhatIfPage tab={page === "tripwires" || route.query.get("tab") === "plant" ? "plant" : "step"} query={route.query} />;
  else if (page === "trials") content = <TrialsPage focus={route.query.get("id") ?? ""} />;
  else if (page === "system") content = <SystemPage />;
  else content = <MapPage onAsk={() => setPalette(true)} />;

  const where = route_ === "tokenfactory" ? "AMD Token Factory" : "AMD";
  const status = STATIC
    ? recorded ? "Public demo · recorded AMD results" : "Public demo · offline results"
    : mode === "amd" ? `Live on ${where} · ${modelLabel || "vLLM"}` : recorded ? `Recorded AMD results · ${recorded}` : "Offline mode · no AMD model";

  return (
    <AppCtx.Provider value={{ mode, modelLabel, openDoc, demo: demo && hasRecordings, amdRoute: route_ }}>
      <div className="app">
        <div className="topbar-wrap">
          <header className="topbar glass">
            <a className="logo" href="#/" aria-label="CROMO home">
              <span className="logo-tile"><small>24</small>Cr</span>
              <span className="logo-word">CROMO</span>
            </a>
            <nav className="nav" aria-label="Main">
              {NAV.map(({ p, label, icon: Icon, also }) => (
                <a key={p} href={`#/${p}`} className={page === p || also?.includes(page) ? "on" : ""} aria-label={label}>
                  <Icon size={15} /> <span className="lbl">{label}</span>
                </a>
              ))}
            </nav>
            <span className="spacer" />
            <button className="ask-trigger" onClick={() => setPalette(true)} aria-label="Ask why about any step">
              <Search size={15} /> <span className="grow label">Ask why about any step…</span> <span className="kbd">Ctrl K</span>
            </button>
            <a href="#/system" className={`pill status ${recorded ? "replay" : mode}`} title={status}>
              <span className="dot" /> <span className="txt">{status}</span>
            </a>
            {hasRecordings && !STATIC && (
              <label className={`pill ${demo ? "replay" : ""}`} title="Demo mode: investigations replay recorded AMD runs (survives GPU or network failure)" style={{ cursor: "pointer" }}>
                <input type="checkbox" checked={demo} onChange={(e) => setDemo(e.target.checked)} style={{ margin: 0 }} />
                Replay
              </label>
            )}
            <button className="icon-btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="Toggle dark mode">
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </header>
        </div>
        <main className="main">{content}</main>
        <footer className="footer">
          CROMO recovers why factory steps exist · All plant data is a <strong>synthetic archive of a fictional company</strong> · MIT licensed · AMD
          Developer Hackathon ACT III
        </footer>
        {palette && <Palette onClose={() => setPalette(false)} />}
        {doc && <DocDrawer target={doc} onClose={() => setDoc(null)} />}
        {needPass && (
          <>
            <div className="scrim" onClick={() => setNeedPass(false)} />
            <div className="palette glass" style={{ padding: 22, width: 420 }} role="dialog" aria-modal="true">
              <div className="row" style={{ marginBottom: 8 }}>
                <Lock size={18} />
                <strong>Demo passcode required</strong>
              </div>
              <p className="small muted" style={{ marginTop: 0 }}>
                Live investigations use GPU time and Evolus credits, so this public demo is protected. Everything else stays open.
              </p>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  setToken(pass);
                  setNeedPass(false);
                }}
                className="row"
              >
                <input className="input" type="password" value={pass} onChange={(e) => setPass(e.target.value)} placeholder="Passcode" autoFocus />
                <button className="btn primary">Unlock</button>
              </form>
            </div>
          </>
        )}
      </div>
    </AppCtx.Provider>
  );
}
