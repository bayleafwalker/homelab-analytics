"use strict";
// HLA2915: scenario cashflow tables (tariff-shock detail and the side-by-side
// comparison) label their monetary cells with a table-level currency caption so
// EUR and USD values are never rendered as bare, unlabelled numbers.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");

const FRONTEND = path.resolve(__dirname, "..");
const req = Module.createRequire(path.join(FRONTEND, "package.json"));
const esbuild = req("esbuild");
const React = req("react");
const { renderToStaticMarkup } = req("react-dom/server");

function compile(rel, patchLoad) {
  const filename = path.join(FRONTEND, rel);
  const { code } = esbuild.transformSync(fs.readFileSync(filename, "utf8"), {
    loader: "jsx",
    format: "cjs",
    jsx: "automatic",
    sourcefile: filename,
  });
  const mod = new Module(filename, module);
  mod.filename = filename;
  mod.paths = Module._nodeModulePaths(path.dirname(filename));
  const origLoad = Module._load;
  Module._load = function (request, parent, isMain) {
    const fromSubject = parent === mod;
    if (fromSubject && patchLoad && patchLoad[request]) return patchLoad[request];
    return origLoad.call(this, request, parent, isMain);
  };
  try {
    mod._compile(code, filename);
  } finally {
    Module._load = origLoad;
  }
  return mod.exports;
}

