import { AppShell } from "@/components/app-shell";
import { RendererDiscovery } from "@/components/renderer-discovery";
import { getCurrentUser, getHaActionProposals, getHaEntities, getHaBridgeStatus, getHaMqttStatus, getHaPolicies, getHaActions, getHaActionsStatus } from "@/lib/backend";
import { getWebRendererDiscovery } from "@/lib/renderer-discovery";

function formatTimestamp(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  return isNaN(d) ? ts : d.toLocaleString("en-IE", { dateStyle: "short", timeStyle: "short" });
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

export default async function HomelabPage({ searchParams }) {
  const [user, discovery, entities, bridge, mqtt, policies, actions, actionsStatus, proposals] = await Promise.all([
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
  const pendingProposals = proposals.filter((proposal) => proposal.status === "pending");
  const canManageApprovals = user.role !== "reader";
  const notice = noticeCopy(searchParams?.notice, searchParams?.action_id);

  return (
    <AppShell
      currentPath="/homelab"
      user={user}
      title="Homelab"
      eyebrow="Home Assistant Integration"
      lede="Live entity state from Home Assistant via WebSocket subscription."
    >
      <section className="stack">
        {notice ? <div className={searchParams?.notice === "approval-resolution-failed" ? "errorBanner" : "successBanner"}>{notice}</div> : null}
        <RendererDiscovery
          title="Published homelab views"
          eyebrow="Web renderer discovery"
          descriptors={discovery.homelab}
        />

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">WebSocket Bridge</div>
              <h2>Live Subscription</h2>
            </div>
            {bridge.enabled ? (
              <span className={`statusPill ${bridge.connected ? "positive" : "negative"}`}>
                {bridge.connected ? "Connected" : "Disconnected"}
              </span>
            ) : (
              <span className="statusPill">Not configured</span>
            )}
          </div>
          <dl className="kvGrid">
            <dt>Status</dt>
            <dd>
              {bridge.enabled
                ? bridge.connected
                  ? "Live — receiving state_changed events"
                  : `Reconnecting (attempt ${bridge.reconnect_count})`
                : "Set HOMELAB_ANALYTICS_HA_URL and HOMELAB_ANALYTICS_HA_TOKEN to enable"}
            </dd>
            <dt>Last sync</dt>
            <dd>{formatTimestamp(bridge.last_sync_at)}</dd>
            {bridge.enabled && (
              <>
                <dt>Reconnects</dt>
                <dd>{bridge.reconnect_count}</dd>
              </>
            )}
          </dl>
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">MQTT Publisher</div>
              <h2>Published Entities</h2>
            </div>
            {mqtt.enabled ? (
              <span className={`statusPill ${mqtt.connected ? "positive" : "negative"}`}>
                {mqtt.connected ? "Publishing" : "Disconnected"}
              </span>
            ) : (
              <span className="statusPill">Not configured</span>
            )}
          </div>
          <dl className="kvGrid">
            <dt>Status</dt>
            <dd>
              {mqtt.enabled
                ? mqtt.connected
                  ? `Publishing ${mqtt.entity_count} entities to HA, including ${mqtt.contract_entity_count} contract-backed ${mqtt.contract_entity_count === 1 ? "summary" : "summaries"}`
                  : "Connecting to MQTT broker…"
                : "Set HOMELAB_ANALYTICS_HA_MQTT_BROKER_URL to enable"}
            </dd>
            <dt>Last publish</dt>
            <dd>{formatTimestamp(mqtt.last_publish_at)}</dd>
            {mqtt.enabled && (
              <>
                <dt>Publish count</dt>
                <dd>{mqtt.publish_count}</dd>
                <dt>Entities</dt>
                <dd>{mqtt.entity_count}</dd>
                <dt>Contract summaries</dt>
                <dd>{mqtt.contract_entity_count}</dd>
                <dt>Publications</dt>
                <dd>{mqtt.publication_keys.length}</dd>
              </>
            )}
          </dl>
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Policy Evaluation</div>
              <h2>Platform Policies</h2>
            </div>
            <span className="statusPill">{policies.length} policies</span>
          </div>
          {policies.length === 0 ? (
            <div className="empty">No policies evaluated.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Policy</th>
                    <th>Description</th>
                    <th>Verdict</th>
                    <th>Value</th>
                    <th>Evaluated</th>
                  </tr>
                </thead>
                <tbody>
                  {policies.map((policy) => (
                    <tr key={policy.id}>
                      <td>{policy.name}</td>
                      <td>{policy.description}</td>
                      <td>
                        <span className={`statusPill ${
                          policy.verdict === "ok" ? "positive"
                          : policy.verdict === "breach" ? "negative"
                          : policy.verdict === "warning" ? "warning"
                          : ""
                        }`}>
                          {policy.verdict}
                        </span>
                      </td>
                      <td>{policy.value ?? "—"}</td>
                      <td>{formatTimestamp(policy.evaluated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Action Dispatch</div>
              <h2>Outbound Actions</h2>
            </div>
            {actionsStatus.enabled ? (
              <span className={`statusPill ${actionsStatus.error_count > 0 ? "warning" : "positive"}`}>
                {actionsStatus.dispatch_count} dispatches
              </span>
            ) : (
              <span className="statusPill">Not configured</span>
            )}
          </div>
          <dl className="kvGrid">
            <dt>Status</dt>
            <dd>
              {actionsStatus.enabled
                ? `Tracking ${actionsStatus.tracked_policies} policies`
                : "Set HOMELAB_ANALYTICS_HA_URL and HOMELAB_ANALYTICS_HA_TOKEN to enable"}
            </dd>
            <dt>Last dispatch</dt>
            <dd>{formatTimestamp(actionsStatus.last_dispatch_at)}</dd>
            {actionsStatus.enabled && (
              <>
                <dt>Errors</dt>
                <dd>{actionsStatus.error_count}</dd>
                <dt>Approval queue</dt>
                <dd>
                  {actionsStatus.approval_pending_count} pending / {actionsStatus.approval_tracked_count} tracked
                </dd>
              </>
            )}
          </dl>
          {actions.length > 0 && (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Policy</th>
                    <th>Class</th>
                    <th>Type</th>
                    <th>Verdict</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {actions.map((action, idx) => (
                    <tr key={`${action.timestamp}-${idx}`}>
                      <td>{formatTimestamp(action.timestamp)}</td>
                      <td>{action.policy_name}</td>
                      <td><span className="statusPill">{action.action_class}</span></td>
                      <td><code className="mono">{action.action_type}</code></td>
                      <td>
                        <span className={`statusPill ${
                          action.verdict === "ok" ? "positive"
                          : action.verdict === "breach" ? "negative"
                          : action.verdict === "warning" ? "warning"
                          : ""
                        }`}>
                          {action.previous_verdict ?? "—"} → {action.verdict}
                        </span>
                      </td>
                      <td>
                        <span className={`statusPill ${
                          action.result === "success" || action.result === "dismissed" || action.result === "approved" ? "positive"
                          : action.result === "failure" ? "negative"
                          : ""
                        }`}>
                          {action.result}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {pendingProposals.length > 0 && (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Policy</th>
                    <th>Verdict</th>
                    <th>Status</th>
                    <th>Target</th>
                    {canManageApprovals ? <th>Actions</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {pendingProposals.map((proposal) => (
                    <tr key={proposal.action_id}>
                      <td>{formatTimestamp(proposal.created_at)}</td>
                      <td>{proposal.policy_name}</td>
                      <td>
                        <span className="statusPill warning">{proposal.verdict}</span>
                      </td>
                      <td>
                        <span className={`statusPill ${proposal.status === "pending" ? "warning" : "positive"}`}>
                          {proposal.status}
                        </span>
                      </td>
                      <td>
                        <code className="mono">
                          {proposal.metadata?.approval_action
                            ? `${proposal.metadata.approval_action.domain}.${proposal.metadata.approval_action.service}`
                            : "—"}
                        </code>
                      </td>
                      {canManageApprovals ? (
                        <td>
                          <div className="buttonRow">
                            <form action={`/homelab/actions/proposals/${proposal.action_id}/approve`} method="post">
                              <button className="primaryButton inlineButton" type="submit">
                                Approve
                              </button>
                            </form>
                            <form action={`/homelab/actions/proposals/${proposal.action_id}/dismiss`} method="post">
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

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Entity State</div>
              <h2>HA Entities</h2>
            </div>
            <span className="statusPill">{entities.length} entities</span>
          </div>

          {entities.length === 0 ? (
            <div className="empty">
              No entities ingested yet. Upload a Home Assistant{" "}
              <code>/api/states</code> export via the{" "}
              <a href="/upload">Upload page</a>.
            </div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Entity ID</th>
                    <th>Friendly Name</th>
                    <th>Class</th>
                    <th>State</th>
                    <th>Unit</th>
                    <th>Area</th>
                    <th>Last Seen</th>
                  </tr>
                </thead>
                <tbody>
                  {entities.map((entity) => (
                    <tr key={entity.entity_id}>
                      <td>
                        <code className="mono">{entity.entity_id}</code>
                      </td>
                      <td>{entity.friendly_name || "—"}</td>
                      <td>
                        <span className="statusPill">
                          {CLASS_LABELS[entity.entity_class] || entity.entity_class}
                        </span>
                      </td>
                      <td>{entity.last_state ?? "—"}</td>
                      <td>{entity.unit || "—"}</td>
                      <td>{entity.area || "—"}</td>
                      <td>{formatTimestamp(entity.last_seen)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>
    </AppShell>
  );
}
