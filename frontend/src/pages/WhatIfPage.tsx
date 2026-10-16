import { BellRing, Scale } from "lucide-react";
import ChangePage from "./ChangePage";
import TripwiresPage from "./TripwiresPage";

/** One page for the two forward-looking questions: "can we change this step?" and "what breaks if the plant changes?" */
export default function WhatIfPage({ tab, query }: { tab: "step" | "plant"; query: URLSearchParams }) {
  return (
    <div>
      <div className="page-head row wrap" style={{ alignItems: "flex-end", gap: 18 }}>
        <div className="grow">
          <div className="eyebrow">What if…?</div>
          <h1 className="h1" style={{ marginTop: 6 }}>Before anything changes, ask which reasons break.</h1>
        </div>
        <nav className="seg" aria-label="What if">
          <a href="#/change" className={tab === "step" ? "on" : ""} aria-current={tab === "step" ? "page" : undefined}><Scale size={15} /> Change a step</a>
          <a href="#/tripwires" className={tab === "plant" ? "on" : ""} aria-current={tab === "plant" ? "page" : undefined}><BellRing size={15} /> Change the plant</a>
        </nav>
      </div>
      {tab === "step" ? <ChangePage initial={query.get("p") ?? ""} /> : <TripwiresPage preset={query.get("preset") ?? ""} />}
    </div>
  );
}
