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

// Collapse a lineage graph into what a person reading one number needs: the
// chain behind it, mart ← transformation relations ← runs ← source assets ←
// source systems, with counts and names per step. The publication's own
// reporting relation is the figure itself, so it is not counted as an input.
export function summariseLineage(graph) {
  const nodes = graph?.nodes || [];
  const publicationKey = graph?.publication_key || null;
  const counts = { relation: 0, run: 0, asset: 0, source: 0 };
  const runs = [];
  const sources = [];
  const relations = [];
  const assets = [];
  let reportingRecorded = false;
  for (const node of nodes) {
    const attributes = node.attributes || {};
    if (node.type === "run") {
      counts.run += 1;
      runs.push(attributes.run_id || String(node.id).replace(/^run:/, ""));
    } else if (node.type === "source") {
      counts.source += 1;
      sources.push(attributes.source_system || String(node.id).replace(/^source:/, ""));
    } else if (node.type === "relation") {
      if (attributes.layer === "landing") {
        counts.asset += 1;
        assets.push(attributes.name);
      } else if (attributes.layer === "reporting" && (!publicationKey || attributes.name === publicationKey)) {
        reportingRecorded = true;
      } else {
        counts.relation += 1;
        relations.push(attributes.name);
      }
    }
  }
  const recorded = reportingRecorded || Object.values(counts).some((count) => count > 0);
  // The API walks only the most recent runs (run_limit) and says when it cut.
  const truncated = graph?.truncated === true;
  const totalRuns = Number.isFinite(graph?.total_runs) ? graph.total_runs : counts.run;
  return { counts, runs, sources, relations, assets, recorded, truncated, totalRuns };
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
