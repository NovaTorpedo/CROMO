import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/600.css";
import "@fontsource-variable/fraunces";
import "./styles.css";
import App from "./App";

try {
  document.documentElement.dataset.theme = localStorage.getItem("cromo.theme") || "light";
} catch {
  document.documentElement.dataset.theme = "light";
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
