import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ControlNav } from "@/components/control-nav";
import {
  getColumnMappings,
  getCurrentUser,
  getDatasetContracts,
  getSourceAssets,
  getSourceSystems,
  getTransformationPackages
} from "@/lib/backend";

function noticeCopy(notice) {
  switch (notice) {
    case "source-system-created":
      return "Source system created.";
    case "source-system-updated":
      return "Source system updated.";
    case "source-asset-created":
      return "Source asset created.";
    case "source-asset-updated":
      return "Source asset updated.";
    default:
      return "";
  }
}

function errorCopy(error) {
  switch (error) {
    case "source-system-failed":
      return "Could not create the source system.";
    case "source-system-update-failed":
      return "Could not update the source system.";
    case "source-asset-failed":
      return "Could not create the source asset.";
    case "source-asset-update-failed":
      return "Could not update the source asset.";
    default:
      return "";
  }
}

function statusCopy(enabled) {
  return enabled ? "active" : "inactive";
}

export default async function ControlCatalogPage({ searchParams }) {
  const user = await getCurrentUser();
  if (user.role !== "admin") {
    redirect("/");
  }

  const [
    sourceSystems,
    datasetContracts,
    columnMappings,
    transformationPackages,
    sourceAssets
  ] = await Promise.all([
    getSourceSystems(),
    getDatasetContracts(),
    getColumnMappings(),
    getTransformationPackages(),
    getSourceAssets()
  ]);

  const activeSourceSystems = sourceSystems.filter((record) => record.enabled);
  const contractById = new Map(
    datasetContracts.map((record) => [record.dataset_contract_id, record])
  );
  const mappingById = new Map(
    columnMappings.map((record) => [record.column_mapping_id, record])
  );
  const packageById = new Map(
    transformationPackages.map((record) => [record.transformation_package_id, record])
  );
  const notice = noticeCopy(searchParams?.notice);
  const error = errorCopy(searchParams?.error);

  return (
    <AppShell
      currentPath="/control"
      user={user}
      title="Control Catalog"
      eyebrow="Admin Access"
      lede="Source registration stays API-backed: register systems, bind source assets, and keep contract and mapping versions explicit before ingestion starts."
    >
      <section className="stack">
        <ControlNav currentPath="/control/catalog" />
        {notice ? <div className="successBanner">{notice}</div> : null}
        {error ? <div className="errorBanner">{error}</div> : null}

        <section className="cards">
          <article className="panel metricCard">
            <div className="metricLabel">Source systems</div>
            <div className="metricValue">{sourceSystems.length}</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Active systems</div>
            <div className="metricValue">{activeSourceSystems.length}</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Source assets</div>
            <div className="metricValue">{sourceAssets.length}</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Contracts / mappings</div>
            <div className="metricValue">
              {datasetContracts.length} / {columnMappings.length}
            </div>
          </article>
        </section>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Registration</div>
              <h2>Create source system</h2>
            </div>
          </div>
          <form className="formGrid fourCol" action="/control/catalog/source-systems" method="post">
            <div className="field">
              <label htmlFor="source-system-id">System id</label>
              <input id="source-system-id" name="source_system_id" type="text" required />
            </div>
            <div className="field">
              <label htmlFor="source-system-name">Name</label>
              <input id="source-system-name" name="name" type="text" required />
            </div>
            <div className="field">
              <label htmlFor="source-system-type">Source type</label>
              <input
                id="source-system-type"
                name="source_type"
                type="text"
                defaultValue="file-drop"
                required
              />
            </div>
            <div className="field">
              <label htmlFor="source-system-transport">Transport</label>
              <input
                id="source-system-transport"
                name="transport"
                type="text"
                defaultValue="filesystem"
                required
              />
            </div>
            <div className="field">
              <label htmlFor="source-system-schedule-mode">Schedule mode</label>
              <input
                id="source-system-schedule-mode"
                name="schedule_mode"
                type="text"
                defaultValue="manual"
                required
              />
            </div>
            <div className="field">
              <label htmlFor="source-system-enabled">Initial status</label>
              <select id="source-system-enabled" name="enabled" defaultValue="true">
                <option value="true">active</option>
                <option value="false">inactive</option>
              </select>
            </div>
            <div className="field spanTwo">
              <label htmlFor="source-system-description">Description</label>
              <input
                id="source-system-description"
                name="description"
                type="text"
                placeholder="Optional description"
              />
            </div>
            <button className="primaryButton inlineButton" type="submit">
              Create source system
            </button>
          </form>
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Binding</div>
              <h2>Create source asset</h2>
            </div>
          </div>
          {activeSourceSystems.length === 0 ||
          datasetContracts.length === 0 ||
          columnMappings.length === 0 ? (
            <div className="empty">
              Source asset creation requires an active source system plus at least one dataset
              contract and column mapping.
            </div>
          ) : (
            <form className="formGrid fourCol" action="/control/catalog/source-assets" method="post">
              <div className="field">
                <label htmlFor="source-asset-id">Asset id</label>
                <input id="source-asset-id" name="source_asset_id" type="text" required />
              </div>
              <div className="field">
                <label htmlFor="source-asset-name">Name</label>
                <input id="source-asset-name" name="name" type="text" required />
              </div>
              <div className="field">
                <label htmlFor="source-asset-type">Asset type</label>
                <input
                  id="source-asset-type"
                  name="asset_type"
                  type="text"
                  defaultValue="dataset"
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="source-asset-enabled">Initial status</label>
                <select id="source-asset-enabled" name="enabled" defaultValue="true">
                  <option value="true">active</option>
                  <option value="false">inactive</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="source-system-select">Source system</label>
                <select id="source-system-select" name="source_system_id" required defaultValue="">
                  <option value="" disabled>
                    Select source system
                  </option>
                  {activeSourceSystems.map((record) => (
                    <option key={record.source_system_id} value={record.source_system_id}>
                      {record.source_system_id}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="dataset-contract-select">Dataset contract</label>
                <select
                  id="dataset-contract-select"
                  name="dataset_contract_id"
                  required
                  defaultValue=""
                >
                  <option value="" disabled>
                    Select contract
                  </option>
                  {datasetContracts.map((record) => (
                    <option key={record.dataset_contract_id} value={record.dataset_contract_id}>
                      {record.dataset_contract_id}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="column-mapping-select">Column mapping</label>
                <select
                  id="column-mapping-select"
                  name="column_mapping_id"
                  required
                  defaultValue=""
                >
                  <option value="" disabled>
                    Select mapping
                  </option>
                  {columnMappings.map((record) => (
                    <option key={record.column_mapping_id} value={record.column_mapping_id}>
                      {record.column_mapping_id}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="transformation-package-select">Transformation package</label>
                <select
                  id="transformation-package-select"
                  name="transformation_package_id"
                  defaultValue=""
                >
                  <option value="">None</option>
                  {transformationPackages.map((record) => (
                    <option
                      key={record.transformation_package_id}
                      value={record.transformation_package_id}
                    >
                      {record.transformation_package_id}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field spanTwo">
                <label htmlFor="source-asset-description">Description</label>
                <input
                  id="source-asset-description"
                  name="description"
                  type="text"
                  placeholder="Optional description"
                />
              </div>
              <button className="primaryButton inlineButton" type="submit">
                Create source asset
              </button>
            </form>
          )}
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Catalog</div>
              <h2>Source systems</h2>
            </div>
          </div>
          {sourceSystems.length === 0 ? (
            <div className="empty">No source systems registered yet.</div>
          ) : (
            <div className="entityList">
              {sourceSystems.map((record) => (
                <article className="entityCard" key={record.source_system_id}>
                  <div className="entityHeader">
                    <div>
                      <div className="metricLabel">{record.source_system_id}</div>
                      <h3>{record.name}</h3>
                    </div>
                    <span className={`statusPill status-${statusCopy(record.enabled)}`}>
                      {statusCopy(record.enabled)}
                    </span>
                  </div>
                  <div className="metaGrid">
                    <div className="metaItem">
                      <div className="metricLabel">Source type</div>
                      <div>{record.source_type}</div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Transport</div>
                      <div>{record.transport}</div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Schedule mode</div>
                      <div>{record.schedule_mode}</div>
                    </div>
                    <div className="metaItem spanTwo">
                      <div className="metricLabel">Description</div>
                      <div className="muted">{record.description || "n/a"}</div>
                    </div>
                  </div>
                  <form
                    className="formGrid fourCol"
                    action={`/control/catalog/source-systems/${record.source_system_id}`}
                    method="post"
                  >
                    <input name="source_system_id" type="hidden" value={record.source_system_id} />
                    <div className="field">
                      <label htmlFor={`system-name-${record.source_system_id}`}>Name</label>
                      <input
                        id={`system-name-${record.source_system_id}`}
                        name="name"
                        type="text"
                        defaultValue={record.name}
                        required
                      />
                    </div>
                    <div className="field">
                      <label htmlFor={`system-type-${record.source_system_id}`}>Source type</label>
                      <input
                        id={`system-type-${record.source_system_id}`}
                        name="source_type"
                        type="text"
                        defaultValue={record.source_type}
                        required
                      />
                    </div>
                    <div className="field">
                      <label htmlFor={`system-transport-${record.source_system_id}`}>Transport</label>
                      <input
                        id={`system-transport-${record.source_system_id}`}
                        name="transport"
                        type="text"
                        defaultValue={record.transport}
                        required
                      />
                    </div>
                    <div className="field">
                      <label htmlFor={`system-schedule-${record.source_system_id}`}>Schedule mode</label>
                      <input
                        id={`system-schedule-${record.source_system_id}`}
                        name="schedule_mode"
                        type="text"
                        defaultValue={record.schedule_mode}
                        required
                      />
                    </div>
                    <div className="field spanTwo">
                      <label htmlFor={`system-description-${record.source_system_id}`}>Description</label>
                      <input
                        id={`system-description-${record.source_system_id}`}
                        name="description"
                        type="text"
                        defaultValue={record.description || ""}
                      />
                    </div>
                    <div className="field">
                      <label htmlFor={`system-enabled-${record.source_system_id}`}>Status</label>
                      <select
                        id={`system-enabled-${record.source_system_id}`}
                        name="enabled"
                        defaultValue={record.enabled ? "true" : "false"}
                      >
                        <option value="true">active</option>
                        <option value="false">inactive</option>
                      </select>
                    </div>
                    <button className="primaryButton inlineButton" type="submit">
                      Save source system
                    </button>
                  </form>
                </article>
              ))}
            </div>
          )}
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Bindings</div>
              <h2>Source assets</h2>
            </div>
          </div>
          {sourceAssets.length === 0 ? (
            <div className="empty">No source assets registered yet.</div>
          ) : (
            <div className="entityList">
              {sourceAssets.map((record) => {
                const datasetContract = contractById.get(record.dataset_contract_id);
                const columnMapping = mappingById.get(record.column_mapping_id);
                const transformationPackage = record.transformation_package_id
                  ? packageById.get(record.transformation_package_id)
                  : null;
                return (
                  <article className="entityCard" key={record.source_asset_id}>
                    <div className="entityHeader">
                      <div>
                        <div className="metricLabel">{record.source_asset_id}</div>
                        <h3>{record.name}</h3>
                      </div>
                      <span className={`statusPill status-${statusCopy(record.enabled)}`}>
                        {statusCopy(record.enabled)}
                      </span>
                    </div>
                    <div className="metaGrid">
                      <div className="metaItem">
                        <div className="metricLabel">Source system</div>
                        <div>{record.source_system_id}</div>
                      </div>
                      <div className="metaItem">
                        <div className="metricLabel">Contract</div>
                        <div>
                          {record.dataset_contract_id}
                          {datasetContract ? ` / v${datasetContract.version}` : ""}
                        </div>
                      </div>
                      <div className="metaItem">
                        <div className="metricLabel">Mapping</div>
                        <div>
                          {record.column_mapping_id}
                          {columnMapping ? ` / v${columnMapping.version}` : ""}
                        </div>
                      </div>
                      <div className="metaItem">
                        <div className="metricLabel">Package</div>
                        <div>{transformationPackage?.handler_key || record.transformation_package_id || "n/a"}</div>
                      </div>
                      <div className="metaItem spanTwo">
                        <div className="metricLabel">Description</div>
                        <div className="muted">{record.description || "n/a"}</div>
                      </div>
                    </div>
                    <form
                      className="formGrid fourCol"
                      action={`/control/catalog/source-assets/${record.source_asset_id}`}
                      method="post"
                    >
                      <input name="source_asset_id" type="hidden" value={record.source_asset_id} />
                      <div className="field">
                        <label htmlFor={`asset-name-${record.source_asset_id}`}>Name</label>
                        <input
                          id={`asset-name-${record.source_asset_id}`}
                          name="name"
                          type="text"
                          defaultValue={record.name}
                          required
                        />
                      </div>
                      <div className="field">
                        <label htmlFor={`asset-type-${record.source_asset_id}`}>Asset type</label>
                        <input
                          id={`asset-type-${record.source_asset_id}`}
                          name="asset_type"
                          type="text"
                          defaultValue={record.asset_type}
                          required
                        />
                      </div>
                      <div className="field">
                        <label htmlFor={`asset-system-${record.source_asset_id}`}>Source system</label>
                        <select
                          id={`asset-system-${record.source_asset_id}`}
                          name="source_system_id"
                          defaultValue={record.source_system_id}
                          required
                        >
                          {sourceSystems.map((item) => (
                            <option key={item.source_system_id} value={item.source_system_id}>
                              {item.source_system_id}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="field">
                        <label htmlFor={`asset-contract-${record.source_asset_id}`}>Dataset contract</label>
                        <select
                          id={`asset-contract-${record.source_asset_id}`}
                          name="dataset_contract_id"
                          defaultValue={record.dataset_contract_id}
                          required
                        >
                          {datasetContracts.map((item) => (
                            <option key={item.dataset_contract_id} value={item.dataset_contract_id}>
                              {item.dataset_contract_id}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="field">
                        <label htmlFor={`asset-mapping-${record.source_asset_id}`}>Column mapping</label>
                        <select
                          id={`asset-mapping-${record.source_asset_id}`}
                          name="column_mapping_id"
                          defaultValue={record.column_mapping_id}
                          required
                        >
                          {columnMappings.map((item) => (
                            <option key={item.column_mapping_id} value={item.column_mapping_id}>
                              {item.column_mapping_id}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="field">
                        <label htmlFor={`asset-package-${record.source_asset_id}`}>Transformation package</label>
                        <select
                          id={`asset-package-${record.source_asset_id}`}
                          name="transformation_package_id"
                          defaultValue={record.transformation_package_id || ""}
                        >
                          <option value="">None</option>
                          {transformationPackages.map((item) => (
                            <option
                              key={item.transformation_package_id}
                              value={item.transformation_package_id}
                            >
                              {item.transformation_package_id}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="field">
                        <label htmlFor={`asset-enabled-${record.source_asset_id}`}>Status</label>
                        <select
                          id={`asset-enabled-${record.source_asset_id}`}
                          name="enabled"
                          defaultValue={record.enabled ? "true" : "false"}
                        >
                          <option value="true">active</option>
                          <option value="false">inactive</option>
                        </select>
                      </div>
                      <div className="field spanTwo">
                        <label htmlFor={`asset-description-${record.source_asset_id}`}>Description</label>
                        <input
                          id={`asset-description-${record.source_asset_id}`}
                          name="description"
                          type="text"
                          defaultValue={record.description || ""}
                        />
                      </div>
                      <button className="primaryButton inlineButton" type="submit">
                        Save source asset
                      </button>
                    </form>
                  </article>
                );
              })}
            </div>
          )}
        </article>

        <section className="layout">
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Dependencies</div>
                <h2>Dataset contracts</h2>
              </div>
            </div>
            {datasetContracts.length === 0 ? (
              <div className="empty">No dataset contracts registered yet.</div>
            ) : (
              <div className="stack compactStack">
                {datasetContracts.map((record) => (
                  <div className="metaItem" key={record.dataset_contract_id}>
                    <div className="metricLabel">{record.dataset_contract_id}</div>
                    <div className="muted">
                      {record.dataset_name} / v{record.version} / {record.columns.length} columns
                    </div>
                  </div>
                ))}
              </div>
            )}
          </article>

          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Dependencies</div>
                <h2>Mappings and packages</h2>
              </div>
            </div>
            <div className="metaGrid">
              <div className="stack compactStack">
                <div className="metricLabel">Column mappings</div>
                {columnMappings.length === 0 ? (
                  <div className="empty">No mappings.</div>
                ) : (
                  columnMappings.map((record) => (
                    <div className="metaItem" key={record.column_mapping_id}>
                      <div>{record.column_mapping_id}</div>
                      <div className="muted">
                        {record.source_system_id} / {record.dataset_contract_id} / v{record.version}
                      </div>
                    </div>
                  ))
                )}
              </div>
              <div className="stack compactStack">
                <div className="metricLabel">Transformation packages</div>
                {transformationPackages.length === 0 ? (
                  <div className="empty">No packages.</div>
                ) : (
                  transformationPackages.map((record) => (
                    <div className="metaItem" key={record.transformation_package_id}>
                      <div>{record.transformation_package_id}</div>
                      <div className="muted">
                        {record.handler_key} / v{record.version}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </article>
        </section>
      </section>
    </AppShell>
  );
}
