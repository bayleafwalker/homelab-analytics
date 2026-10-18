import React from "react";

import { StatePanel } from "../components/state-panel";

export default function NotFound() {
  return (
    <main className="standalonePage" id="main-content">
      <a href="/" className="wordmark">
        Kotona
      </a>
      <StatePanel
        tone="empty"
        title="There's no page at this address"
        action={{ href: "/", label: "Go to dashboard" }}
        secondaryAction={{ href: "/cashflow", label: "Open the cashflow map" }}
      >
        <p>The link may be old, or the page moved. Press Ctrl K on any page to jump to the one you need.</p>
      </StatePanel>
    </main>
  );
}
