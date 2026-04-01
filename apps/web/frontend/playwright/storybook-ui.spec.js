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
