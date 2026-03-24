import Link from "next/link";
import { redirect } from "next/navigation";

import { RetroShell } from "@/components/retro-shell";
import { ServiceTokenPanel } from "@/components/service-token-panel";
import {
  getAuthAuditEvents,
  getCurrentUser,
  getLocalUsers,
  getOperationalSummary,
  getServiceTokens,
} from "@/lib/backend";

export default async function RetroControlPage() {
  const user = await getCurrentUser();
  if (user.role !== "admin") {
    redirect("/retro");
  }

  const [users, authAuditEvents, serviceTokens, operationalSummary] = await Promise.all([
    getLocalUsers(),
    getAuthAuditEvents(20),
    getServiceTokens({ includeRevoked: true }),
    getOperationalSummary(),
  ]);
  const tokenSummary = operationalSummary.auth?.service_tokens || {
    active: serviceTokens.filter((token) => !token.revoked && !token.expired).length,
    expiring_within_7d: 0,
    used_within_24h: 0,
    never_used: 0,
  };

  return (
    <RetroShell
      currentPath="/retro/control"
      user={user}
      title="CRT Control / Security"
      eyebrow="Admin GUI"
      lede="Security posture, local identities, and service-token lifecycle over the same auth and control-plane APIs used by the classic interface."
    >
      <section className="retroMetricGrid">
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Local Users</span>
          <strong>{users.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Active Tokens</span>
          <strong>{tokenSummary.active}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Expiring / 7d</span>
          <strong>{tokenSummary.expiring_within_7d}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Used / 24h</span>
          <strong>{tokenSummary.used_within_24h}</strong>
        </article>
      </section>

      <section className="retroSplit">
        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Identity Deck</div>
              <h2>Local users</h2>
            </div>
            <Link className="retroActionLink" href="/control">
              Classic editor
            </Link>
          </div>
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Last Login</th>
                </tr>
              </thead>
              <tbody>
                {users.map((managedUser) => (
                  <tr key={managedUser.user_id}>
                    <td>{managedUser.username}</td>
                    <td>{managedUser.role}</td>
                    <td>{managedUser.enabled ? "enabled" : "disabled"}</td>
                    <td>{managedUser.last_login_at || "never"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Audit Feed</div>
              <h2>Recent auth events</h2>
            </div>
          </div>
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Event</th>
                  <th>Actor</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {authAuditEvents.map((event) => (
                  <tr key={event.event_id}>
                    <td>{event.occurred_at}</td>
                    <td>{event.event_type}</td>
                    <td>{event.actor_username || "system"}</td>
                    <td>{event.success ? "ok" : "blocked"}</td>
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
            <div className="retroEyebrow">Automation Access</div>
            <h2>Service tokens</h2>
          </div>
          <Link className="retroActionLink" href="/retro/terminal">
            Terminal
          </Link>
        </div>
        <ServiceTokenPanel initialTokens={serviceTokens} />
      </article>
    </RetroShell>
  );
}
