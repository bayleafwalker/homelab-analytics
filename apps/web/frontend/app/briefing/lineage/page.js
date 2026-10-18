import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { Eyebrow } from "@/components/eyebrow";
import { NumMono } from "@/components/num-mono";
import { Pill } from "@/components/pill";
import { getCurrentUser, getPublicationLineage } from "@/lib/backend";

import styles from "../briefing.module.css";

// Lineage drill for a morning-brief line: publication → producing runs →
// relations → source systems, rendered server-side from
// GET /api/lineage/publication/{publication_key}. Run nodes link to the run
// detail page, which carries the landing validation outcome.

const NODE_ORDER = ["publication", "relation", "run", "source"];
const NODE_TITLES = {
  publication: "Publication",
  relation: "Relations it was built from",
  run: "Runs that produced it",
  source: "Source systems",
};

function runIdOf(node) {
  return node.attributes?.run_id || node.id.replace(/^run:/, "");
}

function outgoing(edges, nodeId) {
  return edges.filter((edge) => edge.from === nodeId || edge.to === nodeId);
}

function NodeBody({ node, edges }) {
  const attrs = node.attributes || {};
  if (node.type === "run") {
    const runId = runIdOf(node);
    const related = outgoing(edges, node.id);
    return (
      <>
        <Link href={`/runs/${encodeURIComponent(runId)}`} data-testid={`lineage-run-${runId}`}>
          Run {runId}
        </Link>
        {related.map((edge) => (
          <div key={`${edge.type}:${edge.from}:${edge.to}`} className={styles.detail}>
            {edge.type} {edge.from === node.id ? `→ ${edge.to}` : `← ${edge.from}`}
            {edge.attributes?.row_count !== undefined && edge.attributes?.row_count !== null ? (
              <> · <NumMono>{edge.attributes.row_count}</NumMono> rows</>
            ) : null}
            {edge.attributes?.source_run_id ? <> · source run {edge.attributes.source_run_id}</> : null}
            {edge.attributes?.published_at ? <> · published {edge.attributes.published_at}</> : null}
          </div>
        ))}
      </>
    );
  }
  if (node.type === "relation") {
    return (
      <span>
        {attrs.name} <Pill tone="cool">{attrs.layer}</Pill> {attrs.kind}
      </span>
    );
  }
  if (node.type === "source") {
    return <span>{attrs.source_system}</span>;
  }
  return <span>{attrs.key || node.id}</span>;
}

export default async function BriefingLineagePage({ searchParams }) {
  const user = await getCurrentUser();
  const params = await searchParams;
  const publicationKey = typeof params?.publication_key === "string" ? params.publication_key : "";
  const graph = publicationKey
    ? await getPublicationLineage(publicationKey)
    : { publication_key: "", nodes: [], edges: [] };
  const nodes = Array.isArray(graph.nodes) ? graph.nodes : [];
  const edges = Array.isArray(graph.edges) ? graph.edges : [];
  const hasRuns = nodes.some((node) => node.type === "run");

  return (
    <AppShell
      currentPath="/briefing"
      user={user}
      title="Lineage drill"
      eyebrow="Morning brief"
      lede="Which source runs produced the publication behind a brief line."
    >
      <article className={styles.brief}>
        <header className={styles.masthead}>
          <div>
            <Eyebrow>Publication</Eyebrow>
            <p className={styles.headline}>{publicationKey || "No publication selected"}</p>
          </div>
          <div className={styles.meta}>
            <Link href="/briefing">Back to the brief</Link>
          </div>
        </header>

        {!publicationKey ? (
          <p className={styles.summary}>Open this page from a brief line to trace its lineage.</p>
        ) : !hasRuns ? (
          <p className={styles.summary} data-testid="lineage-empty">
            No publication audit or source lineage has been recorded for {publicationKey}. The
            brief withholds claims it cannot trace; run a transformation refresh to record lineage.
          </p>
        ) : (
          <div className={styles.lineageGroups}>
            {NODE_ORDER.map((type) => {
              const group = nodes.filter((node) => node.type === type);
              if (group.length === 0) return null;
              return (
                <section key={type} className={styles.section}>
                  <div className={styles.sectionHeader}>
                    <h2>{NODE_TITLES[type]}</h2>
                    <Pill>{group.length}</Pill>
                  </div>
                  <ul className={styles.nodeList}>
                    {group.map((node) => (
                      <li key={node.id} className={styles.node}>
                        <NodeBody node={node} edges={edges} />
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
          </div>
        )}

        <footer className={styles.footer}>
          Assembled from publication audit and source lineage records in the control plane.
        </footer>
      </article>
    </AppShell>
  );
}
