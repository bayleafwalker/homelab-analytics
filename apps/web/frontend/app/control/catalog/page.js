import Link from "next/link";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ControlNav } from "@/components/control-nav";
import { MappingPreviewPanel } from "@/components/mapping-preview-panel";
import {
  getColumnMappings,
  getCurrentUser,
  getDatasetContracts,
  getIngestionDefinitions,
  getSourceAssets,
  getSourceSystems,
  getTransformationPackages
} from "@/lib/backend";
import {
  formatColumnsSpec,
  formatRulesSpec,
  suggestVersionId
} from "@/lib/config-spec";

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
    case "source-asset-archived":
      return "Source asset archive state updated.";
    case "source-asset-deleted":
      return "Source asset deleted.";
    case "dataset-contract-created":
      return "Dataset contract version created.";
    case "dataset-contract-archived":
      return "Dataset contract archive state updated.";
    case "column-mapping-created":
      return "Column mapping version created.";
    case "column-mapping-archived":
      return "Column mapping archive state updated.";
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
    case "source-asset-archive-failed":
      return "Could not update the source asset archive state.";
    case "source-asset-delete-failed":
      return "Could not delete the source asset.";
    case "dataset-contract-failed":
      return "Could not create the dataset contract version.";
    case "dataset-contract-archive-failed":
      return "Could not update the dataset contract archive state.";
    case "column-mapping-failed":
      return "Could not create the column mapping version.";
    case "column-mapping-archive-failed":
      return "Could not update the column mapping archive state.";
    default:
      return "";
  }
}

function statusCopy(enabled) {
  return enabled ? "active" : "inactive";
}

function archiveCopy(archived) {
  return archived ? "archived" : "active";
}

