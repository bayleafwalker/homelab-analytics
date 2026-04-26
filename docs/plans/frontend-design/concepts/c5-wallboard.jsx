// Concept 5 — Homelab Wallboard
// Always-on status board for services, devices, alerts. Retro flavour but
// readable and informational, not just decorative.

function Wallboard() {
  const services = [
    { name: 'api',           host: 'hla-api-1',        status: 'ok',   uptime: '38d 04h', cpu: 12, mem: 41 },
    { name: 'worker',        host: 'hla-worker-1',     status: 'ok',   uptime: '38d 04h', cpu: 28, mem: 62 },
    { name: 'web',           host: 'hla-web-1',        status: 'ok',   uptime: '11d 22h', cpu:  8, mem: 24 },
    { name: 'postgres',      host: 'pg-primary',       status: 'ok',   uptime: '92d 18h', cpu: 18, mem: 71 },
    { name: 'duckdb',        host: 'analytics-1',      status: 'ok',   uptime: '38d 04h', cpu: 34, mem: 58 },
    { name: 'minio',         host: 'minio-1',          status: 'warn', uptime: '38d 04h', cpu:  6, mem: 18 },
    { name: 'mqtt',          host: 'broker-1',         status: 'ok',   uptime: '186d',    cpu:  3, mem: 12 },
    { name: 'home-assistant', host: 'ha-core',          status: 'ok',   uptime: '14d 02h', cpu: 22, mem: 48 },
  ];

  const alerts = [
    { t: '11:18', sev: 'warn', text: 'minio: bucket landing-zone 84% full' },
    { t: '08:42', sev: 'info', text: 'op_account import landed (612 rows)' },
    { t: '07:00', sev: 'info', text: 'nightly DuckDB compaction completed in 4m12s' },
    { t: '02:14', sev: 'info', text: 'agent guidance refresh completed' },
  ];

  const devices = [
    { name: 'office',   t: 21.2, h: 44, p: 142 },
    { name: 'living',   t: 22.0, h: 47, p:  86 },
    { name: 'kitchen',  t: 22.4, h: 51, p: 320 },
    { name: 'bedroom',  t: 19.8, h: 49, p:  12 },
    { name: 'utility',  t: 14.8, h: 62, p: 410 },
    { name: 'outdoor',  t:  9.6, h: 78, p:   0 },
  ];

  const grid = (i, j, n) => Math.sin((i + 1) * 0.6 + j * 0.8 + n) * 0.5 + 0.5;

  return (
    <div style={{
      width: '100%', minHeight: '100%',
      background: 'radial-gradient(circle at 12% 4%, rgba(246,199,109,0.06), transparent 32%), radial-gradient(circle at 92% 8%, rgba(138,230,255,0.06), transparent 36%), linear-gradient(180deg, #0d1d14 0%, #08110c 56%, #040806 100%)',
      color: 'var(--retro-text)',
      fontFamily: 'var(--font-mono)',
      padding: '20px 22px',
      position: 'relative',
    }}>
      {/* scanlines */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        backgroundImage: 'repeating-linear-gradient(180deg, rgba(217,255,215,0.06) 0 1px, transparent 1px 4px)',
        opacity: 0.5,
      }} />

      <div style={{ position: 'relative', zIndex: 1 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
          <div>
            <div style={{ color: 'var(--retro-warn)', fontSize: 11, letterSpacing: '0.18em' }}>HOMELAB / WALLBOARD</div>
            <div style={{ fontSize: 32, fontWeight: 600, color: 'var(--retro-text)', textShadow: '0 0 20px rgba(136,255,164,0.25)', marginTop: 4, letterSpacing: '0.04em' }}>
              ALL SYSTEMS<span style={{ color: 'var(--retro-ok)' }}> NOMINAL</span>
            </div>
          </div>
          <div style={{ display: 'grid', gap: 4, textAlign: 'right' }}>
            <div style={{ fontSize: 11, color: 'var(--retro-muted)' }}>2026-04-25 · 11:24:18 IST</div>
            <div style={{ fontSize: 11, color: 'var(--retro-muted)' }}>uptime  38d 04h 12m</div>
            <div style={{ fontSize: 11, color: 'var(--retro-warn)' }}>1 warning · 0 errors</div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 12 }}>
          {/* services grid */}
          <WallPanel title="SERVICES · 8" right="ok 7 / warn 1 / err 0">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, padding: 10 }}>
              {services.map((s) => (
                <div key={s.name} style={{
                  border: `1px solid ${s.status === 'warn' ? 'rgba(246,199,109,0.5)' : 'rgba(136,255,164,0.22)'}`,
                  borderRadius: 6, padding: '10px 10px 8px',
                  background: 'rgba(5,12,8,0.6)',
                  display: 'grid', gap: 6,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: s.status === 'warn' ? 'var(--retro-warn)' : 'var(--retro-ok)', fontWeight: 700 }}>
                      {s.name}
                    </span>
                    <Dot color={s.status === 'warn' ? 'var(--retro-warn)' : 'var(--retro-ok)'} size={7} />
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--retro-muted)' }}>{s.host} · {s.uptime}</div>
                  <div style={{ display: 'grid', gridTemplateColumns: '24px 1fr 32px', gap: 6, alignItems: 'center', fontSize: 10 }}>
                    <span style={{ color: 'var(--retro-muted)' }}>cpu</span>
                    <Bar pct={s.cpu} warn={s.cpu > 70} />
                    <span style={{ textAlign: 'right' }}>{s.cpu}%</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '24px 1fr 32px', gap: 6, alignItems: 'center', fontSize: 10 }}>
                    <span style={{ color: 'var(--retro-muted)' }}>mem</span>
                    <Bar pct={s.mem} warn={s.mem > 80} />
                    <span style={{ textAlign: 'right' }}>{s.mem}%</span>
                  </div>
                </div>
              ))}
            </div>
          </WallPanel>

          {/* alerts feed */}
          <WallPanel title="EVENT FEED" right="last 12h">
            <div style={{ padding: '6px 12px 12px' }}>
              {alerts.map((a, i) => (
                <div key={i} style={{
                  display: 'grid', gridTemplateColumns: '52px 60px 1fr', gap: 8,
                  padding: '8px 0', borderBottom: '1px dashed rgba(136,255,164,0.10)', fontSize: 11,
                }}>
                  <span style={{ color: 'var(--retro-muted)' }}>{a.t}</span>
                  <span style={{ color: a.sev === 'warn' ? 'var(--retro-warn)' : 'var(--retro-accent)' }}>
                    {a.sev.toUpperCase()}
                  </span>
                  <span>{a.text}</span>
                </div>
              ))}
              <div style={{
                marginTop: 10, padding: 10, border: '1px dashed rgba(136,255,164,0.18)', borderRadius: 4,
                fontSize: 11, color: 'var(--retro-muted)',
              }}>
                <div style={{ color: 'var(--retro-warn)', marginBottom: 4 }}>ACK PENDING</div>
                <div>minio bucket usage trending toward 90% threshold; suggest archive of landing/2025-Q4.</div>
              </div>
            </div>
          </WallPanel>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
          {/* devices map */}
          <WallPanel title="DEVICES · 6 ROOMS" right="HA-CORE LINKED">
            <div style={{ padding: 12, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              {devices.map((d) => (
                <div key={d.name} style={{
                  border: '1px solid rgba(136,255,164,0.18)', borderRadius: 6,
                  padding: '10px 12px', background: 'rgba(5,12,8,0.5)',
                  display: 'grid', gap: 4,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--retro-warn)', fontSize: 10, letterSpacing: '0.12em' }}>{d.name.toUpperCase()}</span>
                    <span style={{ fontSize: 10, color: 'var(--retro-muted)' }}>{d.p}W</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 18, color: 'var(--retro-ok)' }}>
                    <span>{d.t.toFixed(1)}°</span>
                    <span style={{ color: 'var(--retro-accent)', fontSize: 13, alignSelf: 'end' }}>{d.h}%</span>
                  </div>
                </div>
              ))}
            </div>
          </WallPanel>

          {/* metrics grid mini-chart */}
          <WallPanel title="HOUSEHOLD POWER · 24H" right="kWh">
            <div style={{ padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                <span style={{ fontSize: 11, color: 'var(--retro-muted)' }}>peak  3.4 kW · 18:42</span>
                <span style={{ fontSize: 11, color: 'var(--retro-warn)' }}>avg  1.07 kW</span>
              </div>
              <svg viewBox="0 0 600 140" width="100%" height="140">
                {Array.from({length: 24}).map((_, j) => {
                  const v = (Math.sin(j * 0.7) + 1) / 2 * (j > 17 || (j > 6 && j < 9) ? 0.92 : 0.45);
                  const h = 10 + v * 110;
                  return <rect key={j} x={j * 25 + 4} y={140 - h} width={20} height={h} fill="var(--retro-ok)" opacity={0.2 + v * 0.7} rx={2} />;
                })}
                {[35, 70, 105].map((y) => <line key={y} x1="0" x2="600" y1={y} y2={y} stroke="rgba(136,255,164,0.06)" />)}
              </svg>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--retro-muted)', marginTop: 4 }}>
                <span>00</span><span>06</span><span>12</span><span>18</span><span>23</span>
              </div>
            </div>
          </WallPanel>
        </div>

        {/* footer ticker */}
        <div style={{
          marginTop: 12, padding: '10px 14px',
          border: '1px solid var(--retro-line)', borderRadius: 6,
          background: 'rgba(8,18,13,0.7)',
          fontSize: 11, color: 'var(--retro-muted)',
          display: 'flex', justifyContent: 'space-between',
        }}>
          <span>● analytics ingested 612 rows · ● 4 budgets evaluated · ● 1 contract renewal due in 12 days · ● mortgage rate review window opens in 4 weeks</span>
          <span style={{ color: 'var(--retro-accent)' }}>F1 ack  ·  F2 expand  ·  F4 silence</span>
        </div>
      </div>
    </div>
  );
}

function WallPanel({ title, right, children }) {
  return (
    <div style={{
      border: '1px solid var(--retro-line)', borderRadius: 8,
      background: 'linear-gradient(180deg, rgba(15,31,21,0.95), rgba(9,21,15,0.92))',
      overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        padding: '8px 12px', borderBottom: '1px solid var(--retro-line)',
        background: 'rgba(0,0,0,0.18)',
        fontSize: 10, letterSpacing: '0.16em',
      }}>
        <span style={{ color: 'var(--retro-warn)' }}>{title}</span>
        <span style={{ color: 'var(--retro-muted)' }}>{right}</span>
      </div>
      {children}
    </div>
  );
}

function Bar({ pct, warn }) {
  return (
    <div style={{ height: 6, background: 'rgba(136,255,164,0.10)', borderRadius: 2 }}>
      <div style={{ height: '100%', width: `${pct}%`, background: warn ? 'var(--retro-warn)' : 'var(--retro-ok)', borderRadius: 2 }} />
    </div>
  );
}

window.Wallboard = Wallboard;
