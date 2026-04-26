// Concept 4 — Cashflow Map
// Sankey-style household money flow: income → buckets → categories.

function CashflowMap() {
  // Sankey nodes laid out manually for clarity.
  // Three columns: sources (left), buckets (mid), endpoints (right).
  const W = 1280, H = 900;

  const sources = [
    { id: 'salary',   label: 'Salary',           amount: 4820, y: 120, h: 220, color: 'var(--ok)' },
    { id: 'freelance', label: 'Freelance',       amount:  320, y: 360, h:  60, color: 'var(--ok)' },
    { id: 'rebates',  label: 'Rebates / interest', amount: 100, y: 440, h:  40, color: 'var(--ok)' },
  ];
  const buckets = [
    { id: 'fixed',     label: 'Fixed costs',    amount: 1793, y: 110, h: 160, color: 'var(--accent-cool)' },
    { id: 'variable',  label: 'Variable spend', amount: 1067, y: 290, h: 110, color: 'var(--accent-warm)' },
    { id: 'savings',   label: 'Savings & invest', amount: 780, y: 420, h:  82, color: 'var(--accent)' },
    { id: 'buffer',    label: 'Buffer',         amount:  600, y: 522, h:  64, color: 'var(--muted)' },
  ];
  const ends = [
    { id: 'mortgage', label: 'Mortgage',      amount: 1284, y: 80,  h: 132, color: 'var(--accent-cool)' },
    { id: 'utility',  label: 'Utilities',     amount:  172, y: 220, h:  18, color: 'var(--accent-cool)' },
    { id: 'subs',     label: 'Subscriptions', amount:  337, y: 244, h:  35, color: 'var(--accent-cool)' },
    { id: 'groc',     label: 'Groceries',     amount:  612, y: 290, h:  64, color: 'var(--accent-warm)' },
    { id: 'transport', label: 'Transport',    amount:  148, y: 360, h:  16, color: 'var(--accent-warm)' },
    { id: 'dining',    label: 'Dining + leisure', amount: 307, y: 380, h: 32, color: 'var(--accent-warm)' },
    { id: 'misc',      label: 'Misc',         amount:  132, y: 416, h:  14, color: 'var(--accent-warm)' },
    { id: 'pension',   label: 'Pension',      amount:  480, y: 432, h:  50, color: 'var(--accent)' },
    { id: 'invest',    label: 'Investments',  amount:  300, y: 484, h:  32, color: 'var(--accent)' },
    { id: 'cash',      label: 'Cash buffer',  amount:  600, y: 520, h:  64, color: 'var(--muted)' },
  ];

  // links source→bucket
  const linksA = [
    { from: 'salary',   to: 'fixed',     v: 1793 },
    { from: 'salary',   to: 'variable',  v: 1067 },
    { from: 'salary',   to: 'savings',   v: 780  },
    { from: 'salary',   to: 'buffer',    v: 600  },
    { from: 'freelance', to: 'variable', v: 320  },
    { from: 'rebates',  to: 'savings',   v: 100  },
  ];
  const linksB = [
    { from: 'fixed',    to: 'mortgage', v: 1284 },
    { from: 'fixed',    to: 'utility',  v: 172  },
    { from: 'fixed',    to: 'subs',     v: 337  },
    { from: 'variable', to: 'groc',     v: 612  },
    { from: 'variable', to: 'transport', v: 148 },
    { from: 'variable', to: 'dining',   v: 307  },
    { from: 'savings',  to: 'pension',  v: 480  },
    { from: 'savings',  to: 'invest',   v: 300  },
    { from: 'buffer',   to: 'cash',     v: 600  },
    { from: 'variable', to: 'misc',     v: 132  },
  ];

  const nodes = Object.fromEntries([...sources, ...buckets, ...ends].map((n) => [n.id, n]));

  const xCols = { source: 220, bucket: 600, end: 980 };
  const colW = 26;

  // Determine x positions per column
  const colOf = (id) => {
    if (sources.find((s) => s.id === id)) return 'source';
    if (buckets.find((s) => s.id === id)) return 'bucket';
    return 'end';
  };

  // Draw a flow band as a smooth bezier
  const flow = (a, b, v, idx, totalIn, totalOut, fromColor) => {
    const aCol = colOf(a), bCol = colOf(b);
    const ax = xCols[aCol] + colW;
    const bx = xCols[bCol];
    // proportional offsets along node heights
    const aN = nodes[a], bN = nodes[b];
    return { ax, bx, ay: aN.y, by: bN.y, h: v / 100 * 4, color: fromColor };
  };

  // Build link geometry with stacked offsets per node
  const stackA = {}; // out-offset per source
  const stackInBucket = {}; // in-offset per bucket
  const stackOutBucket = {}; // out-offset per bucket
  const stackInEnd = {}; // in-offset per end
  const linkWidth = (v) => v / 18; // px

  const drawnA = linksA.map((l) => {
    const fromN = nodes[l.from], toN = nodes[l.to];
    const w = linkWidth(l.v);
    stackA[l.from] = stackA[l.from] || 0;
    stackInBucket[l.to] = stackInBucket[l.to] || 0;
    const ay = fromN.y + stackA[l.from];
    const by = toN.y + stackInBucket[l.to];
    stackA[l.from] += w;
    stackInBucket[l.to] += w;
    return { ...l, ax: xCols.source + colW, bx: xCols.bucket, ay, by, w, color: fromN.color };
  });

  const drawnB = linksB.map((l) => {
    const fromN = nodes[l.from], toN = nodes[l.to];
    const w = linkWidth(l.v);
    stackOutBucket[l.from] = stackOutBucket[l.from] || 0;
    stackInEnd[l.to] = stackInEnd[l.to] || 0;
    const ay = fromN.y + stackOutBucket[l.from];
    const by = toN.y + stackInEnd[l.to];
    stackOutBucket[l.from] += w;
    stackInEnd[l.to] += w;
    return { ...l, ax: xCols.bucket + colW, bx: xCols.end, ay, by, w, color: fromN.color };
  });

  return (
    <div style={{
      width: '100%', minHeight: '100%',
      background: 'radial-gradient(circle at 80% 0%, rgba(15,118,110,0.10), transparent 40%), linear-gradient(180deg, #fdfaf2, #f2ecdf)',
      padding: '32px 40px 40px',
      fontFamily: 'var(--font-sans)',
      color: 'var(--ink)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 24 }}>
        <div>
          <Eyebrow>Cashflow map · April 2026</Eyebrow>
          <div className="display" style={{ fontSize: 36, marginTop: 4 }}>Where the household money goes</div>
        </div>
        <div style={{ display: 'flex', gap: 18, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>
          <span>IN  <strong style={{ color: 'var(--ok)' }} className="num-mono">€5,240</strong></span>
          <span>OUT <strong style={{ color: 'var(--warn)' }} className="num-mono">€3,640</strong></span>
          <span>NET <strong style={{ color: 'var(--accent)' }} className="num-mono">+€1,600</strong></span>
        </div>
      </div>

      <div className="panel-warm" style={{ padding: 20, marginBottom: 16 }}>
        <svg viewBox={`0 0 ${W} 720`} style={{ width: '100%', height: 720, display: 'block' }}>
          {/* column labels */}
          <text x={xCols.source} y="40" fill="var(--muted)" fontFamily="var(--font-mono)" fontSize="11" letterSpacing="0.16em">INCOME</text>
          <text x={xCols.bucket} y="40" fill="var(--muted)" fontFamily="var(--font-mono)" fontSize="11" letterSpacing="0.16em">ALLOCATION</text>
          <text x={xCols.end} y="40" fill="var(--muted)" fontFamily="var(--font-mono)" fontSize="11" letterSpacing="0.16em">DESTINATION</text>

          {/* link bands */}
          {drawnA.map((l, i) => (
            <SankeyLink key={'a'+i} ax={l.ax} ay={l.ay} bx={l.bx} by={l.by} w={l.w} color={l.color} />
          ))}
          {drawnB.map((l, i) => (
            <SankeyLink key={'b'+i} ax={l.ax} ay={l.ay} bx={l.bx} by={l.by} w={l.w} color={l.color} />
          ))}

          {/* nodes */}
          {[...sources, ...buckets, ...ends].map((n) => {
            const x = xCols[colOf(n.id)];
            const labelOnLeft = colOf(n.id) === 'end';
            return (
              <g key={n.id}>
                <rect x={x} y={n.y} width={colW} height={n.h} fill={n.color} rx={3} />
                <text
                  x={labelOnLeft ? x + colW + 10 : x - 10}
                  y={n.y + 14}
                  textAnchor={labelOnLeft ? 'start' : 'end'}
                  fill="var(--ink)"
                  fontSize="13"
                  fontWeight="700"
                >{n.label}</text>
                <text
                  x={labelOnLeft ? x + colW + 10 : x - 10}
                  y={n.y + 30}
                  textAnchor={labelOnLeft ? 'start' : 'end'}
                  fill="var(--muted)"
                  fontFamily="var(--font-mono)"
                  fontSize="11"
                >€{n.amount.toLocaleString()}</text>
              </g>
            );
          })}
        </svg>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
        {[
          { k: 'Fixed share',     v: '49%', m: 'mortgage dominates' },
          { k: 'Discretionary',   v: '29%', m: 'groceries +3.1%' },
          { k: 'Saved + invested', v: '15%', m: 'pension on track' },
          { k: 'Buffer growth',   v: '11%', m: '+€600 to cash' },
        ].map((s) => (
          <div key={s.k} className="panel-warm" style={{ padding: 16 }}>
            <div className="eyebrow">{s.k}</div>
            <div className="display" style={{ fontSize: 28, marginTop: 4 }}>{s.v}</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>{s.m}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SankeyLink({ ax, ay, bx, by, w, color }) {
  const mx = (ax + bx) / 2;
  const d = `M${ax},${ay}
             C${mx},${ay} ${mx},${by} ${bx},${by}
             L${bx},${by + w}
             C${mx},${by + w} ${mx},${ay + w} ${ax},${ay + w} Z`;
  return <path d={d} fill={color} opacity="0.32" />;
}

window.CashflowMap = CashflowMap;
