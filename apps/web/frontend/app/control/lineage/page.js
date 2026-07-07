'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';

import { AppShell } from '@/components/app-shell';
import { ControlNav } from '@/components/control-nav';

const NODE_LABELS = {
  publication: 'Publication',
  run: 'Run',
  relation: 'Relation',
  source: 'Source',
};

const NODE_ORDER = ['source', 'run', 'relation', 'publication'];

const EDGE_LABELS = {
  sources: 'sources',
  produces: 'produces',
  publishes: 'publishes',
};

function LineageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const publicationKey = searchParams.get('publication_key') || '';

  const [user, setUser] = useState(null);
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        const meResponse = await fetch('/auth/me');
        if (!meResponse.ok) {
          router.push('/login');
          return;
        }
        const mePayload = await meResponse.json();
        const currentUser = mePayload?.user;
        if (!currentUser) {
          router.push('/login');
          return;
        }
        setUser(currentUser);

        if (!publicationKey) {
          setGraph({ publication_key: '', nodes: [], edges: [] });
          return;
        }
        const graphResponse = await fetch(
          `/api/lineage/publication/${encodeURIComponent(publicationKey)}`
        );
        if (!graphResponse.ok) {
          throw new Error(`Lineage API returned ${graphResponse.status}`);
        }
        setGraph(await graphResponse.json());
      } catch (err) {
        setError(err.message);
      }
    };
    load();
  }, [router, publicationKey]);

  if (!user || !graph) {
    return (
      <AppShell title="Publication lineage" eyebrow="Operator Access">
        Loading...
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell title="Publication lineage" eyebrow="Operator Access">
        <p style={{ color: '#b71c1c' }}>Error: {error}</p>
      </AppShell>
    );
  }

  const grouped = groupNodes(graph.nodes);
  const edgesByFrom = indexEdgesByFrom(graph.edges);

  return (
    <AppShell
      currentPath="/control"
      user={user}
      title="Publication lineage"
      eyebrow="Operator Access"
    >
      <ControlNav />

      <div style={{ maxWidth: '960px', margin: '0 auto', padding: '20px' }}>
        <h2 style={{ marginTop: 0, fontSize: '20px' }}>
          {publicationKey || 'No publication selected'}
        </h2>
        <p style={{ color: '#666', fontSize: '13px', marginBottom: '24px' }}>
          Nodes: {graph.nodes.length} · Edges: {graph.edges.length}
        </p>

        {!publicationKey && (
          <p style={{ color: '#666' }}>
            Pass{' '}
            <code>?publication_key=&lt;key&gt;</code> to inspect the source-to-publication chain for a specific publication.
          </p>
        )}

        {NODE_ORDER.map((type) => {
          const nodes = grouped[type] || [];
          if (!nodes.length) return null;
          return (
            <section key={type} data-testid={`lineage-section-${type}`} style={{ marginBottom: '24px' }}>
              <h3 style={{ fontSize: '15px', margin: '0 0 8px 0', color: '#333' }}>
                {NODE_LABELS[type]}s ({nodes.length})
              </h3>
              <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                {nodes.map((node) => (
                  <NodeRow
                    key={node.id}
                    node={node}
                    outgoingEdges={edgesByFrom[node.id] || []}
                  />
                ))}
              </ul>
            </section>
          );
        })}

        <p style={{ marginTop: '32px', fontSize: '13px' }}>
          <Link href="/control/confidence">← Back to publication confidence</Link>
        </p>
      </div>
    </AppShell>
  );
}

function NodeRow({ node, outgoingEdges }) {
  return (
    <li
      data-testid={`lineage-node-${node.id}`}
      style={{
        border: '1px solid #e0e0e0',
        borderRadius: '6px',
        padding: '10px 14px',
        marginBottom: '6px',
        fontSize: '13px',
        backgroundColor: '#fafafa',
      }}
    >
      <div style={{ fontFamily: 'monospace', fontWeight: 600 }}>{node.id}</div>
      <div style={{ color: '#666', fontSize: '12px', marginTop: '4px' }}>
        {formatAttributes(node.attributes)}
      </div>
      {outgoingEdges.length > 0 && (
        <ul style={{ listStyle: 'none', margin: '8px 0 0 0', padding: 0 }}>
          {outgoingEdges.map((edge, idx) => (
            <li
              key={`${edge.from}-${edge.to}-${edge.type}-${idx}`}
              style={{ color: '#444', fontSize: '12px', marginLeft: '12px' }}
              data-testid={`lineage-edge-${edge.type}`}
            >
              → {EDGE_LABELS[edge.type] || edge.type} → <code>{edge.to}</code>
              {formatEdgeAttributes(edge.attributes)}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

function groupNodes(nodes) {
  const groups = {};
  for (const node of nodes) {
    if (!groups[node.type]) groups[node.type] = [];
    groups[node.type].push(node);
  }
  return groups;
}

function indexEdgesByFrom(edges) {
  const idx = {};
  for (const edge of edges) {
    if (!idx[edge.from]) idx[edge.from] = [];
    idx[edge.from].push(edge);
  }
  return idx;
}

function formatAttributes(attrs) {
  if (!attrs || Object.keys(attrs).length === 0) return '';
  const parts = Object.entries(attrs)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value]) => `${key}=${value}`);
  return parts.join(' · ');
}

function formatEdgeAttributes(attrs) {
  const formatted = formatAttributes(attrs);
  return formatted ? ` (${formatted})` : '';
}

export default function LineagePage() {
  return (
    <Suspense
      fallback={
        <AppShell title="Publication lineage" eyebrow="Operator Access">
          Loading...
        </AppShell>
      }
    >
      <LineageContent />
    </Suspense>
  );
}
