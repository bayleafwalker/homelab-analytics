// Capture the finance-loop walkthrough images against a running instance.
//
// Usually driven by scripts/capture_finance_loop_screenshots.py, which seeds a
// throwaway demo instance, starts the API and web workloads, writes the two
// upload files and sets the environment below. It can also be pointed at an
// instance you started yourself (docs/runbooks/operator-walkthrough.md,
// section 0):
//
//   FINANCE_LOOP_BASE_URL=http://localhost:8081 \
//   FINANCE_LOOP_USERNAME=demo-admin FINANCE_LOOP_PASSWORD=... \
//   FINANCE_LOOP_GOOD_CSV=/tmp/jan-2026.csv FINANCE_LOOP_BAD_CSV=/tmp/broken.csv \
//   FINANCE_LOOP_OUT_DIR=docs/product/screenshots/finance-loop \
//   node scripts/capture_finance_loop_screenshots.mjs
//
// Playwright (Chromium) is resolved from apps/web/frontend/node_modules, so run
// `npm --prefix apps/web/frontend ci` and `npx playwright install chromium`
// there first. Viewport 1440x1000; 04 is an element shot of the expense-shock
// panel, every other image is the viewport.

import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const frontendRequire = createRequire(path.join(repoRoot, "apps", "web", "frontend", "package.json"));
const { chromium } = frontendRequire("playwright");

function required(name) {
  const value = process.env[name];
  if (!value) {
    console.error(`${name} is required (see the header of ${path.basename(fileURLToPath(import.meta.url))}).`);
    process.exit(2);
  }
  return value;
}

const baseUrl = required("FINANCE_LOOP_BASE_URL").replace(/\/$/, "");
const username = required("FINANCE_LOOP_USERNAME");
const password = required("FINANCE_LOOP_PASSWORD");
const goodCsv = required("FINANCE_LOOP_GOOD_CSV");
const badCsv = required("FINANCE_LOOP_BAD_CSV");
const outDir = path.resolve(process.env.FINANCE_LOOP_OUT_DIR || path.join(repoRoot, "docs", "product", "screenshots", "finance-loop"));
const sourceAsset = process.env.FINANCE_LOOP_SOURCE_ASSET || "demo_op_personal_transactions";
const expensePct = process.env.FINANCE_LOOP_EXPENSE_PCT || "10";

mkdirSync(outDir, { recursive: true });

function shot(name) {
  return path.join(outDir, name);
}

// The web shell builds redirects from the request host, and the session cookie
// is host-scoped: use the same host the server redirects to (localhost) or
// every post-upload page comes back as the sign-in form.
async function settle(page) {
  await page.waitForLoadState("networkidle");
  if (new URL(page.url()).pathname.startsWith("/login")) {
    throw new Error(`Bounced to sign-in at ${page.url()}; is FINANCE_LOOP_BASE_URL on the server's own host?`);
  }
  // Server components stream behind app/**/loading.js skeletons; wait for the
  // page itself, then for fonts.
  await page.locator("main h1").first().waitFor();
  await page.getByText("Loading the latest published figures").waitFor({ state: "detached" });
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
}

async function scrollToHeading(page, text) {
  const heading = page.getByRole("heading", { name: text }).first();
  await heading.waitFor();
  await heading.evaluate((node) => {
    const panel = node.closest("article, section") || node;
    panel.scrollIntoView({ block: "start" });
    window.scrollBy(0, -24);
  });
}

// Submits the configured-CSV card and waits for the route handler's redirect
// (to /ingest-summary/<run_id> when the run lands, back to /upload otherwise).
async function uploadConfigured(page, file, landsOn) {
  await page.goto(`${baseUrl}/upload`);
  await settle(page);
  const form = page.locator('form[action="/upload/configured-csv"]');
  await form.locator('select[name="source_asset_id"]').selectOption(sourceAsset);
  await form.locator('input[type="file"][name="file"]').setInputFiles(file);
  await Promise.all([page.waitForURL(landsOn), form.getByRole("button", { name: "Upload file" }).click()]);
  await settle(page);
}

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  try {
    // Sign in.
    await page.goto(`${baseUrl}/login`);
    await page.fill("#username", username);
    await page.fill("#password", password);
    await Promise.all([page.waitForURL((url) => !url.pathname.startsWith("/login")), page.click('button[type="submit"]')]);

    // 01: a new-period upload lands on its ingest summary.
    await uploadConfigured(page, goodCsv, /\/ingest-summary\/[^/?#]+$/);
    await page.screenshot({ path: shot("01-ingest-summary.png") });

    // 02: Sources with every account export landed.
    await page.goto(`${baseUrl}/sources`);
    await settle(page);
    await page.screenshot({ path: shot("02-sources.png") });

    // 03: /reports, scrolled to the publication trust panel.
    await page.goto(`${baseUrl}/reports`);
    await settle(page);
    await scrollToHeading(page, "Monthly cashflow snapshot");
    await page.screenshot({ path: shot("03-reports-trust.png") });

    // 04: expense shock result (element shot of the panel).
    const panel = page.locator("#expense-shock");
    await panel.scrollIntoViewIfNeeded();
    await panel.getByRole("button", { name: "Run scenario" }).click();
    await panel.locator("#expense-pct").fill(expensePct);
    await panel.getByRole("button", { name: "Run", exact: true }).click();
    const openSaved = panel.getByRole("link", { name: "Open saved scenario" });
    await openSaved.waitFor();
    // The cashflow fetch finishes after the saved-scenario link appears.
    await panel.getByRole("button", { name: "Run", exact: true }).waitFor();
    await page.waitForLoadState("networkidle");
    await panel.screenshot({ path: shot("04-expense-shock.png") });

    // 05: the saved scenario the panel links to.
    await Promise.all([page.waitForURL(/\/scenarios\/[^/]+$/), openSaved.click()]);
    await settle(page);
    await page.screenshot({ path: shot("05-saved-scenario.png") });

    // 06: morning brief.
    await page.goto(`${baseUrl}/briefing`);
    await settle(page);
    await page.screenshot({ path: shot("06-morning-brief.png") });

    // 07: an upload missing a required column is rejected; open its run.
    await uploadConfigured(page, badCsv, (url) => url.pathname === "/upload" && url.searchParams.has("error"));
    const runLink = page.locator('main a[href^="/runs/"]').first();
    if ((await runLink.count()) === 0) {
      const banner = await page.locator(".errorBanner").first().innerText().catch(() => "");
      const detail = await page.locator(".errorBanner + .stack").first().innerText().catch(() => "");
      throw new Error(`The broken upload recorded no run: ${banner} ${detail}`.trim());
    }
    await Promise.all([page.waitForURL(/\/runs\/[^/]+$/), runLink.click()]);
    await settle(page);
    await page.screenshot({ path: shot("07-rejected-run.png") });

    // 08: Sources now offers remediation for that asset.
    await page.goto(`${baseUrl}/sources`);
    await settle(page);
    await page.screenshot({ path: shot("08-sources-remediation.png") });

    console.log(`Wrote 8 images to ${outDir}`);
  } catch (error) {
    const failure = path.join(os.tmpdir(), "finance-loop-capture-failure.png");
    await page.screenshot({ path: failure, fullPage: true }).catch(() => {});
    console.error(`Failed at ${page.url()}; page captured to ${failure}`);
    throw error;
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
