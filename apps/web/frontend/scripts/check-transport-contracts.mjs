#!/usr/bin/env node
/**
 * check-transport-contracts.mjs
 *
 * Enforces that the protected frontend backend-transport boundary stays clean:
 *   1. lib/backend.ts must not contain raw `any` escape hatches.
 *   2. Protected app pages must not bypass lib/backend.ts with raw fetch calls
 *      to the backend API base URL.
 *
 * Exit 0 when clean, exit 1 with a violation report on failure.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// ---------------------------------------------------------------------------
// Rule 1 — transport boundary must not contain raw any
// ---------------------------------------------------------------------------

const TRANSPORT_FILE = path.join(frontendDir, "lib", "backend.ts");

const TRANSPORT_FORBIDDEN = [
  {
    id: "no-promise-any",
    re: /Promise<any>/,
    description: "Promise<any> — return type must use generated operation type",
  },
  {
    id: "no-as-any",
    re: /\bas\s+any\b/,
    description: "as any — type assertion must not erase the transport type",
  },
  {
    id: "no-colon-any",
    re: /:\s*any\b/,
    description: ": any — explicit any type annotation in transport boundary",
  },
];

// ---------------------------------------------------------------------------
// Rule 2 — protected app pages must not call fetch() with a backend URL
// ---------------------------------------------------------------------------

const APP_DIR = path.join(frontendDir, "app");

// Matches fetch("http://... or fetch(`http://... or fetch(process.env.HOMELAB...
const RAW_FETCH_RE = /\bfetch\s*\(\s*(?:`[^`]*http|'[^']*http|"[^"]*http|process\.env\.HOMELAB)/;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isCodeLine(line) {
  const trimmed = line.trim();
  return trimmed.length > 0 && !trimmed.startsWith("//") && !trimmed.startsWith("*");
}

function findTsFiles(dir) {
  const results = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory() && entry.name !== "node_modules" && entry.name !== ".next") {
      results.push(...findTsFiles(full));
    } else if (entry.isFile() && /\.[cm]?tsx?$/.test(entry.name)) {
      results.push(full);
    }
  }
  return results;
}

function checkPatterns(filePath, rules) {
  const lines = fs.readFileSync(filePath, "utf-8").split("\n");
  const violations = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!isCodeLine(line)) continue;
    for (const rule of rules) {
      if (rule.re.test(line)) {
        violations.push({
          file: path.relative(frontendDir, filePath),
          line: i + 1,
          rule: rule.id,
          description: rule.description,
          text: line.trimEnd(),
        });
      }
    }
  }
  return violations;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const violations = [];

// Rule 1
if (fs.existsSync(TRANSPORT_FILE)) {
  violations.push(...checkPatterns(TRANSPORT_FILE, TRANSPORT_FORBIDDEN));
} else {
  process.stderr.write(`Transport file not found: ${TRANSPORT_FILE}\n`);
  process.exit(1);
}

// Rule 2
if (fs.existsSync(APP_DIR)) {
  for (const file of findTsFiles(APP_DIR)) {
    violations.push(
      ...checkPatterns(file, [
        {
          id: "no-raw-backend-fetch",
          re: RAW_FETCH_RE,
          description: "raw fetch() to backend URL — use lib/backend.ts helpers instead",
        },
      ])
    );
  }
}

if (violations.length === 0) {
  process.stdout.write("Frontend transport contract check passed.\n");
  process.exit(0);
}

process.stderr.write(`Frontend transport contract violations (${violations.length}):\n\n`);
for (const v of violations) {
  process.stderr.write(`  ${v.file}:${v.line}  [${v.rule}]\n`);
  process.stderr.write(`  ${v.description}\n`);
  process.stderr.write(`  ${v.text}\n\n`);
}
process.exit(1);
