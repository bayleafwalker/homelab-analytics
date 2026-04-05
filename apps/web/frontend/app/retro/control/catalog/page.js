import Link from "next/link";
import { redirect } from "next/navigation";

import { RetroShell } from "@/components/retro-shell";
import {
  getColumnMappings,
  getCurrentUser,
  getDatasetContracts,
  getExtensionRegistrySources,
  getPublicationDefinitions,
  getSourceAssets,
  getSourceSystems,
  getTransformationPackages,
} from "@/lib/backend";

export default async function RetroControlCatalogPage() {
  const user = await getCurrentUser();
  if (user.role !== "admin") {
    redirect("/retro");
  }

  const [
    sourceSystems,
    sourceAssets,
    datasetContracts,
    columnMappings,
    extensionRegistrySources,
    transformationPackages,
    publicationDefinitions,
  ] = await Promise.all([
    getSourceSystems(),
    getSourceAssets({ includeArchived: true }),
    getDatasetContracts({ includeArchived: true }),
    getColumnMappings({ includeArchived: true }),
    getExtensionRegistrySources({ includeArchived: true }),
    getTransformationPackages({ includeArchived: true }),
    getPublicationDefinitions({ includeArchived: true }),
  ]);

  return (
    <RetroShell
      currentPath="/retro/control/catalog"
      user={user}
      title="CRT Control / Catalog"
      eyebrow="Admin GUI"
      lede="Landing bindings, contracts, mappings, extension sources, and publication packages rendered as a condensed retro control catalog."
    >
      <section className="retroMetricGrid">
        <article className="retroMetricBox retroPanel"><span className="retroMetricLabel">Source Systems</span><strong>{sourceSystems.length}</strong></article>
        <article className="retroMetricBox retroPanel"><span className="retroMetricLabel">Source Assets</span><strong>{sourceAssets.length}</strong></article>
        <article className="retroMetricBox retroPanel"><span className="retroMetricLabel">Contracts / Mappings</span><strong>{datasetContracts.length} / {columnMappings.length}</strong></article>
        <article className="retroMetricBox retroPanel"><span className="retroMetricLabel">Packages / Publications</span><strong>{transformationPackages.length} / {publicationDefinitions.length}</strong></article>
      </section>

      <section className="retroSplit">
        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Ingestion Graph</div>
              <h2>Systems and assets</h2>
            </div>
            <Link className="retroActionLink" href="/control/catalog">
              Classic catalog
            </Link>
          </div>
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>System</th>
                  <th>Transport</th>
                  <th>Schedule</th>
                </tr>
              </thead>
              <tbody>
                {sourceSystems.slice(0, 8).map((record) => (
                  <tr key={record.source_system_id}>
                    <td>{record.name}</td>
                    <td>{record.transport}</td>
                    <td>{record.schedule_mode}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Contract</th>
                  <th>Mapping</th>
                </tr>
              </thead>
              <tbody>
                {sourceAssets.slice(0, 8).map((record) => (
                  <tr key={record.source_asset_id}>
                    <td>{record.name}</td>
                    <td>{record.dataset_contract_id}</td>
                    <td>{record.column_mapping_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Schema Catalog</div>
              <h2>Contracts and mappings</h2>
            </div>
          </div>
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>Dataset Contract</th>
                  <th>Version</th>
                  <th>Extra Columns</th>
                </tr>
              </thead>
              <tbody>
                {datasetContracts.slice(0, 8).map((record) => (
                  <tr key={record.dataset_contract_id}>
                    <td>{record.dataset_name}</td>
                    <td>{record.version}</td>
                    <td>{record.allow_extra_columns ? "allowed" : "strict"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>Mapping</th>
                  <th>Contract</th>
                  <th>Rules</th>
                </tr>
              </thead>
              <tbody>
                {columnMappings.slice(0, 8).map((record) => (
                  <tr key={record.column_mapping_id}>
                    <td>{record.column_mapping_id}</td>
                    <td>{record.dataset_contract_id}</td>
                    <td>{record.rules.length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>

      <section className="retroSplit">
        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Extension Mesh</div>
              <h2>Registry sources</h2>
            </div>
          </div>
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Kind</th>
                  <th>Enabled</th>
                </tr>
              </thead>
              <tbody>
                {extensionRegistrySources.slice(0, 8).map((record) => (
                  <tr key={record.extension_registry_source_id}>
                    <td>{record.name}</td>
                    <td>{record.source_kind}</td>
                    <td>{record.enabled ? "yes" : "no"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Publication Mesh</div>
              <h2>Packages and definitions</h2>
            </div>
          </div>
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>Package</th>
                  <th>Handler</th>
                  <th>Version</th>
                </tr>
              </thead>
              <tbody>
                {transformationPackages.slice(0, 8).map((record) => (
                  <tr key={record.transformation_package_id}>
                    <td>{record.name}</td>
                    <td>{record.handler_key}</td>
                    <td>{record.version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>Publication</th>
                  <th>Key</th>
                  <th>Package</th>
                </tr>
              </thead>
              <tbody>
                {publicationDefinitions.slice(0, 8).map((record) => (
                  <tr key={record.publication_definition_id}>
                    <td>{record.name}</td>
                    <td>{record.publication_key}</td>
                    <td>{record.transformation_package_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </RetroShell>
  );
}
