// Thin client for the CROMO API. The browser never holds model or Evolus keys; the only
// secret it may send is the demo passcode a viewer types in (X-Access-Token).
//
// STATIC mode (VITE_STATIC=1) serves the public read-only demo from pre-exported JSON
// files (scripts/export_static.py) so it can be hosted for free on GitHub Pages.

export const STATIC = import.meta.env.VITE_STATIC === "1";
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
const TOKEN_KEY = "cromo.passcode";

export function getToken(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}
export function setToken(t: string) {
  try {
    sessionStorage.setItem(TOKEN_KEY, t);
  } catch {
    /* storage unavailable */
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type Listener = () => void;
const authListeners = new Set<Listener>();
export function onAuthRequired(fn: Listener) {
  authListeners.add(fn);
  return () => {
    authListeners.delete(fn);
  };
}

export const slug = (s: string) => s.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80);

/** Map an API path to a static JSON file of the exported demo. */
function staticPath(path: string): string {
  const [p, q] = path.split("?");
  const qs = new URLSearchParams(q || "");
  let m;
  if ((m = p.match(/^\/api\/steps\/([A-Z]+-\d+)\/events$/))) return `${BASE}/data/events/${m[1]}.json`;
  if ((m = p.match(/^\/api\/steps\/([A-Z]+-\d+)$/))) return `${BASE}/data/steps/${m[1]}.json`;
  if ((m = p.match(/^\/api\/docs\/(ACC-\d+)$/))) return `${BASE}/data/docs/${m[1]}.json`;
  if (p === "/api/compare") return `${BASE}/data/compare/${qs.get("a")}_${qs.get("b")}.json`;
  return `${BASE}/data${p.replace(/^\/api/, "")}.json`;
}

export function pageUrl(acc: string, page: number) {
  return STATIC ? `${BASE}/data/pages/${acc}-${page}.webp` : `/api/docs/${acc}/pages/${page}`;
}

function headers(json = true): HeadersInit {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  const t = getToken();
  if (t) h["X-Access-Token"] = t;
  return h;
}

async function handle<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j?.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* not json */
    }
    if (r.status === 401) authListeners.forEach((f) => f());
    throw new ApiError(r.status, msg);
  }
  return r.json() as Promise<T>;
}

export async function get<T>(path: string): Promise<T> {
  if (STATIC) {
    const r = await fetch(staticPath(path));
    if (!r.ok) throw new ApiError(404, "Not included in the public demo. Run CROMO locally for this.");
    return r.json() as Promise<T>;
  }
  return handle<T>(await fetch(path, { headers: headers(false) }));
}

const READ_ONLY = "This public demo is read-only (pre-recorded results). Run CROMO locally - `docker compose up` - for live use.";

async function staticPost<T>(path: string, body: any): Promise<T> {
  let file: string | null = null;
  if (path === "/api/v1/change-check") file = `${BASE}/data/change/${slug(body.proposal)}.json`;
  else if (path === "/api/tripwires/simulate") file = `${BASE}/data/tripwires/${slug(`${body.from}-${body.to}`)}.json`;
  else if (path === "/api/ask") file = `${BASE}/data/ask/${slug(body.question)}.json`;
  if (file) {
    const r = await fetch(file);
    if (r.ok) return r.json() as Promise<T>;
    throw new ApiError(403, "The public demo includes pre-computed answers for the example buttons only. " + READ_ONLY);
  }
  throw new ApiError(403, READ_ONLY);
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  if (STATIC) return staticPost<T>(path, body);
  return handle<T>(await fetch(path, { method: "POST", headers: headers(), body: body === undefined ? undefined : JSON.stringify(body) }));
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Stream newline-delimited JSON events (investigations, replays). */
export async function streamNdjson(path: string, method: "GET" | "POST", onEvent: (ev: any) => void, signal?: AbortSignal): Promise<void> {
  if (STATIC) {
    // live investigations and replays both replay the recorded event stream with its original timing
    const step = path.match(/\/api\/steps\/([A-Z]+-\d+)\//)?.[1];
    let rec: { events: any[]; recorded_at?: number; provider?: string; models?: any; hardware?: string } | null = null;
    const r = await fetch(`${BASE}/data/runs/${step}.json`);
    if (r.ok) rec = await r.json();
    else {
      const e = await fetch(`${BASE}/data/events/${step}.json`);
      if (!e.ok) throw new ApiError(404, "No recorded run for this step.");
      rec = await e.json();
    }
    if (rec?.recorded_at) onEvent({ type: "replay", recorded_at: rec.recorded_at, provider: rec.provider, models: rec.models, hardware: rec.hardware });
    let prev: number | null = null;
    for (const ev of rec!.events) {
      if (signal?.aborted) return;
      if (prev !== null && ev.t) await sleep(Math.min(1800, Math.max(60, (ev.t - prev) * 1000)));
      prev = ev.t ?? prev;
      onEvent(ev);
    }
    return;
  }
  const r = await fetch(path, { method, headers: headers(false), signal });
  if (!r.ok || !r.body) {
    await handle(r);
    return;
  }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (line) {
        try {
          onEvent(JSON.parse(line));
        } catch {
          /* ignore malformed line */
        }
      }
    }
  }
}

export const eur = (n: number | null | undefined, compact = false) => {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  if (compact && Math.abs(n) >= 1000) return `€${(n / 1000).toFixed(n >= 100000 ? 0 : 1)}k`;
  return `€${Math.round(n).toLocaleString("en-US")}`;
};
