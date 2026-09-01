import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ControlNav } from "@/components/control-nav";
import { PolicyAuthoringPanel } from "@/components/policy-authoring-panel";
import { PolicyForm } from "@/components/policy-form";
import { PolicyRuleSummary } from "@/components/policy-rule-summary";
import {
  getCurrentUser,
  getHaPolicyEvaluation,
  getPolicyDefinitions,
  getReferenceablePublications
} from "@/lib/backend";

function noticeCopy(notice) {
  switch (notice) {
    case "policy-created":
      return "Policy created.";
    case "policy-updated":
      return "Policy updated.";
    case "policy-enabled":
      return "Policy enabled.";
    case "policy-disabled":
      return "Policy disabled.";
    case "policy-deleted":
      return "Policy deleted.";
    default:
      return "";
  }
}

function errorCopy(error) {
  switch (error) {
    case "create-failed":
      return "Could not create the policy. Check the rule against the publication it reads.";
    case "update-failed":
      return "Could not update the policy.";
    case "enable-failed":
      return "Could not enable the policy. Its publication reference is validated again on enable, so a publication that has since been removed will block it.";
    case "disable-failed":
      return "Could not disable the policy.";
    case "delete-failed":
      return "Could not delete the policy.";
    default:
      return "";
  }
}

const VERDICT_TONES = {
  ok: "ok",
  warning: "warm",
  breach: "warn",
  unavailable: "neutral"
};

const AUTHORITY_COPY = {
  registry: {
    tone: "ok",
    label: "registry",
    detail: "Policies are being read live from the control plane."
  },
  snapshot: {
    tone: "warm",
    label: "snapshot",
    detail:
      "Degraded: the registry is unreachable, so the last known good policy set is being evaluated. Changes made here will not take effect until the registry is reachable again."
  },
  unavailable: {
    tone: "warn",
    label: "unavailable",
    detail:
      "No policy set is being evaluated: there is no registry configured, or it is unreachable and no snapshot exists. Verdicts below are stale or absent."
  }
};

function VerdictPill({ verdict }) {
  const resolved = verdict || "unavailable";
  return (
    <span className="pill" data-tone={VERDICT_TONES[resolved] || "neutral"}>
      {resolved}
    </span>
  );
}

/**
 * Latest evaluation result for a policy, or an explicit absence.
 *
 * A policy with no result is not the same as a passing policy, so the two are
 * never rendered alike.
 */
function EvaluationSummary({ result }) {
  if (!result) {
    return (
      <div className="muted">
        Not evaluated in the last cycle — no verdict to show.
      </div>
    );
  }
  return (
    <div className="compactStack">
      <div>
        <VerdictPill verdict={result.verdict} />
        {result.value ? <span className="muted"> observed {result.value}</span> : null}
      </div>
      {result.reason ? <div>{result.reason}</div> : null}
      {result.input_freshness ? (
        <div className="muted">
          Input {result.input_freshness.freshness_state.toLowerCase()},{" "}
          {result.input_freshness.completeness_pct}% complete, assessed{" "}
          {result.input_freshness.assessed_at}
        </div>
      ) : null}
    </div>
  );
}

