import Link from "next/link";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ControlNav } from "@/components/control-nav";
import {
  getCurrentUser,
  getPackCatalog,
  getPackChangePlan,
  getPackHistory
} from "@/lib/backend";
import {
  MAX_PACK_REASON_LENGTH,
  PACK_ACTION_LABELS,
  isPackAction,
  packPlanHref
} from "@/lib/pack-lifecycle";

import styles from "./packs.module.css";

const NOTICE_COPY = {
  "pack-applied": "Change applied. It is recorded in the history below with your reason."
};

const ERROR_COPY = {
  "pack-refused":
    "The change was refused: the platform re-checked it and found a blocking diagnostic. The refusal is in the history; preview the change again to see why.",
  "pack-conflict":
    "The pack changed after the preview was made (someone else acted first). Review the current state and preview again.",
  "pack-invalid": "A lifecycle change needs an action and a reason.",
  "pack-forbidden": "Only admins can change pack lifecycle state.",
  "pack-failed": "Could not apply the change."
};

const COMPATIBILITY = {
  compatible: { tone: "ok", label: "compatible" },
  warning: { tone: "warm", label: "compatible with warnings" },
  incompatible: { tone: "warn", label: "incompatible" }
};

const STATE = {
  not_installed: { tone: "neutral", label: "not installed" },
  enabled: { tone: "ok", label: "enabled" },
  disabled: { tone: "warm", label: "disabled" }
};

const CHANGE_TONES = {
  added: "cool",
  removed: "warn",
  schema_changed: "warm",
  unchanged: "neutral"
};

function CompatibilityPill({ status }) {
  const resolved = COMPATIBILITY[status] || COMPATIBILITY.incompatible;
  return (
    <span className="pill" data-tone={resolved.tone}>
      {resolved.label}
    </span>
  );
}

function StatePill({ state }) {
  const resolved = STATE[state] || STATE.not_installed;
  return (
    <span className="pill" data-tone={resolved.tone}>
      {resolved.label}
    </span>
  );
}

