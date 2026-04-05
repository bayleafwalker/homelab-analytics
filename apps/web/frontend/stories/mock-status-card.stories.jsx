import React from "react";
import { expect, within } from "@storybook/test";
import { delay, http, HttpResponse } from "msw";

import { MockStatusCard } from "./support/mock-status-card.jsx";

const meta = {
  title: "Data Fetch/MockStatusCard",
  component: MockStatusCard,
};

export default meta;

export const HealthyStatus = {
  parameters: {
    msw: {
      handlers: [
        http.get("/storybook/status", async () => {
          await delay(50);
          return HttpResponse.json({
            message: "Connected to Storybook contract mocks.",
            contract: "retro-shell",
            mode: "publish",
          });
        }),
      ],
    },
  },
  args: {
    endpoint: "/storybook/status",
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(
      await canvas.findByText("Connected to Storybook contract mocks.")
    ).toBeInTheDocument();
    await expect(canvas.getByText("retro-shell")).toBeInTheDocument();
  },
};
