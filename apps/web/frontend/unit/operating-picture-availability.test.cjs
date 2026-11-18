"use strict";

const assert = require("node:assert/strict");
const Module = require("node:module");
const path = require("node:path");
const test = require("node:test");
const { buildSync } = require("esbuild");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

const source = path.resolve(__dirname, "../components/operating-picture-view.js");
const compiled = buildSync({
  entryPoints: [source],
  bundle: true,
  format: "cjs",
  loader: { ".js": "jsx" },
  jsx: "automatic",
  packages: "external",
  platform: "node",
  write: false,
}).outputFiles[0].text;
const subject = new Module(source, module);
subject.filename = source;
subject.paths = Module._nodeModulePaths(path.dirname(source));
subject._compile(compiled, source);
const { OperatingPictureView } = subject.exports;

function render(unavailable) {
  return renderToStaticMarkup(React.createElement(OperatingPictureView, {
    freshnessDomains: [],
    horizonDays: [],
    rankedAttention: [],
    affordabilityRatios: [],
    topCategories: [],
    recentChanges: [],
    unavailable,
  }));
}

test("the attention queue reports all clear only for an available empty feed", () => {
  const empty = render({});
  assert.match(empty, /No attention items\. All clear\./);
  assert.match(empty, /No ratios yet\./);
  assert.match(empty, /No category spend yet\./);

  const unavailable = render({
    attentionItems: true,
    cashflowRows: true,
    freshnessDatasets: true,
    upcomingFixedCosts: true,
    affordabilityRatios: true,
    categorySpend: true,
  });
  for (const panel of ["Attention queue", "Cashflow", "Source freshness", "Horizon", "Affordability", "Category spend"]) {
    assert.ok(unavailable.includes(`${panel} unavailable`), panel);
  }
  assert.doesNotMatch(unavailable, /All clear|No ratios yet|No category spend yet|No data/);
});
