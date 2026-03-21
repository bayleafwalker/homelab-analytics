import { AppShell } from "@/components/app-shell";
import { getCurrentUser, getHaEntities, getHaBridgeStatus } from "@/lib/backend";

function formatTimestamp(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  return isNaN(d) ? ts : d.toLocaleString("en-IE", { dateStyle: "short", timeStyle: "short" });
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

export default async function HomelabPage() {
  const [user, entities, bridge] = await Promise.all([
    getCurrentUser(),
    getHaEntities(),
    getHaBridgeStatus(),
  ]);

  return (
    <AppShell
      currentPath="/homelab"
      user={user}
      title="Homelab"
      eyebrow="Home Assistant Integration"
      lede="Live entity state from Home Assistant via WebSocket subscription."
    >
      <section className="stack">
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

