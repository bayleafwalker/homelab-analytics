// Monetary publications keep one row per currency and never convert between
// them. These helpers group and select rows without summing across currencies
// and without choosing "the" row when several denominations exist.

// Rows split by currency, sorted by code; rows with no currency (usage-only
// periods, empty fallbacks) form a trailing group with currency === null.
export function splitByCurrency(rows) {
  const groups = new Map();
  for (const row of rows || []) {
    const key = row?.currency || null;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => (a === null) - (b === null) || String(a).localeCompare(String(b)))
    .map(([currency, groupRows]) => ({ currency, rows: groupRows }));
}

// All rows of the newest month, one per currency. `monthKey` names the column
// ("booking_month", "billing_month", ...). Rows with no usable month are ignored.
export function latestMonthRows(rows, monthKey, { upTo = null } = {}) {
  const months = [...new Set((rows || []).map((r) => r?.[monthKey]).filter(Boolean))]
    .filter((m) => !upTo || m <= upTo)
    .sort();
  const latest = months.at(-1);
  return latest ? rows.filter((r) => r[monthKey] === latest) : [];
}

// The only row, or null when there are none or several. Callers that need a
// single scalar use this so a multi-currency answer is unavailable instead of
// an arbitrary pick.
export function soleRow(rows) {
  return Array.isArray(rows) && rows.length === 1 ? rows[0] : null;
}

// Sums `field` within one currency only. Never pass rows of mixed currencies.
export function sumField(rows, field) {
  return (rows || []).reduce((sum, row) => sum + Number(row?.[field] || 0), 0);
}
