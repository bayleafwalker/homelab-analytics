import React from "react";
import { expect, within } from "@storybook/test";

import { RetroShell } from "../components/retro-shell";
import { adminUser, operatorUser, retroStoryBody } from "./support/fixtures.jsx";

function ShellStory(args) {
  return (
    <RetroShell {...args}>
      {retroStoryBody(
        "Retro operating picture",
        "A stable Storybook surface for the alternate CRT-style renderer."
      )}
    </RetroShell>
  );
}

const meta = {
  title: "Shells/RetroShell",
  component: RetroShell,
  render: ShellStory,
};

export default meta;

export const OperatorOverview = {
  args: {
    currentPath: "/retro",
    user: operatorUser,
    title: "Homelab Analytics // CRT",
    eyebrow: "Parallel retro shell",
    lede: "Reviewable shell state for operator navigation and status chrome.",
    renderedAt: "2026-04-01 11:24:00",
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByLabelText("Retro navigation")).toBeInTheDocument();
    await expect(canvas.getByText("LINK: STABLE")).toBeInTheDocument();
    await expect(canvas.getByText("operator / operator")).toBeInTheDocument();
  },
};

export const AdminControl = {
  args: {
    currentPath: "/retro/control",
    user: adminUser,
    title: "Homelab Analytics // CRT",
    eyebrow: "Parallel retro shell",
    lede: "Admin routes expose control, catalog, execution, and terminal links.",
    renderedAt: "2026-04-01 11:24:00",
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Control")).toBeInTheDocument();
    await expect(canvas.getByText("Catalog")).toBeInTheDocument();
    await expect(canvas.getByText("Terminal")).toBeInTheDocument();
  },
};
