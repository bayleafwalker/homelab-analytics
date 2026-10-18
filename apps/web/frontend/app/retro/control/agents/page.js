import Link from "next/link";
import { redirect } from "next/navigation";

import { RetroShell } from "@/components/retro-shell";
import {
  getActionProposals,
  getAgentPrincipals,
  getAgentToolCatalog,
  getCurrentUser
} from "@/lib/backend";

/**
 * Retro agents view — a read-only mirror of /control/agents.
 *
 * Like the retro policies page it mirrors what an operator monitors (the
 * pending queue, recent resolutions, the agents observed in the queue and the
 * tool catalog) and carries no approve or dismiss forms: resolving a proposal
 * needs the review card (effect, change preview, evidence trust), which lives
 * in the classic shell.
 */

function lastEvent(proposal) {
  const history = proposal.history || [];
  return history.length ? history[history.length - 1] : null;
}

function resolverLine(proposal) {
  const event = lastEvent(proposal);
  const actor = proposal.resolved_by || event?.actor || "unknown";
  const provider = event?.actor_auth_provider ? ` (${event.actor_auth_provider})` : "";
  return `${actor}${provider}`;
}

export default async function RetroControlAgentsPage() {
  const user = await getCurrentUser();
  // Same audience as the classic page: operators and admins.
  if (user.role !== "admin" && user.role !== "operator") {
    redirect("/retro");
  }

  const [all, principals, tools] = await Promise.all([
    getActionProposals(),
    getAgentPrincipals(),
    getAgentToolCatalog()
  ]);
  const pending = all.filter((proposal) => proposal.status === "pending");
  const resolved = all.filter((proposal) => proposal.status !== "pending");
  const fromAgents = pending.filter((proposal) => proposal.source_kind === "agent").length;
  const draftTools = tools.filter((tool) => tool.effect !== "read").length;

  return (
    <RetroShell
      currentPath="/retro/control/agents"
      user={user}
      title="CRT Control / Agents"
      eyebrow="Operator Access"
      lede="The approval queue agents, the assistant and policies draft into, over the same proposal API the classic interface reads. Review and resolution live in the classic shell."
    >
      <section className="retroMetricGrid">
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Pending</span>
          <strong>{pending.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">From Agents</span>
          <strong>{fromAgents}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Resolved</span>
          <strong>{resolved.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Agents Seen</span>
          <strong>{principals.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Tools</span>
          <strong>
            {tools.length} ({draftTools} draft)
          </strong>
        </article>
      </section>

      <section className="retroSplit">
        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Inbox</div>
              <h2>Pending proposals</h2>
            </div>
            <Link className="retroActionLink" href="/control/agents">
              Review in classic shell
            </Link>
          </div>
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>Proposal</th>
                  <th>Source</th>
                  <th>Adapter</th>
                  <th>Drafted</th>
                </tr>
              </thead>
              <tbody>
                {pending.length === 0 ? (
                  <tr>
                    <td colSpan={4}>Nothing waiting for a decision.</td>
                  </tr>
                ) : (
                  pending.slice(0, 12).map((proposal) => (
                    <tr key={proposal.action_id}>
                      <td>
                        <Link href={`/control/agents#${proposal.action_id}`}>
                          {proposal.policy_name}
                        </Link>
                        <div className="retroEyebrow">origin {proposal.policy_id}</div>
                      </td>
                      <td>{proposal.source_kind}</td>
                      <td>{proposal.adapter}</td>
                      <td>
                        {proposal.created_by || "unknown"}
                        <div className="retroEyebrow">{proposal.created_at}</div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">History</div>
              <h2>Recent resolutions</h2>
            </div>
            <Link className="retroActionLink" href="/control/agents?view=history">
              Full history
            </Link>
          </div>
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>Proposal</th>
                  <th>Status</th>
                  <th>Resolved by</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {resolved.slice(0, 12).map((proposal) => (
                  <tr key={proposal.action_id}>
                    <td>{proposal.policy_name}</td>
                    <td>{proposal.status}</td>
                    <td>{resolverLine(proposal)}</td>
                    <td>{proposal.resolution_reason || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>

      <article className="retroPanel">
        <div className="retroSectionHeader">
          <div>
            <div className="retroEyebrow">Observed, not registered</div>
            <h2>Agents in the queue</h2>
          </div>
        </div>
        <div className="retroTableWrap">
          <table className="retroTable">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Origin</th>
                <th>Proposals</th>
                <th>Last seen</th>
              </tr>
            </thead>
            <tbody>
              {principals.slice(0, 12).map((principal) => (
                <tr key={`${principal.created_by}-${principal.origin}`}>
                  <td>
                    {principal.created_by}
                    <div className="retroEyebrow">{principal.source_kind}</div>
                  </td>
                  <td>{principal.origin}</td>
                  <td>
                    {principal.pending} pending · {principal.approved} approved ·{" "}
                    {principal.dismissed} rejected
                  </td>
                  <td>{principal.last_seen_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>
    </RetroShell>
  );
}
