'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { AppShell } from '@/components/app-shell';
import { ControlNav } from '@/components/control-nav';
import { getCurrentUser } from '@/lib/backend';

const VERDICT_COLORS = {
  'TRUSTWORTHY': { bg: '#e8f5e9', text: '#2e7d32', label: 'Trustworthy' },
  'DEGRADED': { bg: '#fff3e0', text: '#e65100', label: 'Degraded' },
  'UNRELIABLE': { bg: '#fce4ec', text: '#c2185b', label: 'Unreliable' },
  'UNAVAILABLE': { bg: '#ffebee', text: '#b71c1c', label: 'Unavailable' },
};

const FRESHNESS_COLORS = {
  'CURRENT': { bg: '#e8f5e9', text: '#2e7d32', label: 'Current' },
  'DUE_SOON': { bg: '#fff3e0', text: '#e65100', label: 'Due soon' },
  'OVERDUE': { bg: '#fce4ec', text: '#c2185b', label: 'Overdue' },
  'MISSING_PERIOD': { bg: '#ffebee', text: '#b71c1c', label: 'Missing period' },
  'PARSE_FAILED': { bg: '#ffebee', text: '#b71c1c', label: 'Parse failed' },
  'UNCONFIGURED': { bg: '#f5f5f5', text: '#666', label: 'Unconfigured' },
};

function Badge({ value, colorMap }) {
  const colors = colorMap[value] || { bg: '#f5f5f5', text: '#666', label: value };
  return (
    <span style={{
      display: 'inline-block',
      padding: '4px 12px',
      borderRadius: '4px',
      backgroundColor: colors.bg,
      color: colors.text,
      fontSize: '12px',
      fontWeight: '500',
    }}>
      {colors.label}
    </span>
  );
}

function DomainCard({ domain, count, verdict }) {
  const verdictInfo = VERDICT_COLORS[verdict] || VERDICT_COLORS['UNAVAILABLE'];
  return (
    <div style={{
      padding: '16px',
      border: '1px solid #e0e0e0',
      borderRadius: '8px',
      marginBottom: '12px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ margin: '0 0 8px 0', textTransform: 'capitalize', fontSize: '16px' }}>
            {domain}
          </h3>
          <p style={{ margin: '0', color: '#666', fontSize: '12px' }}>
            {count} publication{count !== 1 ? 's' : ''}
          </p>
        </div>
        <Badge value={verdict} colorMap={VERDICT_COLORS} />
      </div>
    </div>
  );
}

function PublicationRow({ pub, hideStale }) {
  const verdict = pub.confidence_verdict || 'UNAVAILABLE';
  if (hideStale && verdict === 'TRUSTWORTHY') {
    return null;
  }

  const assessedAt = new Date(pub.assessed_at);
  const now = new Date();
  const hoursAgo = Math.floor((now - assessedAt) / (1000 * 60 * 60));

  return (
    <tr style={{ borderBottom: '1px solid #e0e0e0' }}>
      <td style={{ padding: '12px', fontSize: '13px' }}>{pub.publication_key}</td>
      <td style={{ padding: '12px', textAlign: 'center' }}>
        <Badge value={verdict} colorMap={VERDICT_COLORS} />
      </td>
      <td style={{ padding: '12px', textAlign: 'center' }}>
        <Badge value={pub.freshness_state} colorMap={FRESHNESS_COLORS} />
      </td>
      <td style={{ padding: '12px', textAlign: 'center', fontSize: '13px' }}>
        {pub.completeness_pct}%
      </td>
      <td style={{ padding: '12px', fontSize: '11px', color: '#666' }}>
        {hoursAgo < 1 ? 'just now' : hoursAgo < 24 ? `${hoursAgo}h ago` : `${Math.floor(hoursAgo / 24)}d ago`}
      </td>
    </tr>
  );
}

export default function ConfidencePage() {
  const [user, setUser] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [hideStale, setHideStale] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const loadData = async () => {
      try {
        const currentUser = await getCurrentUser();
        if (currentUser.role === 'reader') {
          router.push('/');
          return;
        }
        setUser(currentUser);

        const response = await fetch('/api/control/confidence');
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        const result = await response.json();
        setData(result);
      } catch (err) {
        setError(err.message);
      }
    };
    loadData();
  }, [router]);

  if (!user || !data) {
    return <AppShell title="Publication confidence" eyebrow="Operator Access">Loading...</AppShell>;
  }

  if (error) {
    return (
      <AppShell title="Publication confidence" eyebrow="Operator Access">
        <p style={{ color: '#b71c1c' }}>Error: {error}</p>
      </AppShell>
    );
  }

  const filteredPubs = hideStale
    ? data.publications.filter(p => p.confidence_verdict !== 'TRUSTWORTHY')
    : data.publications;

  return (
    <AppShell
      currentPath="/control"
      user={user}
      title="Publication confidence"
      eyebrow="Operator Access"
    >
      <ControlNav />

      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '20px' }}>
        <div style={{ marginBottom: '32px' }}>
          <h2 style={{ margin: '0 0 16px 0', fontSize: '20px' }}>Domain summary</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
            {data.domain_summaries.map((domain) => (
              <DomainCard
                key={domain.domain}
                domain={domain.domain}
                count={domain.count}
                verdict={domain.verdict}
              />
            ))}
          </div>
        </div>

        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2 style={{ margin: '0', fontSize: '20px' }}>Publications</h2>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
              <input
                type="checkbox"
                checked={hideStale}
                onChange={(e) => setHideStale(e.target.checked)}
              />
              Show issues only
            </label>
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e0e0e0', backgroundColor: '#f9f9f9' }}>
                <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600' }}>Publication</th>
                <th style={{ padding: '12px', textAlign: 'center', fontWeight: '600' }}>Verdict</th>
                <th style={{ padding: '12px', textAlign: 'center', fontWeight: '600' }}>Freshness</th>
                <th style={{ padding: '12px', textAlign: 'center', fontWeight: '600' }}>Complete</th>
                <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600' }}>Assessed</th>
              </tr>
            </thead>
            <tbody>
              {filteredPubs.length > 0 ? (
                filteredPubs.map((pub) => (
                  <PublicationRow
                    key={pub.publication_key}
                    pub={pub}
                    hideStale={hideStale}
                  />
                ))
              ) : (
                <tr>
                  <td colSpan="5" style={{ padding: '24px', textAlign: 'center', color: '#666' }}>
                    No publications found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  );
}
