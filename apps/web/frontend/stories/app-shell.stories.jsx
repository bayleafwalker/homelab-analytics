import React from "react";
import { expect, within } from "@storybook/test";

import { AppShell } from "../components/app-shell";
import { adminUser, operatorUser, storyBody } from "./support/fixtures.jsx";

function ShellStory(args) {
  return (
    <AppShell {...args}>
      {storyBody(
        "Household operating picture",
        "A stable Storybook surface for the primary authenticated shell."
      )}
    </AppShell>
  );
}

const meta = {
  title: "Shells/AppShell",
  component: AppShell,
  render: ShellStory,
};

export default meta;

export const OperatorLanding = {
  args: {
    currentPath: "/upload",
    user: operatorUser,
    title: "Homelab Analytics",
    eyebrow: "Operator control plane",
    lede: "Reviewable navigation and shell chrome for the primary product routes.",
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    await expect(canvas.getByText("Upload")).toBeInTheDocument();
    await expect(canvas.getByText("operator / operator")).toBeInTheDocument();
  },
};

export const AdminControl = {
  args: {
    currentPath: "/control",
    user: adminUser,
    title: "Homelab Analytics",
    eyebrow: "Admin control plane",
    lede: "Admin navigation exposes the control surface without changing shell structure.",
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Control")).toBeInTheDocument();
    await expect(canvas.getByRole("link", { name: "Retro" })).toBeInTheDocument();
  },
};
