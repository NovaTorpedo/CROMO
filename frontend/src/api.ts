// Thin client for the CROMO API. The browser never holds model or Evolus keys; the only
// secret it may send is the demo passcode a viewer types in (X-Access-Token).

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
  return handle<T>(await fetch(path, { headers: headers(false) }));
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  return handle<T>(await fetch(path, { method: "POST", headers: headers(), body: body === undefined ? undefined : JSON.stringify(body) }));
}

/** Stream newline-delimited JSON events (investigations, replays). */
export async function streamNdjson(
  path: string,
  method: "GET" | "POST",
  onEvent: (ev: any) => void,
  signal?: AbortSignal,
): Promise<void> {
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
