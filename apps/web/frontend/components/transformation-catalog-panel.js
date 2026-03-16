function referenceSummary(records, field) {
  if (!records || records.length === 0) {
    return "none";
  }
  const values = records.map((record) => record[field]);
  if (values.length <= 3) {
    return values.join(", ");
  }
  return `${values.slice(0, 3).join(", ")} +${values.length - 3} more`;
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

function summarizeValues(values = []) {
  if (!values || values.length === 0) {
    return "none";
  }
  return values.join(", ");
}

function archiveCopy(archived) {
  return archived ? "archived" : "active";
}

function packageOptionLabel(record) {
  return `${record.transformation_package_id}${record.archived ? " / archived" : ""}`;
}

export function TransformationCatalogPanel({
  transformationPackages,
  publicationDefinitions,
  transformationHandlers,
  publicationKeys
}) {
  const publicationDefinitionsByPackageId = buildReferenceMap(
    publicationDefinitions,
    "transformation_package_id"
  );
  const handlerByKey = new Map(
    transformationHandlers.map((handler) => [handler.handler_key, handler])
  );
  const publicationByKey = new Map(
    publicationKeys.map((publication) => [publication.publication_key, publication])
  );

  return (
    <div className="stack">
      <article className="panel section">
        <div className="sectionHeader">
          <div>
            <div className="eyebrow">Dependencies</div>
            <h2>Create transformation package</h2>
          </div>
        </div>
        <div className="muted">
          Choose a registered handler key instead of typing an import path. Built-in
          and active external handlers both appear here.
        </div>
        <form
          className="formGrid threeCol"
          action="/control/catalog/transformation-packages"
          method="post"
        >
          <div className="field">
            <label htmlFor="transformation-package-id">Package id</label>
            <input
              id="transformation-package-id"
              name="transformation_package_id"
              type="text"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="transformation-package-name">Name</label>
            <input id="transformation-package-name" name="name" type="text" required />
          </div>
          <div className="field">
            <label htmlFor="transformation-package-version">Version</label>
            <input
              id="transformation-package-version"
              name="version"
              type="number"
              min="1"
              defaultValue="1"
              required
            />
          </div>
          <div className="field spanTwo">
            <label htmlFor="transformation-package-handler">Handler key</label>
            <select
              id="transformation-package-handler"
              name="handler_key"
              defaultValue={transformationHandlers[0]?.handler_key || ""}
              required
            >
              {transformationHandlers.map((handler) => (
                <option key={handler.handler_key} value={handler.handler_key}>
                  {handler.handler_key}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="transformation-package-description">Description</label>
            <input
              id="transformation-package-description"
              name="description"
              type="text"
              placeholder="Optional description"
            />
          </div>
          <button className="primaryButton inlineButton" type="submit">
            Create transformation package
          </button>
        </form>
      </article>

      <article className="panel section">
        <div className="sectionHeader">
          <div>
            <div className="eyebrow">Dependencies</div>
            <h2>Create publication definition</h2>
          </div>
        </div>
        <div className="muted">
          Publication keys come from registered handler support and published reporting
          extensions. Extension-provided publication keys are globally available.
        </div>
        <form
          className="formGrid threeCol"
          action="/control/catalog/publication-definitions"
          method="post"
        >
          <div className="field">
            <label htmlFor="publication-definition-id">Publication id</label>
            <input
              id="publication-definition-id"
              name="publication_definition_id"
              type="text"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="publication-definition-name">Name</label>
            <input id="publication-definition-name" name="name" type="text" required />
          </div>
          <div className="field">
            <label htmlFor="publication-definition-package">Transformation package</label>
            <select
              id="publication-definition-package"
              name="transformation_package_id"
              defaultValue={
                transformationPackages.find((record) => !record.archived)
                  ?.transformation_package_id ||
                transformationPackages[0]?.transformation_package_id ||
                ""
              }
              required
            >
              {transformationPackages.map((record) => (
                <option
                  key={record.transformation_package_id}
                  value={record.transformation_package_id}
                >
                  {packageOptionLabel(record)}
                </option>
              ))}
            </select>
          </div>
          <div className="field spanTwo">
            <label htmlFor="publication-definition-key">Publication key</label>
            <select
              id="publication-definition-key"
              name="publication_key"
              defaultValue={publicationKeys[0]?.publication_key || ""}
              required
            >
              {publicationKeys.map((publication) => (
                <option
                  key={publication.publication_key}
                  value={publication.publication_key}
                >
                  {publication.publication_key}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="publication-definition-description">Description</label>
            <input
              id="publication-definition-description"
              name="description"
              type="text"
              placeholder="Optional description"
            />
          </div>
          <button className="primaryButton inlineButton" type="submit">
            Create publication definition
          </button>
        </form>
      </article>

      <article className="panel section">
        <div className="sectionHeader">
          <div>
            <div className="eyebrow">Discovery</div>
            <h2>Available transformation handlers</h2>
          </div>
        </div>
        {transformationHandlers.length === 0 ? (
          <div className="empty">No transformation handlers are available.</div>
        ) : (
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Handler key</th>
                  <th>Default publications</th>
                  <th>Supported publications</th>
                </tr>
              </thead>
              <tbody>
                {transformationHandlers.map((handler) => (
                  <tr key={handler.handler_key}>
                    <td>{handler.handler_key}</td>
                    <td>{summarizeValues(handler.default_publications)}</td>
                    <td>{summarizeValues(handler.supported_publications)}</td>
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
            <div className="eyebrow">Discovery</div>
            <h2>Available publication keys</h2>
          </div>
        </div>
        {publicationKeys.length === 0 ? (
          <div className="empty">No publication keys are available.</div>
        ) : (
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Publication key</th>
                  <th>Source kinds</th>
                  <th>Supported handlers</th>
                  <th>Reporting extensions</th>
                </tr>
              </thead>
              <tbody>
                {publicationKeys.map((publication) => (
                  <tr key={publication.publication_key}>
                    <td>{publication.publication_key}</td>
                    <td>{summarizeValues(publication.source_kinds)}</td>
                    <td>{summarizeValues(publication.supported_handlers)}</td>
                    <td>{summarizeValues(publication.reporting_extensions)}</td>
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
            <div className="eyebrow">Dependencies</div>
            <h2>Transformation packages</h2>
          </div>
        </div>
        {transformationPackages.length === 0 ? (
          <div className="empty">No transformation packages.</div>
        ) : (
          <div className="entityList">
            {transformationPackages.map((record) => {
              const definitions =
                publicationDefinitionsByPackageId.get(record.transformation_package_id) || [];
              const handler = handlerByKey.get(record.handler_key);
              return (
                <article className="entityCard" key={record.transformation_package_id}>
                  <div className="entityHeader">
                    <div>
                      <div className="metricLabel">{record.transformation_package_id}</div>
                      <h3>{record.name}</h3>
                    </div>
                    <div className="buttonRow">
                      <span className="statusPill status-active">v{record.version}</span>
                      <span
                        className={`statusPill status-${
                          record.archived ? "archived" : "active"
                        }`}
                      >
                        {archiveCopy(record.archived)}
                      </span>
                    </div>
                  </div>
                  <div className="metaGrid">
                    <div className="metaItem">
                      <div className="metricLabel">Handler key</div>
                      <div>{record.handler_key}</div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Default publications</div>
                      <div className="muted">
                        {summarizeValues(handler?.default_publications || [])}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Supported publications</div>
                      <div className="muted">
                        {summarizeValues(handler?.supported_publications || [])}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Publication definitions</div>
                      <div>{definitions.length}</div>
                      <div className="muted">
                        {referenceSummary(definitions, "publication_definition_id")}
                      </div>
                    </div>
                    <div className="metaItem spanTwo">
                      <div className="metricLabel">Description</div>
                      <div className="muted">{record.description || "n/a"}</div>
                    </div>
                  </div>
                  <form
                    className="formGrid threeCol"
                    action={`/control/catalog/transformation-packages/${record.transformation_package_id}`}
                    method="post"
                  >
                    <input
                      name="transformation_package_id"
                      type="hidden"
                      value={record.transformation_package_id}
                    />
                    <div className="field">
                      <label
                        htmlFor={`transformation-package-name-${record.transformation_package_id}`}
                      >
                        Name
                      </label>
                      <input
                        id={`transformation-package-name-${record.transformation_package_id}`}
                        name="name"
                        type="text"
                        defaultValue={record.name}
                        required
                      />
                    </div>
                    <div className="field">
                      <label
                        htmlFor={`transformation-package-version-${record.transformation_package_id}`}
                      >
                        Version
                      </label>
                      <input
                        id={`transformation-package-version-${record.transformation_package_id}`}
                        name="version"
                        type="number"
                        min="1"
                        defaultValue={String(record.version)}
                        required
                      />
                    </div>
                    <div className="field spanTwo">
                      <label
                        htmlFor={`transformation-package-handler-${record.transformation_package_id}`}
                      >
                        Handler key
                      </label>
                      <select
                        id={`transformation-package-handler-${record.transformation_package_id}`}
                        name="handler_key"
                        defaultValue={record.handler_key}
                        required
                      >
                        {transformationHandlers.map((handler) => (
                          <option key={handler.handler_key} value={handler.handler_key}>
                            {handler.handler_key}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="field">
                      <label
                        htmlFor={`transformation-package-description-${record.transformation_package_id}`}
                      >
                        Description
                      </label>
                      <input
                        id={`transformation-package-description-${record.transformation_package_id}`}
                        name="description"
                        type="text"
                        defaultValue={record.description || ""}
                        placeholder="Optional description"
                      />
                    </div>
                    <button className="primaryButton inlineButton" type="submit">
                      Update package
                    </button>
                  </form>
                  <form
                    action={`/control/catalog/transformation-packages/${record.transformation_package_id}/archive`}
                    method="post"
                  >
                    <input
                      name="archived"
                      type="hidden"
                      value={record.archived ? "false" : "true"}
                    />
                    <button className="ghostButton inlineButton" type="submit">
                      {record.archived ? "Restore package" : "Archive package"}
                    </button>
                  </form>
                </article>
              );
            })}
          </div>
        )}
      </article>

      <article className="panel section">
        <div className="sectionHeader">
          <div>
            <div className="eyebrow">Dependencies</div>
            <h2>Publication definitions</h2>
          </div>
        </div>
        {publicationDefinitions.length === 0 ? (
          <div className="empty">No publication definitions registered yet.</div>
        ) : (
          <div className="entityList">
            {publicationDefinitions.map((record) => {
              const publication = publicationByKey.get(record.publication_key);
              return (
                <article className="entityCard" key={record.publication_definition_id}>
                  <div className="entityHeader">
                    <div>
                      <div className="metricLabel">{record.publication_definition_id}</div>
                      <h3>{record.name}</h3>
                    </div>
                    <div className="buttonRow">
                      <span className="statusPill status-active">
                        {record.publication_key}
                      </span>
                      <span
                        className={`statusPill status-${
                          record.archived ? "archived" : "active"
                        }`}
                      >
                        {archiveCopy(record.archived)}
                      </span>
                    </div>
                  </div>
                  <div className="metaGrid">
                    <div className="metaItem">
                      <div className="metricLabel">Transformation package</div>
                      <div>{record.transformation_package_id}</div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Supported handlers</div>
                      <div className="muted">
                        {summarizeValues(publication?.supported_handlers || [])}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Reporting extensions</div>
                      <div className="muted">
                        {summarizeValues(publication?.reporting_extensions || [])}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Source kinds</div>
                      <div className="muted">
                        {summarizeValues(publication?.source_kinds || [])}
                      </div>
                    </div>
                    <div className="metaItem spanTwo">
                      <div className="metricLabel">Description</div>
                      <div className="muted">{record.description || "n/a"}</div>
                    </div>
                  </div>
                  <form
                    className="formGrid threeCol"
                    action={`/control/catalog/publication-definitions/${record.publication_definition_id}`}
                    method="post"
                  >
                    <input
                      name="publication_definition_id"
                      type="hidden"
                      value={record.publication_definition_id}
                    />
                    <div className="field">
                      <label
                        htmlFor={`publication-definition-name-${record.publication_definition_id}`}
                      >
                        Name
                      </label>
                      <input
                        id={`publication-definition-name-${record.publication_definition_id}`}
                        name="name"
                        type="text"
                        defaultValue={record.name}
                        required
                      />
                    </div>
                    <div className="field">
                      <label
                        htmlFor={`publication-definition-package-${record.publication_definition_id}`}
                      >
                        Transformation package
                      </label>
                      <select
                        id={`publication-definition-package-${record.publication_definition_id}`}
                        name="transformation_package_id"
                        defaultValue={record.transformation_package_id}
                        required
                      >
                        {transformationPackages.map((transformationPackage) => (
                          <option
                            key={transformationPackage.transformation_package_id}
                            value={transformationPackage.transformation_package_id}
                          >
                            {packageOptionLabel(transformationPackage)}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="field spanTwo">
                      <label
                        htmlFor={`publication-definition-key-${record.publication_definition_id}`}
                      >
                        Publication key
                      </label>
                      <select
                        id={`publication-definition-key-${record.publication_definition_id}`}
                        name="publication_key"
                        defaultValue={record.publication_key}
                        required
                      >
                        {publicationKeys.map((publicationRecord) => (
                          <option
                            key={publicationRecord.publication_key}
                            value={publicationRecord.publication_key}
                          >
                            {publicationRecord.publication_key}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="field">
                      <label
                        htmlFor={`publication-definition-description-${record.publication_definition_id}`}
                      >
                        Description
                      </label>
                      <input
                        id={`publication-definition-description-${record.publication_definition_id}`}
                        name="description"
                        type="text"
                        defaultValue={record.description || ""}
                        placeholder="Optional description"
                      />
                    </div>
                    <button className="primaryButton inlineButton" type="submit">
                      Update publication
                    </button>
                  </form>
                  <form
                    action={`/control/catalog/publication-definitions/${record.publication_definition_id}/archive`}
                    method="post"
                  >
                    <input
                      name="archived"
                      type="hidden"
                      value={record.archived ? "false" : "true"}
                    />
                    <button className="ghostButton inlineButton" type="submit">
                      {record.archived ? "Restore publication" : "Archive publication"}
                    </button>
                  </form>
                </article>
              );
            })}
          </div>
        )}
      </article>
    </div>
  );
}
