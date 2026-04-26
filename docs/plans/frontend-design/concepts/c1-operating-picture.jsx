// Concept 1 — Operating Picture v2
// Same warm DNA as the existing AppShell, but with stronger rhythm:
// - magazine-grade hero with one stat that matters
// - "freshness pulse" replacing scattered status pills
// - attention queue treated as an editorial list, not a table
// - explicit weekly horizon strip

function FreshnessPulse() {
  const domains = [
    { name: 'Finance',     band: 'green',  detail: 'op_account · 16h ago' },
    { name: 'Recurring',   band: 'green',  detail: 'subscriptions · 2d ago' },
    { name: 'Utilities',   band: 'yellow', detail: 'contract_prices · 5d ago' },
    { name: 'Loans',       band: 'green',  detail: 'loan_repayments · 1d ago' },
    { name: 'Budgets',     band: 'red',    detail: 'budgets · 14d — stale' },
  ];
  const colors = { green: 'var(--ok)', yellow: 'var(--accent-warm)', red: 'var(--warn)' };
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
      {domains.map((d) => (
        <div key={d.name} style={{
          border: '1px solid var(--line)', borderRadius: 16, padding: '14px 14px 16px',
          background: 'rgba(255,255,255,0.5)',
          display: 'grid', gap: 8,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--ink)' }}>{d.name}</span>
            <Dot color={colors[d.band]} size={9} />
          </div>
          <div style={{ height: 6, borderRadius: 999, background: 'rgba(19,40,51,0.06)', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: d.band === 'green' ? '92%' : d.band === 'yellow' ? '54%' : '12%', background: colors[d.band] }} />
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)' }}>{d.detail}</div>
        </div>
      ))}
    </div>
  );
}

function HorizonStrip() {
  const days = [
    { d: 'Mon 28', label: 'Energy bill',          amount: '€172.18', tone: 'cool' },
    { d: 'Tue 29', label: 'Netflix renewal',       amount: '€15.99',  tone: 'neutral' },
    { d: 'Wed 30', label: '—',                      amount: '',        tone: 'empty' },
    { d: 'Thu 01', label: 'Mortgage payment',      amount: '€1,284',  tone: 'accent' },
    { d: 'Fri 02', label: 'Spotify, Disney+',      amount: '€22.98',  tone: 'neutral' },
    { d: 'Sat 03', label: '—',                      amount: '',        tone: 'empty' },
    { d: 'Sun 04', label: 'Energy contract review', amount: '',        tone: 'warm' },
  ];
  const bg = {
    cool: 'rgba(11,95,131,0.08)', neutral: 'rgba(255,255,255,0.5)', empty: 'transparent',
    accent: 'rgba(15,118,110,0.10)', warm: 'rgba(201,106,61,0.12)',
  };
  const border = {
    cool: 'var(--accent-cool)', neutral: 'var(--line)', empty: 'var(--line)',
    accent: 'var(--accent)', warm: 'var(--accent-warm)',
  };
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 10 }}>
      {days.map((d, i) => (
        <div key={i} style={{
          border: `1px solid ${d.tone === 'empty' ? 'transparent' : border[d.tone]}`,
          background: bg[d.tone],
          borderRadius: 14, padding: '12px 12px 14px', minHeight: 96,
          display: 'grid', gap: 6, alignContent: 'start',
        }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)', letterSpacing: '0.04em' }}>{d.d}</div>
          <div style={{ fontWeight: 600, fontSize: 13, lineHeight: 1.3, color: d.tone === 'empty' ? 'var(--muted)' : 'var(--ink)' }}>{d.label}</div>
          {d.amount && <div className="num-mono" style={{ fontWeight: 700, fontSize: 13 }}>{d.amount}</div>}
        </div>
      ))}
    </div>
  );
}

