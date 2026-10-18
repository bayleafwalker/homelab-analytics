import React from "react";
import { expect, within } from "@storybook/test";

import { CommandPalette } from "../components/command-palette";
import { paletteEntriesForUser } from "../lib/nav-model";
import { adminUser } from "./support/fixtures.jsx";

const meta = {
  title: "Shells/CommandPalette",
  component: CommandPalette,
  parameters: { layout: "padded" },
  render: (args) => (
    <main style={{ maxWidth: 240 }}>
      <CommandPalette {...args} />
    </main>
  ),
};

export default meta;

export const AdminEntries = {
  args: {
    entries: paletteEntriesForUser(adminUser),
    currentPath: "/reports",
  },
  // Interaction is covered by playwright/ui-innovation.spec.js; a play
  // function here would race the keyboard test.
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole("button", { name: /Jump to a page/ })).toBeInTheDocument();
  },
};
