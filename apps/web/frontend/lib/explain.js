import { cache } from "react";

import { getPublicationConfidence, getPublicationLineage } from "@/lib/backend";

// Server-side loader for the <Explain> primitive. Reads go through
// lib/backend.ts (ADR web-surface-shell-decision §4.3); nothing here runs in
// the browser. React's request-scoped cache() means a page with six figures
// from the same publication asks the API for its lineage once, and admins
// get one confidence listing per request rather than one call per figure.

function isRedirect(error) {
  return Boolean(
    error && typeof error === "object" && "digest" in error && String(error.digest).startsWith("NEXT_REDIRECT")
  );
}

const lineageFor = cache(async (publicationKey) => {
  try {
    return { graph: await getPublicationLineage(publicationKey), error: null };
  } catch (error) {
    if (isRedirect(error)) throw error;
    return { graph: null, error: error instanceof Error ? error.message : String(error) };
  }
});

// Confidence is an admin control-plane read (/control/confidence); other roles
// never trigger it.
const confidenceIndex = cache(async () => {
  try {
    const payload = await getPublicationConfidence();
    const index = new Map();
    for (const row of payload?.publications || []) {
      if (row?.publication_key) index.set(row.publication_key, row);
    }
    return index;
  } catch (error) {
    if (isRedirect(error)) throw error;
    return null;
  }
});

const NODE_TYPES = ["source", "run", "relation"];

// Collapse a lineage graph into what a person reading one number needs: how
// many sources, runs and relations stand behind it, and the runs themselves.
export function summariseLineage(graph) {
  const nodes = graph?.nodes || [];
  const counts = { source: 0, run: 0, relation: 0 };
  const runs = [];
  const sources = [];
  for (const node of nodes) {
    if (NODE_TYPES.includes(node.type)) counts[node.type] += 1;
    if (node.type === "run") {
      runs.push(node.attributes?.run_id || String(node.id).replace(/^run:/, ""));
    }
    if (node.type === "source") {
      sources.push(node.attributes?.source_system || String(node.id).replace(/^source:/, ""));
    }
  }
  return { counts, runs, sources, recorded: counts.source + counts.run + counts.relation > 0 };
}

/**
 * Load everything an explanation shows for one publication.
 *
 * @param {string} publicationKey reporting publication the figure is read from
 * @param {{ user?: { role?: string } | null, confidence?: object | null }} [options]
 *   `confidence` lets a caller pass a verdict it already has (the morning
 *   brief carries one per line) instead of a second read.
 */
export async function loadExplanation(publicationKey, { user = null, confidence = undefined } = {}) {
  const isAdmin = user?.role === "admin";
  const [lineage, index] = await Promise.all([
    lineageFor(publicationKey),
    confidence === undefined && isAdmin ? confidenceIndex() : Promise.resolve(null),
  ]);
  const row = confidence === undefined ? index?.get(publicationKey) || null : confidence;
  return {
    publicationKey,
    publicationName:
      row?.publication_name && row.publication_name !== publicationKey ? row.publication_name : null,
    lineage: lineage.graph ? summariseLineage(lineage.graph) : null,
    lineageError: lineage.error,
    confidence: row
      ? {
          verdict: row.confidence_verdict || row.verdict || null,
          freshness: row.freshness_state || null,
          completeness: row.completeness_pct ?? null,
          assessedAt: row.assessed_at || null,
        }
      : null,
    canSeeControl: isAdmin,
  };
}
