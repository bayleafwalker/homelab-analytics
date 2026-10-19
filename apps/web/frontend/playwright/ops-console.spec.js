const { test, expect } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;

// Ops Console (sprint console-grid-rise): layout fit, keyboard map, palette
// hand-off and accessibility. No screenshot baselines (CI-owned).

async function gotoStory(page, storyId) {
  await page.goto(`/iframe.html?id=${storyId}&viewMode=story&globals=a11y.manual:!true`);
  await expect(page.locator("#storybook-root")).toBeVisible();
  await expect(page.locator("#storybook-root")).not.toContainText(
    "The component failed to render properly"
  );
}

async function expectAccessible(page, selector = "#storybook-root") {
  const results = await new AxeBuilder({ page }).include(selector).analyze();
  const message = results.violations.map((v) => `${v.id}: ${v.nodes.length} node(s)`).join("\n");
  expect(results.violations, message).toEqual([]);
}

for (const story of ["admin", "reader", "nothing-yet"]) {
  test(`console ${story} stays accessible`, async ({ page }) => {
    await gotoStory(page, `console-consoleview--${story}`);
    await expect(page.locator(".console")).toBeVisible();
    await expectAccessible(page);
  });
}

for (const story of ["full", "sparse", "date-only", "empty"]) {
  test(`heat grid ${story} stays accessible`, async ({ page }) => {
    await gotoStory(page, `console-heatgrid--${story}`);
    await expect(page.locator(".heatGrid")).toBeVisible();
    await expect(page.locator(".heatTable tbody tr")).toHaveCount(7);
    await expectAccessible(page);
  });
}

test("console fits one 1440x900 screen without scrolling", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await gotoStory(page, "console-consoleview--admin");
  const metrics = await page.evaluate(() => {
    const root = document.scrollingElement;
    const bodies = [...document.querySelectorAll(".consolePanelBody")].map((body) => ({
      id: body.closest("[data-panel-id]").dataset.panelId,
      overflow: body.scrollHeight - body.clientHeight,
    }));
    const grid = getComputedStyle(document.querySelector(".consoleGrid"));
    return {
      pageOverflow: root.scrollHeight - root.clientHeight,
      bodies,
      columns: grid.gridTemplateColumns.split(" ").length,
      rows: grid.gridTemplateRows.split(" ").length,
    };
  });
  expect(metrics.pageOverflow).toBeLessThanOrEqual(0);
  expect(metrics.columns).toBe(3);
  expect(metrics.rows).toBe(2);
  for (const body of metrics.bodies) {
    expect(body.overflow, `${body.id} panel clips its content`).toBeLessThanOrEqual(1);
  }
});

test("F1-F5 focus panels and Ctrl+K opens the shared command palette", async ({ page }) => {
  await gotoStory(page, "console-consoleview--admin");
  const order = ["cashflow", "heatmap", "attention", "runs", "categories"];
  for (const [index, id] of order.entries()) {
    await page.keyboard.press(`F${index + 1}`);
    await expect(page.locator(`[data-panel-id="${id}"]`)).toBeFocused();
  }
  // One palette, hosted in the command stub; no second Cmd+K handler.
  await expect(page.locator("dialog.palette")).toHaveCount(1);
  await expect(page.locator('[data-panel-id="command"] .paletteTrigger')).toBeVisible();
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: "Jump to a page" });
  await expect(dialog).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Search pages" })).toBeFocused();
  // F-keys do not steal focus while the palette is open.
  await page.keyboard.press("F2");
  await expect(page.getByRole("combobox", { name: "Search pages" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});

test("console stacks at phone width without horizontal scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoStory(page, "console-consoleview--admin");
  const overflowX = await page.evaluate(
    () => document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth
  );
  expect(overflowX).toBeLessThanOrEqual(0);
  const columns = await page.evaluate(
    () => getComputedStyle(document.querySelector(".consoleGrid")).gridTemplateColumns.split(" ").length
  );
  expect(columns).toBe(1);
});
