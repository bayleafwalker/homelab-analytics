import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ControlNav } from "@/components/control-nav";
import { PolicyRuleSummary } from "@/components/policy-rule-summary";
import {
  getCurrentUser,
  getHaPolicyEvaluation,
  getPolicyDefinitions,
} from "@/lib/backend";

export default async function PolicyDetailPage({ params }) {
  const user = await getCurrentUser();
  if (user.role !== "admin") {
    redirect("/");
  }

  const { policyId } = await params;
  const [definitions, evaluation] = await Promise.all([
    getPolicyDefinitions(),
    getHaPolicyEvaluation(),
  ]);
  const definition = definitions.find((item) => item.policy_id === policyId);
  const result = evaluation.policies.find((item) => item.id === policyId);
  if (!definition && !result) {
    notFound();
  }

  const rule = definition?.rule_document;
  const freshness = result?.input_freshness;

  return (
    <AppShell
      currentPath="/control"
      user={user}
      title={definition?.display_name || result?.name || policyId}
    >
      <section className="stack">
        <ControlNav activePath="/control/policies" />
        <Link href="/control/policies">Back to policies</Link>
        {rule ? <PolicyRuleSummary ruleDocument={rule} /> : null}
        <article className="panel section">
          <div className="sectionHeader">
            <h2>Input freshness</h2>
          </div>
          {freshness ? (
            <dl>
              <dt>Input</dt>
              <dd>{rule?.publication_key || "Evaluated input"}</dd>
              <dt>Freshness</dt>
              <dd>{freshness.freshness_state}</dd>
              <dt>Completeness</dt>
              <dd>{freshness.completeness_pct == null ? "Unavailable" : `${freshness.completeness_pct}%`}</dd>
              <dt>Assessed</dt>
              <dd>{freshness.assessed_at || "Unavailable"}</dd>
            </dl>
          ) : (
            <p className="muted">Input freshness is unavailable.</p>
          )}
        </article>
      </section>
    </AppShell>
  );
}
