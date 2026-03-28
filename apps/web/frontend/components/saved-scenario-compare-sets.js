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

  const scenarioById = useMemo(() => {
    return new Map(scenarios.map((row) => [row.scenario_id, row]));
  }, [scenarios]);

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
      persistSavedSets((currentSavedSets) => [
        savedSet,
        ...currentSavedSets.filter(
          (row) => row.compare_set_id !== savedSet.compare_set_id,
        ),
      ]);
      setSetLabel(savedSet.label || label);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Could not save the compare set.");
    } finally {
      setIsSaving(false);
    }
  }

  async function removeSavedSet(compareSetId) {
    setError("");
    try {
      const response = await fetch(`/api/scenarios/compare-sets/${compareSetId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(
          await readErrorMessage(response, "Could not remove the compare set."),
        );
      }
      persistSavedSets((currentSavedSets) =>
        currentSavedSets.filter((row) => row.compare_set_id !== compareSetId),
      );
    } catch (removeError) {
      setError(
        removeError instanceof Error ? removeError.message : "Could not remove the compare set.",
      );
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

        {savedSets.length === 0 ? (
          <p className="muted">No shared compare sets yet.</p>
        ) : (
          <div className="stack">
            {savedSets.map((savedSet) => {
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

                  <div className="buttonRow">
                    <Link className="ghostButton inlineButton" href={compareHref}>
                      Open compare set
                    </Link>
                    <button
                      className="ghostButton inlineButton"
                      type="button"
                      onClick={() => removeSavedSet(savedSet.compare_set_id)}
                    >
                      Remove
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </article>
  );
}
