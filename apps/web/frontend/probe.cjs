const { chromium } = require("@playwright/test");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on("console", (m) => console.log("CONSOLE:", m.type(), m.text().slice(0, 400)));
  page.on("pageerror", (e) => console.log("PAGEERROR:", String(e).slice(0, 600)));
  await page.goto("http://127.0.0.1:6006/iframe.html?id=control-plane-policyform--template-requires-threshold&viewMode=story");
  await page.waitForTimeout(3000);
  console.log("ROOT HTML:", (await page.locator("#storybook-root").innerHTML()).slice(0, 300));
  await browser.close();
})();
