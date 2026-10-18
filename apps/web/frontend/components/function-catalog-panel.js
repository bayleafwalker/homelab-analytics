import { ResponsiveTable } from "./responsive-table";

function totalFunctions(functionsByKind) {
  return Object.values(functionsByKind || {}).reduce(
    (count, functions) => count + (Array.isArray(functions) ? functions.length : 0),
    0
  );
}

function boolCopy(value) {
  return value ? "yes" : "no";
}

const FUNCTION_COLUMNS = [
  { key: "function_key", header: "Function key", primary: true },
  { key: "source", header: "Source" },
  { key: "module", header: "Module" },
  { key: "io", header: "Input / output", cell: (record) => `${record.input_type} / ${record.output_type}` },
  { key: "deterministic", header: "Deterministic", cell: (record) => boolCopy(record.deterministic) },
  { key: "side_effects", header: "Side effects", cell: (record) => boolCopy(record.side_effects) },
  { key: "description", header: "Description" },
];

export function FunctionCatalogPanel({ functionsByKind }) {
  const kindEntries = Object.entries(functionsByKind || {}).filter(([, functions]) =>
    Array.isArray(functions)
  );
  const functionCount = totalFunctions(functionsByKind);
  const columnMappingFunctions = functionsByKind?.column_mapping_value || [];

  return (
    <article className="panel section">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">Extensibility</div>
          <h2>Custom functions</h2>
        </div>
      </div>
      <div className="metaGrid">
        <div className="metaItem">
          <div className="metricLabel">Loaded functions</div>
          <div>{functionCount}</div>
        </div>
        <div className="metaItem">
          <div className="metricLabel">Column mapping functions</div>
          <div>{columnMappingFunctions.length}</div>
        </div>
        <div className="metaItem spanTwo">
          <div className="metricLabel">Binding note</div>
          <div className="muted">
            Configured CSV column mappings can bind a registered{" "}
            <code>function_key</code> as the optional fourth mapping-rule field.
          </div>
        </div>
      </div>
      {functionCount === 0 ? (
        <div className="empty">
          No active custom functions are loaded from external registry revisions.
        </div>
      ) : (
        <div className="stack compactStack">
          {kindEntries.map(([kind, functions]) => (
            <div key={kind} className="stack compactStack">
              <div className="metricLabel">{kind}</div>
              <ResponsiveTable
                label={`Custom ${kind} functions`}
                rows={functions}
                rowKey={(record) => `${kind}-${record.function_key}`}
                columns={FUNCTION_COLUMNS}
              />
            </div>
          ))}
        </div>
      )}
    </article>
  );
}
