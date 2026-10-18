import Link from "next/link";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ControlNav } from "@/components/control-nav";
import {
  getActionProposalReview,
  getActionProposals,
  getAgentPrincipals,
  getAgentToolCatalog,
  getCurrentUser
} from "@/lib/backend";
import { MAX_RESOLUTION_REASON_LENGTH } from "@/lib/agent-proposal-resolution";

import styles from "./agents.module.css";

const VIEWS = [
  { key: "inbox", label: "Inbox" },
  { key: "history", label: "History" },
  { key: "agents", label: "Agents" },
  { key: "tools", label: "Tools" }
];

const NOTICE_COPY = {
  "proposal-approved": "Proposal approved. The decision and your reason are in its history.",
  "proposal-dismissed": "Proposal rejected. It cannot be approved afterwards."
};

const ERROR_COPY = {
  "proposal-already-resolved":
    "That proposal was already resolved — someone (or a policy clearing) got there first. Its current state is shown below.",
  "proposal-forbidden":
    "This session cannot resolve proposals. Agents and service tokens can draft but never approve; sign in as an operator.",
  "proposal-missing":
    "That proposal does not exist. Check the link; resolved proposals stay listed under History.",
  "proposal-release-failed":
    "Home Assistant did not accept the approval release, so the proposal stays pending.",
  "proposal-resolution-failed": "Could not resolve the proposal."
};

// Trust guidance → pill tone and plain-language label.
const GUIDANCE = {
  state_as_current: { tone: "ok", label: "evidence current" },
  state_with_caveat: { tone: "warm", label: "evidence caveated" },
  do_not_state_as_current: { tone: "warn", label: "evidence stale" },
  trust_unknown: { tone: "neutral", label: "trust unknown" }
};

const SOURCE_TONES = { agent: "accent", assistant: "cool", policy: "neutral", operator: "neutral" };

function GuidancePill({ guidance }) {
  const resolved = GUIDANCE[guidance] || GUIDANCE.trust_unknown;
  return (
    <span className="pill" data-tone={resolved.tone}>
      {resolved.label}
    </span>
  );
}

function ChangePreview({ rows }) {
  return (
    <div className={styles.diff} role="table" aria-label="What approval changes">
      {rows.map((row) => (
        <div role="row" key={row.field} style={{ display: "contents" }}>
          <span role="rowheader" className={styles.diffLabel}>
            {row.label}
          </span>
          <span
            role="cell"
            className={styles.diffBefore}
            data-changes={row.changes}
            data-empty={row.before == null}
          >
            {row.before ?? "—"}
          </span>
          <span role="cell" className={styles.diffArrow} aria-hidden="true">
            →
          </span>
          <span role="cell" className={styles.diffAfter} data-changes={row.changes}>
            {row.after ?? "—"}
          </span>
        </div>
      ))}
    </div>
  );
}

function trustLine(trust) {
  if (!trust) {
    return "not recorded";
  }
  const parts = [trust.confidence_verdict, trust.freshness_state].filter(Boolean);
  return parts.length ? parts.join(" · ") : "no snapshot";
}

