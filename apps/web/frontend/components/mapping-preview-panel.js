"use client";

import { useState } from "react";

function initialMappingIdForContract(columnMappings, datasetContractId) {
  return (
    columnMappings.find((record) => record.dataset_contract_id === datasetContractId)
      ?.column_mapping_id || ""
  );
}

export function MappingPreviewPanel({
  datasetContracts,
  columnMappings,
  initialContractId = "",
  initialMappingId = ""
}) {
  const resolvedInitialContractId =
    initialContractId || datasetContracts[0]?.dataset_contract_id || "";
  const [datasetContractId, setDatasetContractId] = useState(resolvedInitialContractId);
  const [columnMappingId, setColumnMappingId] = useState(
    initialMappingId || initialMappingIdForContract(columnMappings, resolvedInitialContractId)
  );
  const [sampleCsv, setSampleCsv] = useState("");
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const filteredMappings = columnMappings.filter(
    (record) => record.dataset_contract_id === datasetContractId
  );

  async function submitPreview(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");
    try {
      const response = await fetch("/control/catalog/preview", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          dataset_contract_id: datasetContractId,
          column_mapping_id: columnMappingId,
          sample_csv: sampleCsv,
          preview_limit: 5
        })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || payload.detail || "Preview failed.");
      }
      setPreview(payload.preview || null);
    } catch (previewError) {
      setPreview(null);
      setError(previewError.message || "Preview failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="stack compactStack">
      <form className="formGrid threeCol" onSubmit={submitPreview}>
        <div className="field">
          <label htmlFor="preview-contract">Dataset contract</label>
          <select
            id="preview-contract"
            value={datasetContractId}
            onChange={(event) => {
              const nextContractId = event.target.value;
              setDatasetContractId(nextContractId);
              setColumnMappingId(initialMappingIdForContract(columnMappings, nextContractId));
            }}
          >
            {datasetContracts.map((record) => (
              <option key={record.dataset_contract_id} value={record.dataset_contract_id}>
                {record.dataset_contract_id}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="preview-mapping">Column mapping</label>
          <select
            id="preview-mapping"
            value={columnMappingId}
            onChange={(event) => setColumnMappingId(event.target.value)}
          >
            {filteredMappings.map((record) => (
              <option key={record.column_mapping_id} value={record.column_mapping_id}>
                {record.column_mapping_id}
              </option>
            ))}
          </select>
        </div>
        <div className="buttonRow">
          <button className="primaryButton inlineButton" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Previewing..." : "Preview mapping"}
          </button>
        </div>
        <div className="field spanThree">
          <label htmlFor="preview-sample">Sample CSV</label>
          <textarea
            id="preview-sample"
            value={sampleCsv}
            onChange={(event) => setSampleCsv(event.target.value)}
            placeholder={"booking_date,account_number,payee,amount_eur,memo\n2026-01-01,000123,Corner Store,-12.50,Groceries"}
            rows={8}
            required
          />
        </div>
      </form>

      {error ? <div className="errorBanner">{error}</div> : null}

      {preview ? (
        <div className="stack compactStack">
          <div className="metaGrid">
            <div className="metaItem">
              <div className="metricLabel">Source header</div>
              <div className="muted">{preview.source_header.join(", ") || "n/a"}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Mapped header</div>
              <div className="muted">{preview.mapped_header.join(", ") || "n/a"}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Sample rows</div>
              <div>{preview.sample_row_count}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Validation</div>
              <div>{preview.issues.length === 0 ? "passed" : `${preview.issues.length} issue(s)`}</div>
            </div>
          </div>

          {preview.preview_rows.length === 0 ? (
            <div className="empty">No mapped rows were produced from the sample.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    {preview.mapped_header.map((column) => (
                      <th key={column}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.preview_rows.map((row, index) => (
                    <tr key={`preview-row-${index}`}>
                      {preview.mapped_header.map((column) => (
                        <td key={`${column}-${index}`}>{row[column] || ""}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {preview.issues.length > 0 ? (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Message</th>
                    <th>Column</th>
                    <th>Row</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.issues.map((issue, index) => (
                    <tr key={`preview-issue-${index}-${issue.code}`}>
                      <td>{issue.code}</td>
                      <td>{issue.message}</td>
                      <td>{issue.column || "n/a"}</td>
                      <td>{issue.row_number || "n/a"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="empty">
          Paste a sample CSV and preview the saved contract and mapping before rebinding a source
          asset or uploading a file.
        </div>
      )}
    </div>
  );
}
