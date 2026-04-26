// Concept 2 — Ops Console
// Bloomberg-ish dense terminal for power users: every pixel earns its place.
// All data, narrow padding, fixed-width type, hot-key affordances.

function OpsConsole() {
  const headerCells = [
    ['LINK',     'STABLE'],
    ['LATENCY',  '38ms'],
    ['STAMP',    '2026-04-25 11:24'],
    ['USER',     'admin'],
    ['SESSION',  '6h12m'],
  ];
  const heatRows = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const heatCols = 24;

  const heat = (i, j) => {
    const v = (Math.sin(i * 1.7 + j * 0.4) + 1) / 2 * (j > 7 && j < 22 ? 1 : 0.4);
    return v;
  };

  return (
    <div style={{
      width: '100%', minHeight: '100%',
      background: 'linear-gradient(180deg, #0d1d14 0%, #08110c 60%)',
      color: 'var(--retro-text)',
      fontFamily: 'var(--font-mono)', fontSize: 12,
      padding: '14px 16px',
    }}>
      {/* top status bar */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'auto 1fr auto', gap: 16, alignItems: 'center',
        padding: '6px 12px', border: '1px solid var(--retro-line)', borderRadius: 6,
        background: 'rgba(8,18,13,0.8)', marginBottom: 10,
      }}>
        <span style={{ color: 'var(--retro-warn)', fontWeight: 700, letterSpacing: '0.16em' }}>HLA-OPS // CONSOLE</span>
        <div style={{ display: 'flex', gap: 24, justifyContent: 'center', flexWrap: 'wrap' }}>
          {headerCells.map(([k, v]) => (
            <span key={k} style={{ display: 'inline-flex', gap: 6 }}>
              <span style={{ color: 'var(--retro-muted)' }}>{k}</span>
              <span style={{ color: 'var(--retro-ok)' }}>{v}</span>
            </span>
          ))}
        </div>
        <span style={{ color: 'var(--retro-warn)' }}>F1:HELP F2:RUNS F3:SRC F4:LOAN F5:UTIL ⌥Q:QUIT</span>
      </div>

      {/* main grid: 3 cols × 2 rows */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1.1fr 1.4fr 1fr', gridTemplateRows: '1fr 1fr',
        gap: 10, height: 770,
      }}>
        {/* monitor cell — net cashflow ticker */}
        <div style={panelStyle()}>
          <PanelHeader title="MTHLY CASHFLOW · 12M" right="EUR · NET" />
          <div style={{ padding: 14, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 14, alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 10, color: 'var(--retro-muted)' }}>LATEST</div>
              <div style={{ fontSize: 38, color: 'var(--retro-ok)', lineHeight: 1, fontWeight: 600 }}>+1,600</div>
              <div style={{ fontSize: 10, color: 'var(--retro-warn)', marginTop: 6 }}>Δ12M  +5.6%</div>
              <div style={{ fontSize: 10, color: 'var(--retro-muted)', marginTop: 2 }}>σ12M  248</div>
            </div>
            <Spark values={DATA.net} width={260} height={86} color="#88ffa4" fill={false} strokeWidth={1.4} />
          </div>
          <div style={{ padding: '0 14px 14px', display: 'flex', justifyContent: 'space-between', color: 'var(--retro-muted)', fontSize: 10 }}>
            {DATA.months.map((m) => <span key={m}>{m.slice(0,1)}</span>)}
          </div>
        </div>

        {/* day-of-week × hour heatmap of spend */}
        <div style={panelStyle()}>
          <PanelHeader title="SPEND HEATMAP · 28D" right="rows: dow  cols: hour" />
          <div style={{ padding: 14, display: 'grid', gridTemplateColumns: '24px 1fr', gap: 8, alignItems: 'center' }}>
            <div style={{ display: 'grid', gap: 2 }}>
              {heatRows.map((r) => <div key={r} style={{ fontSize: 10, color: 'var(--retro-muted)', height: 16, lineHeight: '16px' }}>{r}</div>)}
            </div>
            <div style={{ display: 'grid', gridTemplateRows: 'repeat(7, 16px)', gap: 2 }}>
              {heatRows.map((r, i) => (
                <div key={r} style={{ display: 'grid', gridTemplateColumns: `repeat(${heatCols}, 1fr)`, gap: 2 }}>
                  {Array.from({length: heatCols}).map((_, j) => {
                    const v = heat(i, j);
                    return <div key={j} style={{ background: `rgba(136,255,164,${0.08 + v * 0.78})`, borderRadius: 2 }} />;
                  })}
                </div>
              ))}
            </div>
          </div>
          <div style={{ padding: '0 14px 14px', fontSize: 10, color: 'var(--retro-muted)', display: 'flex', justifyContent: 'space-between' }}>
            <span>00</span><span>06</span><span>12</span><span>18</span><span>23</span>
          </div>
        </div>

        {/* attention queue */}
        <div style={panelStyle()}>
          <PanelHeader title="ATTENTION" right={`${DATA.attention.length} OPEN`} />
          <div style={{ padding: '6px 12px 12px' }}>
            {DATA.attention.map((a, i) => (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '34px 1fr', gap: 8,
                padding: '8px 0', borderBottom: '1px dashed rgba(136,255,164,0.14)', fontSize: 11,
              }}>
                <span style={{ color: a.sev === 1 ? '#ff8b8b' : a.sev === 2 ? 'var(--retro-warn)' : 'var(--retro-muted)' }}>
                  S{a.sev}
                </span>
                <div>
                  <div style={{ color: 'var(--retro-text)' }}>{a.title}</div>
                  <div style={{ color: 'var(--retro-muted)', fontSize: 10, marginTop: 2 }}>{a.domain.toUpperCase()} · {a.detail}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* runs table */}
        <div style={panelStyle()}>
          <PanelHeader title="INGESTION RUNS · TAIL 8" right="↑ NEWEST" />
          <div style={{ padding: '6px 12px 12px', fontSize: 11 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '70px 1fr 1fr 60px 80px', gap: 8, color: 'var(--retro-warn)', padding: '4px 0', borderBottom: '1px solid rgba(246,199,109,0.2)' }}>
              <span>RUN</span><span>SOURCE</span><span>FILE</span><span>ROWS</span><span>STATUS</span>
            </div>
            {[...DATA.runs, ...DATA.runs].slice(0, 8).map((r, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '70px 1fr 1fr 60px 80px', gap: 8, padding: '6px 0', borderBottom: '1px dashed rgba(136,255,164,0.10)' }}>
                <span style={{ color: 'var(--retro-muted)' }}>{r.id}</span>
                <span>{r.source}</span>
                <span style={{ color: 'var(--retro-muted)' }}>{r.file}</span>
                <span style={{ color: 'var(--retro-text)', textAlign: 'right' }}>{r.rows}</span>
                <span style={{
                  color: r.status === 'rejected' ? '#ff8b8b'
                       : r.status === 'enqueued' ? 'var(--retro-warn)'
                       : 'var(--retro-ok)',
                }}>{r.status.toUpperCase()}</span>
              </div>
            ))}
          </div>
        </div>

        {/* category bars + ratios */}
        <div style={panelStyle()}>
          <PanelHeader title="SPEND BY CATEGORY · APR" right="EUR" />
          <div style={{ padding: 14, display: 'grid', gap: 10 }}>
            {DATA.categories.map((c) => (
              <div key={c.label} style={{ display: 'grid', gridTemplateColumns: '110px 1fr 70px', gap: 10, alignItems: 'center', fontSize: 11 }}>
                <span>{c.label.toLowerCase()}</span>
                <div style={{ height: 10, background: 'rgba(136,255,164,0.08)', borderRadius: 2 }}>
                  <div style={{ height: '100%', width: `${c.share * 100 * 2.4}%`, background: 'var(--retro-ok)', borderRadius: 2 }} />
                </div>
                <span style={{ textAlign: 'right', color: 'var(--retro-text)' }}>{c.amount.toFixed(0)}</span>
              </div>
            ))}
            <div style={{ marginTop: 6, paddingTop: 10, borderTop: '1px dashed rgba(136,255,164,0.2)', display: 'grid', gap: 6 }}>
              {DATA.ratios.map((r) => (
                <div key={r.name} style={{ display: 'grid', gridTemplateColumns: '1fr 50px', fontSize: 11 }}>
                  <span style={{ color: 'var(--retro-muted)' }}>{r.name}</span>
                  <span style={{ textAlign: 'right', color: r.state === 'ok' ? 'var(--retro-ok)' : '#ff8b8b' }}>{r.pct.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* command line */}
        <div style={{ ...panelStyle(), gridColumn: 'span 1' }}>
          <PanelHeader title="COMMAND" right="READY" />
          <div style={{ padding: 14, display: 'grid', gap: 8, fontSize: 11 }}>
            {[
              ['> runs --tail 20',       'OK · 20 rows'],
              ['> sources fresh',         'OK · 1 yellow, 1 red'],
              ['> scenario rate +0.5pp',  'OK · DSR 18.2 → 19.4'],
              ['> attention --sev 1',     'OK · 1 item'],
            ].map(([cmd, out], i) => (
              <div key={i}>
                <div style={{ color: 'var(--retro-ok)' }}>{cmd}</div>
                <div style={{ color: 'var(--retro-muted)', paddingLeft: 12 }}>{out}</div>
              </div>
            ))}
            <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 6, borderTop: '1px solid var(--retro-line)', paddingTop: 10 }}>
              <span style={{ color: 'var(--retro-warn)' }}>$</span>
              <span style={{ color: 'var(--retro-text)' }}>_</span>
              <span style={{ display: 'inline-block', width: 7, height: 14, background: 'var(--retro-ok)', animation: 'blink 1s infinite' }} />
            </div>
          </div>
        </div>
      </div>
      <style>{`@keyframes blink { 50% { opacity: 0; } }`}</style>
    </div>
  );
}

function panelStyle() {
  return {
    border: '1px solid var(--retro-line)',
    borderRadius: 8,
    background: 'linear-gradient(180deg, rgba(15,31,21,0.98), rgba(9,21,15,0.92))',
    boxShadow: 'inset 0 0 0 1px rgba(136,255,164,0.04)',
    overflow: 'hidden',
    display: 'grid',
    gridTemplateRows: 'auto 1fr',
  };
}

function PanelHeader({ title, right }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '8px 12px', borderBottom: '1px solid var(--retro-line)',
      background: 'rgba(0,0,0,0.2)',
      fontSize: 10, letterSpacing: '0.16em',
    }}>
      <span style={{ color: 'var(--retro-warn)' }}>{title}</span>
      <span style={{ color: 'var(--retro-muted)' }}>{right}</span>
    </div>
  );
}

window.OpsConsole = OpsConsole;