export default async function ControlPoliciesPage({ searchParams }) {
  const user = await getCurrentUser();
  if (user.role !== "admin") {
    redirect("/");
  }

  const [definitions, evaluation, authoring] = await Promise.all([
    getPolicyDefinitions(),
    getHaPolicyEvaluation(),
    getReferenceablePublications()
  ]);
  const publications = authoring.publications;

  const resultById = new Map(evaluation.policies.map((result) => [result.id, result]));
  const definitionIds = new Set(definitions.map((definition) => definition.policy_id));
  // Results with no registry row behind them are the code built-ins. They are
  // shown so the operator sees every policy that can fire, but they are not
  // editable here — they are defined in code, not in the registry.
  const builtinResults = evaluation.policies.filter(
    (result) => !definitionIds.has(result.id)
  );

  const authority = evaluation.authority;
  const authorityCopy = authority ? AUTHORITY_COPY[authority.mode] : null;
  const enabledCount = definitions.filter((definition) => definition.enabled).length;
  const breachCount = evaluation.policies.filter(
    (result) => result.verdict === "breach"
  ).length;
  const unavailableCount = evaluation.policies.filter(
    (result) => result.verdict === "unavailable"
  ).length;

  const notice = noticeCopy(searchParams?.notice);
  const error = errorCopy(searchParams?.error);

  return (
    <AppShell
      currentPath="/control"
      user={user}
      title="Policies"
      eyebrow="Admin Access"
      lede="Operator-authored rules evaluated against published data. Every verdict states the comparison behind it, and a policy whose input is stale reports unavailable rather than guessing."
    >
      <section className="stack">
        <ControlNav currentPath="/control/policies" />
        {notice ? <div className="successBanner">{notice}</div> : null}
        {error ? <div className="errorBanner">{error}</div> : null}

        {authorityCopy && authority.mode !== "registry" ? (
          <div className="errorBanner">
            <strong>Authority: {authorityCopy.label}.</strong> {authorityCopy.detail}
            {authority.last_error ? ` Last error: ${authority.last_error}` : ""}
          </div>
        ) : null}

        <section className="cards">
          <article className="panel metricCard">
            <div className="metricLabel">Operator policies</div>
            <div className="metricValue">{definitions.length}</div>
            <div className="muted">{enabledCount} enabled.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Built-in policies</div>
            <div className="metricValue">{builtinResults.length}</div>
            <div className="muted">Defined in code, not editable here.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Breaching</div>
            <div className="metricValue">{breachCount}</div>
            <div className="muted">Policies whose condition is currently met.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Unavailable</div>
            <div className="metricValue">{unavailableCount}</div>
            <div className="muted">No confident verdict — see each reason.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Authority mode</div>
            <div className="metricValue">
              {authorityCopy ? (
                <span className="pill" data-tone={authorityCopy.tone}>
                  {authorityCopy.label}
                </span>
              ) : (
                <span className="pill" data-tone="neutral">
                  not evaluating
                </span>
              )}
            </div>
            <div className="muted">
              {authorityCopy
                ? authorityCopy.detail
                : "No policy evaluator is wired into this deployment."}
            </div>
          </article>
        </section>

        <section className="panel stack">
          <div className="sectionHeader">
            <h2>Operator-authored policies</h2>
          </div>
          {definitions.length === 0 ? (
            <div className="empty">
              No operator policies yet. Authored policies are evaluated on every
              cycle alongside the built-ins.
            </div>
          ) : (
            <div className="entityList">
              {definitions.map((definition) => (
                <article className="entityCard" key={definition.policy_id}>
                  <div className="entityHeader">
                    <div>
                      <strong>{definition.display_name}</strong>
                      <div className="muted">{definition.policy_id}</div>
                    </div>
                    <div className="buttonRow">
                      <span className="pill" data-tone="cool">
                        {definition.source_kind}
                      </span>
                      <span
                        className="pill"
                        data-tone={definition.enabled ? "ok" : "neutral"}
                      >
                        {definition.enabled ? "enabled" : "disabled"}
                      </span>
                    </div>
                  </div>
                  {definition.description ? <p>{definition.description}</p> : null}
                  <PolicyRuleSummary ruleDocument={definition.rule_document} />
                  <EvaluationSummary result={resultById.get(definition.policy_id)} />
                  <div className="buttonRow">
                    <form
                      action={`/control/policies/${definition.policy_id}/enabled`}
                      method="post"
                    >
                      <input
                        name="enabled"
                        type="hidden"
                        value={definition.enabled ? "false" : "true"}
                      />
                      <button className="ghostButton" type="submit">
                        {definition.enabled ? "Disable policy" : "Enable policy"}
                      </button>
                    </form>
                    <form
                      action={`/control/policies/${definition.policy_id}/delete`}
                      method="post"
                    >
                      <button className="ghostButton" type="submit">
                        Delete policy
                      </button>
                    </form>
                  </div>
                  <details>
                    <summary>Edit this policy</summary>
                    <PolicyForm
                      publications={publications}
                      ruleSchemaVersion={authoring.ruleSchemaVersion}
                      policy={definition}
                      action={`/control/policies/${definition.policy_id}`}
                      submitLabel="Save changes"
                    />
                  </details>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="panel stack">
          <div className="sectionHeader">
            <h2>Author a policy</h2>
          </div>
          {publications.length === 0 ? (
            <div className="empty">
              No publications are available to reference, so a publication-based
              rule cannot be authored yet.
            </div>
          ) : null}
          <PolicyAuthoringPanel
            publications={publications}
            ruleSchemaVersion={authoring.ruleSchemaVersion}
          />
        </section>

        <section className="panel stack">
          <div className="sectionHeader">
            <h2>Built-in policies</h2>
          </div>
          <p className="muted">
            Defined in code rather than the registry, because none is expressible
            behaviour-identically in the shipped rule kinds. They cannot be
            edited or deleted here, and a registry policy can never take one of
            their ids.
          </p>
          {builtinResults.length === 0 ? (
            <div className="empty">No built-in policy results in the last cycle.</div>
          ) : (
            <div className="entityList">
              {builtinResults.map((result) => (
                <article className="entityCard" key={result.id}>
                  <div className="entityHeader">
                    <div>
                      <strong>{result.name}</strong>
                      <div className="muted">{result.id}</div>
                    </div>
                    <div className="buttonRow">
                      <span className="pill" data-tone="neutral">
                        builtin
                      </span>
                      {result.approval_required ? (
                        <span className="pill" data-tone="accent">
                          approval gated
                        </span>
                      ) : null}
                    </div>
                  </div>
                  {result.description ? <p>{result.description}</p> : null}
                  <EvaluationSummary result={result} />
                </article>
              ))}
            </div>
          )}
        </section>
      </section>
    </AppShell>
  );
}