function OperatingPictureV2() {
  return (
    <div style={{
      width: '100%', minHeight: '100%',
      background: 'radial-gradient(circle at 8% 0%, rgba(201,106,61,0.18), transparent 32%), radial-gradient(circle at 96% 4%, rgba(15,118,110,0.16), transparent 36%), linear-gradient(180deg, #f7f3eb, var(--bg))',
      padding: '36px 44px 56px',
      fontFamily: 'var(--font-sans)',
    }}>
      {/* topbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 }}>
        <div>
          <Eyebrow>Household Intelligence</Eyebrow>
          <div className="display" style={{ fontSize: 28, marginTop: 4 }}>Operating Picture</div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          {['Dashboard', 'Runs', 'Costs', 'Utilities', 'Loans', 'Sources'].map((t, i) => (
            <span key={t} style={{
              padding: '8px 14px', borderRadius: 999, fontSize: 13, fontWeight: 700,
              color: i === 0 ? 'var(--ink)' : 'var(--muted)',
              background: i === 0 ? 'rgba(19,40,51,0.06)' : 'transparent',
            }}>{t}</span>
          ))}
          <span style={{ padding: '8px 12px', borderRadius: 999, fontSize: 12, fontWeight: 800, background: 'rgba(11,95,131,0.10)', color: 'var(--accent-cool)' }}>admin / admin</span>
        </div>
      </div>

      {/* hero */}
      <div className="panel-warm" style={{ padding: '40px 44px', marginBottom: 22, position: 'relative', overflow: 'hidden' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 40, alignItems: 'end' }}>
          <div>
            <Eyebrow style={{ color: 'var(--accent-warm)' }}>April 2026 · Week 17</Eyebrow>
            <h1 className="display" style={{ fontSize: 88, margin: '12px 0 8px', maxWidth: '14ch' }}>
              Net <span className="num-mono" style={{ fontWeight: 600 }}>+€1,600</span>
            </h1>
            <p style={{ color: 'var(--muted)', fontSize: 17, lineHeight: 1.55, maxWidth: '52ch', margin: 0 }}>
              On track. Spending is 4.3% above the 12-month median, mostly groceries; utilities are below trend after the
              March correction. One contract decision needs you this week.
            </p>
          </div>
          <div style={{ display: 'grid', gap: 16 }}>
            <div>
              <div className="eyebrow" style={{ color: 'var(--muted)' }}>Cashflow · last 12 months</div>
              <Spark values={DATA.net} width={420} height={88} color="var(--accent)" />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
                <span>{DATA.months[0]}</span><span>{DATA.months[DATA.months.length - 1]}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* freshness pulse */}
      <div className="panel-warm" style={{ padding: 24, marginBottom: 22 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
          <div>
            <Eyebrow>Confidence</Eyebrow>
            <div className="display" style={{ fontSize: 22, marginTop: 2 }}>Source freshness pulse</div>
          </div>
          <span style={{ color: 'var(--accent-cool)', fontWeight: 700, fontSize: 13 }}>Manage sources →</span>
        </div>
        <FreshnessPulse />
      </div>

      {/* horizon strip */}
      <div className="panel-warm" style={{ padding: 24, marginBottom: 22 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
          <div>
            <Eyebrow>Next seven days</Eyebrow>
            <div className="display" style={{ fontSize: 22, marginTop: 2 }}>Horizon</div>
          </div>
          <span style={{ color: 'var(--muted)', fontSize: 13 }}>4 obligations · €1,495 outflow</span>
        </div>
        <HorizonStrip />
      </div>

      {/* attention + ratios */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: 22, marginBottom: 22 }}>
        <div className="panel-warm" style={{ padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 18 }}>
            <div>
              <Eyebrow>Attention queue</Eyebrow>
              <div className="display" style={{ fontSize: 22, marginTop: 2 }}>Decisions pending</div>
            </div>
            <span style={{ color: 'var(--muted)', fontSize: 13 }}>{DATA.attention.length} items</span>
          </div>
          <div style={{ display: 'grid', gap: 0 }}>
            {DATA.attention.map((a, i) => (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '40px 1fr auto', gap: 16, alignItems: 'start',
                padding: '14px 0', borderTop: i ? '1px solid var(--line)' : 'none',
              }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)', paddingTop: 3 }}>0{i + 1}</div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                    {a.sev === 1 && <Pill tone="warn">urgent</Pill>}
                    {a.sev === 2 && <Pill tone="warm">soon</Pill>}
                    {a.sev === 3 && <Pill tone="neutral">watch</Pill>}
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)' }}>{a.domain}</span>
                  </div>
                  <div style={{ fontWeight: 600, fontSize: 15, lineHeight: 1.35 }}>{a.title}</div>
                  <div style={{ color: 'var(--muted)', fontSize: 13, marginTop: 2 }}>{a.detail}</div>
                </div>
                <span style={{ color: 'var(--accent-cool)', fontWeight: 700, fontSize: 13, paddingTop: 3 }}>Review →</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: 'grid', gap: 22 }}>
          <div className="panel-warm" style={{ padding: 24 }}>
            <Eyebrow>Affordability</Eyebrow>
            <div style={{ display: 'grid', gap: 14, marginTop: 14 }}>
              {DATA.ratios.map((r) => (
                <div key={r.name}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{r.name}</span>
                    <span className="num-mono" style={{ fontWeight: 700, color: r.state === 'ok' ? 'var(--ok)' : 'var(--warn)' }}>
                      {r.pct.toFixed(1)}%
                    </span>
                  </div>
                  <div style={{ height: 8, borderRadius: 999, background: 'rgba(19,40,51,0.06)', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%', width: `${Math.min(r.pct, 100)}%`,
                      background: r.state === 'ok' ? 'var(--ok)' : 'var(--warn)',
                    }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel-warm" style={{ padding: 24 }}>
            <Eyebrow>Top categories · April</Eyebrow>
            <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
              {DATA.categories.map((c) => (
                <div key={c.label} style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 14, alignItems: 'center' }}>
                  <span style={{ fontSize: 13 }}>{c.label}</span>
                  <span className="num-mono" style={{ fontSize: 13, color: 'var(--muted)' }}>
                    {c.delta === 0 ? '·' : (c.delta > 0 ? '▲' : '▼')} {c.delta !== 0 ? Math.abs(c.delta).toFixed(1) + '%' : ''}
                  </span>
                  <span className="num-mono" style={{ fontSize: 13, fontWeight: 700 }}>{fmtEUR(c.amount, { dec: 2 })}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

window.OperatingPictureV2 = OperatingPictureV2;
