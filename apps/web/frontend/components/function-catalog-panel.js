function totalFunctions(functionsByKind) {
  return Object.values(functionsByKind || {}).reduce(
    (count, functions) => count + (Array.isArray(functions) ? functions.length : 0),
    0
  );
}

function boolCopy(value) {
  return value ? "yes" : "no";
}

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
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Function key</th>
                      <th>Source</th>
                      <th>Module</th>
                      <th>Input / output</th>
                      <th>Deterministic</th>
                      <th>Side effects</th>
                      <th>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {functions.map((record) => (
                      <tr key={`${kind}-${record.function_key}`}>
                        <td>{record.function_key}</td>
                        <td>{record.source}</td>
                        <td>{record.module}</td>
                        <td>
                          {record.input_type} / {record.output_type}
                        </td>
                        <td>{boolCopy(record.deterministic)}</td>
                        <td>{boolCopy(record.side_effects)}</td>
                        <td>{record.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}
