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
    case "source-asset-created":
      return "Source asset created.";
    default:
      return "";
  }
}

function errorCopy(error) {
  switch (error) {
    case "source-system-failed":
      return "Could not create the source system.";
    case "source-asset-failed":
      return "Could not create the source asset.";
    default:
      return "";
  }
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
  const notice = noticeCopy(searchParams?.notice);
  const error = errorCopy(searchParams?.error);

  return (
    <AppShell
      currentPath="/control"
      user={user}
      title="Control Catalog"
      eyebrow="Admin Access"
      lede="Source registration stays API-backed: register source systems, bind source assets, and inspect the contracts that drive ingestion."
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
            <div className="field spanThree">
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
          {sourceSystems.length === 0 || datasetContracts.length === 0 || columnMappings.length === 0 ? (
            <div className="empty">
              Source asset creation requires at least one source system, dataset contract, and
              column mapping.
            </div>
          ) : (
            <form className="formGrid threeCol" action="/control/catalog/source-assets" method="post">
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
                <label htmlFor="source-system-select">Source system</label>
                <select id="source-system-select" name="source_system_id" required defaultValue="">
                  <option value="" disabled>
                    Select source system
                  </option>
                  {sourceSystems.map((record) => (
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

        <section className="layout">
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
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Id</th>
                      <th>Name</th>
                      <th>Type</th>
                      <th>Transport</th>
                      <th>Schedule</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sourceSystems.map((record) => (
                      <tr key={record.source_system_id}>
                        <td>{record.source_system_id}</td>
                        <td>{record.name}</td>
                        <td>{record.source_type}</td>
                        <td>{record.transport}</td>
                        <td>{record.schedule_mode}</td>
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
                <div className="eyebrow">Bindings</div>
                <h2>Source assets</h2>
              </div>
            </div>
            {sourceAssets.length === 0 ? (
              <div className="empty">No source assets registered yet.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Id</th>
                      <th>Name</th>
                      <th>Contract</th>
                      <th>Mapping</th>
                      <th>Package</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sourceAssets.map((record) => (
                      <tr key={record.source_asset_id}>
                        <td>{record.source_asset_id}</td>
                        <td>{record.name}</td>
                        <td>{record.dataset_contract_id}</td>
                        <td>{record.column_mapping_id}</td>
                        <td>{record.transformation_package_id || "n/a"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </article>
        </section>

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
              <div className="stack">
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
            <div className="stack">
              <div className="metaGrid">
                <div>
                  <div className="metricLabel">Column mappings</div>
                  <div className="stack compactStack">
                    {columnMappings.length === 0 ? (
                      <div className="empty">No mappings.</div>
                    ) : (
                      columnMappings.map((record) => (
                        <div className="metaItem" key={record.column_mapping_id}>
                          <div>{record.column_mapping_id}</div>
                          <div className="muted">
                            {record.source_system_id} / {record.dataset_contract_id}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
                <div>
                  <div className="metricLabel">Transformation packages</div>
                  <div className="stack compactStack">
                    {transformationPackages.length === 0 ? (
                      <div className="empty">No packages.</div>
                    ) : (
                      transformationPackages.map((record) => (
                        <div className="metaItem" key={record.transformation_package_id}>
                          <div>{record.transformation_package_id}</div>
                          <div className="muted">{record.handler_key}</div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          </article>
        </section>
      </section>
    </AppShell>
  );
}