function formatTime(value) {
  if (!value) {
    return "—";
  }
  return new Date(value).toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

/** The lifecycle actions that make sense from a pack's current state. */
function stateActions(pack) {
  const installation = pack.installation;
  if (!installation) {
    return [];
  }
  const actions = [];
  if (installation.previous_version) {
    actions.push({ action: "rollback", version: null });
  }
  actions.push({ action: installation.enabled ? "disable" : "enable", version: null });
  actions.push({ action: installation.pinned_version ? "unpin" : "pin", version: null });
  return actions;
}

function versionAction(pack, row) {
  if (!pack.installation) {
    return "install";
  }
  if (row.relation === "upgrade") {
    return "upgrade";
  }
  return null;
}

function PackCard({ pack }) {
  const installation = pack.installation;
  return (
    <article className={`entityCard ${styles.packCard}`} id={`pack-${pack.pack_key}`}>
      <div className="entityHeader">
        <div>
          <strong>{pack.display_name}</strong>
          <div className="muted">
            <code>{pack.pack_key}</code> · {pack.pack_kind} pack · trust {pack.trust_level}
          </div>
        </div>
        <div className="buttonRow">
          <StatePill state={pack.state} />
          {installation ? (
            <CompatibilityPill status={installation.compatibility_snapshot.status} />
          ) : null}
          {pack.upgrade_available ? (
            <span className="pill" data-tone="accent">
              upgrade available
            </span>
          ) : null}
        </div>
      </div>

      {pack.description ? <p>{pack.description}</p> : null}

      {installation ? (
        <dl className={styles.facts}>
          <dt>Installed</dt>
          <dd>{installation.installed_version}</dd>
          <dt>Rollback target</dt>
          <dd>{installation.previous_version || "—"}</dd>
          <dt>Pinned</dt>
          <dd>{installation.pinned_version || "not pinned"}</dd>
          <dt>Last change</dt>
          <dd>{formatTime(installation.updated_at)}</dd>
        </dl>
      ) : null}
      {installation && !pack.installed_version_cached ? (
        <div className="errorBanner">
          The installed version is no longer in the local registry cache, so it cannot be
          re-verified. Re-sync its registry source before enabling or rolling back.
        </div>
      ) : null}

      <div className="tableWrap">
        <table className={styles.versionTable}>
          <thead>
            <tr>
              <th>Version</th>
              <th>Compatibility</th>
              <th>Publications</th>
              <th>Registry source</th>
              <th>Preview</th>
            </tr>
          </thead>
          <tbody>
            {pack.versions.map((row) => {
              const action = versionAction(pack, row);
              return (
                <tr key={row.version} data-relation={row.relation}>
                  <td>
                    <strong>{row.version}</strong>
                    <div className="muted">{row.relation}</div>
                  </td>
                  <td>
                    <CompatibilityPill status={row.compatibility_status} />
                    {row.issues.length > 0 ? (
                      <ul className={styles.diagnostics}>
                        {row.issues.map((issue) => (
                          <li key={issue}>{issue}</li>
                        ))}
                      </ul>
                    ) : null}
                    {row.warnings.length > 0 ? (
                      <ul className={styles.diagnostics} data-severity="warning">
                        {row.warnings.map((warning) => (
                          <li key={warning}>{warning}</li>
                        ))}
                      </ul>
                    ) : null}
                  </td>
                  <td>
                    {row.publications.length === 0 ? (
                      <span className="muted">none</span>
                    ) : (
                      row.publications.map((publication) => (
                        <div key={publication.publication_key}>
                          <code>{publication.publication_key}</code>{" "}
                          <span className="muted">@{publication.schema_version}</span>
                        </div>
                      ))
                    )}
                  </td>
                  <td>
                    {row.source_name}
                    <div className="muted">
                      <code>{row.extension_registry_revision_id}</code>
                    </div>
                  </td>
                  <td>
                    {action ? (
                      <Link className="ghostButton" href={packPlanHref(pack.pack_key, action, row.version)}>
                        Preview {PACK_ACTION_LABELS[action].toLowerCase()}
                      </Link>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {stateActions(pack).length > 0 ? (
        <div className="buttonRow">
          {stateActions(pack).map(({ action, version }) => (
            <Link
              key={action}
              className="ghostButton"
              href={packPlanHref(pack.pack_key, action, version)}
            >
              Preview {PACK_ACTION_LABELS[action].toLowerCase()}
            </Link>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function PlanPreview({ plan, version }) {
  const blocking = plan.diagnostics.filter((d) => d.severity === "blocking");
  const warnings = plan.diagnostics.filter((d) => d.severity === "warning");
  return (
    <section className={`panel ${styles.planPanel}`} id="plan" aria-label="Dry-run plan">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">Dry run · nothing has changed yet</div>
          <h2>
            {PACK_ACTION_LABELS[plan.action] || plan.action} <code>{plan.pack_key}</code>
          </h2>
          <div className="muted">
            {plan.from_version || "not installed"} → {plan.to_version || "—"}
            {plan.to_enabled === false ? " (disabled)" : ""} · checked against platform{" "}
            {plan.platform_version}
          </div>
        </div>
        <CompatibilityPill status={plan.compatibility_status} />
      </div>

      {blocking.length > 0 ? (
        <div className="errorBanner">
          <strong>This change would be refused.</strong>
          <ul className={styles.diagnostics}>
            {blocking.map((diagnostic) => (
              <li key={`${diagnostic.code}-${diagnostic.message}`}>
                <code>{diagnostic.code}</code> {diagnostic.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {warnings.length > 0 ? (
        <ul className={styles.diagnostics} data-severity="warning" aria-label="Warnings">
          {warnings.map((diagnostic) => (
            <li key={`${diagnostic.code}-${diagnostic.message}`}>
              <code>{diagnostic.code}</code> {diagnostic.message}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="compactStack">
        <strong>Publications this change touches</strong>
        {plan.publication_changes.length === 0 ? (
          <div className="muted">No publication contracts change.</div>
        ) : (
          <div className="tableWrap">
            <table className={styles.versionTable}>
              <thead>
                <tr>
                  <th>Publication</th>
                  <th>Change</th>
                  <th>Schema</th>
                  <th>Required by</th>
                </tr>
              </thead>
              <tbody>
                {plan.publication_changes.map((change) => (
                  <tr key={change.publication_key} data-breaking={change.breaking}>
                    <td>
                      <code>{change.publication_key}</code>
                    </td>
                    <td>
                      <span className="pill" data-tone={CHANGE_TONES[change.change] || "neutral"}>
                        {change.change.replace("_", " ")}
                      </span>
                      {change.breaking ? <div className="muted">breaking</div> : null}
                    </td>
                    <td>
                      {change.from_schema_version || "—"} → {change.to_schema_version || "—"}
                    </td>
                    <td>{change.dependents.length ? change.dependents.join(", ") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="muted">
          Contracts affected:{" "}
          {plan.contracts_affected.length ? plan.contracts_affected.join(", ") : "none"}
        </div>
        {plan.source ? (
          <div className="muted">
            From {plan.source.source_name}, revision{" "}
            <code>{plan.source.extension_registry_revision_id}</code>, entry digest{" "}
            <code>{plan.source.entry_digest.slice(0, 12)}</code>
          </div>
        ) : null}
      </div>

      {plan.allowed ? (
        <form
          className={styles.actionForm}
          action={`/control/packs/${encodeURIComponent(plan.pack_key)}/actions`}
          method="post"
        >
          <input type="hidden" name="action" value={plan.action} />
          <input type="hidden" name="version" value={version || plan.to_version || ""} />
          <div className="field">
            <label htmlFor="pack-reason">Reason (required; recorded in the history)</label>
            <textarea
              id="pack-reason"
              name="reason"
              required
              maxLength={MAX_PACK_REASON_LENGTH}
              placeholder="Why make this change?"
            />
          </div>
          <div className="buttonRow">
            <button className="primaryButton" type="submit">
              Confirm {PACK_ACTION_LABELS[plan.action].toLowerCase()}
            </button>
            <Link className="ghostButton" href="/control/packs">
              Cancel
            </Link>
          </div>
        </form>
      ) : (
        <div className="buttonRow">
          <Link className="ghostButton" href="/control/packs">
            Close preview
          </Link>
        </div>
      )}
    </section>
  );
}

function HistoryTable({ events }) {
  if (events.length === 0) {
    return <div className="muted">No lifecycle changes have been made or refused yet.</div>;
  }
  return (
    <div className="tableWrap">
      <table className={styles.versionTable}>
        <thead>
          <tr>
            <th>When</th>
            <th>Pack</th>
            <th>Change</th>
            <th>Outcome</th>
            <th>Actor</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.event_id} data-outcome={event.outcome}>
              <td>{formatTime(event.occurred_at)}</td>
              <td>
                <code>{event.pack_key}</code>
              </td>
              <td>
                {PACK_ACTION_LABELS[event.action] || event.action}
                <div className="muted">
                  {event.from_version || "—"} → {event.to_version || "—"}
                </div>
              </td>
              <td>
                <span className="pill" data-tone={event.outcome === "applied" ? "ok" : "warn"}>
                  {event.outcome}
                </span>
                {event.outcome === "refused" ? (
                  <ul className={styles.diagnostics}>
                    {event.compatibility_snapshot.issues.map((issue) => (
                      <li key={issue}>{issue}</li>
                    ))}
                  </ul>
                ) : null}
              </td>
              <td>
                {event.actor}
                {event.actor_role ? <div className="muted">{event.actor_role}</div> : null}
              </td>
              <td>{event.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function ControlPacksPage({ searchParams }) {
  const user = await getCurrentUser();
  if (user.role !== "admin") {
    redirect("/");
  }

  const planPack = typeof searchParams?.plan === "string" ? searchParams.plan : "";
  const planAction = isPackAction(searchParams?.action) ? searchParams.action : null;
  const planVersion = typeof searchParams?.version === "string" ? searchParams.version : null;

  const [catalog, history, plan] = await Promise.all([
    getPackCatalog(),
    getPackHistory(),
    planPack && planAction
      ? getPackChangePlan(planPack, { action: planAction, version: planVersion })
      : Promise.resolve(null)
  ]);
  const installed = catalog.packs.filter((pack) => pack.state !== "not_installed");
  const upgrades = catalog.packs.filter((pack) => pack.upgrade_available);

  const notice = NOTICE_COPY[searchParams?.notice] || "";
  const error = ERROR_COPY[searchParams?.error] || "";

  return (
    <AppShell
      currentPath="/control"
      user={user}
      title="Packs"
      eyebrow="Admin Access"
      lede="Extension packs offered by the external registries this platform has already synced. Every change is previewed first — which publications and contracts it touches, and whether anything blocks it — then applied with a reason you can find in the history."
    >
      <section className="stack">
        <ControlNav currentPath="/control/packs" />
        {notice ? <div className="successBanner">{notice}</div> : null}
        {error ? <div className="errorBanner">{error}</div> : null}

        <section className="cards">
          <article className="panel metricCard">
            <div className="metricLabel">Installed</div>
            <div className="metricValue">{installed.length}</div>
            <div className="muted">
              {installed.filter((pack) => pack.state === "enabled").length} enabled
            </div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Upgrades</div>
            <div className="metricValue">{upgrades.length}</div>
            <div className="muted">Newer cached versions available.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Registry cache</div>
            <div className="metricValue">{catalog.registry.entries}</div>
            <div className="muted">
              pack versions from {catalog.registry.sources_scanned} source(s)
            </div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Platform</div>
            <div className="metricValue">{catalog.platform_version}</div>
            <div className="muted">{catalog.platform_packs.length} built-in packs loaded</div>
          </article>
        </section>

        {plan ? <PlanPreview plan={plan} version={planVersion} /> : null}
        {planPack && planAction && !plan ? (
          <div className="errorBanner">That change could not be planned.</div>
        ) : null}

        <div className={styles.trustNote}>
          <strong>Trust boundary.</strong> This page never fetches code. The catalog lists only
          revisions a registry sync already validated and cached locally; sync a source under
          the registry controls to see new versions. Installed pack code runs in the platform
          process.
        </div>

        {catalog.registry.errors.length > 0 ? (
          <div className="errorBanner">
            <strong>Some cached registry revisions were skipped.</strong>
            <ul className={styles.diagnostics}>
              {catalog.registry.errors.map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <section className="stack" aria-label="Pack catalog">
          <div className="sectionHeader">
            <h2>Catalog</h2>
          </div>
          {catalog.packs.length === 0 ? (
            <div className="muted">
              No cached registry revision advertises a pack yet. A registry manifest lists its
              packs under <code>packs</code>.
            </div>
          ) : (
            catalog.packs.map((pack) => <PackCard key={pack.pack_key} pack={pack} />)
          )}
        </section>

        <section className="stack" aria-label="Built-in packs">
          <div className="sectionHeader">
            <h2>Built-in packs</h2>
          </div>
          <div className="muted">
            Shipped with the platform and always loaded; their publications count as provided
            when packs are checked for conflicts.
          </div>
          <div className="buttonRow">
            {catalog.platform_packs.map((pack) => (
              <span className="pill" data-tone="neutral" key={pack.name}>
                {pack.name} {pack.version} · {pack.publication_count} publications
              </span>
            ))}
          </div>
        </section>

        <section className="stack" aria-label="Lifecycle history">
          <div className="sectionHeader">
            <h2>History</h2>
          </div>
          <HistoryTable events={history} />
        </section>
      </section>
    </AppShell>
  );
}
