import React from "react";
import { expect, userEvent } from "@storybook/test";

import { ConsolePanel, ConsoleShell } from "../components/console-shell";
import { adminUser } from "./support/fixtures.jsx";

const NOW = "2026-10-18T07:42:00";
const FKEYS = ["F1", "F2", "F3", "F4", "F5", null];

const meta = {
  title: "Console/ConsoleShell",
  component: ConsoleShell,
  parameters: { layout: "fullscreen" },
  render: (args) => (
    <main aria-label="Ops console">
      <ConsoleShell {...args}>
        {FKEYS.map((fkey, index) => (
          <ConsolePanel key={index} id={`panel-${index + 1}`} fkey={fkey || undefined} title={`Panel ${index + 1}`}>
            <p className="consoleEmpty">Grid cell {index + 1}</p>
          </ConsolePanel>
        ))}
      </ConsoleShell>
    </main>
  ),
};

export default meta;

export const Layout = {
  args: {
    user: adminUser,
    stamp: NOW,
    status: [
      { label: "attention", value: 2, tone: "warn" },
      { label: "failed runs", value: 0, tone: "ok" },
    ],
  },
  play: async ({ canvasElement }) => {
    await expect(canvasElement.querySelectorAll("[data-panel-id]")).toHaveLength(6);
    const grid = canvasElement.querySelector(".consoleGrid");
    const style = getComputedStyle(grid);
    await expect(style.display).toBe("grid");
    await expect(style.columnGap).toBe("10px");
    await userEvent.keyboard("{F4}");
    await expect(canvasElement.querySelector('[data-panel-id="panel-4"]')).toHaveFocus();
  },
};
