const { chromium } = require(process.argv[2]);

async function main() {
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    await page.setContent("<main>HLA Playwright runtime ready</main>");
    const text = await page.locator("main").textContent();
    if (text !== "HLA Playwright runtime ready") {
      throw new Error("headless Chromium returned unexpected page content");
    }
    process.stdout.write("Playwright Chromium launch, page, and close preflight passed.\n");
  } finally {
    if (browser) await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`Playwright Chromium preflight failed: ${error.stack || error}\n`);
  process.exitCode = 1;
});
