// Shared display formatting for reporting values. Reporting rows carry
// DECIMAL(18,4) strings ("2474.9800"); people read money with two decimals,
// a currency mark and grouping. Missing values render as an em dash rather
// than "NaN" or "0".

const LOCALE = "en-GB";
const MONTHS_LONG = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export function toNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

// grouping: false drops thousands separators (dense console panels).
export function formatMoney(value, currency, { signed = false, whole = false, grouping = true } = {}) {
  const number = toNumber(value);
  if (number === null) return "—";
  const digits = whole ? 0 : 2;
  const options = {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    signDisplay: signed ? "exceptZero" : "auto",
    useGrouping: grouping,
  };
  const code = typeof currency === "string" && /^[A-Z]{3}$/.test(currency) ? currency : null;
  if (code) {
    return new Intl.NumberFormat(LOCALE, { ...options, style: "currency", currency: code }).format(number);
  }
  return new Intl.NumberFormat(LOCALE, options).format(number);
}

export function formatPercent(value, { digits = 1, fromRatio = false } = {}) {
  const number = toNumber(value);
  if (number === null) return "—";
  const pct = fromRatio ? number * 100 : number;
  return `${pct.toFixed(digits)}%`;
}

// "2025-12" -> "December 2025"; anything else passes through unchanged.
export function formatMonth(value, { short = false } = {}) {
  const match = /^(\d{4})-(\d{2})$/.exec(String(value || ""));
  if (!match) return value ? String(value) : "—";
  const name = MONTHS_LONG[Number(match[2]) - 1];
  if (!name) return String(value);
  return short ? `${name.slice(0, 3)} ${match[1]}` : `${name} ${match[1]}`;
}

export function monthsBetween(older, newer) {
  const a = /^(\d{4})-(\d{2})/.exec(String(older || ""));
  const b = /^(\d{4})-(\d{2})/.exec(String(newer || ""));
  if (!a || !b) return null;
  return (Number(b[1]) * 12 + Number(b[2])) - (Number(a[1]) * 12 + Number(a[2]));
}

// "2026-03-09T00:00:00+00:00" -> "9 Mar 2026" (UTC calendar day, so the
// same instant reads the same on the server and in the browser).
export function formatDay(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ""));
  if (!match) return value ? String(value) : "—";
  const name = MONTHS_LONG[Number(match[2]) - 1];
  if (!name) return String(value);
  return `${Number(match[3])} ${name.slice(0, 3)} ${match[1]}`;
}
