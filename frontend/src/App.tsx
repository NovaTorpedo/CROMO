import { useCallback, useEffect, useState } from "react";
import { Lock, Moon, Search, Sun } from "lucide-react";
import { get, onAuthRequired, setToken } from "./api";
import { AppCtx, go, useRoute, type DocTarget } from "./components/common";
import DocDrawer from "./components/DocDrawer";
import MapPage from "./pages/MapPage";
import StepPage from "./pages/StepPage";
import AskPage from "./pages/AskPage";
import TripwiresPage from "./pages/TripwiresPage";
import ChangePage from "./pages/ChangePage";
import TrialsPage from "./pages/TrialsPage";
import SystemPage from "./pages/SystemPage";

interface Health { ok: boolean; mode: "amd" | "fixture" }
interface SysLite { config: { roles: { reasoner: { model: string | null } }; hardware: string } }

const NAV = [
  ["", "Fossil Map"],
  ["ask", "Ask"],
  ["tripwires", "Tripwires"],
  ["change", "Before you change"],
  ["trials", "Trials"],
  ["system", "System · AMD"],
];

function useTheme() {
  const [theme, setTheme] = useState<string>(() => {
    try {
      return localStorage.getItem("cromo.theme") || "dark";
    } catch {
      return "dark";
    }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("cromo.theme", theme);
    } catch {
      /* ignore */
    }
  }, [theme]);
  return [theme, setTheme] as const;
}

export default function App() {
  const route = useRoute();
  const [theme, setTheme] = useTheme();
  const [mode, setMode] = useState<"amd" | "fixture">("fixture");
  const [modelLabel, setModelLabel] = useState("");
  const [doc, setDoc] = useState<DocTarget | null>(null);
  const [needPass, setNeedPass] = useState(false);
  const [pass, setPass] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    get<Health>("/api/health").then((h) => setMode(h.mode)).catch(() => {});
    get<SysLite>("/api/system")
      .then((s) => setModelLabel(`${s.config.roles.reasoner.model ?? ""}`))
      .catch(() => {});
    return onAuthRequired(() => setNeedPass(true));
  }, []);

  const openDoc = useCallback((t: DocTarget) => setDoc(t), []);
  const page = route.path[0] ?? "";

  let content;
  if (page === "step" && route.path[1]) content = <StepPage stepId={route.path[1].toUpperCase()} query={route.query} />;
  else if (page === "ask") content = <AskPage initial={route.query.get("q") ?? ""} />;
  else if (page === "tripwires") content = <TripwiresPage />;
  else if (page === "change") content = <ChangePage initial={route.query.get("p") ?? ""} />;
  else if (page === "trials") content = <TrialsPage focus={route.query.get("id") ?? ""} />;
  else if (page === "system") content = <SystemPage />;
  else content = <MapPage />;

  return (
    <AppCtx.Provider value={{ mode, modelLabel, openDoc }}>
      <div className="app">
        <header className="topbar">
          <a className="logo" href="#/" aria-label="CROMO home">
            <span className="logo-tile">
              <small>24</small>Cr
            </span>
            <span className="logo-word">CROMO</span>
          </a>
          <nav className="nav" aria-label="Main">
            {NAV.map(([p, label]) => (
              <a key={p} href={`#/${p}`} className={page === p || (p === "" && page === "step") ? "on" : ""}>
                {label}
              </a>
            ))}
          </nav>
          <div className="spacer" />
          <form
            className="row"
            style={{ gap: 6 }}
            onSubmit={(e) => {
              e.preventDefault();
              if (q.trim()) go(`/ask?q=${encodeURIComponent(q.trim())}`);
            }}
          >
            <div style={{ position: "relative" }}>
              <Search size={15} style={{ position: "absolute", left: 10, top: 10, opacity: 0.6 }} />
              <input
                className="input"
                style={{ paddingLeft: 32, width: 250, paddingTop: 7, paddingBottom: 7 }}
                placeholder="Ask about any step…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                aria-label="Ask about any step"
              />
            </div>
          </form>
          <a href="#/system" className={`mode-badge ${mode === "amd" ? "mode-amd" : "mode-fixture"}`} title="Where the models run">
            <span className={`dot ${mode === "amd" ? "pulse" : ""}`} />
            {mode === "amd" ? `AMD live · ${modelLabel || "vLLM"}` : "Offline fixture mode"}
          </a>
          <button className="icon-btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="Toggle theme">
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </header>
        <main className="main">{content}</main>
        <footer className="footer">
          CROMO · recovers why factory steps exist · Data: <strong>synthetic archive of a fictional plant</strong> (Valdorso Coatings) ·
          MIT licensed · Built for the AMD Developer Hackathon ACT III
        </footer>
        {doc && <DocDrawer target={doc} onClose={() => setDoc(null)} />}
        {needPass && (
          <>
            <div className="drawer-back" onClick={() => setNeedPass(false)} />
            <div className="card card-pad" style={{ position: "fixed", zIndex: 80, top: "30%", left: "50%", transform: "translateX(-50%)", width: 380 }}>
              <div className="row" style={{ marginBottom: 8 }}>
                <Lock size={18} />
                <strong>Demo passcode required</strong>
              </div>
              <p className="small muted" style={{ marginTop: 0 }}>
                Live investigations spend GPU time and Evolus credits, so this public demo is protected. Read-only views and recorded AMD runs
                stay open to everyone.
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
