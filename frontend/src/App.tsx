import { useCallback, useEffect, useState } from "react";
import { Lock, Moon, Sun } from "lucide-react";
import { STATIC, get, onAuthRequired, setToken } from "./api";
import { AppCtx, useRoute, type DocTarget } from "./components/common";
import DocDrawer from "./components/DocDrawer";
import MapPage from "./pages/MapPage";
import StepPage from "./pages/StepPage";
import AskPage from "./pages/AskPage";
import TripwiresPage from "./pages/TripwiresPage";
import ChangePage from "./pages/ChangePage";
import TrialsPage from "./pages/TrialsPage";
import SystemPage from "./pages/SystemPage";

interface Health { ok: boolean; mode: "amd" | "fixture"; results?: { provider: string; model: string } | null }
interface SysLite { config: { roles: { reasoner: { model: string | null } } } }

const NAV: [string, string][] = [
  ["", "Plant map"],
  ["ask", "Ask why"],
  ["tripwires", "Tripwires"],
  ["change", "Check a change"],
  ["trials", "Trials"],
  ["system", "System"],
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
  const [recorded, setRecorded] = useState<string | null>(null);
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
    get<SysLite>("/api/system").then((s) => setModelLabel(s.config.roles.reasoner.model ?? "")).catch(() => {});
    return onAuthRequired(() => setNeedPass(true));
  }, []);

  const openDoc = useCallback((t: DocTarget) => setDoc(t), []);
  const page = route.path[0] ?? "";

  let content;
  if (page === "step" && route.path[1]) content = <StepPage stepId={route.path[1].toUpperCase()} query={route.query} />;
  else if (page === "ask") content = <AskPage initial={route.query.get("q") ?? ""} />;
  else if (page === "tripwires") content = <TripwiresPage preset={route.query.get("preset") ?? ""} />;
  else if (page === "change") content = <ChangePage initial={route.query.get("p") ?? ""} />;
  else if (page === "trials") content = <TrialsPage focus={route.query.get("id") ?? ""} />;
  else if (page === "system") content = <SystemPage />;
  else content = <MapPage />;

  return (
    <AppCtx.Provider value={{ mode, modelLabel, openDoc }}>
      <div className="app">
        <header className="topbar">
          <a className="logo" href="#/" aria-label="CROMO home">
            <span className="logo-tile"><small>24</small>Cr</span>
            <span className="logo-word">CROMO</span>
          </a>
          <nav className="nav" aria-label="Main">
            {NAV.map(([p, label]) => (
              <a key={p} href={`#/${p}`} className={page === p || (p === "" && page === "step") ? "on" : ""}>{label}</a>
            ))}
          </nav>
          <div className="spacer" />
          <a href="#/system" className={`pill ${recorded ? "replay" : mode}`} title="Where the models run">
            <span className="dot" />
            {STATIC ? (recorded ? `Public demo · recorded AMD results` : "Public demo · offline results") : mode === "amd" ? `Live on AMD · ${modelLabel || "vLLM"}` : recorded ? `Recorded AMD results · ${recorded}` : "Offline mode · no AMD model connected"}
          </a>
          <button className="icon-btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="Toggle dark mode">
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </header>
        <main className="main">{content}</main>
        <footer className="footer">
          CROMO recovers why factory steps exist · All plant data is a <strong>synthetic archive of a fictional company</strong> · MIT licensed · AMD
          Developer Hackathon ACT III
        </footer>
        {doc && <DocDrawer target={doc} onClose={() => setDoc(null)} />}
        {needPass && (
          <>
            <div className="drawer-back" onClick={() => setNeedPass(false)} />
            <div className="card card-pad" style={{ position: "fixed", zIndex: 80, top: "28%", left: "50%", transform: "translateX(-50%)", width: 400 }}>
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
