import { redirect } from "next/navigation";
import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { ControlNav } from "@/components/control-nav";
import { getAuthAuditEvents, getCurrentUser, getLocalUsers } from "@/lib/backend";

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

  const [users, authAuditEvents] = await Promise.all([
    getLocalUsers(),
    getAuthAuditEvents(40)
  ]);
  const notice = noticeCopy(searchParams?.notice);
  const error = errorCopy(searchParams?.error);

  return (
    <AppShell
      currentPath="/control"
      user={user}
      title="Authenticated Control Plane"
      eyebrow="Admin Access"
      lede="Bootstrap local auth is now audited and manageable from the web shell. This page still stays API-backed and intentionally thin."
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
            <div className="metricLabel">Recent auth events</div>
            <div className="metricValue">{authAuditEvents.length}</div>
            <div className="muted">Latest login, logout, and user-management activity.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Control pages</div>
            <div className="metricValue">2</div>
            <div className="muted">
              <Link className="inlineLink" href="/control/catalog">
                Catalog
              </Link>
              {" / "}
              <Link className="inlineLink" href="/control/execution">
                Execution
              </Link>
            </div>
          </article>
        </section>

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
      </section>
    </AppShell>
  );
}
