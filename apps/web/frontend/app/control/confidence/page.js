'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { AppShell } from '@/components/app-shell';
import { ControlNav } from '@/components/control-nav';

const VERDICT_COLORS = {
  trustworthy: { bg: '#e8f5e9', text: '#2e7d32', label: 'Trustworthy' },
  degraded: { bg: '#fff3e0', text: '#e65100', label: 'Degraded' },
  unreliable: { bg: '#fce4ec', text: '#c2185b', label: 'Unreliable' },
  unavailable: { bg: '#ffebee', text: '#b71c1c', label: 'Unavailable' },
};

const FRESHNESS_COLORS = {
  current: { bg: '#e8f5e9', text: '#2e7d32', label: 'Current' },
  due_soon: { bg: '#fff3e0', text: '#e65100', label: 'Due soon' },
  stale: { bg: '#fce4ec', text: '#c2185b', label: 'Stale' },
  unavailable: { bg: '#ffebee', text: '#b71c1c', label: 'Unavailable' },
};

function Badge({ value, colorMap }) {
  const normalizedValue = String(value || 'unavailable').toLowerCase();
  const colors = colorMap[normalizedValue] || {
    bg: '#f5f5f5',
    text: '#666',
    label: normalizedValue,
  };
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

function DomainCard({ domain, count, verdict, degradedCount, staleCount }) {
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
            {' | '}
            {degradedCount} degraded
            {' | '}
            {staleCount} stale
          </p>
        </div>
        <Badge value={verdict} colorMap={VERDICT_COLORS} />
      </div>
    </div>
  );
}

