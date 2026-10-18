import React, { useState } from "react";

import { WallRefreshControl } from "../components/wallboard-live";

// Drives the wallboard refresh loop without the Next router: each refresh
// bumps a counter so Playwright can check when the board would re-render.

function RefreshHarness({ intervalMs }) {
  const [count, setCount] = useState(0);
  return (
    <main aria-label="Wallboard refresh">
      <div className="wall" style={{ minHeight: "auto" }}>
        <WallRefreshControl
          renderedAt="2026-10-18T07:42:00Z"
          intervalMs={intervalMs}
          refresh={() => setCount((value) => value + 1)}
        />
        <p className="wallLine">
          Refreshes: <span data-testid="refresh-count">{count}</span>
        </p>
      </div>
    </main>
  );
}

const meta = {
  title: "Wallboard/Refresh",
  component: WallRefreshControl,
  parameters: { layout: "fullscreen" },
  render: (args) => <RefreshHarness {...args} />,
};

export default meta;

// Long interval: only visibility changes and hotkeys trigger refreshes.
export const ManualOnly = {
  args: { intervalMs: 3_600_000 },
};

// Short interval to observe ticks being skipped while hidden or hovered.
export const FastTick = {
  args: { intervalMs: 300 },
};
