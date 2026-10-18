import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { ControlNav } from "@/components/control-nav";
import { StatePanel } from "@/components/state-panel";
import { getCurrentUser, getPublicationKeys, getPublicationLineage } from "@/lib/backend";

// Server component (ADR web-surface-shell-decision §4.3). The previous
// client version fetched /auth/me and /api/lineage from the browser, which
// nothing routes to the API in split-origin deployments, so it bounced to
// /login. Reads now go through lib/backend.ts like every other page.

const NODE_LABELS = {
  publication: "Publication",
  run: "Run",
  relation: "Relation",
  source: "Source",
};

const NODE_ORDER = ["source", "run", "relation", "publication"];

const EDGE_LABELS = {
  sources: "sources",
  produces: "produces",
  publishes: "publishes",
};

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
  if (!attrs || Object.keys(attrs).length === 0) return "";
  return Object.entries(attrs)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([key, value]) => `${key}=${value}`)
    .join(", ");
}

function isRedirect(error) {
  return Boolean(
    error && typeof error === "object" && "digest" in error && String(error.digest).startsWith("NEXT_REDIRECT")
  );
}

export default async function LineagePage({ searchParams }) {
  const publicationKey = typeof searchParams?.publication_key === "string" ? searchParams.publication_key : "";
  const user = await getCurrentUser();

  let keys = [];
  try {
    keys = (await getPublicationKeys()).map((row) => row.publication_key).filter(Boolean);
  } catch (error) {
    if (isRedirect(error)) throw error;
  }

  let graph = null;
  let loadError = null;
  if (publicationKey) {
    try {
      graph = await getPublicationLineage(publicationKey);
    } catch (error) {
      if (isRedirect(error)) throw error;
      loadError = error instanceof Error ? error.message : String(error);
    }
  }

  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];
  const grouped = groupNodes(nodes);
  const edgesByFrom = indexEdgesByFrom(edges);
  const onlyRoot = nodes.length <= 1 && edges.length === 0;

  return (
    <AppShell
      currentPath="/control/lineage"
      user={user}
      title="Publication lineage"
      eyebrow="Admin control plane"
      lede="Trace a publication back through relations and runs to the sources it was built from."
    >
      <ControlNav currentPath="/control/lineage" />

      <section className="panel section lineagePickerPanel">
        <form className="lineagePicker" action="/control/lineage" method="get">
          <label htmlFor="lineage-publication">Publication</label>
          <input
            id="lineage-publication"
            name="publication_key"
            list="lineage-publication-keys"
            defaultValue={publicationKey}
            placeholder="mart_monthly_cashflow"
            autoComplete="off"
          />
          <datalist id="lineage-publication-keys">
            {keys.map((key) => (
              <option key={key} value={key} />
            ))}
          </datalist>
          <button className="primaryButton" type="submit">
            Show lineage
          </button>
        </form>
      </section>

      {!publicationKey ? (
        <StatePanel tone="empty" title="Pick a publication to trace">
          <p>Choose a publication above to see the source-to-publication chain behind it.</p>
        </StatePanel>
      ) : loadError ? (
        <StatePanel tone="error" title="Couldn't load the lineage graph">
          <p>{loadError}</p>
        </StatePanel>
      ) : (
        <section className="panel section" aria-labelledby="lineage-heading">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">
                {nodes.length} node{nodes.length === 1 ? "" : "s"}, {edges.length} edge{edges.length === 1 ? "" : "s"}
              </div>
              <h2 id="lineage-heading">
                <code>{publicationKey}</code>
              </h2>
            </div>
            <Link className="inlineLink" href="/control/confidence">
              Publication confidence
            </Link>
          </div>
          {onlyRoot ? (
            <StatePanel tone="empty" compact title="No lineage recorded yet">
              <p>
                The graph only has the publication itself: no run has recorded which relations and
                sources fed it in this deployment yet.
              </p>
            </StatePanel>
          ) : null}
          {NODE_ORDER.map((type) => {
            const typed = grouped[type] || [];
            if (!typed.length) return null;
            return (
              <section key={type} data-testid={`lineage-section-${type}`} className="lineageGroup">
                <h3>
                  {NODE_LABELS[type]}s ({typed.length})
                </h3>
                <ul className="lineageList">
                  {typed.map((node) => (
                    <li key={node.id} data-testid={`lineage-node-${node.id}`} className="lineageNode">
                      <code>{node.id}</code>
                      {formatAttributes(node.attributes) ? (
                        <div className="muted">{formatAttributes(node.attributes)}</div>
                      ) : null}
                      {(edgesByFrom[node.id] || []).length ? (
                        <ul className="lineageEdges">
                          {edgesByFrom[node.id].map((edge, index) => (
                            <li key={`${edge.from}-${edge.to}-${edge.type}-${index}`} data-testid={`lineage-edge-${edge.type}`}>
                              {EDGE_LABELS[edge.type] || edge.type} <code>{edge.to}</code>
                              {formatAttributes(edge.attributes) ? ` (${formatAttributes(edge.attributes)})` : ""}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </section>
      )}
    </AppShell>
  );
}
