const { defineConfig, devices } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./playwright",
  timeout: 30_000,
  expect: {
    toHaveScreenshot: {
      animations: "disabled",
      caret: "hide",
    },
  },
  use: {
    baseURL: process.env.STORYBOOK_BASE_URL || "http://127.0.0.1:6006",
    viewport: { width: 1440, height: 960 },
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],
});
