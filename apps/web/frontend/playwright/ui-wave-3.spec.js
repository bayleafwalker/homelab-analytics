const { test, expect } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;

// Behaviour and accessibility checks for the wave-3 primitives: <Explain>,
// <ResponsiveTable> and <AsOfScrubber>. No screenshot baselines (CI-owned).

async function gotoStory(page, storyId) {
  await page.goto(`/iframe.html?id=${storyId}&viewMode=story`);
  await expect(page.locator("#storybook-root")).toBeVisible();
  await expect(page.locator("#storybook-root")).not.toContainText(
    "The component failed to render properly"
  );
}

async function expectAccessible(page) {
  const results = await new AxeBuilder({ page }).include("#storybook-root").analyze();
  const message = results.violations.map((v) => `${v.id}: ${v.nodes.length} node(s)`).join("\n");
  expect(results.violations, message).toEqual([]);
}

test("explain opens from the keyboard and closes with Escape", async ({ page }) => {
  await gotoStory(page, "primitives-explain--no-lineage-recorded");
  const trigger = page.locator("summary.explainTrigger");
  await expect(trigger).toHaveAccessibleName(/Explain Income, December 2025/);
  const panel = page.locator(".explainPanel");
  await expect(panel).toBeHidden();

  await trigger.focus();
  await page.keyboard.press("Enter");
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("mart_monthly_cashflow");
  await expect(panel).toContainText("No runs or sources recorded behind it yet");
  await expect(page.getByRole("link", { name: "Trace full lineage" })).toHaveAttribute(
    "href",
    "/briefing/lineage?publication_key=mart_monthly_cashflow"
  );
  await expectAccessible(page);

  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
  await expect(trigger).toBeFocused();
});

test("explain closes on an outside click", async ({ page }) => {
  await gotoStory(page, "primitives-explain--recorded-lineage");
  await page.locator("summary.explainTrigger").click();
  await expect(page.locator(".explainPanel")).toContainText("3 ingestion runs behind it");
  // The DuckDB path records the chain: mart <- relations <- runs <- assets <- systems.
  await expect(page.locator(".explainPanel")).toContainText("2 relations it was built from");
  await expect(page.locator(".explainPanel")).toContainText("fact_transaction");
  await expect(page.locator(".explainPanel")).toContainText("3 source assets landed");
  await page.mouse.click(5, 500);
  await expect(page.locator(".explainPanel")).toBeHidden();
});

test("explain says when the lineage walk left older runs out", async ({ page }) => {
  await gotoStory(page, "primitives-explain--truncated-lineage");
  await page.locator("summary.explainTrigger").click();
  await expect(page.getByTestId("explain-lineage-truncated")).toContainText(
    "Showing the 50 most recent runs of 212"
  );
  await expectAccessible(page);
});

test("explain says nothing about truncation for a whole graph", async ({ page }) => {
  await gotoStory(page, "primitives-explain--recorded-lineage");
  await page.locator("summary.explainTrigger").click();
  await expect(page.locator(".explainPanel")).toBeVisible();
  await expect(page.getByTestId("explain-lineage-truncated")).toHaveCount(0);
});

for (const story of ["lineage-unavailable", "wallboard"]) {
  test(`explain ${story} stays accessible when open`, async ({ page }) => {
    await gotoStory(page, `primitives-explain--${story}`);
    await page.locator("summary.explainTrigger").click();
    await expect(page.locator(".explainPanel")).toBeVisible();
    await expectAccessible(page);
  });
}

test("explain panel stays inside a phone-width viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await gotoStory(page, "primitives-explain--recorded-lineage");
  await page.locator("summary.explainTrigger").click();
  const box = await page.locator(".explainPanel").boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(390);
});

test("responsive table is a table on wide screens and slips at phone width", async ({ page }) => {
  await gotoStory(page, "primitives-responsivetable--sources");
  await expect(page.locator(".rtable thead")).toBeVisible();
  await expectAccessible(page);

  await page.setViewportSize({ width: 390, height: 800 });
  await gotoStory(page, "primitives-responsivetable--sources");
  const scroll = await page.locator(".rtable").evaluate((el) => el.scrollWidth - el.clientWidth);
  expect(scroll).toBeLessThanOrEqual(1);
  await expect(page.locator("td[data-primary='true']").first()).toContainText("OP personal account");
  const label = await page
    .locator("td[data-label='Last ingested']")
    .first()
    .evaluate((el) => getComputedStyle(el, "::before").content);
  expect(label).toContain("Last ingested");
  // Still a table for assistive tech.
  await expect(page.locator(".rtable").getByRole("table")).toBeAttached();
  await expectAccessible(page);
});

test("as-of scrubber marks the viewed month and shows gaps as inert", async ({ page }) => {
  await gotoStory(page, "primitives-responsivetable--as-of-scrubber-with-gap");
  const nav = page.getByRole("navigation", { name: "View the dashboard as of a month" });
  await expect(nav.locator('[aria-current="true"]')).toHaveAccessibleName("March 2025");
  await expect(nav.getByRole("link", { name: "April 2025" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "August 2025" })).toHaveAttribute("href", "#latest");
  await expect(nav.getByRole("link", { name: "Back to latest" })).toBeVisible();
  await expectAccessible(page);
});

test("sparkline month labels stay readable and never overlap at any card width", async ({ page }) => {
  await gotoStory(page, "primitives-sparklinechart--dashboard-trend-widths");
  for (const [cardWidth, expected] of [
    [300, ["2025-01", "2025-07", "2025-12"]],
    [1000, ["2025-01", "2025-04", "2025-07", "2025-09", "2025-12"]],
  ]) {
    const card = page.getByTestId(`trend-${cardWidth}`);
    const boxes = await card.locator(".chartAxisLabel").evaluateAll((nodes) =>
      nodes
        .filter((node) => getComputedStyle(node).display !== "none")
        .map((node) => {
          const rect = node.getBoundingClientRect();
          return { text: node.textContent, left: rect.left, right: rect.right, size: parseFloat(getComputedStyle(node).fontSize) };
        })
    );
    expect(boxes.map((box) => box.text)).toEqual(expected);
    const chart = await card.locator(".chartWrap").boundingBox();
    for (let i = 0; i < boxes.length; i += 1) {
      // Same type size at every width (the old SVG text shrank to ~5px).
      expect(boxes[i].size).toBeGreaterThanOrEqual(11);
      expect(boxes[i].left).toBeGreaterThanOrEqual(chart.x - 0.5);
      expect(boxes[i].right).toBeLessThanOrEqual(chart.x + chart.width + 0.5);
      if (i > 0) expect(boxes[i].left).toBeGreaterThan(boxes[i - 1].right + 4);
    }
  }
});
