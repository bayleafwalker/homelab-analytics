"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

function scenarioLabel(snapshot, fallbackId) {
  if (!snapshot) {
    return fallbackId || "Unknown scenario";
  }
  const type = snapshot.scenario_type ? ` (${snapshot.scenario_type})` : "";
  return `${snapshot.label || fallbackId || "Unknown scenario"}${type}`;
}

async function readErrorMessage(response, fallback) {
  try {
    const payload = await response.json();
    return payload?.detail || payload?.error || fallback;
  } catch {
    return fallback;
  }
}

export function SavedScenarioCompareSets({
  scenarios,
  initialSavedSets = [],
  leftScenarioId,
  rightScenarioId,
}) {
  const [savedSets, setSavedSets] = useState(() => initialSavedSets);
  const [setLabel, setSetLabel] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [renameDrafts, setRenameDrafts] = useState(() =>
    Object.fromEntries(initialSavedSets.map((row) => [row.compare_set_id, row.label || ""])),
  );
  const [pendingCompareSetId, setPendingCompareSetId] = useState("");

  const scenarioById = useMemo(() => {
    return new Map(scenarios.map((row) => [row.scenario_id, row]));
  }, [scenarios]);

  const activeSets = useMemo(
    () => savedSets.filter((row) => row.status !== "archived"),
    [savedSets],
  );
  const archivedSets = useMemo(
    () => savedSets.filter((row) => row.status === "archived"),
    [savedSets],
  );

  const leftScenario = scenarioById.get(leftScenarioId);
  const rightScenario = scenarioById.get(rightScenarioId);
  const defaultLabel = useMemo(() => {
    return `Compare: ${scenarioLabel(leftScenario, leftScenarioId)} vs ${scenarioLabel(
      rightScenario,
      rightScenarioId,
    )}`;
  }, [leftScenario, leftScenarioId, rightScenario, rightScenarioId]);

  useEffect(() => {
    setSavedSets(initialSavedSets);
  }, [initialSavedSets]);

  useEffect(() => {
    setRenameDrafts(
      Object.fromEntries(initialSavedSets.map((row) => [row.compare_set_id, row.label || ""])),
    );
  }, [initialSavedSets]);

  useEffect(() => {
    setSetLabel(defaultLabel);
    setError("");
  }, [defaultLabel]);

  const currentPairReady = Boolean(
    leftScenarioId && rightScenarioId && leftScenarioId !== rightScenarioId,
  );
  const sameScenarioSelected = Boolean(
    leftScenarioId && rightScenarioId && leftScenarioId === rightScenarioId,
  );
  const currentPairDescription = currentPairReady
    ? `${scenarioLabel(leftScenario, leftScenarioId)} and ${scenarioLabel(
        rightScenario,
        rightScenarioId,
      )}`
    : sameScenarioSelected
      ? "Pick two different scenarios before saving a shared compare set."
      : "Pick two scenarios before saving a shared compare set.";

  function persistSavedSets(nextSavedSets) {
    setSavedSets((currentSavedSets) =>
      typeof nextSavedSets === "function" ? nextSavedSets(currentSavedSets) : nextSavedSets,
    );
  }

  function persistSavedSetRow(savedSet) {
    persistSavedSets((currentSavedSets) => [
      savedSet,
      ...currentSavedSets.filter((row) => row.compare_set_id !== savedSet.compare_set_id),
    ]);
    setRenameDrafts((currentDrafts) => ({
      ...currentDrafts,
      [savedSet.compare_set_id]: savedSet.label || "",
    }));
  }

  async function saveCurrentPair(event) {
    event.preventDefault();
    if (!currentPairReady || isSaving) {
      return;
    }
    setIsSaving(true);
    setError("");
    const label = setLabel.trim() || defaultLabel;

    try {
      const response = await fetch("/api/scenarios/compare-sets", {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({
          left_scenario_id: leftScenarioId,
          right_scenario_id: rightScenarioId,
          label,
        }),
      });

      if (!response.ok) {
        throw new Error(
          await readErrorMessage(response, "Could not save the compare set."),
        );
      }

      const savedSet = await response.json();
      persistSavedSetRow(savedSet);
      setSetLabel(savedSet.label || label);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Could not save the compare set.");
    } finally {
      setIsSaving(false);
    }
  }

  async function renameSavedSet(compareSetId) {
    const nextLabel = (renameDrafts[compareSetId] || "").trim();
    if (!nextLabel) {
      setError("Compare set label cannot be empty.");
      return;
    }
    setPendingCompareSetId(compareSetId);
    setError("");
    try {
      const response = await fetch(`/api/scenarios/compare-sets/${compareSetId}`, {
        method: "PATCH",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({ label: nextLabel }),
      });
      if (!response.ok) {
        throw new Error(
          await readErrorMessage(response, "Could not rename the compare set."),
        );
      }
      const savedSet = await response.json();
      persistSavedSetRow(savedSet);
    } catch (removeError) {
      setError(removeError instanceof Error ? removeError.message : "Could not rename the compare set.");
    } finally {
      setPendingCompareSetId("");
    }
  }

  async function archiveSavedSet(compareSetId) {
    setPendingCompareSetId(compareSetId);
    setError("");
    try {
      const response = await fetch(`/api/scenarios/compare-sets/${compareSetId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(
          await readErrorMessage(response, "Could not archive the compare set."),
        );
      }
      const archivedSet = await response.json();
      persistSavedSets((currentSavedSets) =>
        currentSavedSets.map((row) =>
          row.compare_set_id === archivedSet.compare_set_id
            ? { ...row, status: "archived" }
            : row,
        ),
      );
    } catch (archiveError) {
      setError(
        archiveError instanceof Error ? archiveError.message : "Could not archive the compare set.",
      );
    } finally {
      setPendingCompareSetId("");
    }
  }

  async function restoreSavedSet(compareSetId) {
    setPendingCompareSetId(compareSetId);
    setError("");
    try {
      const response = await fetch(`/api/scenarios/compare-sets/${compareSetId}/restore`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(
          await readErrorMessage(response, "Could not restore the compare set."),
        );
      }
      const restoredSet = await response.json();
      persistSavedSets((currentSavedSets) =>
        currentSavedSets.map((row) =>
          row.compare_set_id === restoredSet.compare_set_id
            ? { ...row, status: "active" }
            : row,
        ),
      );
    } catch (restoreError) {
      setError(
        restoreError instanceof Error
          ? restoreError.message
          : "Could not restore the compare set.",
      );
    } finally {
      setPendingCompareSetId("");
    }
  }

  return (
    <article className="panel section">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">Shared compare sets</div>
          <h2>Saved compare shortcuts</h2>
        </div>
      </div>

      <div className="stack">
        <p className="muted">
          Save a recurring pair once and reopen it later from this deployment, not just this browser.
        </p>

        <form className="stack" onSubmit={saveCurrentPair} style={{ gap: "0.85rem" }}>
          <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
            <label className="stack" style={{ gap: "0.35rem" }}>
              <span className="eyebrow">Set label</span>
              <input
                aria-label="Saved compare set label"
                className="panel"
                style={{ padding: "0.8rem 0.9rem", borderRadius: "10px", width: "100%" }}
                value={setLabel}
                onChange={(event) => setSetLabel(event.target.value)}
                placeholder={defaultLabel}
                type="text"
              />
            </label>

            <div className="panel" style={{ padding: "0.8rem 0.9rem" }}>
              <div className="eyebrow">Current pair</div>
              <div>{currentPairDescription}</div>
            </div>
          </div>

          {error ? (
            <p className="muted" style={{ color: "var(--warn)" }}>
              {error}
            </p>
          ) : null}

          <div className="buttonRow">
            <button
              className="primaryButton inlineButton"
              type="submit"
              disabled={!currentPairReady || isSaving}
            >
              {isSaving ? "Saving..." : "Save compare set"}
            </button>
          </div>
        </form>

        {activeSets.length === 0 && archivedSets.length === 0 ? (
          <p className="muted">No shared compare sets yet.</p>
        ) : (
          <div className="stack">
            <div className="stack">
              <div className="buttonRow" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0 }}>Active compare sets</h3>
                {archivedSets.length > 0 ? (
                  <button
                    className="ghostButton inlineButton"
                    type="button"
                    onClick={() => setShowArchived((current) => !current)}
                  >
                    {showArchived
                      ? "Hide archived compare sets"
                      : `Show archived compare sets (${archivedSets.length})`}
                  </button>
                ) : null}
              </div>

              {activeSets.length === 0 ? (
                <p className="muted">No active shared compare sets yet.</p>
              ) : (
                <div className="stack">
                  {activeSets.map((savedSet) => {
                    const leftLabel =
                      scenarioById.get(savedSet.left_scenario_id)?.label ||
                      savedSet.left_scenario_label ||
                      savedSet.left_scenario_id;
                    const rightLabel =
                      scenarioById.get(savedSet.right_scenario_id)?.label ||
                      savedSet.right_scenario_label ||
                      savedSet.right_scenario_id;
                    const compareHref = `/scenarios/compare?left=${encodeURIComponent(
                      savedSet.left_scenario_id,
                    )}&right=${encodeURIComponent(savedSet.right_scenario_id)}`;

                    return (
                      <article
                        className="panel"
                        key={savedSet.compare_set_id}
                        style={{ padding: "0.9rem 1rem", display: "grid", gap: "0.65rem" }}
                      >
                        <div className="buttonRow" style={{ justifyContent: "space-between" }}>
                          <div>
                            <div className="eyebrow">{savedSet.label}</div>
                            <div className="muted" style={{ fontSize: "0.95rem" }}>
                              {leftLabel} vs {rightLabel}
                            </div>
                          </div>
                          <span className="muted" style={{ alignSelf: "center", fontSize: "0.82rem" }}>
                            {savedSet.created_at ? savedSet.created_at.slice(0, 10) : "—"}
                          </span>
                        </div>

                        <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
                          <label className="stack" style={{ gap: "0.35rem" }}>
                            <span className="eyebrow">Rename compare set</span>
                            <input
                              aria-label={`Rename compare set ${savedSet.compare_set_id}`}
                              className="panel"
                              style={{ padding: "0.75rem 0.9rem", borderRadius: "10px", width: "100%" }}
                              value={renameDrafts[savedSet.compare_set_id] ?? savedSet.label ?? ""}
                              onChange={(event) =>
                                setRenameDrafts((currentDrafts) => ({
                                  ...currentDrafts,
                                  [savedSet.compare_set_id]: event.target.value,
                                }))
                              }
                              type="text"
                            />
                          </label>
                          <div className="panel" style={{ padding: "0.8rem 0.9rem" }}>
                            <div className="eyebrow">Status</div>
                            <div>{savedSet.status || "active"}</div>
                          </div>
                        </div>

                        <div className="buttonRow">
                          <Link className="ghostButton inlineButton" href={compareHref}>
                            Open compare set
                          </Link>
                          <button
                            className="ghostButton inlineButton"
                            type="button"
                            onClick={() => renameSavedSet(savedSet.compare_set_id)}
                            disabled={pendingCompareSetId === savedSet.compare_set_id}
                          >
                            {pendingCompareSetId === savedSet.compare_set_id ? "Saving..." : "Rename compare set"}
                          </button>
                          <button
                            className="ghostButton inlineButton"
                            type="button"
                            onClick={() => archiveSavedSet(savedSet.compare_set_id)}
                            disabled={pendingCompareSetId === savedSet.compare_set_id}
                          >
                            Archive compare set
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}

              {showArchived && archivedSets.length > 0 ? (
                <div className="stack">
                  <div className="buttonRow" style={{ justifyContent: "space-between", alignItems: "center" }}>
                    <h3 style={{ margin: 0 }}>Archived compare sets</h3>
                    <span className="muted">{archivedSets.length} archived</span>
                  </div>
                  <div className="stack">
                    {archivedSets.map((savedSet) => {
                      const leftLabel =
                        scenarioById.get(savedSet.left_scenario_id)?.label ||
                        savedSet.left_scenario_label ||
                        savedSet.left_scenario_id;
                      const rightLabel =
                        scenarioById.get(savedSet.right_scenario_id)?.label ||
                        savedSet.right_scenario_label ||
                        savedSet.right_scenario_id;
                      const compareHref = `/scenarios/compare?left=${encodeURIComponent(
                        savedSet.left_scenario_id,
                      )}&right=${encodeURIComponent(savedSet.right_scenario_id)}`;

                      return (
                        <article
                          className="panel"
                          key={savedSet.compare_set_id}
                          style={{ padding: "0.9rem 1rem", display: "grid", gap: "0.65rem" }}
                        >
                          <div className="buttonRow" style={{ justifyContent: "space-between" }}>
                            <div>
                              <div className="eyebrow">{savedSet.label}</div>
                              <div className="muted" style={{ fontSize: "0.95rem" }}>
                                {leftLabel} vs {rightLabel}
                              </div>
                            </div>
                            <span className="muted" style={{ alignSelf: "center", fontSize: "0.82rem" }}>
                              {savedSet.created_at ? savedSet.created_at.slice(0, 10) : "—"}
                            </span>
                          </div>

                          <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
                            <label className="stack" style={{ gap: "0.35rem" }}>
                              <span className="eyebrow">Rename compare set</span>
                              <input
                                aria-label={`Rename compare set ${savedSet.compare_set_id}`}
                                className="panel"
                                style={{ padding: "0.75rem 0.9rem", borderRadius: "10px", width: "100%" }}
                                value={renameDrafts[savedSet.compare_set_id] ?? savedSet.label ?? ""}
                                onChange={(event) =>
                                  setRenameDrafts((currentDrafts) => ({
                                    ...currentDrafts,
                                    [savedSet.compare_set_id]: event.target.value,
                                  }))
                                }
                                type="text"
                              />
                            </label>
                            <div className="panel" style={{ padding: "0.8rem 0.9rem" }}>
                              <div className="eyebrow">Status</div>
                              <div>{savedSet.status || "archived"}</div>
                            </div>
                          </div>

                          <div className="buttonRow">
                            <Link className="ghostButton inlineButton" href={compareHref}>
                              Open compare set
                            </Link>
                            <button
                              className="ghostButton inlineButton"
                              type="button"
                              onClick={() => renameSavedSet(savedSet.compare_set_id)}
                              disabled={pendingCompareSetId === savedSet.compare_set_id}
                            >
                              {pendingCompareSetId === savedSet.compare_set_id ? "Saving..." : "Rename compare set"}
                            </button>
                            <button
                              className="ghostButton inlineButton"
                              type="button"
                              onClick={() => restoreSavedSet(savedSet.compare_set_id)}
                              disabled={pendingCompareSetId === savedSet.compare_set_id}
                            >
                              Restore compare set
                            </button>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                </div>
              ) : null}
              {archivedSets.length > 0 && !showArchived ? (
                <p className="muted">Archived compare sets are hidden until you expand the archived section.</p>
              ) : null}
            </div>
          </div>
        )}
      </div>
    </article>
  );
}
