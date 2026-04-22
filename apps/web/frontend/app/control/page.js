import { redirect } from "next/navigation";
import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { ControlNav } from "@/components/control-nav";
import { ServiceTokenPanel } from "@/components/service-token-panel";
import {
  getAuthAuditEvents,
  getCurrentUser,
  getLocalUsers,
  getOperationalSummary,
  getPublicationAudit,
  getServiceTokens,
  getTerminalCommands,
} from "@/lib/backend";

function noticeCopy(notice) {
  switch (notice) {
    case "user-created":
      return "User created.";
    case "user-updated":
      return "User updated.";
    case "password-reset":
      return "Password reset.";
    default:
      return "";
  }
}

function errorCopy(error) {
  switch (error) {
    case "create-failed":
      return "Could not create the user.";
    case "update-failed":
      return "Could not update the user.";
    case "password-reset-failed":
      return "Could not reset the password.";
    default:
      return "";
  }
}

export default async function ControlPage({ searchParams }) {
  const user = await getCurrentUser();
  if (user.role !== "admin") {
    redirect("/");
  }

  const [users, authAuditEvents, serviceTokens, operationalSummary, publicationAuditSummary, terminalCommands] = await Promise.all([
    getLocalUsers(),
    getAuthAuditEvents(40),
    getServiceTokens({ includeRevoked: true }),
    getOperationalSummary(),
    getPublicationAudit({ summary: true }),
    getTerminalCommands(),
  ]);
  const tokenSummary = operationalSummary.auth?.service_tokens || {
    active: serviceTokens.filter((token) => !token.revoked && !token.expired).length,
    expiring_within_7d: 0,
    used_within_24h: 0,
    never_used: 0
  };
  const tokenAuditSummary = operationalSummary.auth?.audit || {
    service_token_events_last_7d: 0,
    service_token_event_counts: {}
  };
  const notice = noticeCopy(searchParams?.notice);
  const error = errorCopy(searchParams?.error);

  return (
    <AppShell
      currentPath="/control"
      user={user}
      title="Authenticated Control Plane"
      eyebrow="Admin Access"
      lede="Shared deployments should prefer OIDC. Local auth stays available as an explicit break-glass path, and this page remains API-backed and intentionally thin."
    >
      <section className="stack">
        <ControlNav currentPath="/control" />
        {notice ? <div className="successBanner">{notice}</div> : null}
        {error ? <div className="errorBanner">{error}</div> : null}

        <section className="cards">
          <article className="panel metricCard">
            <div className="metricLabel">Local users</div>
            <div className="metricValue">{users.length}</div>
            <div className="muted">Bootstrap auth identities under admin control.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Active tokens</div>
            <div className="metricValue">{tokenSummary.active}</div>
            <div className="muted">Scoped automation credentials currently usable.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Expiring in 7d</div>
            <div className="metricValue">{tokenSummary.expiring_within_7d}</div>
            <div className="muted">Tokens that should be rotated before they go hard-expired.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Used in 24h</div>
            <div className="metricValue">{tokenSummary.used_within_24h}</div>
            <div className="muted">Automation credentials with recent activity.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Token audit events</div>
            <div className="metricValue">{tokenAuditSummary.service_token_events_last_7d}</div>
            <div className="muted">Create, revoke, and failed-token events seen in the last 7 days.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Reporting backend</div>
            <div className="metricValue">{operationalSummary.reporting_mode_label || "—"}</div>
            <div className="muted">
              {operationalSummary.reporting_mode === "postgres"
                ? "Published mode — reporting reads from Postgres marts."
                : operationalSummary.reporting_mode === "duckdb"
                  ? "Warehouse mode — reporting reads directly from DuckDB."
                  : null}
            </div>
          </article>
        </section>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Automation Access</div>
              <h2>Service tokens</h2>
            </div>
            <div className="muted">
              <Link className="inlineLink" href="/control/catalog">
                Catalog
              </Link>
              {" / "}
              <Link className="inlineLink" href="/control/execution">
                Execution
              </Link>
            </div>
          </div>
          <div className="metaGrid">
            <div className="metaItem">
              <div className="metricLabel">Never used</div>
              <div>{tokenSummary.never_used}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Created / revoked / failed</div>
              <div className="muted">
                {(tokenAuditSummary.service_token_event_counts?.service_token_created || 0)}
                {" / "}
                {(tokenAuditSummary.service_token_event_counts?.service_token_revoked || 0)}
                {" / "}
                {(tokenAuditSummary.service_token_event_counts?.service_token_auth_failed || 0)}
              </div>
            </div>
          </div>
          <ServiceTokenPanel initialTokens={serviceTokens} />
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Bootstrap Admin</div>
              <h2>Create local user</h2>
            </div>
          </div>
          <form className="adminFormGrid" action="/control/users" method="post">
            <div className="field">
              <label htmlFor="new-username">Username</label>
              <input id="new-username" name="username" type="text" required />
            </div>
            <div className="field">
              <label htmlFor="new-password">Password</label>
              <input id="new-password" name="password" type="password" required />
            </div>
            <div className="field">
              <label htmlFor="new-role">Role</label>
              <select id="new-role" name="role" defaultValue="reader">
                <option value="reader">reader</option>
                <option value="operator">operator</option>
                <option value="admin">admin</option>
              </select>
            </div>
            <button className="primaryButton inlineButton" type="submit">
              Create user
            </button>
          </form>
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">User Management</div>
              <h2>Local users</h2>
            </div>
          </div>
          {users.length === 0 ? (
            <div className="empty">No local users found.</div>
          ) : (
            <div className="stack">
              {users.map((managedUser) => (
                <section className="adminCard" key={managedUser.user_id}>
                  <div className="adminCardHeader">
                    <div>
                      <div className="metricLabel">{managedUser.username}</div>
                      <div className="muted">
                        {managedUser.user_id} / created {managedUser.created_at}
                      </div>
                    </div>
                    <span className="userBadge">
                      {managedUser.role} / {managedUser.enabled ? "enabled" : "disabled"}
                    </span>
                  </div>
                  <div className="adminActions">
                    <form
                      className="adminFormGrid compactForm"
                      action={`/control/users/${managedUser.user_id}`}
                      method="post"
                    >
                      <div className="field">
                        <label htmlFor={`role-${managedUser.user_id}`}>Role</label>
                        <select
                          id={`role-${managedUser.user_id}`}
                          name="role"
                          defaultValue={managedUser.role}
                        >
                          <option value="reader">reader</option>
                          <option value="operator">operator</option>
                          <option value="admin">admin</option>
                        </select>
                      </div>
                      <div className="field">
                        <label htmlFor={`enabled-${managedUser.user_id}`}>Status</label>
                        <select
                          id={`enabled-${managedUser.user_id}`}
                          name="enabled"
                          defaultValue={String(managedUser.enabled)}
                        >
                          <option value="true">enabled</option>
                          <option value="false">disabled</option>
                        </select>
                      </div>
                      <button className="ghostButton inlineButton" type="submit">
                        Save access
                      </button>
                    </form>

                    <form
                      className="adminFormGrid compactForm"
                      action={`/control/users/${managedUser.user_id}/password`}
                      method="post"
                    >
                      <div className="field">
                        <label htmlFor={`password-${managedUser.user_id}`}>New password</label>
                        <input
                          id={`password-${managedUser.user_id}`}
                          name="password"
                          type="password"
                          required
                        />
                      </div>
                      <button className="ghostButton inlineButton" type="submit">
                        Reset password
                      </button>
                    </form>
                  </div>
                </section>
              ))}
            </div>
          )}
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Security Audit</div>
              <h2>Recent auth events</h2>
            </div>
          </div>
          {authAuditEvents.length === 0 ? (
            <div className="empty">No auth events recorded yet.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Event</th>
                    <th>Actor</th>
                    <th>Subject</th>
                    <th>Remote</th>
                    <th>Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {authAuditEvents.map((event) => (
                    <tr key={event.event_id}>
                      <td>{event.occurred_at}</td>
                      <td>
                        <span className={`statusPill ${event.success ? "status-landed" : "status-rejected"}`}>
                          {event.event_type}
                        </span>
                      </td>
                      <td>{event.actor_username || "system"}</td>
                      <td>{event.subject_username || event.subject_user_id || "n/a"}</td>
                      <td>{event.remote_addr || "n/a"}</td>
                      <td>{event.detail || "n/a"}</td>
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
              <div className="eyebrow">Data Integrity</div>
              <h2>Publication audit</h2>
            </div>
          </div>
          {publicationAuditSummary.length === 0 ? (
            <p className="muted">No audit records yet.</p>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Publication</th>
                    <th>Last run</th>
                    <th>Published at</th>
                  </tr>
                </thead>
                <tbody>
                  {publicationAuditSummary.map((record) => (
                    <tr key={record.publication_key}>
                      <td>{record.publication_key}</td>
                      <td>{record.run_id || "n/a"}</td>
                      <td>{record.published_at || "n/a"}</td>
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
              <div className="eyebrow">Operator Tools</div>
              <h2>Terminal command library</h2>
            </div>
            <Link className="ghostButton" href="/retro/terminal">
              Open terminal
            </Link>
          </div>
          <div className="muted" style={{ marginBottom: "12px" }}>
            Allowlisted read-only and narrow mutating commands available via the retro terminal. No shell access or arbitrary execution.
          </div>
          {terminalCommands.length === 0 ? (
            <div className="empty">No terminal commands registered.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Command</th>
                    <th>Description</th>
                    <th>Kind</th>
                  </tr>
                </thead>
                <tbody>
                  {terminalCommands.map((cmd) => (
                    <tr key={cmd.name}>
                      <td>
                        <code style={{ fontFamily: "monospace", fontSize: "0.85rem" }}>
                          {cmd.usage}
                        </code>
                      </td>
                      <td>{cmd.description}</td>
                      <td>
                        <span className={`statusPill ${cmd.mutating ? "status-pending" : "status-landed"}`}>
                          {cmd.mutating ? "mutating" : "read-only"}
                        </span>
                      </td>
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
