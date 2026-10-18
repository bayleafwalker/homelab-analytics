const { test, expect } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;

// Behaviour and accessibility checks for the Cashflow Map, wallboard, state
// primitives and command palette. No screenshot baselines here: they are
// CI-owned and these surfaces are still moving.

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

async function expectAccessible(page, selector = "#storybook-root") {
  const results = await new AxeBuilder({ page }).include(selector).analyze();
  expect(results.violations, violationMessage(results.violations)).toEqual([]);
}

for (const story of ["demo-month", "categorised-with-occasional", "focused-payee", "overspent", "sparse"]) {
  test(`cashflow sankey ${story} renders flows and stays accessible`, async ({ page }) => {
    await gotoStory(page, `cashflow-cashflowsankey--${story}`);
    const svg = page.locator("svg.sankey");
    await expect(svg).toBeVisible();
    expect(await svg.locator("path.sankeyLink").count()).toBeGreaterThan(2);
    await expectAccessible(page);
  });
}

test("cashflow sankey payees are keyboard reachable links", async ({ page }) => {
  await gotoStory(page, "cashflow-cashflowsankey--categorised-with-occasional");
  const groceries = page.getByRole("link", { name: /Groceries/ });
  await groceries.focus();
  await expect(groceries).toBeFocused();
  await expect(groceries).toHaveAttribute("href", "#out:groceries");
});

test("cashflow sankey draws nothing when no money has been published", async ({ page }) => {
  await gotoStory(page, "cashflow-cashflowsankey--empty");
  await expect(page.locator("svg.sankey")).toHaveCount(0);
  await expect(page.getByText("No account transactions have been published yet.")).toBeVisible();
});

for (const story of ["bucket-ledger", "bucket-ledger-overspent", "bucket-ledger-sparse"]) {
  test(`cashflow ${story} lists the buckets and stays accessible`, async ({ page }) => {
    await gotoStory(page, `cashflow-cashflowsankey--${story}`);
    expect(await page.locator(".cashflowLedger > div").count()).toBeGreaterThan(0);
    await expectAccessible(page);
  });
}

for (const story of ["mixed", "nothing-trusted-yet"]) {
  test(`briefing ${story} renders every section and stays accessible`, async ({ page }) => {
    await gotoStory(page, `pages-briefing--${story}`);
    expect(await page.locator('[data-testid^="brief-section-"]').count()).toBe(7);
    await expectAccessible(page, "main");
  });
}

test("cashflow flow list is the narrow-screen alternative", async ({ page }) => {
  await gotoStory(page, "cashflow-cashflowsankey--narrow-flow-list");
  await expect(page.getByRole("heading", { name: /Regular spending/ })).toBeVisible();
  await expectAccessible(page);
});

for (const story of ["standard", "compact", "nothing-connected"]) {
  test(`wallboard ${story} stays accessible`, async ({ page }) => {
    await gotoStory(page, `wallboard-wallboardview--${story}`);
    await expect(page.locator(".wall")).toBeVisible();
    await expectAccessible(page);
  });
}

test("wallboard standard lays out the kiosk grid", async ({ page }) => {
  await gotoStory(page, "wallboard-wallboardview--standard");
  for (const area of ["services", "events", "devices", "power"]) {
    await expect(page.locator(`.wallPanel[data-area="${area}"]`)).toBeVisible();
  }
  await expect(page.getByLabel("Upcoming payments")).toBeVisible();
  await expect(page.getByText("R refresh · P pause")).toBeVisible();
  const columns = await page
    .locator(".wallGrid")
    .evaluate((node) => getComputedStyle(node).gridTemplateColumns.split(" ").map(parseFloat));
  expect(columns).toHaveLength(2);
  expect(columns[0] / columns[1]).toBeCloseTo(1.4, 1);
});

test("wallboard compact mode hides the event feed and hotkey hint", async ({ page }) => {
  await gotoStory(page, "wallboard-wallboardview--compact");
  await expect(page.locator('.wallPanel[data-area="events"]')).toHaveCount(0);
  await expect(page.getByText("R refresh · P pause")).toHaveCount(0);
  await expect(page.getByLabel("Upcoming payments")).toBeVisible();
  const size = await page
    .locator(".wallReadingValue")
    .first()
    .evaluate((node) => parseFloat(getComputedStyle(node).fontSize));
  expect(size).toBe(48);
});

for (const story of ["service-tile-up", "devices", "events", "power", "power-ambiguous"]) {
  test(`wallboard panel ${story} renders`, async ({ page }) => {
    await gotoStory(page, `wallboard-panels--${story}`);
    await expect(page.locator(".wall")).toBeVisible();
    await expectAccessible(page);
  });
}

test("app shell rail groups the nav, marks the current page and stays accessible", async ({ page }) => {
  await gotoStory(page, "shells-appshell--admin-control");
  const nav = page.getByRole("navigation", { name: "Primary" });
  await expect(nav.getByRole("link", { name: "Control" })).toHaveAttribute("aria-current", "page");
  await expect(nav.getByRole("list", { name: "Money" })).toBeVisible();
  await expectAccessible(page);
});

test("app shell collapses to a menu button at phone width", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoStory(page, "shells-appshell--admin-control");
  const nav = page.getByRole("navigation", { name: "Primary" });
  await expect(nav).toBeHidden();
  await page.getByRole("button", { name: "Menu" }).click();
  await expect(nav).toBeVisible();
  await expect(page.getByRole("button", { name: "Close menu" })).toHaveAttribute("aria-expanded", "true");
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(width).toBeLessThanOrEqual(390);
});

test("state panels expose one alert and polite statuses", async ({ page }) => {
  await gotoStory(page, "primitives-statepanel--all-tones");
  await expect(page.getByRole("alert")).toContainText("This page couldn't load");
  await expectAccessible(page);
});

test("command palette opens with the keyboard and follows the highlighted link", async ({ page }) => {
  await gotoStory(page, "shells-commandpalette--admin-entries");
  const input = page.getByRole("combobox", { name: "Search pages" });
  await expect(page.getByRole("button", { name: /Jump to a page/ })).toBeVisible();
  // The shortcut listener attaches after hydration; retry until it opens.
  await expect(async () => {
    if (!(await input.isVisible())) await page.keyboard.press("Control+k");
    await expect(input).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 10_000 });
  await expect(input).toBeFocused();
  await input.fill("cash");
  await expect(page.getByRole("option", { name: "Cashflow map" })).toHaveAttribute("aria-selected", "true");
  await input.fill("ctrl lin");
  await expect(page.getByRole("option", { name: "Control: lineage" })).toHaveAttribute(
    "aria-selected",
    "true"
  );
  await input.fill("");
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("option").nth(1)).toHaveAttribute("aria-selected", "true");
  await expectAccessible(page, "dialog");
  await page.keyboard.press("Escape");
  await expect(input).toBeHidden();
});
