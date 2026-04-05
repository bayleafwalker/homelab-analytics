from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "apps" / "web" / "frontend"


def test_ui_contract_artifacts_exist_for_current_shells() -> None:
    expected = [
        FRONTEND / "ui-contracts" / "default-shell" / "intent.md",
        FRONTEND / "ui-contracts" / "default-shell" / "baseline.tokens.json",
        FRONTEND / "ui-contracts" / "default-shell" / "ui-contract.yaml",
        FRONTEND / "ui-contracts" / "retro-shell" / "intent.md",
        FRONTEND / "ui-contracts" / "retro-shell" / "baseline.tokens.json",
        FRONTEND / "ui-contracts" / "retro-shell" / "ui-contract.yaml",
    ]

    missing = [path for path in expected if not path.is_file()]
    assert missing == []


def test_frontend_package_scripts_cover_ui_contract_workflow() -> None:
    package_json = json.loads((FRONTEND / "package.json").read_text())
    scripts = package_json["scripts"]

    for script_name in [
        "tokens:build",
        "tokens:check",
        "storybook",
        "storybook:build",
        "playwright:test",
        "ui:test",
    ]:
        assert script_name in scripts


def test_generated_tokens_are_loaded_by_global_styles() -> None:
    globals_css = (FRONTEND / "app" / "globals.css").read_text()
    generated_css = (FRONTEND / "app" / "generated" / "ui-tokens.css").read_text()

    assert '@import "./generated/ui-tokens.css";' in globals_css
    assert "--bg:" in generated_css
    assert "--retro-bg:" in generated_css


def test_storybook_and_playwright_scaffolding_exist() -> None:
    expected = [
        FRONTEND / ".storybook" / "main.ts",
        FRONTEND / ".storybook" / "preview.js",
        FRONTEND / "stories" / "app-shell.stories.jsx",
        FRONTEND / "stories" / "retro-shell.stories.jsx",
        FRONTEND / "stories" / "sparkline-chart.stories.jsx",
        FRONTEND / "stories" / "mock-status-card.stories.jsx",
        FRONTEND / "playwright.config.js",
        FRONTEND / "playwright" / "storybook-ui.spec.js",
    ]

    missing = [path for path in expected if not path.is_file()]
    assert missing == []
