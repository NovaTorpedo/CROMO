import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// CROMO_BASE=/CROMO/ for the GitHub Pages static demo; "/" when served by the backend.
export default defineConfig({
  base: process.env.CROMO_BASE || "/",
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8765" } },
  build: { outDir: process.env.CROMO_OUT || "dist", emptyOutDir: !process.env.CROMO_OUT, sourcemap: false, chunkSizeWarningLimit: 900 },
});
