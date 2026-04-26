// Shared primitives used across concept artboards.
const Eyebrow = ({ children, color, style }) => (
  <div className="eyebrow" style={{ color: color || 'var(--accent)', ...style }}>{children}</div>
);

const Pill = ({ tone = 'neutral', children, style }) => {
  const tones = {
    neutral: { color: 'var(--muted)', bg: 'rgba(19,40,51,0.06)' },
    ok:      { color: 'var(--ok)',    bg: 'rgba(42,157,143,0.14)' },
    warn:    { color: 'var(--warn)',  bg: 'rgba(209,73,91,0.12)' },
    cool:    { color: 'var(--accent-cool)', bg: 'rgba(11,95,131,0.12)' },
    accent:  { color: 'var(--accent)', bg: 'rgba(15,118,110,0.12)' },
    warm:    { color: 'var(--accent-warm)', bg: 'rgba(201,106,61,0.14)' },
  };
  const t = tones[tone] || tones.neutral;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      borderRadius: 999, padding: '3px 10px',
      fontSize: 11, fontWeight: 700, letterSpacing: '0.04em',
      textTransform: 'lowercase',
      color: t.color, background: t.bg,
      ...style,
    }}>{children}</span>
  );
};

const Dot = ({ color = 'var(--ok)', size = 8, style }) => (
  <span style={{
    display: 'inline-block', width: size, height: size, borderRadius: '50%',
    background: color, boxShadow: `0 0 ${size}px ${color}`, ...style,
  }} />
);

// Tiny inline SVG sparkline. values: number[]
const Spark = ({ values, width = 220, height = 44, color = 'var(--accent)', fill = true, strokeWidth = 1.6 }) => {
  if (!values || values.length === 0) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = width / (values.length - 1 || 1);
  const pad = 2;
  const pts = values.map((v, i) => [
    i * stepX,
    pad + (height - pad * 2) * (1 - (v - min) / range),
  ]);
  const d = pts.map((p, i) => (i === 0 ? `M${p[0]},${p[1]}` : `L${p[0]},${p[1]}`)).join(' ');
  const area = `${d} L${width},${height} L0,${height} Z`;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: 'block', overflow: 'visible' }}>
      {fill && <path d={area} fill={color} opacity="0.12" />}
      <path d={d} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};

// Vertical bar series
const Bars = ({ values, width = 220, height = 44, color = 'var(--accent)', gap = 2 }) => {
  if (!values || values.length === 0) return null;
  const max = Math.max(...values, 1);
  const bw = (width - gap * (values.length - 1)) / values.length;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      {values.map((v, i) => {
        const h = (v / max) * height;
        return <rect key={i} x={i * (bw + gap)} y={height - h} width={bw} height={h} fill={color} rx={1.5} />;
      })}
    </svg>
  );
};

// Realistic-ish data drawn from your domain (EUR, monthly, etc.)
const DATA = {
  months: ['May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr'],
  income:  [4820, 4820, 4820, 5120, 4820, 4820, 5380, 5120, 4820, 4820, 5120, 5240],
  expense: [3110, 3290, 2980, 3540, 3120, 3460, 3910, 4220, 3380, 3210, 3490, 3640],
  net:     [1710, 1530, 1840, 1580, 1700, 1360, 1470, 900,  1440, 1610, 1630, 1600],
  utility: [184, 192, 168, 142, 138, 162, 218, 264, 248, 222, 196, 172],
  categories: [
    { label: 'Housing',        amount: 1284.00, share: 0.353, delta: -0.4 },
    { label: 'Groceries',      amount:  612.40, share: 0.168, delta: +3.1 },
    { label: 'Utilities',      amount:  172.18, share: 0.047, delta: -7.2 },
    { label: 'Transport',      amount:  148.60, share: 0.041, delta: +1.6 },
    { label: 'Subscriptions',  amount:   94.30, share: 0.026, delta:  0.0 },
  ],
  attention: [
    { sev: 1, title: 'Energy contract renewal in 12 days', domain: 'utilities', detail: 'Current fixed price expires 07 May; market index +14% YoY' },
    { sev: 2, title: 'Mortgage rate review window opens',  domain: 'loans',     detail: 'Bank offer letter received 22 Apr · 4 wk window' },
    { sev: 2, title: '3 subscriptions renewing this week',  domain: 'recurring', detail: '€38.97 total · 1 unused for 60+ days' },
    { sev: 3, title: 'Account import 9 days stale',         domain: 'sources',   detail: 'op_account · last landed 16 Apr' },
  ],
  runs: [
    { id: 'r-2049', source: 'op_account',     file: 'op-2026-04.csv',     status: 'landed',    rows: 612 },
    { id: 'r-2048', source: 'revolut_personal', file: 'rev-2026-04.csv',   status: 'completed', rows:  87 },
    { id: 'r-2047', source: 'contract_prices', file: 'energy-q2-2026.csv', status: 'enqueued',  rows:   4 },
    { id: 'r-2046', source: 'op_gold_invoice', file: 'oper-04-2026.pdf',   status: 'rejected',  rows:   0 },
  ],
  ratios: [
    { name: 'Housing / income',     pct: 26.8, state: 'ok' },
    { name: 'Total cost / income',  pct: 70.4, state: 'warn' },
    { name: 'Debt service ratio',   pct: 18.2, state: 'ok' },
  ],
};

const fmtEUR = (n, opts = {}) => {
  const v = Number(n);
  const sign = opts.sign && v > 0 ? '+' : '';
  return `${sign}€${v.toLocaleString('en-IE', { minimumFractionDigits: opts.dec ?? 0, maximumFractionDigits: opts.dec ?? 0 })}`;
};

Object.assign(window, { Eyebrow, Pill, Dot, Spark, Bars, DATA, fmtEUR });
