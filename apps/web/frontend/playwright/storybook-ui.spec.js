const { test, expect } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;

async function gotoStory(page, storyId) {
  await page.goto(`/iframe.html?id=${storyId}&viewMode=story`);
  await expect(page.locator("#storybook-root")).toBeVisible();
  await expect(page.locator("#storybook-root")).not.toContainText(
    "The component failed to render properly"
  );
}

function violationMessage(violations) {
  return violations
    .map((violation) => `${violation.id}: ${violation.nodes.length} node(s)`)
    .join("\n");
}

test("app shell story stays accessible and visually stable", async ({ page }) => {
  await gotoStory(page, "shells-appshell--admin-control");
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.locator("main")).toHaveScreenshot("app-shell-admin-control.png");

  const results = await new AxeBuilder({ page }).include("main").analyze();
  expect(results.violations, violationMessage(results.violations)).toEqual([]);
});

test("retro shell story stays accessible and visually stable", async ({ page }) => {
  await gotoStory(page, "shells-retroshell--admin-control");
  await expect(page.getByRole("navigation", { name: "Retro navigation" })).toBeVisible();
  await expect(page.locator("main")).toHaveScreenshot("retro-shell-admin-control.png");

  const results = await new AxeBuilder({ page }).include("main").analyze();
  expect(results.violations, violationMessage(results.violations)).toEqual([]);
});

test("msw-backed story resolves mocked response", async ({ page }) => {
  await gotoStory(page, "data-fetch-mockstatuscard--healthy-status");
  await expect(page.getByText("Connected to Storybook contract mocks.")).toBeVisible();
  await expect(page.getByText("retro-shell")).toBeVisible();
});

test("upload wizard enforces accept/retry gating before upload", async ({ page }) => {
  await gotoStory(page, "guided-onboarding-uploaddetectionwizard--accept-retry-gating");

  const fileInput = page.locator('input[type="file"]');
  const runDryRunButton = page.getByRole("button", { name: "Run dry-run" });
  const uploadButton = page.getByRole("button", { name: "Upload file" });

  await expect(runDryRunButton).toBeDisabled();
  await expect(uploadButton).toBeDisabled();

  await fileInput.setInputFiles({
    name: "sample.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("date,amount,description\n2026-03-01,24.50,Grocery\n"),
  });

  await expect(page.getByText("Detected target")).toBeVisible();
  await expect(runDryRunButton).toBeEnabled();

  await runDryRunButton.click();

  await expect(page.getByText("Dry-run preview")).toBeVisible();
  await expect(
    page.getByText(
      "Decision point: accept the preview to continue or retry dry-run after fixing inputs."
    )
  ).toBeVisible();
  await expect(page.getByText("Unknown column value")).toBeVisible();
  await expect(uploadButton).toBeDisabled();

  await page.getByRole("button", { name: "Accept preview" }).click();
  await expect(page.getByText("Dry-run accepted. Upload is now enabled.")).toBeVisible();
  await expect(uploadButton).toBeEnabled();

  await page.getByRole("button", { name: "Retry dry-run" }).click();
  await expect(
    page.getByText(
      "Decision point: accept the preview to continue or retry dry-run after fixing inputs."
    )
  ).toBeVisible();
  await expect(page.getByText("Unknown column value")).toHaveCount(0);
  await expect(uploadButton).toBeDisabled();

  await page.getByRole("button", { name: "Accept preview" }).click();
  await expect(uploadButton).toBeEnabled();
});
