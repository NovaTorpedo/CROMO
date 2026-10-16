import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

// Production builds carry their own Content-Security-Policy, because GitHub Pages cannot send headers
// (the backend also sends it as a header). Not applied to the dev server, whose HMR needs inline scripts.
const CSP =
  "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; " +
  "connect-src 'self'; font-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'self'";
const cspMeta = (): Plugin => ({
  name: "cromo-csp-meta",
  apply: "build",
  transformIndexHtml: () => [{ tag: "meta", attrs: { "http-equiv": "Content-Security-Policy", content: CSP }, injectTo: "head-prepend" }],
});

// CROMO_BASE=/CROMO/ for the GitHub Pages static demo; "/" when served by the backend.
export default defineConfig({
  base: process.env.CROMO_BASE || "/",
  plugins: [react(), cspMeta()],
  server: { port: 5173, proxy: { "/api": process.env.CROMO_API || "http://localhost:8765" } },
  build: { outDir: process.env.CROMO_OUT || "dist", emptyOutDir: !process.env.CROMO_OUT, sourcemap: false, chunkSizeWarningLimit: 900 },
});