function CompletenessBar({ value }) {
  const boundedValue = Math.max(0, Math.min(100, Number(value || 0)));
  return (
    <div style={{ display: 'grid', gap: '6px', minWidth: '120px' }}>
      <div
        style={{
          height: '8px',
          borderRadius: '999px',
          backgroundColor: '#eef2f7',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${boundedValue}%`,
            height: '100%',
            backgroundColor: boundedValue >= 100 ? '#2e7d32' : '#e65100',
          }}
        />
      </div>
      <span style={{ fontSize: '12px', color: '#4b5563' }}>{boundedValue}%</span>
    </div>
  );
}

function formatAssessedAt(value) {
  if (!value) return 'No assessment';
  const assessedAt = new Date(value);
  const now = new Date();
  const hoursAgo = Math.floor((now - assessedAt) / (1000 * 60 * 60));
  if (hoursAgo < 1) return 'just now';
  if (hoursAgo < 24) return `${hoursAgo}h ago`;
  return `${Math.floor(hoursAgo / 24)}d ago`;
}

function PublicationRow({ pub }) {
  const verdict = pub.confidence_verdict || 'unavailable';
  const lineageHref = `/control/lineage?publication_key=${encodeURIComponent(pub.publication_key)}`;

  return (
    <tr style={{ borderBottom: '1px solid #e0e0e0' }}>
      <td style={{ padding: '12px', fontSize: '13px' }}>
        <div style={{ fontWeight: '700' }}>{pub.publication_name || pub.publication_key}</div>
        <div style={{ color: '#667085', fontSize: '12px' }}>{pub.publication_key}</div>
      </td>
      <td style={{ padding: '12px', fontSize: '13px', textTransform: 'capitalize' }}>
        {pub.domain || 'platform'}
      </td>
      <td style={{ padding: '12px', textAlign: 'center' }}>
        <Badge value={verdict} colorMap={VERDICT_COLORS} />
      </td>
      <td style={{ padding: '12px', textAlign: 'center' }}>
        <Badge value={pub.freshness_state} colorMap={FRESHNESS_COLORS} />
      </td>
      <td style={{ padding: '12px', textAlign: 'center', fontSize: '13px' }}>
        <CompletenessBar value={pub.completeness_pct} />
      </td>
      <td style={{ padding: '12px', textAlign: 'center', fontSize: '13px' }}>
        {pub.source_count || 0}
      </td>
      <td style={{ padding: '12px', fontSize: '11px', color: '#666' }}>
        {formatAssessedAt(pub.assessed_at)}
      </td>
      <td style={{ padding: '12px', textAlign: 'center', fontSize: '12px' }}>
        <Link href={lineageHref} data-testid={`lineage-link-${pub.publication_key}`}>
          Lineage
        </Link>
      </td>
    </tr>
  );
}

export default function ConfidencePage() {
  const [user, setUser] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [staleOnly, setStaleOnly] = useState(false);
  const [verdictFilter, setVerdictFilter] = useState('');
  const router = useRouter();

  useEffect(() => {
    const loadData = async () => {
      try {
        const meResponse = await fetch('/auth/me');
        if (!meResponse.ok) { router.push('/login'); return; }
        const mePayload = await meResponse.json();
        const currentUser = mePayload?.user;
        if (!currentUser || currentUser.role === 'reader') {
          router.push('/');
          return;
        }
        setUser(currentUser);

        const params = new URLSearchParams();
        if (staleOnly) params.set('stale_only', 'true');
        if (verdictFilter) params.set('verdict', verdictFilter);
        const query = params.toString();
        const response = await fetch(
          `/api/control/confidence${query ? `?${query}` : ''}`
        );
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        const result = await response.json();
        setData(result);
      } catch (err) {
        setError(err.message);
      }
    };
    loadData();
  }, [router, staleOnly, verdictFilter]);

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
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
              gap: '12px',
            }}
          >
            {data.domain_summaries.map((domain) => (
              <DomainCard
                key={domain.domain}
                domain={domain.domain}
                count={domain.count}
                verdict={domain.verdict}
                degradedCount={domain.degraded_count}
                staleCount={domain.stale_count}
              />
            ))}
          </div>
        </div>

        <div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '16px',
            }}
          >
            <h2 style={{ margin: '0', fontSize: '20px' }}>Publications</h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '13px',
                }}
              >
                <input
                  type="checkbox"
                  checked={staleOnly}
                  onChange={(e) => setStaleOnly(e.target.checked)}
                />
                Stale only
              </label>
              <select
                value={verdictFilter}
                onChange={(e) => setVerdictFilter(e.target.value)}
                style={{
                  minWidth: '160px',
                  padding: '8px 10px',
                  border: '1px solid #d0d5dd',
                  borderRadius: '6px',
                }}
                aria-label="Verdict filter"
              >
                <option value="">All verdicts</option>
                <option value="trustworthy">Trustworthy</option>
                <option value="degraded">Degraded</option>
                <option value="unreliable">Unreliable</option>
                <option value="unavailable">Unavailable</option>
              </select>
            </div>
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e0e0e0', backgroundColor: '#f9f9f9' }}>
                <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600' }}>
                  Publication
                </th>
                <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600' }}>Domain</th>
                <th style={{ padding: '12px', textAlign: 'center', fontWeight: '600' }}>Verdict</th>
                <th style={{ padding: '12px', textAlign: 'center', fontWeight: '600' }}>
                  Freshness
                </th>
                <th style={{ padding: '12px', textAlign: 'center', fontWeight: '600' }}>
                  Complete
                </th>
                <th style={{ padding: '12px', textAlign: 'center', fontWeight: '600' }}>Sources</th>
                <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600' }}>Assessed</th>
                <th style={{ padding: '12px', textAlign: 'center', fontWeight: '600' }}>Lineage</th>
              </tr>
            </thead>
            <tbody>
              {data.publications.length > 0 ? (
                data.publications.map((pub) => (
                  <PublicationRow
                    key={pub.publication_key}
                    pub={pub}
                  />
                ))
              ) : (
                <tr>
                  <td colSpan="8" style={{ padding: '24px', textAlign: 'center', color: '#666' }}>
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