function optionLabel(record, version, archived = false) {
  return `${record}${version ? ` / v${version}` : ""}${archived ? " / archived" : ""}`;
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

function resolveContractDraft(datasetContracts, cloneId) {
  const cloned = datasetContracts.find((record) => record.dataset_contract_id === cloneId);
  if (!cloned) {
    return {
      datasetContractId: "",
      datasetName: "",
      version: "1",
      allowExtraColumns: "false",
      columnsSpec: ""
    };
  }
  const nextVersion = cloned.version + 1;
  return {
    datasetContractId: suggestVersionId(cloned.dataset_contract_id, nextVersion),
    datasetName: cloned.dataset_name,
    version: String(nextVersion),
    allowExtraColumns: cloned.allow_extra_columns ? "true" : "false",
    columnsSpec: formatColumnsSpec(cloned.columns)
  };
}

function resolveMappingDraft(columnMappings, cloneId) {
  const cloned = columnMappings.find((record) => record.column_mapping_id === cloneId);
  if (!cloned) {
    return {
      columnMappingId: "",
      sourceSystemId: "",
      datasetContractId: "",
      version: "1",
      rulesSpec: ""
    };
  }
  const nextVersion = cloned.version + 1;
  return {
    columnMappingId: suggestVersionId(cloned.column_mapping_id, nextVersion),
    sourceSystemId: cloned.source_system_id,
    datasetContractId: cloned.dataset_contract_id,
    version: String(nextVersion),
    rulesSpec: formatRulesSpec(cloned.rules)
  };
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
    sourceAssets,
    ingestionDefinitions
  ] = await Promise.all([
    getSourceSystems(),
    getDatasetContracts({ includeArchived: true }),
    getColumnMappings({ includeArchived: true }),
    getTransformationPackages(),
    getSourceAssets({ includeArchived: true }),
    getIngestionDefinitions({ includeArchived: true })
  ]);

  const activeSourceSystems = sourceSystems.filter((record) => record.enabled);
  const activeDatasetContracts = datasetContracts.filter((record) => !record.archived);
  const archivedDatasetContracts = datasetContracts.filter((record) => record.archived);
  const activeColumnMappings = columnMappings.filter((record) => !record.archived);
  const archivedColumnMappings = columnMappings.filter((record) => record.archived);
  const activeSourceAssets = sourceAssets.filter((record) => !record.archived);
  const archivedSourceAssets = sourceAssets.filter((record) => record.archived);
  const contractById = new Map(
    datasetContracts.map((record) => [record.dataset_contract_id, record])
  );
  const mappingById = new Map(
    columnMappings.map((record) => [record.column_mapping_id, record])
  );
  const packageById = new Map(
    transformationPackages.map((record) => [record.transformation_package_id, record])
  );
  const sourceAssetsByContractId = buildReferenceMap(sourceAssets, "dataset_contract_id");
  const sourceAssetsByMappingId = buildReferenceMap(sourceAssets, "column_mapping_id");
  const ingestionDefinitionsBySourceAssetId = buildReferenceMap(
    ingestionDefinitions,
    "source_asset_id"
  );
  const contractDraft = resolveContractDraft(datasetContracts, searchParams?.contract_clone);
  const mappingDraft = resolveMappingDraft(columnMappings, searchParams?.mapping_clone);
  const notice = noticeCopy(searchParams?.notice);
  const error = errorCopy(searchParams?.error);

  return (
    <AppShell
      currentPath="/control"
      user={user}
      title="Control Catalog"
      eyebrow="Admin Access"
      lede="Version source registration, contract design, and mapping changes explicitly. Browser uploads and configured ingestion should reuse saved control-plane versions instead of inventing ad hoc schemas."
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
            <div className="metricValue">{activeSourceAssets.length}</div>
            <div className="muted">{archivedSourceAssets.length} archived assets</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Contracts / mappings</div>
            <div className="metricValue">
              {activeDatasetContracts.length} / {activeColumnMappings.length}
            </div>
            <div className="muted">
              {archivedDatasetContracts.length} archived contracts / {archivedColumnMappings.length} archived mappings
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
          activeDatasetContracts.length === 0 ||
          activeColumnMappings.length === 0 ? (
            <div className="empty">
              Source asset creation requires an active source system plus at least one active
              dataset contract and column mapping version.
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
                  {activeDatasetContracts.map((record) => (
                    <option key={record.dataset_contract_id} value={record.dataset_contract_id}>
                      {optionLabel(record.dataset_contract_id, record.version)}
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
                  {activeColumnMappings.map((record) => (
                    <option key={record.column_mapping_id} value={record.column_mapping_id}>
                      {optionLabel(record.column_mapping_id, record.version)}
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

        <section className="layout">
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Versioning</div>
                <h2>Create dataset contract version</h2>
              </div>
            </div>
            <div className="muted">
              One line per column: <code>name,type,required|optional</code>.
            </div>
            <form className="formGrid threeCol" action="/control/catalog/dataset-contracts" method="post">
              <div className="field">
                <label htmlFor="dataset-contract-id">Contract id</label>
                <input
                  id="dataset-contract-id"
                  name="dataset_contract_id"
                  type="text"
                  defaultValue={contractDraft.datasetContractId}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="dataset-contract-name">Dataset name</label>
                <input
                  id="dataset-contract-name"
                  name="dataset_name"
                  type="text"
                  defaultValue={contractDraft.datasetName}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="dataset-contract-version">Version</label>
                <input
                  id="dataset-contract-version"
                  name="version"
                  type="number"
                  min="1"
                  defaultValue={contractDraft.version}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="dataset-contract-allow-extra">Allow extra columns</label>
                <select
                  id="dataset-contract-allow-extra"
                  name="allow_extra_columns"
                  defaultValue={contractDraft.allowExtraColumns}
                >
                  <option value="false">false</option>
                  <option value="true">true</option>
                </select>
              </div>
              <div className="buttonRow">
                <Link className="ghostButton" href="/control/catalog">
                  Clear draft
                </Link>
              </div>
              <div className="field spanThree">
                <label htmlFor="dataset-contract-columns">Columns</label>
                <textarea
                  id="dataset-contract-columns"
                  name="columns_spec"
                  rows={10}
                  defaultValue={contractDraft.columnsSpec}
                  placeholder={"booked_at,date,required\naccount_id,string,required\ndescription,string,optional"}
                  required
                />
              </div>
              <button className="primaryButton inlineButton" type="submit">
                Create contract version
              </button>
            </form>
          </article>

          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Versioning</div>
                <h2>Create column mapping version</h2>
              </div>
            </div>
            <div className="muted">
              One line per rule: <code>target_column,source_column,default_value</code>.
            </div>
            <form className="formGrid threeCol" action="/control/catalog/column-mappings" method="post">
              <div className="field">
                <label htmlFor="column-mapping-id">Mapping id</label>
                <input
                  id="column-mapping-id"
                  name="column_mapping_id"
                  type="text"
                  defaultValue={mappingDraft.columnMappingId}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="column-mapping-source-system">Source system</label>
                <select
                  id="column-mapping-source-system"
                  name="source_system_id"
                  defaultValue={mappingDraft.sourceSystemId}
                  required
                >
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
                <label htmlFor="column-mapping-contract">Dataset contract</label>
                <select
                  id="column-mapping-contract"
                  name="dataset_contract_id"
                  defaultValue={mappingDraft.datasetContractId}
                  required
                >
                  <option value="" disabled>
                    Select contract
                  </option>
                  {activeDatasetContracts.map((record) => (
                    <option key={record.dataset_contract_id} value={record.dataset_contract_id}>
                      {optionLabel(record.dataset_contract_id, record.version)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="column-mapping-version">Version</label>
                <input
                  id="column-mapping-version"
                  name="version"
                  type="number"
                  min="1"
                  defaultValue={mappingDraft.version}
                  required
                />
              </div>
              <div className="buttonRow">
                <Link className="ghostButton" href="/control/catalog">
                  Clear draft
                </Link>
              </div>
              <div className="field spanThree">
                <label htmlFor="column-mapping-rules">Rules</label>
                <textarea
                  id="column-mapping-rules"
                  name="rules_spec"
                  rows={10}
                  defaultValue={mappingDraft.rulesSpec}
                  placeholder={"booked_at,booking_date,\namount,amount_eur,\ncurrency,,EUR"}
                  required
                />
              </div>
              <button className="primaryButton inlineButton" type="submit">
                Create mapping version
              </button>
            </form>
          </article>
        </section>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Preview</div>
              <h2>Mapping preview</h2>
            </div>
          </div>
          {activeDatasetContracts.length === 0 || activeColumnMappings.length === 0 ? (
            <div className="empty">
              Create an active dataset contract and column mapping before previewing sample CSV.
            </div>
          ) : (
            <MappingPreviewPanel
              datasetContracts={activeDatasetContracts}
              columnMappings={activeColumnMappings}
              initialContractId={mappingDraft.datasetContractId || activeDatasetContracts[0]?.dataset_contract_id}
              initialMappingId={mappingDraft.columnMappingId || activeColumnMappings[0]?.column_mapping_id}
            />
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
                const sourceAssetDefinitions =
                  ingestionDefinitionsBySourceAssetId.get(record.source_asset_id) || [];
                return (
                  <article className="entityCard" key={record.source_asset_id}>
                    <div className="entityHeader">
                      <div>
                        <div className="metricLabel">{record.source_asset_id}</div>
                        <h3>{record.name}</h3>
                      </div>
                      <div className="buttonRow">
                        <span className={`statusPill status-${statusCopy(record.enabled)}`}>
                          {statusCopy(record.enabled)}
                        </span>
                        <span
                          className={`statusPill status-${record.archived ? "archived" : "active"}`}
                        >
                          {archiveCopy(record.archived)}
                        </span>
                      </div>
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
                          {datasetContract?.archived ? " / archived" : ""}
                        </div>
                      </div>
                      <div className="metaItem">
                        <div className="metricLabel">Mapping</div>
                        <div>
                          {record.column_mapping_id}
                          {columnMapping ? ` / v${columnMapping.version}` : ""}
                          {columnMapping?.archived ? " / archived" : ""}
                        </div>
                      </div>
                      <div className="metaItem">
                        <div className="metricLabel">Package</div>
                        <div>{transformationPackage?.handler_key || record.transformation_package_id || "n/a"}</div>
                      </div>
                      <div className="metaItem">
                        <div className="metricLabel">Ingestion definitions</div>
                        <div>{sourceAssetDefinitions.length}</div>
                        <div className="muted">
                          {referenceSummary(
                            sourceAssetDefinitions,
                            "ingestion_definition_id"
                          )}
                        </div>
                      </div>
                      <div className="metaItem">
                        <div className="metricLabel">Binding impact</div>
                        <div className="muted">
                          {datasetContract?.archived || columnMapping?.archived
                            ? "This asset is still bound to archived contract or mapping versions."
                            : "Bindings are on active contract and mapping versions."}
                        </div>
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
                              {optionLabel(
                                item.dataset_contract_id,
                                item.version,
                                item.archived
                              )}
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
                              {optionLabel(
                                item.column_mapping_id,
                                item.version,
                                item.archived
                              )}
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
                    <div className="buttonRow">
                      <form
                        action={`/control/catalog/source-assets/${record.source_asset_id}/archive`}
                        method="post"
                      >
                        <input
                          name="archived"
                          type="hidden"
                          value={record.archived ? "false" : "true"}
                        />
                        <button className="ghostButton" type="submit">
                          {record.archived ? "Restore asset" : "Archive asset"}
                        </button>
                      </form>
                      {record.archived ? (
                        <form
                          action={`/control/catalog/source-assets/${record.source_asset_id}/delete`}
                          method="post"
                        >
                          <button className="ghostButton" type="submit">
                            Delete archived asset
                          </button>
                        </form>
                      ) : null}
                    </div>
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
              <div className="entityList">
                {datasetContracts.map((record) => {
                  const boundSourceAssets =
                    sourceAssetsByContractId.get(record.dataset_contract_id) || [];
                  return (
                  <article className="entityCard" key={record.dataset_contract_id}>
                    <div className="entityHeader">
                      <div>
                        <div className="metricLabel">{record.dataset_contract_id}</div>
                        <h3>
                          {record.dataset_name} / v{record.version}
                        </h3>
                      </div>
                      <span className={`statusPill status-${record.archived ? "archived" : "active"}`}>
                        {archiveCopy(record.archived)}
                      </span>
                    </div>
                    <div className="metaGrid">
                      <div className="metaItem">
                        <div className="metricLabel">Columns</div>
                        <div>{record.columns.length}</div>
                      </div>
                      <div className="metaItem">
                        <div className="metricLabel">Allow extra columns</div>
                        <div>{record.allow_extra_columns ? "true" : "false"}</div>
                      </div>
                      <div className="metaItem">
                        <div className="metricLabel">Source assets</div>
                        <div>{boundSourceAssets.length}</div>
                        <div className="muted">
                          {referenceSummary(boundSourceAssets, "source_asset_id")}
                        </div>
                      </div>
                      <div className="metaItem">
                        <div className="metricLabel">Archive impact</div>
                        <div className="muted">
                          {record.archived && boundSourceAssets.length > 0
                            ? "Archived version is still referenced by active control-plane bindings."
                            : "No bound source assets depend on this version."}
                        </div>
                      </div>
                      <div className="metaItem spanTwo">
                        <div className="metricLabel">Specification</div>
                        <pre className="specBlock">{formatColumnsSpec(record.columns)}</pre>
                      </div>
                    </div>
                    <div className="buttonRow">
                      <Link
                        className="ghostButton"
                        href={`/control/catalog?contract_clone=${record.dataset_contract_id}`}
                      >
                        Create next version
                      </Link>
                      <form
                        action={`/control/catalog/dataset-contracts/${record.dataset_contract_id}/archive`}
                        method="post"
                      >
                        <input
                          name="archived"
                          type="hidden"
                          value={record.archived ? "false" : "true"}
                        />
                        <button className="ghostButton" type="submit">
                          {record.archived ? "Restore version" : "Archive version"}
                        </button>
                      </form>
                    </div>
                  </article>
                );
                })}
              </div>
            )}
          </article>

          <div className="stack">
            <article className="panel section">
              <div className="sectionHeader">
                <div>
                  <div className="eyebrow">Dependencies</div>
                  <h2>Column mappings</h2>
                </div>
              </div>
              {columnMappings.length === 0 ? (
                <div className="empty">No column mappings registered yet.</div>
              ) : (
                <div className="entityList">
                  {columnMappings.map((record) => {
                    const boundSourceAssets =
                      sourceAssetsByMappingId.get(record.column_mapping_id) || [];
                    return (
                    <article className="entityCard" key={record.column_mapping_id}>
                      <div className="entityHeader">
                        <div>
                          <div className="metricLabel">{record.column_mapping_id}</div>
                          <h3>
                            {record.source_system_id} / v{record.version}
                          </h3>
                        </div>
                        <span
                          className={`statusPill status-${record.archived ? "archived" : "active"}`}
                        >
                          {archiveCopy(record.archived)}
                        </span>
                      </div>
                      <div className="metaGrid">
                        <div className="metaItem">
                          <div className="metricLabel">Dataset contract</div>
                          <div>{record.dataset_contract_id}</div>
                        </div>
                        <div className="metaItem">
                          <div className="metricLabel">Rules</div>
                          <div>{record.rules.length}</div>
                        </div>
                        <div className="metaItem">
                          <div className="metricLabel">Source assets</div>
                          <div>{boundSourceAssets.length}</div>
                          <div className="muted">
                            {referenceSummary(boundSourceAssets, "source_asset_id")}
                          </div>
                        </div>
                        <div className="metaItem">
                          <div className="metricLabel">Archive impact</div>
                          <div className="muted">
                            {record.archived && boundSourceAssets.length > 0
                              ? "Archived version is still referenced by saved source assets."
                              : "No bound source assets depend on this version."}
                          </div>
                        </div>
                        <div className="metaItem spanTwo">
                          <div className="metricLabel">Specification</div>
                          <pre className="specBlock">{formatRulesSpec(record.rules)}</pre>
                        </div>
                      </div>
                      <div className="buttonRow">
                        <Link
                          className="ghostButton"
                          href={`/control/catalog?mapping_clone=${record.column_mapping_id}`}
                        >
                          Create next version
                        </Link>
                        <form
                          action={`/control/catalog/column-mappings/${record.column_mapping_id}/archive`}
                          method="post"
                        >
                          <input
                            name="archived"
                            type="hidden"
                            value={record.archived ? "false" : "true"}
                          />
                          <button className="ghostButton" type="submit">
                            {record.archived ? "Restore version" : "Archive version"}
                          </button>
                        </form>
                      </div>
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
                  <h2>Transformation packages</h2>
                </div>
              </div>
              {transformationPackages.length === 0 ? (
                <div className="empty">No transformation packages.</div>
              ) : (
                <div className="stack compactStack">
                  {transformationPackages.map((record) => (
                    <div className="metaItem" key={record.transformation_package_id}>
                      <div className="metricLabel">{record.transformation_package_id}</div>
                      <div className="muted">
                        {record.handler_key} / v{record.version}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </article>
          </div>
        </section>
      </section>
    </AppShell>
  );
}
