import Link from "next/link";
import { redirect } from "next/navigation";

import { RetroShell } from "@/components/retro-shell";
import { describeRule } from "@/components/policy-rule-summary";
import {
  getCurrentUser,
  getHaPolicyEvaluation,
  getPolicyDefinitions
} from "@/lib/backend";

/**
 * Retro policy view — read-only by design.
 *
 * The retro shell mirrors what the classic surfaces show rather than
 * duplicating how they are edited: its catalog page carries no mutation forms
 * at all. Policy authoring stays in the classic shell, where the rule-kind
 * form, publication picker and preview live. Verdicts, reasons and authority
 * mode are worth mirroring, because they are what an operator monitors.
 */
export default async function RetroControlPoliciesPage() {
  const user = await getCurrentUser();
  if (user.role !== "admin") {
    redirect("/retro");
  }

  const [definitions, evaluation] = await Promise.all([
    getPolicyDefinitions(),
    getHaPolicyEvaluation()
  ]);

  const resultById = new Map(evaluation.policies.map((result) => [result.id, result]));
  const definitionIds = new Set(definitions.map((definition) => definition.policy_id));
  const builtinResults = evaluation.policies.filter(
    (result) => !definitionIds.has(result.id)
  );
  const authority = evaluation.authority;
  const breachCount = evaluation.policies.filter(
    (result) => result.verdict === "breach"
  ).length;
  const unavailableCount = evaluation.policies.filter(
    (result) => result.verdict === "unavailable"
  ).length;

  return (
    <RetroShell
      currentPath="/retro/control/policies"
      user={user}
      title="CRT Control / Policies"
      eyebrow="Admin GUI"
      lede="Policy verdicts with the comparison behind each one, over the same evaluation API the classic interface reads. Authoring lives in the classic shell."
    >
      <section className="retroMetricGrid">
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Operator Policies</span>
          <strong>{definitions.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Built-ins</span>
          <strong>{builtinResults.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Breaching</span>
          <strong>{breachCount}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Unavailable</span>
          <strong>{unavailableCount}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Authority</span>
          <strong>{authority ? authority.mode : "not evaluating"}</strong>
        </article>
      </section>

      {authority && authority.mode !== "registry" ? (
        <article className="retroPanel">
          <div className="retroEyebrow">Degraded authority</div>
          <p>
            Effective mode is {authority.mode}. Policy changes made in the
            classic shell will not take effect until the registry is reachable
            again.
            {authority.last_error ? ` Last error: ${authority.last_error}` : ""}
          </p>
        </article>
      ) : null}

      <section className="retroSplit">
        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Registry</div>
              <h2>Operator-authored policies</h2>
            </div>
            <Link className="retroActionLink" href="/control/policies">
              Classic policies
            </Link>
          </div>
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>Policy</th>
                  <th>State</th>
                  <th>Verdict</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {definitions.slice(0, 12).map((definition) => {
                  const result = resultById.get(definition.policy_id);
                  return (
                    <tr key={definition.policy_id}>
                      <td>
                        {definition.display_name}
                        <div className="retroEyebrow">
                          {describeRule(definition.rule_document).summary}
                        </div>
                      </td>
                      <td>{definition.enabled ? "enabled" : "disabled"}</td>
                      <td>{result ? result.verdict : "not evaluated"}</td>
                      <td>{result?.reason || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </article>

        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Code</div>
              <h2>Built-in policies</h2>
            </div>
          </div>
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>Policy</th>
                  <th>Verdict</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {builtinResults.slice(0, 12).map((result) => (
                  <tr key={result.id}>
                    <td>{result.name}</td>
                    <td>{result.verdict}</td>
                    <td>{result.reason || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </RetroShell>
  );
}
