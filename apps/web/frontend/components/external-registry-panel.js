function archiveCopy(archived) {
  return archived ? "archived" : "active";
}

function statusCopy(enabled) {
  return enabled ? "active" : "inactive";
}

function summarizeTuple(values = []) {
  if (values.length === 0) {
    return "none";
  }
  if (values.length <= 2) {
    return values.join(", ");
  }
  return `${values.slice(0, 2).join(", ")} +${values.length - 2} more`;
}

function buildReferenceMap(records, field) {
  const references = new Map();
  for (const record of records) {
    const key = record[field];
    const current = references.get(key) || [];
    current.push(record);
    references.set(key, current);
  }
  return references;
}

function sortByCreatedAt(records) {
  return [...records].sort((left, right) =>
    String(right.created_at || "").localeCompare(String(left.created_at || ""))
  );
}

export function ExternalRegistryPanel({ sources, revisions, activations }) {
  const revisionsBySourceId = buildReferenceMap(
    revisions,
    "extension_registry_source_id"
  );
  const activationBySourceId = new Map(
    activations.map((activation) => [
      activation.extension_registry_source_id,
      activation
    ])
  );

  return (
    <article className="panel section">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">Extensibility</div>
          <h2>Create external registry source</h2>
        </div>
      </div>
      <div className="muted">
        GitHub repositories use the generic <code>git</code> source kind.{" "}
        <code>path</code> sources must already be mounted into the API and worker
        runtimes before sync can validate them.
      </div>
      <form
        className="formGrid fourCol"
        action="/control/catalog/extension-registry-sources"
        method="post"
      >
        <div className="field">
          <label htmlFor="extension-registry-source-id">Source id</label>
          <input
            id="extension-registry-source-id"
            name="extension_registry_source_id"
            type="text"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="extension-registry-source-name">Name</label>
          <input id="extension-registry-source-name" name="name" type="text" required />
        </div>
        <div className="field">
          <label htmlFor="extension-registry-source-kind">Source kind</label>
          <select
            id="extension-registry-source-kind"
            name="source_kind"
            defaultValue="path"
          >
            <option value="path">path</option>
            <option value="git">git</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="extension-registry-source-enabled">Initial status</label>
          <select
            id="extension-registry-source-enabled"
            name="enabled"
            defaultValue="true"
          >
            <option value="true">active</option>
            <option value="false">inactive</option>
          </select>
        </div>
        <div className="field spanTwo">
          <label htmlFor="extension-registry-source-location">Location</label>
          <input
            id="extension-registry-source-location"
            name="location"
            type="text"
            placeholder="/srv/extensions/weather or https://github.com/org/repo.git"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="extension-registry-source-ref">Desired ref</label>
          <input
            id="extension-registry-source-ref"
            name="desired_ref"
            type="text"
            placeholder="main or a tag"
          />
        </div>
        <div className="field">
          <label htmlFor="extension-registry-source-subdirectory">Subdirectory</label>
          <input
            id="extension-registry-source-subdirectory"
            name="subdirectory"
            type="text"
            placeholder="extensions/household"
          />
        </div>
        <div className="field">
          <label htmlFor="extension-registry-source-secret-name">Auth secret name</label>
          <input
            id="extension-registry-source-secret-name"
            name="auth_secret_name"
            type="text"
            placeholder="github-token"
          />
        </div>
        <div className="field">
          <label htmlFor="extension-registry-source-secret-key">Auth secret key</label>
          <input
            id="extension-registry-source-secret-key"
            name="auth_secret_key"
            type="text"
            placeholder="token"
          />
        </div>
        <button className="primaryButton inlineButton" type="submit">
          Create external source
        </button>
      </form>

      <div className="stack compactStack">
        <div className="sectionHeader">
          <div>
            <div className="eyebrow">Extensibility</div>
            <h2>External registry sources</h2>
          </div>
        </div>
        {sources.length === 0 ? (
          <div className="empty">No external registry sources configured yet.</div>
        ) : (
          <div className="entityList">
            {sources.map((source) => {
              const sourceRevisions = sortByCreatedAt(
                revisionsBySourceId.get(source.extension_registry_source_id) || []
              );
              const latestRevision = sourceRevisions[0] || null;
              const activation =
                activationBySourceId.get(source.extension_registry_source_id) || null;
              const activatedRevision = sourceRevisions.find(
                (revision) =>
                  revision.extension_registry_revision_id ===
                  activation?.extension_registry_revision_id
              );
              const validatedRevisions = sourceRevisions.filter(
                (revision) => revision.sync_status === "validated"
              );

              return (
                <article
                  className="entityCard"
                  key={source.extension_registry_source_id}
                >
                  <div className="entityHeader">
                    <div>
                      <div className="metricLabel">
                        {source.extension_registry_source_id}
                      </div>
                      <h3>{source.name}</h3>
                    </div>
                    <div className="buttonRow">
                      <span className={`statusPill status-${statusCopy(source.enabled)}`}>
                        {statusCopy(source.enabled)}
                      </span>
                      <span
                        className={`statusPill status-${
                          source.archived ? "archived" : "active"
                        }`}
                      >
                        {archiveCopy(source.archived)}
                      </span>
                    </div>
                  </div>
                  <div className="metaGrid">
                    <div className="metaItem">
                      <div className="metricLabel">Source kind</div>
                      <div>{source.source_kind}</div>
                    </div>
                    <div className="metaItem spanTwo">
                      <div className="metricLabel">Location</div>
                      <div className="muted">{source.location}</div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Desired ref</div>
                      <div>{source.desired_ref || "default"}</div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Subdirectory</div>
                      <div>{source.subdirectory || "root"}</div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Auth secret</div>
                      <div>
                        {source.auth_secret_name && source.auth_secret_key
                          ? `${source.auth_secret_name} / ${source.auth_secret_key}`
                          : "none"}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Validated revisions</div>
                      <div>{validatedRevisions.length}</div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Active revision</div>
                      <div>
                        {activatedRevision?.extension_registry_revision_id || "none"}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Active resolved ref</div>
                      <div>{activatedRevision?.resolved_ref || "n/a"}</div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Latest extension modules</div>
                      <div className="muted">
                        {summarizeTuple(latestRevision?.extension_modules || [])}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Latest function modules</div>
                      <div className="muted">
                        {summarizeTuple(latestRevision?.function_modules || [])}
                      </div>
                    </div>
                    <div className="metaItem spanTwo">
                      <div className="metricLabel">Latest validation</div>
                      <div className="muted">
                        {latestRevision
                          ? `${latestRevision.sync_status}${
                              latestRevision.validation_error
                                ? ` / ${latestRevision.validation_error}`
                                : ""
                            }`
                          : "No sync has run yet."}
                      </div>
                    </div>
                  </div>

                  <form
                    className="formGrid fourCol"
                    action={`/control/catalog/extension-registry-sources/${source.extension_registry_source_id}`}
                    method="post"
                  >
                    <input
                      name="extension_registry_source_id"
                      type="hidden"
                      value={source.extension_registry_source_id}
                    />
                    <div className="field">
                      <label
                        htmlFor={`extension-registry-source-name-${source.extension_registry_source_id}`}
                      >
                        Name
                      </label>
                      <input
                        id={`extension-registry-source-name-${source.extension_registry_source_id}`}
                        name="name"
                        type="text"
                        defaultValue={source.name}
                        required
                      />
                    </div>
                    <div className="field">
                      <label
                        htmlFor={`extension-registry-source-kind-${source.extension_registry_source_id}`}
                      >
                        Source kind
                      </label>
                      <select
                        id={`extension-registry-source-kind-${source.extension_registry_source_id}`}
                        name="source_kind"
                        defaultValue={source.source_kind}
                      >
                        <option value="path">path</option>
                        <option value="git">git</option>
                      </select>
                    </div>
                    <div className="field spanTwo">
                      <label
                        htmlFor={`extension-registry-source-location-${source.extension_registry_source_id}`}
                      >
                        Location
                      </label>
                      <input
                        id={`extension-registry-source-location-${source.extension_registry_source_id}`}
                        name="location"
                        type="text"
                        defaultValue={source.location}
                        required
                      />
                    </div>
                    <div className="field">
                      <label
                        htmlFor={`extension-registry-source-ref-${source.extension_registry_source_id}`}
                      >
                        Desired ref
                      </label>
                      <input
                        id={`extension-registry-source-ref-${source.extension_registry_source_id}`}
                        name="desired_ref"
                        type="text"
                        defaultValue={source.desired_ref || ""}
                      />
                    </div>
                    <div className="field">
                      <label
                        htmlFor={`extension-registry-source-subdirectory-${source.extension_registry_source_id}`}
                      >
                        Subdirectory
                      </label>
                      <input
                        id={`extension-registry-source-subdirectory-${source.extension_registry_source_id}`}
                        name="subdirectory"
                        type="text"
                        defaultValue={source.subdirectory || ""}
                      />
                    </div>
                    <div className="field">
                      <label
                        htmlFor={`extension-registry-source-secret-name-${source.extension_registry_source_id}`}
                      >
                        Auth secret name
                      </label>
                      <input
                        id={`extension-registry-source-secret-name-${source.extension_registry_source_id}`}
                        name="auth_secret_name"
                        type="text"
                        defaultValue={source.auth_secret_name || ""}
                      />
                    </div>
                    <div className="field">
                      <label
                        htmlFor={`extension-registry-source-secret-key-${source.extension_registry_source_id}`}
                      >
                        Auth secret key
                      </label>
                      <input
                        id={`extension-registry-source-secret-key-${source.extension_registry_source_id}`}
                        name="auth_secret_key"
                        type="text"
                        defaultValue={source.auth_secret_key || ""}
                      />
                    </div>
                    <div className="field">
                      <label
                        htmlFor={`extension-registry-source-enabled-${source.extension_registry_source_id}`}
                      >
                        Status
                      </label>
                      <select
                        id={`extension-registry-source-enabled-${source.extension_registry_source_id}`}
                        name="enabled"
                        defaultValue={source.enabled ? "true" : "false"}
                      >
                        <option value="true">active</option>
                        <option value="false">inactive</option>
                      </select>
                    </div>
                    <button className="primaryButton inlineButton" type="submit">
                      Save external source
                    </button>
                  </form>

                  <div className="buttonRow">
                    <form
                      action={`/control/catalog/extension-registry-sources/${source.extension_registry_source_id}/sync`}
                      method="post"
                    >
                      <input name="activate" type="hidden" value="false" />
                      <button className="ghostButton" type="submit">
                        Sync revision
                      </button>
                    </form>
                    <form
                      action={`/control/catalog/extension-registry-sources/${source.extension_registry_source_id}/sync`}
                      method="post"
                    >
                      <input name="activate" type="hidden" value="true" />
                      <button className="ghostButton" type="submit">
                        Sync and activate
                      </button>
                    </form>
                    <form
                      action={`/control/catalog/extension-registry-sources/${source.extension_registry_source_id}/archive`}
                      method="post"
                    >
                      <input
                        name="archived"
                        type="hidden"
                        value={source.archived ? "false" : "true"}
                      />
                      <button className="ghostButton" type="submit">
                        {source.archived ? "Restore source" : "Archive source"}
                      </button>
                    </form>
                  </div>

                  {validatedRevisions.length > 0 ? (
                    <form
                      className="formGrid threeCol"
                      action={`/control/catalog/extension-registry-sources/${source.extension_registry_source_id}/activate`}
                      method="post"
                    >
                      <div className="field spanTwo">
                        <label
                          htmlFor={`extension-registry-source-activate-${source.extension_registry_source_id}`}
                        >
                          Activate validated revision
                        </label>
                        <select
                          id={`extension-registry-source-activate-${source.extension_registry_source_id}`}
                          name="extension_registry_revision_id"
                          defaultValue={
                            activatedRevision?.extension_registry_revision_id ||
                            validatedRevisions[0]?.extension_registry_revision_id
                          }
                        >
                          {validatedRevisions.map((revision) => (
                            <option
                              key={revision.extension_registry_revision_id}
                              value={revision.extension_registry_revision_id}
                            >
                              {revision.extension_registry_revision_id}
                              {revision.resolved_ref
                                ? ` / ${revision.resolved_ref}`
                                : ""}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="buttonRow">
                        <button className="primaryButton inlineButton" type="submit">
                          Activate revision
                        </button>
                      </div>
                    </form>
                  ) : null}

                  {sourceRevisions.length === 0 ? (
                    <div className="empty">
                      No synced revisions for this source yet.
                    </div>
                  ) : (
                    <div className="tableWrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Revision</th>
                            <th>Status</th>
                            <th>Resolved ref</th>
                            <th>Imports</th>
                            <th>Extension modules</th>
                            <th>Function modules</th>
                            <th>Created</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sourceRevisions.map((revision) => (
                            <tr key={revision.extension_registry_revision_id}>
                              <td>
                                {revision.extension_registry_revision_id}
                                {revision.extension_registry_revision_id ===
                                activation?.extension_registry_revision_id
                                  ? " / active"
                                  : ""}
                              </td>
                              <td>
                                {revision.sync_status}
                                {revision.validation_error
                                  ? ` / ${revision.validation_error}`
                                  : ""}
                              </td>
                              <td>{revision.resolved_ref || "n/a"}</td>
                              <td>{summarizeTuple(revision.import_paths || [])}</td>
                              <td>{summarizeTuple(revision.extension_modules || [])}</td>
                              <td>{summarizeTuple(revision.function_modules || [])}</td>
                              <td>{revision.created_at}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </div>
    </article>
  );
}
