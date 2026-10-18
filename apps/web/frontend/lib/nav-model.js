// Canonical navigation registry for the default shell.
//
// One list of entries, rendered by the shell rail and by the command palette
// (docs/decisions/web-surface-shell-decision.md, Section 4.2). Role visibility
// lives here once. A new top-level route under app/ must add an entry, or be
// listed in NAV_UNLISTED_ROUTES with a reason; tests/test_web_auth.py checks it.

const ROLE_ORDER = { reader: 0, operator: 1, admin: 2 };

export const NAV_GROUPS = [
  { id: "today", label: "Today" },
  { id: "money", label: "Money" },
  { id: "home", label: "Home" },
  { id: "data", label: "Data" },
  { id: "admin", label: "Admin" },
];

export const NAV_ENTRIES = [
  { href: "/", label: "Dashboard", group: "today", minRole: "reader", keywords: "home overview start" },
  { href: "/operating-picture", label: "Operating picture", group: "today", minRole: "reader", keywords: "summary freshness horizon attention" },
  { href: "/briefing", label: "Morning brief", group: "today", minRole: "reader", keywords: "brief summary daily morning news" },
  { href: "/cashflow", label: "Cashflow map", group: "today", minRole: "reader", keywords: "sankey income spending money flow where" },
  { href: "/wallboard", label: "Wallboard", group: "today", minRole: "reader", keywords: "kiosk tablet tv ambient status" },
  { href: "/console", label: "Ops console", group: "today", minRole: "reader", keywords: "power user grid heatmap keyboard runs terminal" },
  { href: "/reports", label: "Reports", group: "money", minRole: "reader", keywords: "finance monthly publications cashflow expense shock trust" },
  { href: "/budgets", label: "Budgets", group: "money", minRole: "reader", keywords: "envelopes variance" },
  { href: "/loans", label: "Loans", group: "money", minRole: "reader", keywords: "mortgage debt repayment" },
  { href: "/costs", label: "Costs", group: "money", minRole: "reader", keywords: "cost model tariff" },
  { href: "/scenarios", label: "Scenarios", group: "money", minRole: "reader", keywords: "what-if compare" },
  { href: "/utilities", label: "Utilities", group: "home", minRole: "reader", keywords: "electricity water contracts" },
  { href: "/homelab", label: "Homelab", group: "home", minRole: "reader", keywords: "services backups storage" },
  { href: "/sources", label: "Sources", group: "data", minRole: "operator", keywords: "freshness remediation stale" },
  { href: "/upload", label: "Upload", group: "data", minRole: "operator", keywords: "import statement csv file" },
  { href: "/onboarding", label: "Onboarding", group: "data", minRole: "operator", keywords: "setup getting started" },
  { href: "/runs", label: "Runs", group: "data", minRole: "reader", keywords: "ingestion history" },
  { href: "/review", label: "Review", group: "data", minRole: "reader", keywords: "ingestion review queue" },
  { href: "/control", label: "Control", group: "admin", minRole: "admin", keywords: "security users admin" },
];

// Deep links that are reachable from the command palette but do not take a
// slot in the rail. They keep the newer control pages discoverable.
export const NAV_DEEP_LINKS = [
  { href: "/control/catalog", label: "Control: catalog", minRole: "admin", keywords: "sources contracts mappings" },
  { href: "/control/execution", label: "Control: execution", minRole: "admin", keywords: "schedules dispatch" },
  { href: "/control/policies", label: "Control: policies", minRole: "admin", keywords: "rules authority" },
  { href: "/control/packs", label: "Control: packs", minRole: "admin", keywords: "extensions install upgrade rollback registry" },
  { href: "/control/freshness", label: "Control: freshness", minRole: "admin", keywords: "stale sla" },
  { href: "/control/lineage", label: "Control: lineage", minRole: "admin", keywords: "graph upstream" },
  { href: "/control/confidence", label: "Control: confidence", minRole: "admin", keywords: "trust verdict" },
  { href: "/control#users", label: "Control: users", minRole: "admin", keywords: "accounts roles" },
  { href: "/control#service-tokens", label: "Control: service tokens", minRole: "admin", keywords: "api tokens" },
  { href: "/first-answer", label: "First answer", minRole: "reader", keywords: "first run result" },
  { href: "/retro", label: "Retro shell", minRole: "reader", keywords: "crt cockpit terminal" },
];

// Top-level app/ routes that intentionally have no nav entry.
export const NAV_UNLISTED_ROUTES = {
  auth: "auth route handlers",
  login: "sign-in page",
  generated: "generated token stylesheet",
  health: "probe proxy",
  ready: "probe proxy",
  metrics: "probe proxy",
  retro: "secondary shell, linked from the rail footer",
  "first-answer": "post-upload landing, reached from onboarding",
  "ingest-summary": "post-upload landing, reached from upload",
  api: "same-origin API proxy route handlers for client components",
};

export function hasRequiredRole(user, requiredRole) {
  const have = ROLE_ORDER[user?.role];
  const need = ROLE_ORDER[requiredRole] ?? 0;
  return have !== undefined && have >= need;
}

export function navEntriesForUser(user) {
  return NAV_ENTRIES.filter((entry) => hasRequiredRole(user, entry.minRole));
}

export function navGroupsForUser(user) {
  const entries = navEntriesForUser(user);
  return NAV_GROUPS.map((group) => ({
    ...group,
    entries: entries.filter((entry) => entry.group === group.id),
  })).filter((group) => group.entries.length > 0);
}

export function paletteEntriesForUser(user) {
  const groupLabel = Object.fromEntries(NAV_GROUPS.map((group) => [group.id, group.label]));
  return [
    ...navEntriesForUser(user).map((entry) => ({ ...entry, section: groupLabel[entry.group] })),
    ...NAV_DEEP_LINKS.filter((entry) => hasRequiredRole(user, entry.minRole)).map((entry) => ({
      ...entry,
      section: "More",
    })),
  ];
}

export function isActivePath(href, currentPath) {
  if (!currentPath) return false;
  if (href === "/") return currentPath === "/";
  return currentPath === href || currentPath.startsWith(`${href}/`);
}

// Small fuzzy matcher: every query character must appear in order. Prefix and
// word-start hits rank higher. Returns -1 when there is no match.
export function scoreEntry(entry, query) {
  const q = query.trim().toLowerCase();
  if (!q) return 0;
  const label = entry.label.toLowerCase();
  if (label.startsWith(q)) return 100 - label.length;
  const words = `${label} ${entry.keywords || ""}`;
  if (words.split(/\s+/).some((word) => word.startsWith(q))) return 60;
  let position = -1;
  for (const char of q) {
    position = label.indexOf(char, position + 1);
    if (position === -1) return words.includes(q) ? 20 : -1;
  }
  return 40 - position;
}

export function filterPaletteEntries(entries, query) {
  return entries
    .map((entry, index) => ({ entry, index, score: scoreEntry(entry, query) }))
    .filter((item) => item.score >= 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .map((item) => item.entry);
}