function EvidenceList({ evidence }) {
  if (evidence.length === 0) {
    return <div className="muted">No publications cited.</div>;
  }
  return (
    <div>
      <div className={`${styles.evidenceRow} ${styles.evidenceHead}`}>
        <span>Publication</span>
        <span>At draft</span>
        <span>Now</span>
        <span>Drill down</span>
      </div>
      {evidence.map((item) => (
        <div className={styles.evidenceRow} key={item.publication_key}>
          <div>
            <strong>{item.display_name || item.publication_key}</strong>
            <div className="muted">{item.publication_key}</div>
            {!item.known ? (
              <span className="pill" data-tone="warn">
                not in catalog
              </span>
            ) : null}
          </div>
          <div className="muted">
            {trustLine(item.at_draft)}
            {item.at_draft?.assessed_at ? <div>assessed {item.at_draft.assessed_at}</div> : null}
          </div>
          <div>
            {item.now ? (
              <div className="compactStack">
                <GuidancePill guidance={item.now.guidance} />
                <span className="muted">{trustLine(item.now)}</span>
                {item.now.validation_state || item.now.completeness_state ? (
                  <span className="muted">
                    validation {item.now.validation_state || "unknown"}, completeness{" "}
                    {item.now.completeness_state || "unknown"}
                  </span>
                ) : null}
              </div>
            ) : (
              <span className="muted">—</span>
            )}
          </div>
          <div className={styles.drillLinks}>
            {item.known ? (
              <>
                <Link
                  className="inlineLink"
                  href={`/control/lineage?publication_key=${encodeURIComponent(item.publication_key)}`}
                >
                  Lineage
                </Link>
                <Link className="inlineLink" href="/control/confidence">
                  Confidence
                </Link>
              </>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}

function ProposalMeta({ proposal }) {
  return (
    <div className={styles.metaLine}>
      <span>origin {proposal.policy_id}</span>
      <span>drafted by {proposal.created_by || "unknown"}</span>
      <span>{proposal.created_at}</span>
      <span>{proposal.action_id}</span>
    </div>
  );
}

function ReviewCard({ review }) {
  const { proposal, effect, change_preview: changePreview, evidence, trust } = review;
  return (
    <article className={`entityCard ${styles.reviewCard}`} id={proposal.action_id}>
      <div className="entityHeader">
        <div>
          <strong>{proposal.policy_name}</strong>
          <ProposalMeta proposal={proposal} />
        </div>
        <div className="buttonRow">
          <span className="pill" data-tone={SOURCE_TONES[proposal.source_kind] || "neutral"}>
            {proposal.source_kind}
          </span>
          <GuidancePill guidance={trust.guidance} />
        </div>
      </div>

      {proposal.source_summary ? <p>{proposal.source_summary}</p> : null}

      <div className={styles.effect} data-external={effect.external_effect}>
        <strong>What approval does.</strong> {effect.summary}
      </div>

      <ChangePreview rows={changePreview} />

      <section className="compactStack" aria-label="Evidence">
        <strong>Evidence</strong>
        <EvidenceList evidence={evidence} />
      </section>

      {trust.caveats.length > 0 ? (
        <ul className={styles.caveats} aria-label="Caveats">
          {trust.caveats.map((caveat) => (
            <li key={caveat}>{caveat}</li>
          ))}
        </ul>
      ) : null}

      <form
        className={styles.resolveForm}
        action={`/control/agents/proposals/${encodeURIComponent(proposal.action_id)}/approve`}
        method="post"
      >
        <label className="muted" htmlFor={`reason-${proposal.action_id}`}>
          Reason (recorded in the proposal history; optional)
        </label>
        <textarea
          className={styles.reason}
          id={`reason-${proposal.action_id}`}
          name="reason"
          maxLength={MAX_RESOLUTION_REASON_LENGTH}
          placeholder="Why approve or reject this?"
        />
        <div className="buttonRow">
          <button className="primaryButton" type="submit">
            Approve
          </button>
          <button
            className="ghostButton"
            type="submit"
            formAction={`/control/agents/proposals/${encodeURIComponent(proposal.action_id)}/dismiss`}
          >
            Reject
          </button>
        </div>
      </form>
    </article>
  );
}

function HistoryCard({ proposal }) {
  return (
    <article className="entityCard compactStack" id={proposal.action_id}>
      <div className="entityHeader">
        <div>
          <strong>{proposal.policy_name}</strong>
          <ProposalMeta proposal={proposal} />
        </div>
        <span className="pill" data-tone={proposal.status === "approved" ? "ok" : "neutral"}>
          {proposal.status}
        </span>
      </div>
      <ol className={styles.timeline} aria-label="Proposal history">
        {proposal.history.map((event, index) => (
          <li key={`${event.kind}-${index}`}>
            <strong>{event.kind}</strong>
            <span>
              {event.at}
              {event.actor ? ` · ${event.actor}` : ""}
              {event.actor_auth_provider ? ` (${event.actor_auth_provider})` : ""}
              {event.reason ? ` — “${event.reason}”` : ""}
            </span>
          </li>
        ))}
      </ol>
    </article>
  );
}

function InboxView({ reviews }) {
  if (reviews.length === 0) {
    return (
      <div className="empty">
        Nothing waiting. Agent, assistant, and policy proposals land here and stay
        pending until an operator decides.
      </div>
    );
  }
  return (
    <div className="entityList">
      {reviews.map((review) => (
        <ReviewCard key={review.proposal.action_id} review={review} />
      ))}
    </div>
  );
}

function HistoryView({ proposals }) {
  if (proposals.length === 0) {
    return <div className="empty">No resolved proposals since the API last started.</div>;
  }
  return (
    <div className="entityList">
      {proposals.map((proposal) => (
        <HistoryCard key={proposal.action_id} proposal={proposal} />
      ))}
    </div>
  );
}

function AgentsView({ principals }) {
  return (
    <div className="stack">
      <div className="muted">
        Identities observed in the proposal queue. This deployment does not register
        agents; identity comes from the authenticated token name (or the declared
        origin when auth is disabled). Manage agent credentials under{" "}
        <Link className="inlineLink" href="/control#service-tokens">
          Service tokens
        </Link>
        .
      </div>
      {principals.length === 0 ? (
        <div className="empty">No agent or assistant has drafted a proposal yet.</div>
      ) : (
        <div className="tableWrap">
          <table className={styles.catalogTable}>
            <thead>
              <tr>
                <th>Identity</th>
                <th>Origin</th>
                <th>Proposals</th>
                <th>Outcomes</th>
                <th>Cited publications</th>
                <th>Last seen</th>
              </tr>
            </thead>
            <tbody>
              {principals.map((principal) => (
                <tr key={`${principal.created_by}-${principal.origin}`}>
                  <td>
                    <strong>{principal.created_by}</strong>
                    <div className="muted">{principal.source_kind}</div>
                  </td>
                  <td>
                    <code>{principal.origin}</code>
                  </td>
                  <td>{principal.proposal_count}</td>
                  <td>
                    {principal.pending} pending · {principal.approved} approved ·{" "}
                    {principal.dismissed} rejected
                  </td>
                  <td>
                    {principal.cited_publications.length
                      ? principal.cited_publications.join(", ")
                      : "none"}
                  </td>
                  <td>{principal.last_seen_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const SCOPE_COPY = {
  catalog: "any publication (semantic index)",
  named: "the named publication",
  cited: "publications the agent cites",
  scenario_engine: "scenario engine baselines",
  none: "no publication data"
};

function ToolsView({ tools }) {
  return (
    <div className="stack">
      <div className="muted">
        The tools the MCP server offers agents, from the same catalog the server
        uses. Read tools never change state; draft tools only enter the approval
        queue or create disabled policy drafts.
      </div>
      <div className="tableWrap">
        <table className={styles.catalogTable}>
          <thead>
            <tr>
              <th>Tool</th>
              <th>Effect</th>
              <th>Reads</th>
              <th>Endpoints</th>
              <th>Token scope</th>
              <th>Vuoro operation</th>
            </tr>
          </thead>
          <tbody>
            {tools.map((tool) => (
              <tr key={tool.name}>
                <td>
                  <strong>{tool.title}</strong>
                  <div>
                    <code>{tool.name}</code>
                  </div>
                </td>
                <td>
                  <span className="pill" data-tone={tool.effect === "read" ? "cool" : "warm"}>
                    {tool.effect}
                  </span>
                </td>
                <td>
                  {SCOPE_COPY[tool.publication_scope] || tool.publication_scope}
                  {tool.publication_note ? (
                    <div className="muted">{tool.publication_note}</div>
                  ) : null}
                </td>
                <td>
                  {tool.endpoints.slice(0, 2).map((endpoint) => (
                    <div key={`${endpoint.method}-${endpoint.path}`}>
                      <code>
                        {endpoint.method} {endpoint.path}
                      </code>
                    </div>
                  ))}
                  {tool.endpoints.length > 2 ? (
                    <div className="muted">+{tool.endpoints.length - 2} more</div>
                  ) : null}
                </td>
                <td>
                  <code>{tool.required_scope}</code>
                  {!tool.token_reachable ? (
                    <div className="warnText">{tool.access_note}</div>
                  ) : null}
                </td>
                <td>
                  <code>{tool.vuoro_operation}</code>
                  <div className="muted">
                    {tool.execution_semantics} · idempotency {tool.idempotency}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default async function ControlAgentsPage({ searchParams }) {
  const user = await getCurrentUser();
  // Operators resolve proposals (control.action_proposals.write); readers
  // and agents never do, so they are sent home.
  if (user.role !== "admin" && user.role !== "operator") {
    redirect("/");
  }
  const view = VIEWS.some((item) => item.key === searchParams?.view)
    ? searchParams.view
    : "inbox";

  const [pending, all, principals, tools] = await Promise.all([
    getActionProposals({ status: "pending" }),
    getActionProposals(),
    getAgentPrincipals(),
    getAgentToolCatalog()
  ]);
  const resolved = all.filter((proposal) => proposal.status !== "pending");
  const reviews =
    view === "inbox"
      ? await Promise.all(pending.map((proposal) => getActionProposalReview(proposal.action_id)))
      : [];
  const staleEvidence = reviews.filter(
    (review) => review.trust.guidance === "do_not_state_as_current"
  ).length;

  const notice = NOTICE_COPY[searchParams?.notice] || "";
  const error = ERROR_COPY[searchParams?.error] || "";

  return (
    <AppShell
      currentPath="/control"
      user={user}
      title="Agents"
      eyebrow="Operator Access"
      lede="Every action an agent, the assistant, or a policy proposes waits here. Each one shows what approval would do, the evidence it rests on and how trustworthy that evidence is now. Nothing runs until an operator decides."
    >
      <section className="stack">
        <ControlNav currentPath="/control/agents" />
        {notice ? <div className="successBanner">{notice}</div> : null}
        {error ? <div className="errorBanner">{error}</div> : null}

        <section className="cards">
          <article className="panel metricCard">
            <div className="metricLabel">Pending</div>
            <div className="metricValue">{pending.length}</div>
            <div className="muted">Waiting for an operator decision.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Resolved</div>
            <div className="metricValue">{resolved.length}</div>
            <div className="muted">Kept in the control plane with their full history.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Agent identities</div>
            <div className="metricValue">{principals.length}</div>
            <div className="muted">Observed in the queue, not registered.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Agent tools</div>
            <div className="metricValue">{tools.length}</div>
            <div className="muted">
              {tools.filter((tool) => tool.effect === "read").length} read ·{" "}
              {tools.filter((tool) => tool.effect === "draft").length} draft
            </div>
          </article>
        </section>

        <nav className={styles.viewNav} aria-label="Agent control views">
          {VIEWS.map((item) => (
            <Link
              key={item.key}
              className={styles.viewLink}
              data-active={item.key === view}
              href={item.key === "inbox" ? "/control/agents" : `/control/agents?view=${item.key}`}
            >
              {item.label}
              {item.key === "inbox" && pending.length ? ` (${pending.length})` : ""}
            </Link>
          ))}
        </nav>

        <section className={`panel stack ${styles.viewBody}`}>
          {view === "inbox" && staleEvidence > 0 ? (
            <div className="errorBanner">
              {staleEvidence} pending proposal{staleEvidence === 1 ? "" : "s"} cite evidence
              that is stale or unreliable now. Check the evidence before approving.
            </div>
          ) : null}
          {view === "inbox" ? <InboxView reviews={reviews} /> : null}
          {view === "history" ? <HistoryView proposals={resolved} /> : null}
          {view === "agents" ? <AgentsView principals={principals} /> : null}
          {view === "tools" ? <ToolsView tools={tools} /> : null}
        </section>
      </section>
    </AppShell>
  );
}
