import React from "react";
import { expect, within } from "@storybook/test";
import { http, HttpResponse } from "msw";

import { UploadDetectionWizard } from "../components/upload-detection-wizard";

const meta = {
  title: "Guided Onboarding/UploadDetectionWizard",
  component: UploadDetectionWizard,
};

export default meta;

export const AcceptRetryGating = {
  parameters: {
    msw: {
      handlers: (() => {
        let dryRunAttempts = 0;

        return [
          http.post("/upload/detect", () =>
            HttpResponse.json({
              detection: {
                candidate: {
                  kind: "configured_csv",
                  title: "Configured CSV upload",
                  contract_id: "configured/source_asset_demo",
                  upload_path: "/upload/configured-csv",
                  source_asset_id: "source_asset_demo",
                  confidence_label: "high",
                  confidence_score: 0.95,
                  matched_columns: ["date", "amount", "description"],
                  missing_columns: [],
                  expected_columns: ["date", "amount", "description"],
                },
                alternatives: [],
              },
            })
          ),
          http.post("/upload/dry-run", () => {
            dryRunAttempts += 1;
            const withIssues = dryRunAttempts === 1;
            return HttpResponse.json({
              preview: {
                target: {
                  title: "Configured CSV upload",
                },
                row_count: 1,
                date_range: {
                  start: "2026-03-01",
                  end: "2026-03-01",
                  column: "date",
                },
                issues: withIssues
                  ? [
                      {
                        code: "invalid_amount",
                        message: "Unknown column value",
                        column: "amount",
                        row_number: 1,
                      },
                    ]
                  : [],
              },
            });
          }),
        ];
      })(),
    },
  },
  args: {
    activeSourceAssets: [{ source_asset_id: "source_asset_demo" }],
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Source Type Detection")).toBeInTheDocument();
    await expect(canvas.getByRole("button", { name: "Run dry-run" })).toBeDisabled();
  },
};