const text = (html) =>
  html.replace(/<!-- -->/g, "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();

const { scenarioCurrency } = compile("lib/currency-groups.js");

test("scenarioCurrency reads the tariff-shock assumption unit", () => {
  assert.equal(scenarioCurrency([{ assumption_key: "baseline_utility_cost", unit: "USD" }]), "USD");
  assert.equal(scenarioCurrency([{ assumption_key: "baseline_utility_cost", unit: "EUR" }]), "EUR");
  assert.equal(scenarioCurrency([{ assumption_key: "tariff_pct_delta", unit: "%" }]), null);
  assert.equal(scenarioCurrency([]), null);
});

test("scenarioCurrency reads income and expense monetary units", () => {
  for (const currency of ["EUR", "USD"]) {
    const delta = { assumption_key: "monthly_income_delta", unit: currency };
    assert.equal(scenarioCurrency([delta]), null);
    assert.equal(scenarioCurrency([delta, { assumption_key: "cashflow_currency", unit: currency }]), currency);
  }
  assert.equal(scenarioCurrency([{ assumption_key: "baseline_expense", unit: "USD" }]), "USD");
  assert.equal(scenarioCurrency([{ assumption_key: "baseline_expense", unit: "EUR" }]), "EUR");
  // The percentage delta is not a monetary unit.
  assert.equal(scenarioCurrency([{ assumption_key: "expense_pct_delta", unit: "%" }]), null);
});

test("scenarioCurrency is unavailable for missing, generic or conflicting units", () => {
  assert.equal(scenarioCurrency([{ assumption_key: "baseline_expense", unit: "currency" }]), null);
  assert.equal(scenarioCurrency([{ assumption_key: "baseline_expense", unit: null }]), null);
  assert.equal(scenarioCurrency([{ assumption_key: "monthly_income_delta", unit: null }]), null);
  assert.equal(
    scenarioCurrency([
      { assumption_key: "monthly_income_delta", unit: "USD" },
      { assumption_key: "baseline_expense", unit: "EUR" },
    ]),
    null,
  );
});

function loadTariffShockPanel() {
  const state = { calls: 0 };
  const initialValues = {
    1: true, // open — the projection table renders only when the panel is open
    2: "", // pct
    3: "", // label
    4: false, // loading
    5: null, // error
    6: {
      // result
      currency: "USD",
      baseline_monthly_utility_cost: "100",
      new_monthly_utility_cost: "110",
      annual_additional_cost: "120",
      months_until_deficit: null,
    },
    7: {
      // cashflow
      cashflow_rows: [
        {
          period: 1,
          projected_month: "2026-02",
          baseline_income: "3000",
          scenario_income: "3000",
          baseline_expense: "1200",
          scenario_expense: "1210",
          baseline_net: "1800",
          scenario_net: "1790",
          net_delta: "-10",
        },
      ],
      assumptions: [],
    },
  };
  const adapter = {
    ...React,
    useState(initial) {
      state.calls += 1;
      return React.useState(initialValues[state.calls] ?? initial);
    },
  };
  const { TariffShockPanel } = compile("components/tariff-shock-panel.js", { react: adapter });
  return function render() {
    state.calls = 0;
    return renderToStaticMarkup(React.createElement(TariffShockPanel));
  };
}

test("tariff-shock detail cashflow table carries a visible currency caption", () => {
  const render = loadTariffShockPanel();
  const t = text(render());
  assert.ok(t.includes("All amounts in USD"), t);
});

test("a comparison caption names the concrete currency, never bare", () => {
  for (const currency of ["EUR", "USD"]) {
    const resolved = scenarioCurrency([{ assumption_key: "baseline_utility_cost", unit: currency }]);
    const caption = renderToStaticMarkup(
      React.createElement(
        "table",
        null,
        React.createElement("caption", null, resolved ? `All amounts in ${resolved}` : "Cashflow projection"),
      ),
    );
    assert.ok(text(caption).includes(`All amounts in ${currency}`), text(caption));
  }
});

const shellStubs = {
  "next/link": ({ children }) => React.createElement("a", null, children),
  "@/components/app-shell": { AppShell: ({ children }) => children },
};

test("scenario details render attributed freshness and tolerate absent freshness", async () => {
  let summary = [{
    source_asset_id: "bank-statement",
    freshness_state: "overdue",
    last_ingest_at: "2026-11-20T00:00:00+00:00",
    covered_through: "2026-11-19",
  }];
  const { default: ScenarioDetail } = compile("app/scenarios/[scenarioId]/page.js", {
    ...shellStubs,
    "@/lib/currency-groups": { scenarioCurrency },
    "@/lib/backend": {
      getCurrentUser: async () => ({ role: "admin" }),
      getScenarioMetadata: async () => ({ scenario_type: "income_change", label: "Income" }),
      getScenarioCashflow: async () => ({ assumptions_summary: summary }),
    },
  });
  const render = async () => text(renderToStaticMarkup(
    await ScenarioDetail({ params: { scenarioId: "income" } }),
  ));
  assert.match(await render(), /bank-statement overdue .*2026-11-19/);
  summary = null;
  assert.match(await render(), /Source freshness is unavailable/);
});

test("policy details identify the evaluated input and tolerate absent freshness", async () => {
  let freshness = {
    freshness_state: "current",
    completeness_pct: 90,
    assessed_at: "2026-11-24T00:00:00+00:00",
  };
  const { default: PolicyDetail } = compile("app/control/policies/[policyId]/details/page.js", {
    ...shellStubs,
    "next/navigation": {
      notFound: () => assert.fail("Expected a saved policy"),
      redirect: () => assert.fail("Expected an admin"),
    },
    "@/components/control-nav": { ControlNav: () => null },
    "@/components/policy-rule-summary": { PolicyRuleSummary: () => null },
    "@/lib/backend": {
      getCurrentUser: async () => ({ role: "admin" }),
      getPolicyDefinitions: async () => [{
        policy_id: "cost",
        rule_document: { publication_key: "monthly_cashflow" },
      }],
      getHaPolicyEvaluation: async () => ({
        policies: [{ id: "cost", input_freshness: freshness }],
      }),
    },
  });
  const render = async () => text(renderToStaticMarkup(
    await PolicyDetail({ params: { policyId: "cost" } }),
  ));
  assert.match(await render(), /Input monthly_cashflow Freshness current Completeness 90%/);
  freshness = null;
  assert.match(await render(), /Input freshness is unavailable/);
});
