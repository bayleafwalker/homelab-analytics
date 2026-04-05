"use client";

import React, { useMemo, useRef, useState } from "react";

const MANUAL_TARGETS = [
  { uploadPath: "/upload/account-transactions", label: "Account transactions" },
  { uploadPath: "/upload/subscriptions", label: "Subscriptions" },
  { uploadPath: "/upload/contract-prices", label: "Contract prices" },
  { uploadPath: "/upload/budgets", label: "Budgets" },
  { uploadPath: "/upload/loan-repayments", label: "Loan repayments" },
  { uploadPath: "/upload/ha-states", label: "HA states (JSON)" },
  {
    uploadPath: "/upload/configured-csv",
    label: "Configured CSV upload",
    requiresSourceAsset: true
  }
];

function formatConfidenceLabel(candidate) {
  const label = candidate?.confidence_label;
  const score = Number(candidate?.confidence_score || 0);
  if (!label) {
    return "";
  }
  return `${label} (${Math.round(score * 100)}%)`;
}

function isConfiguredUpload(uploadPath) {
  return uploadPath === "/upload/configured-csv";
}

function appendUnique(values, nextValue) {
  if (!nextValue || values.includes(nextValue)) {
    return values;
  }
  return [...values, nextValue];
}

function asStringArray(value) {
  return Array.isArray(value)
    ? value
        .map((entry) => String(entry || "").trim())
        .filter(Boolean)
    : [];
}

function mappingStatus(matchedColumns, missingColumns) {
  if (matchedColumns.length === 0) {
    return "No mapped canonical fields";
  }
  if (missingColumns.length === 0) {
    return "Ready to ingest";
  }
  return `Needs review (${missingColumns.length} missing field${missingColumns.length === 1 ? "" : "s"})`;
}

function formatIssueLocation(issue) {
  const parts = [];
  if (issue?.column) {
    parts.push(`column ${issue.column}`);
  }
  if (issue?.row_number) {
    parts.push(`row ${issue.row_number}`);
  }
  return parts.join(" / ");
}

function formatDateRangeLabel(dateRange) {
  if (!dateRange?.start || !dateRange?.end) {
    return "n/a";
  }
  const column = dateRange?.column ? ` (${dateRange.column})` : "";
  return `${dateRange.start} to ${dateRange.end}${column}`;
}

