import Link from "next/link";

import { RetroShell } from "@/components/retro-shell";
import {
  getCurrentUser,
  getHaActionProposals,
  getHaActions,
  getHaActionsStatus,
  getHaBridgeStatus,
  getHaEntities,
  getHaMqttStatus,
  getHaPolicies,
} from "@/lib/backend";
import { getWebRendererDiscovery } from "@/lib/renderer-discovery";

function formatTimestamp(value) {
  if (!value) {
    return "—";
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString("en-IE", { dateStyle: "short", timeStyle: "short" });
}

function noticeCopy(notice, actionId) {
  switch (notice) {
    case "approval-approved":
      return actionId ? `Approval ${actionId} approved.` : "Approval approved.";
    case "approval-dismissed":
      return actionId ? `Approval ${actionId} dismissed.` : "Approval dismissed.";
    case "approval-resolution-failed":
      return "Could not resolve the approval request.";
    default:
      return "";
  }
}

const CLASS_LABELS = {
  sensor: "Sensor",
  binary_sensor: "Binary Sensor",
  switch: "Switch",
  light: "Light",
  climate: "Climate",
  cover: "Cover",
  fan: "Fan",
  lock: "Lock",
  media_player: "Media Player",
  other: "Other",
};

export default async function RetroOperationsPage({ searchParams }) {
  const [user, discovery, entities, bridge, mqtt, policies, actions, actionsStatus, proposals] =
    await Promise.all([
      getCurrentUser(),
      getWebRendererDiscovery(),
      getHaEntities(),
      getHaBridgeStatus(),
      getHaMqttStatus(),
      getHaPolicies(),
      getHaActions(),
      getHaActionsStatus(),
      getHaActionProposals(),
  ]);
  const operationDescriptors = discovery.homelab;
  const pendingProposals = proposals.filter((proposal) => proposal.status === "pending");
  const canManageApprovals = user.role === "admin";
  const notice = noticeCopy(searchParams?.notice, searchParams?.action_id);

  return (
    <RetroShell
      currentPath="/retro/operations"
      user={user}
      title="CRT Deck / Operations"
      eyebrow="Retro Detail View"
      lede="Homelab and Home Assistant operational signals rendered inside the retro shell over the existing HA bridge and action-status APIs."
    >
      {notice ? <div className={searchParams?.notice === "approval-resolution-failed" ? "errorBanner" : "successBanner"}>{notice}</div> : null}
      <section className="retroMetricGrid">
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Entities</span>
          <strong>{entities.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Policies</span>
          <strong>{policies.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Actions</span>
          <strong>{actionsStatus.dispatch_count || 0}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">MQTT Entities</span>
          <strong>{mqtt.entity_count || 0}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Bridge</span>
          <strong>{bridge.connected ? "LIVE" : bridge.enabled ? "DOWN" : "OFF"}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Published Views</span>
          <strong>{operationDescriptors.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Approval Queue</span>
          <strong>{actionsStatus.approval_pending_count || 0}</strong>
        </article>
      </section>

      <article className="retroPanel">
        <div className="retroSectionHeader">
          <div>
            <div className="retroEyebrow">Discovery Bus</div>
            <h2>Published homelab views</h2>
          </div>
          <Link className="retroActionLink" href="/homelab">
            Classic homelab
          </Link>
        </div>
        <div className="retroModuleLinks">
          {operationDescriptors.length === 0 ? (
            <div className="retroEmptyState">No published homelab descriptors discovered.</div>
          ) : (
            operationDescriptors.map((descriptor) => (
              <article key={descriptor.key} id={descriptor.anchor} className="retroSubPanel">
                <div className="retroMonoStrong">{descriptor.nav_label}</div>
                <div className="retroMuted">
                  {descriptor.publications.map((publication) => publication.display_name).join(" / ") ||
                    "Published homelab view"}
                </div>
                <Link className="retroActionLink" href={descriptor.nav_path}>
                  Classic route
                </Link>
              </article>
            ))
          )}
        </div>
      </article>

      <section className="retroSplit">
        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">WebSocket Bridge</div>
              <h2>Live subscription</h2>
            </div>
          </div>
          <div className="retroListBlock">
            <div className="retroListRow">
              Status: {bridge.enabled ? (bridge.connected ? "connected" : `reconnecting (${bridge.reconnect_count})`) : "not configured"}
            </div>
            <div className="retroListRow">Last sync: {formatTimestamp(bridge.last_sync_at)}</div>
            <div className="retroListRow">Reconnects: {bridge.reconnect_count || 0}</div>
          </div>
        </article>

        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">MQTT Publisher</div>
              <h2>Published entities</h2>
            </div>
          </div>
          <div className="retroListBlock">
            <div className="retroListRow">Status: {mqtt.enabled ? (mqtt.connected ? "publishing" : "disconnected") : "not configured"}</div>
            <div className="retroListRow">Last publish: {formatTimestamp(mqtt.last_publish_at)}</div>
            <div className="retroListRow">Entities: {mqtt.entity_count}</div>
            <div className="retroListRow">Contract summaries: {mqtt.contract_entity_count}</div>
          </div>
        </article>
      </section>

      <article className="retroPanel">
        <div className="retroSectionHeader">
          <div>
            <div className="retroEyebrow">Approval Queue</div>
            <h2>Pending approvals</h2>
          </div>
        </div>
        <div className="retroListBlock">
          <div className="retroListRow">
            Pending proposals: {actionsStatus.approval_pending_count || 0}
          </div>
          <div className="retroListRow">
            Tracked proposals: {actionsStatus.approval_tracked_count || 0}
          </div>
        </div>
        {pendingProposals.length === 0 ? (
          <div className="retroEmptyState">No pending approval-gated proposals.</div>
        ) : (
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>Policy</th>
                  <th>Verdict</th>
                  <th>Target</th>
                  {canManageApprovals ? <th>Actions</th> : null}
                </tr>
              </thead>
              <tbody>
                {pendingProposals.slice(0, 10).map((proposal) => (
                  <tr key={proposal.action_id}>
                    <td>{proposal.policy_name}</td>
                    <td>{proposal.verdict}</td>
                    <td>
                      {proposal.metadata?.approval_action
                        ? `${proposal.metadata.approval_action.domain}.${proposal.metadata.approval_action.service}`
                        : "—"}
                    </td>
                    {canManageApprovals ? (
                      <td>
                        <div className="buttonRow">
                          <form action={`/retro/operations/actions/proposals/${proposal.action_id}/approve`} method="post">
                            <button className="primaryButton inlineButton" type="submit">
                              Approve
                            </button>
                          </form>
                          <form action={`/retro/operations/actions/proposals/${proposal.action_id}/dismiss`} method="post">
                            <button className="ghostButton inlineButton" type="submit">
                              Dismiss
                            </button>
                          </form>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </article>

      <section className="retroSplit">
        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Policy Evaluation</div>
              <h2>Platform policies</h2>
            </div>
          </div>
          {policies.length === 0 ? (
            <div className="retroEmptyState">No policies evaluated.</div>
          ) : (
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Policy</th>
                    <th>Verdict</th>
                    <th>Value</th>
                    <th>Evaluated</th>
                  </tr>
                </thead>
                <tbody>
                  {policies.slice(0, 12).map((policy) => (
                    <tr key={policy.id}>
                      <td>{policy.name}</td>
                      <td>{policy.verdict}</td>
                      <td>{policy.value ?? "—"}</td>
                      <td>{formatTimestamp(policy.evaluated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>

        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Action Dispatch</div>
              <h2>Outbound actions</h2>
            </div>
          </div>
          {actions.length === 0 ? (
            <div className="retroEmptyState">No outbound actions recorded.</div>
          ) : (
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Policy</th>
                    <th>Action</th>
                    <th>Verdict</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {actions.slice(0, 12).map((action, index) => (
                    <tr key={`${action.timestamp}-${index}`}>
                      <td>{formatTimestamp(action.timestamp)}</td>
                      <td>{action.policy_name}</td>
                      <td>{action.action_type}</td>
                      <td>{action.verdict}</td>
                      <td>{action.result}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>

      <article className="retroPanel">
        <div className="retroSectionHeader">
          <div>
            <div className="retroEyebrow">Entity State</div>
            <h2>HA entities</h2>
          </div>
        </div>
        {entities.length === 0 ? (
          <div className="retroEmptyState">No entities ingested yet.</div>
        ) : (
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>Entity</th>
                  <th>Name</th>
                  <th>Class</th>
                  <th>State</th>
                  <th>Area</th>
                  <th>Last Seen</th>
                </tr>
              </thead>
              <tbody>
                {entities.slice(0, 20).map((entity) => (
                  <tr key={entity.entity_id}>
                    <td>{entity.entity_id}</td>
                    <td>{entity.friendly_name || "—"}</td>
                    <td>{CLASS_LABELS[entity.entity_class] || entity.entity_class}</td>
                    <td>{entity.last_state ?? "—"}</td>
                    <td>{entity.area || "—"}</td>
                    <td>{formatTimestamp(entity.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </article>
    </RetroShell>
  );
}
