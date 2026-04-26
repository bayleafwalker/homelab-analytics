// Concept 3 — Morning Briefing
// Editorial calm. Reads like a daily front page for your household.
// One headline, one chart, one decision, one trend per "section."

function MorningBriefing() {
  return (
    <div style={{
      width: '100%', minHeight: '100%',
      background: 'linear-gradient(180deg, #fdfaf2 0%, #f5efde 100%)',
      padding: '52px 64px 64px',
      fontFamily: 'var(--font-sans)',
      color: 'var(--ink)',
    }}>
      {/* masthead */}
      <div style={{ borderBottom: '2px solid var(--ink)', paddingBottom: 18, marginBottom: 36, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <div className="display" style={{ fontSize: 56, fontWeight: 600, letterSpacing: '-0.02em', lineHeight: 1 }}>The Briefing</div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--muted)', marginTop: 8, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            Saturday · 25 April 2026 · Issue 117 · for admin
          </div>
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)' }}>
          <span>EUR · IE</span>
          <span>·</span>
          <span style={{ color: 'var(--ok)' }}>● ALL SOURCES NOMINAL</span>
        </div>
      </div>

      {/* lede */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 56, marginBottom: 44 }}>
        <div>
          <div className="eyebrow" style={{ color: 'var(--accent-warm)', marginBottom: 10 }}>Lead story</div>
          <h1 className="display" style={{ fontSize: 64, lineHeight: 1.02, margin: 0, fontWeight: 500, maxWidth: '14ch' }}>
            April closes net-positive for the eighth straight month.
          </h1>
          <p style={{ fontSize: 19, lineHeight: 1.55, color: 'var(--ink)', maxWidth: '52ch', marginTop: 22 }}>
            Net cashflow held at <strong className="num-mono">+€1,600</strong>, broadly in line with the
            twelve-month median. Spending edged up 4.3%, almost entirely in groceries, while utilities
            continued their March-correction softening. <em>One contract decision is due before Friday.</em>
          </p>
        </div>
        <div style={{ borderLeft: '1px solid var(--line)', paddingLeft: 32 }}>
          <div className="eyebrow" style={{ marginBottom: 14 }}>By the numbers</div>
          <div style={{ display: 'grid', gap: 14 }}>
            {[
              { k: 'Income',      v: '€5,240',  m: 'highest since Nov' },
              { k: 'Expense',     v: '€3,640',  m: '+4.3% vs median' },
              { k: 'Net',         v: '+€1,600', m: 'on plan' },
              { k: 'Recurring',   v: '€1,793/mo', m: 'unchanged' },
            ].map((s) => (
              <div key={s.k} style={{ display: 'grid', gridTemplateColumns: '1fr auto', alignItems: 'baseline', gap: 12, paddingBottom: 12, borderBottom: '1px solid var(--line)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>{s.k}</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>{s.m}</div>
                </div>
                <div className="num-mono" style={{ fontSize: 22, fontWeight: 600 }}>{s.v}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* big chart panel */}
      <div style={{ marginBottom: 44 }}>
        <div className="eyebrow" style={{ marginBottom: 12 }}>Chart of the week</div>
        <div className="display" style={{ fontSize: 26, marginBottom: 18, maxWidth: '40ch' }}>
          Income vs expense, narrowing in winter, widening again into spring.
        </div>
        <div style={{ position: 'relative', padding: '6px 0', borderTop: '1px solid var(--ink)', borderBottom: '1px solid var(--ink)' }}>
          <svg viewBox="0 0 1100 220" style={{ width: '100%', height: 220, display: 'block' }}>
            {[0, 0.25, 0.5, 0.75, 1].map((p) => (
              <line key={p} x1="0" x2="1100" y1={20 + p * 180} y2={20 + p * 180} stroke="rgba(19,40,51,0.06)" />
            ))}
            <Series values={DATA.income}  color="var(--ok)"   width={1100} height={200} top={20} />
            <Series values={DATA.expense} color="var(--warn)" width={1100} height={200} top={20} dashed />
            <Series values={DATA.net}     color="var(--accent)" width={1100} height={200} top={20} thick />
          </svg>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)', marginTop: 6 }}>
            {DATA.months.map((m) => <span key={m}>{m}</span>)}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 22, marginTop: 14, fontSize: 13 }}>
          <Legend color="var(--ok)" label="Income" />
          <Legend color="var(--warn)" label="Expense" dashed />
          <Legend color="var(--accent)" label="Net" thick />
        </div>
      </div>

      {/* three columns: decisions / trends / quiet */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 40, paddingTop: 24, borderTop: '2px solid var(--ink)' }}>
        <div>
          <div className="eyebrow" style={{ color: 'var(--warn)', marginBottom: 8 }}>Decisions</div>
          <div className="display" style={{ fontSize: 24, marginBottom: 14, lineHeight: 1.15 }}>What needs you</div>
          {DATA.attention.slice(0, 3).map((a, i) => (
            <div key={i} style={{ paddingBottom: 14, marginBottom: 14, borderBottom: '1px solid var(--line)' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>
                {a.domain.toUpperCase()} · {a.sev === 1 ? 'URGENT' : a.sev === 2 ? 'SOON' : 'WATCH'}
              </div>
              <div style={{ fontSize: 16, fontWeight: 600, lineHeight: 1.3 }}>{a.title}</div>
              <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 4 }}>{a.detail}</div>
            </div>
          ))}
        </div>
        <div>
          <div className="eyebrow" style={{ color: 'var(--accent-cool)', marginBottom: 8 }}>Trends</div>
          <div className="display" style={{ fontSize: 24, marginBottom: 14, lineHeight: 1.15 }}>What moved</div>
          {[
            { k: 'Groceries', v: '+€48 wow', spark: [3.1, 3.3, 3.0, 3.5, 3.2, 3.6, 3.9], color: 'var(--warn)' },
            { k: 'Utilities', v: '−€26 mom', spark: [2.18, 2.22, 1.96, 1.82, 1.72], color: 'var(--ok)' },
            { k: 'Dining',    v: '+€12 wow', spark: [0.4, 0.5, 0.4, 0.6, 0.5, 0.7, 0.7], color: 'var(--warn)' },
          ].map((t) => (
            <div key={t.k} style={{ paddingBottom: 14, marginBottom: 14, borderBottom: '1px solid var(--line)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontWeight: 700, fontSize: 15 }}>{t.k}</span>
                <span className="num-mono" style={{ fontSize: 13, color: t.color, fontWeight: 700 }}>{t.v}</span>
              </div>
              <Spark values={t.spark} width={300} height={36} color={t.color} />
            </div>
          ))}
        </div>
        <div>
          <div className="eyebrow" style={{ color: 'var(--ok)', marginBottom: 8 }}>Quiet</div>
          <div className="display" style={{ fontSize: 24, marginBottom: 14, lineHeight: 1.15 }}>Held steady</div>
          {[
            'Mortgage payment landed on time, twelfth straight month.',
            'Subscription footprint flat at €94 / month; nothing renewed unexpectedly.',
            'Loan repayments tracking 2.4% ahead of plan year-to-date.',
          ].map((q, i) => (
            <p key={i} style={{ fontSize: 14, lineHeight: 1.55, color: 'var(--ink)', margin: '0 0 14px', paddingBottom: 14, borderBottom: '1px solid var(--line)' }}>{q}</p>
          ))}
        </div>
      </div>

      {/* footer */}
      <div style={{ marginTop: 44, paddingTop: 16, borderTop: '1px solid var(--line)', display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)' }}>
        <span>Built from 4 sources · 5,148 transactions reviewed · last refresh 16h ago</span>
        <span>hla.briefing/2026-04-25</span>
      </div>
    </div>
  );
}

function Series({ values, color, width, height, top, dashed, thick }) {
  const min = Math.min(...values), max = Math.max(...values);
  const range = max - min || 1;
  const stepX = width / (values.length - 1);
  const pts = values.map((v, i) => [i * stepX, top + height * (1 - (v - min) / range)]);
  const d = pts.map((p, i) => (i === 0 ? `M${p[0]},${p[1]}` : `L${p[0]},${p[1]}`)).join(' ');
  return <path d={d} fill="none" stroke={color} strokeWidth={thick ? 2.4 : 1.6} strokeDasharray={dashed ? '4 4' : ''} strokeLinecap="round" />;
}

function Legend({ color, label, dashed, thick }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontWeight: 600 }}>
      <span style={{ width: 24, height: 0, borderTop: `${thick ? 3 : 2}px ${dashed ? 'dashed' : 'solid'} ${color}` }} />
      {label}
    </span>
  );
}

window.MorningBriefing = MorningBriefing;