export function UploadDetectionWizard({ activeSourceAssets }) {
  const fileInputRef = useRef(null);
  const detectRequestIdRef = useRef(0);
  const dryRunRequestIdRef = useRef(0);
  const [sourceName, setSourceName] = useState("manual-upload");
  const [uploadPath, setUploadPath] = useState(MANUAL_TARGETS[0].uploadPath);
  const [sourceAssetId, setSourceAssetId] = useState("");
  const [selectedFileName, setSelectedFileName] = useState("");
  const [detection, setDetection] = useState(null);
  const [detecting, setDetecting] = useState(false);
  const [detectError, setDetectError] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);
  const [dryRunPreview, setDryRunPreview] = useState(null);
  const [dryRunLoading, setDryRunLoading] = useState(false);
  const [dryRunError, setDryRunError] = useState("");
  const [dryRunAccepted, setDryRunAccepted] = useState(false);

  const sourceAssetOptions = useMemo(
    () => activeSourceAssets.map((record) => record.source_asset_id),
    [activeSourceAssets]
  );

  function resetDryRunState() {
    dryRunRequestIdRef.current += 1;
    setDryRunPreview(null);
    setDryRunLoading(false);
    setDryRunError("");
    setDryRunAccepted(false);
  }

  async function detectFile(file) {
    const requestId = detectRequestIdRef.current + 1;
    detectRequestIdRef.current = requestId;
    setDetectError("");
    setDetecting(true);
    resetDryRunState();
    try {
      const formData = new FormData();
      formData.set("file", file);
      const response = await fetch("/upload/detect", {
        method: "POST",
        body: formData
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.error || "Source detection failed.");
      }
      if (requestId !== detectRequestIdRef.current) {
        return;
      }
      const detected = payload?.detection || null;
      setDetection(detected);
      const candidate = detected?.candidate;
      if (candidate?.upload_path) {
        setUploadPath(candidate.upload_path);
      }
      if (candidate?.kind === "configured_csv" && candidate?.source_asset_id) {
        setSourceAssetId(String(candidate.source_asset_id));
      }
    } catch (error) {
      if (requestId !== detectRequestIdRef.current) {
        return;
      }
      setDetection(null);
      setDetectError(error instanceof Error ? error.message : "Source detection failed.");
    } finally {
      if (requestId === detectRequestIdRef.current) {
        setDetecting(false);
      }
    }
  }

  async function runDryRun() {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setDryRunError("Choose a file before running dry-run.");
      return;
    }
    const resolvedUploadPath = uploadPath;
    const requiresSourceAsset = isConfiguredUpload(resolvedUploadPath);
    if (requiresSourceAsset && !sourceAssetId) {
      setDryRunError("Select source asset before running dry-run.");
      return;
    }
    const requestId = dryRunRequestIdRef.current + 1;
    dryRunRequestIdRef.current = requestId;
    setDryRunError("");
    setDryRunLoading(true);
    setDryRunAccepted(false);
    try {
      const formData = new FormData();
      formData.set("file", file);
      formData.set("upload_path", resolvedUploadPath);
      if (requiresSourceAsset) {
        formData.set("source_asset_id", sourceAssetId);
      }
      const response = await fetch("/upload/dry-run", {
        method: "POST",
        body: formData
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.error || "Dry-run preview failed.");
      }
      if (requestId !== dryRunRequestIdRef.current) {
        return;
      }
      setDryRunPreview(payload?.preview || null);
      if (!payload?.preview) {
        setDryRunError("Dry-run preview did not return any data.");
      }
    } catch (error) {
      if (requestId !== dryRunRequestIdRef.current) {
        return;
      }
      setDryRunPreview(null);
      setDryRunError(error instanceof Error ? error.message : "Dry-run preview failed.");
    } finally {
      if (requestId === dryRunRequestIdRef.current) {
        setDryRunLoading(false);
      }
    }
  }

  function syncFileInput(file) {
    const input = fileInputRef.current;
    if (!input || typeof DataTransfer === "undefined") {
      return;
    }
    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
  }

  function acceptSelectedFile(file) {
    setSelectedFileName(file.name || "");
    syncFileInput(file);
    detectFile(file);
  }

  function onFileInputChange(event) {
    const file = event.target.files?.[0];
    if (!file) {
      detectRequestIdRef.current += 1;
      setSelectedFileName("");
      setDetection(null);
      setDetecting(false);
      resetDryRunState();
      return;
    }
    setSelectedFileName(file.name || "");
    detectFile(file);
  }

  function onDrop(event) {
    event.preventDefault();
    setIsDragOver(false);
    const file = event.dataTransfer.files?.[0];
    if (!file) {
      return;
    }
    acceptSelectedFile(file);
  }

  const candidate = detection?.candidate || null;
  const alternatives = Array.isArray(detection?.alternatives)
    ? detection.alternatives
    : [];
  const matchedColumns = asStringArray(candidate?.matched_columns);
  const missingColumns = asStringArray(candidate?.missing_columns);
  const expectedColumns = asStringArray(candidate?.expected_columns);
  const rawCanonicalMatchedColumns = asStringArray(candidate?.canonical_matched_columns);
  const rawCanonicalMissingColumns = asStringArray(candidate?.canonical_missing_columns);
  const rawCanonicalExpectedColumns = asStringArray(candidate?.canonical_expected_columns);
  const hasCanonicalPreview =
    rawCanonicalMatchedColumns.length > 0 ||
    rawCanonicalMissingColumns.length > 0 ||
    rawCanonicalExpectedColumns.length > 0;
  const canonicalMatchedColumns =
    hasCanonicalPreview
      ? rawCanonicalMatchedColumns
      : matchedColumns;
  const canonicalMissingColumns =
    hasCanonicalPreview
      ? rawCanonicalMissingColumns
      : missingColumns;
  const canonicalExpectedColumns =
    hasCanonicalPreview
      ? rawCanonicalExpectedColumns
      : expectedColumns;
  const publicationPreview = candidate?.publication_preview || null;
  const resolvedUploadPath = uploadPath;
  const needsSourceAsset = isConfiguredUpload(resolvedUploadPath);
  const knownSourceAssetIds = appendUnique(
    sourceAssetOptions,
    candidate?.kind === "configured_csv" ? String(candidate?.source_asset_id || "") : ""
  );
  const canRunDryRun =
    selectedFileName &&
    (!needsSourceAsset || Boolean(sourceAssetId));
  const canSubmit = canRunDryRun && Boolean(dryRunPreview) && dryRunAccepted;
  const dryRunIssues = Array.isArray(dryRunPreview?.issues)
    ? dryRunPreview.issues
    : [];

  return (
    <article className="panel section">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">Guided Onboarding</div>
          <h2>Source Type Detection</h2>
        </div>
      </div>
      <div className="muted uploadWizardSummary">
        Drop a file to detect upload target and contract confidence before ingestion.
      </div>

      <form className="formGrid threeCol" action={resolvedUploadPath} method="post" encType="multipart/form-data">
        <div className="field spanTwo">
          <label htmlFor="guided-source-name">Source name</label>
          <input
            id="guided-source-name"
            name="source_name"
            type="text"
            value={sourceName}
            onChange={(event) => setSourceName(event.target.value)}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="guided-upload-target">Upload target</label>
          <select
            id="guided-upload-target"
            value={resolvedUploadPath}
            onChange={(event) => {
              setUploadPath(event.target.value);
              resetDryRunState();
            }}
          >
            {MANUAL_TARGETS.map((target) => (
              <option key={target.uploadPath} value={target.uploadPath}>
                {target.label}
              </option>
            ))}
          </select>
        </div>

        <div
          className="dropZone spanTwo"
          data-active={isDragOver ? "true" : "false"}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragOver(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            setIsDragOver(false);
          }}
          onDrop={onDrop}
        >
          <div className="dropZoneTitle">Drop file here</div>
          <div className="muted">
            or use the file picker. CSV and JSON are detected from content; XLSX can still be
            uploaded manually.
          </div>
          {selectedFileName ? (
            <div className="detectedContract">Selected file: {selectedFileName}</div>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="guided-file">File</label>
          <input
            id="guided-file"
            ref={fileInputRef}
            name="file"
            type="file"
            accept=".csv,.xlsx,.json,text/csv,application/json"
            onChange={onFileInputChange}
            required
          />
        </div>

        {needsSourceAsset ? (
          <div className="field spanTwo">
            <label htmlFor="guided-source-asset">Source asset</label>
            <select
              id="guided-source-asset"
              name="source_asset_id"
              value={sourceAssetId}
              onChange={(event) => {
                setSourceAssetId(event.target.value);
                resetDryRunState();
              }}
              required
            >
              <option value="" disabled>
                Select source asset
              </option>
              {knownSourceAssetIds.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        <div className="spanThree uploadWizardActions">
          <div className="muted">
            Run a validation dry-run before upload. This parses the file without landing.
          </div>
          <div className="uploadWizardActionButtons">
            <button
              className="primaryButton inlineButton"
              type="button"
              onClick={() => {
                runDryRun();
              }}
              disabled={!canRunDryRun || dryRunLoading}
            >
              {dryRunLoading ? "Running dry-run..." : "Run dry-run"}
            </button>
            {dryRunPreview ? (
              <button
                className="primaryButton inlineButton"
                type="button"
                onClick={() => {
                  setDryRunAccepted(false);
                  runDryRun();
                }}
                disabled={dryRunLoading}
              >
                Retry dry-run
              </button>
            ) : null}
            {dryRunPreview ? (
              <button
                className="primaryButton inlineButton"
                type="button"
                onClick={() => setDryRunAccepted(true)}
                disabled={dryRunLoading}
              >
                Accept preview
              </button>
            ) : null}
          </div>
        </div>

        <button className="primaryButton inlineButton" type="submit" disabled={!canSubmit}>
          Upload file
        </button>
      </form>

      {detecting ? <div className="muted">Detecting source type...</div> : null}
      {detectError ? <div className="errorBanner">{detectError}</div> : null}
      {dryRunLoading ? <div className="muted">Running validation dry-run...</div> : null}
      {dryRunError ? <div className="errorBanner">{dryRunError}</div> : null}

      {dryRunPreview ? (
        <div className="stack compactStack uploadWizardPreview">
          <div className="metricLabel">Dry-run preview</div>
          <div className="metaGrid uploadWizardMeta">
            <div className="metaItem">
              <div className="metricLabel">Target</div>
              <div>{dryRunPreview?.target?.title || "n/a"}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Row count</div>
              <div>{Number(dryRunPreview?.row_count || 0)}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Date range</div>
              <div>{formatDateRangeLabel(dryRunPreview?.date_range)}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Detected issues</div>
              <div className={dryRunIssues.length > 0 ? "warnText" : "muted"}>
                {dryRunIssues.length}
              </div>
            </div>
          </div>
          {dryRunIssues.length > 0 ? (
            <div className="stack compactStack uploadWizardIssueList">
              <div className="metricLabel">Dry-run issues</div>
              <div className="entityList">
                {dryRunIssues.map((issue, index) => (
                  <article className="entityCard" key={`${issue.code || "issue"}-${index}`}>
                    <div className="entityHeader">
                      <div>
                        <div className="metricLabel">{issue.code || "validation_issue"}</div>
                        <h3>{issue.message || "Validation issue detected."}</h3>
                      </div>
                      {formatIssueLocation(issue) ? (
                        <span className="statusPill status-rejected">
                          {formatIssueLocation(issue)}
                        </span>
                      ) : null}
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : null}
          {dryRunAccepted ? (
            <div className="successBanner uploadWizardDecision">
              Dry-run accepted. Upload is now enabled.
            </div>
          ) : (
            <div className="muted uploadWizardDecision">
              Decision point: accept the preview to continue or retry dry-run after fixing inputs.
            </div>
          )}
        </div>
      ) : null}

      {candidate ? (
        <div className="metaGrid uploadWizardMeta">
          <div className="metaItem">
            <div className="metricLabel">Detected target</div>
            <div>{candidate.title}</div>
          </div>
          <div className="metaItem">
            <div className="metricLabel">Contract</div>
            <div>{candidate.contract_id}</div>
          </div>
          <div className="metaItem">
            <div className="metricLabel">Confidence</div>
            <div className="confidenceBadge">{formatConfidenceLabel(candidate)}</div>
          </div>
          <div className="metaItem">
            <div className="metricLabel">Matched columns</div>
            <div>{matchedColumns.join(", ") || "n/a"}</div>
          </div>
          <div className="metaItem">
            <div className="metricLabel">Mapping status</div>
            <div className={canonicalMissingColumns.length > 0 ? "warnText" : ""}>
              {mappingStatus(canonicalMatchedColumns, canonicalMissingColumns)}
            </div>
          </div>
        </div>
      ) : null}

      {candidate ? (
        <div className="stack compactStack uploadWizardPreview">
          <div className="metricLabel">Mapping preview</div>
          <div className="metaGrid uploadWizardMeta">
            <div className="metaItem">
              <div className="metricLabel">Canonical fields expected</div>
              <div>{canonicalExpectedColumns.join(", ") || "n/a"}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Canonical fields mapped</div>
              <div>{canonicalMatchedColumns.join(", ") || "n/a"}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Weak or missing fields</div>
              <div className={canonicalMissingColumns.length > 0 ? "warnText" : "muted"}>
                {canonicalMissingColumns.join(", ") || "none"}
              </div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Source columns matched</div>
              <div>{matchedColumns.join(", ") || "n/a"}</div>
            </div>
          </div>
        </div>
      ) : null}

      {candidate ? (
        <div className="stack compactStack uploadWizardPreview">
          <div className="metricLabel">Publication preview</div>
          {!publicationPreview ? (
            <div className="muted">No publication preview available for this source.</div>
          ) : (
            <div className="metaGrid uploadWizardMeta">
              <div className="metaItem">
                <div className="metricLabel">Direct publications</div>
                <div>
                  {Array.isArray(publicationPreview.direct) &&
                  publicationPreview.direct.length > 0
                    ? publicationPreview.direct
                        .map((entry) => entry?.name || entry?.publication_key || "")
                        .filter(Boolean)
                        .join(", ")
                    : "none"}
                </div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Additional refreshed views</div>
                <div>
                  {Array.isArray(publicationPreview.derived) &&
                  publicationPreview.derived.length > 0
                    ? publicationPreview.derived
                        .map((entry) => entry?.name || entry?.publication_key || "")
                        .filter(Boolean)
                        .join(", ")
                    : "none"}
                </div>
                <div className="muted">
                  May require additional source data before showing meaningful values.
                </div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Transformation package</div>
                <div>{publicationPreview.transformation_package_id || "n/a"}</div>
              </div>
            </div>
          )}
        </div>
      ) : null}

      {alternatives.length > 0 ? (
        <div className="stack compactStack">
          <div className="metricLabel">Other possible matches</div>
          <div className="entityList">
            {alternatives.map((record, index) => (
              <article className="entityCard" key={`${record.title || "alt"}-${index}`}>
                <div className="entityHeader">
                  <div>
                    <div className="metricLabel">{record.kind}</div>
                    <h3>{record.title}</h3>
                  </div>
                  <span className="statusPill status-enqueued">
                    {formatConfidenceLabel(record)}
                  </span>
                </div>
                <div className="muted">{record.contract_id}</div>
              </article>
            ))}
          </div>
        </div>
      ) : null}
    </article>
  );
}
