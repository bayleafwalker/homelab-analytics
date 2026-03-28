"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "homelab_scenario_compare_sets_v1";

function readSavedSets() {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeSavedSets(savedSets) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(savedSets));
  } catch {
    // Ignore storage quota and privacy-mode failures.
  }
}

function makeSetId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `compare-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function scenarioLabel(snapshot, fallbackId) {
  if (!snapshot) {
    return fallbackId || "Unknown scenario";
  }
  const type = snapshot.scenario_type ? ` (${snapshot.scenario_type})` : "";
  return `${snapshot.label || fallbackId || "Unknown scenario"}${type}`;
}

export function SavedScenarioCompareSets({
  scenarios,
  leftScenarioId,
  rightScenarioId,
}) {
  const [savedSets, setSavedSets] = useState([]);
  const [setLabel, setSetLabel] = useState("");

  useEffect(() => {
    const nextSavedSets = readSavedSets();
    setSavedSets(nextSavedSets);
  }, []);

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
    setSetLabel(defaultLabel);
  }, [defaultLabel]);

  const currentPairReady = Boolean(leftScenarioId && rightScenarioId);
  const currentPairDescription = currentPairReady
    ? `${scenarioLabel(leftScenario, leftScenarioId)} and ${scenarioLabel(
        rightScenario,
        rightScenarioId,
      )}`
    : "Pick two scenarios before saving a compare set.";

  function persistSavedSets(nextSavedSets) {
    setSavedSets(nextSavedSets);
    writeSavedSets(nextSavedSets);
  }

  function saveCurrentPair(event) {
    event.preventDefault();
    if (!currentPairReady) {
      return;
    }
    const trimmedLabel = setLabel.trim() || defaultLabel;
    const nextSavedSet = {
      id: makeSetId(),
      label: trimmedLabel,
      leftScenarioId,
      rightScenarioId,
      leftScenarioLabel: leftScenario?.label || leftScenarioId,
      rightScenarioLabel: rightScenario?.label || rightScenarioId,
      createdAt: new Date().toISOString(),
    };
    const nextSavedSets = [
      nextSavedSet,
      ...savedSets.filter(
        (savedSet) =>
          !(
            savedSet.leftScenarioId === leftScenarioId &&
            savedSet.rightScenarioId === rightScenarioId
          ),
      ),
    ];
    persistSavedSets(nextSavedSets);
    setSetLabel(trimmedLabel);
  }

  function removeSavedSet(id) {
    const nextSavedSets = savedSets.filter((savedSet) => savedSet.id !== id);
    persistSavedSets(nextSavedSets);
  }

  function clearSavedSets() {
    persistSavedSets([]);
  }

  return (
    <article className="panel section">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">Saved compare sets</div>
          <h2>Browser-local compare shortcuts</h2>
        </div>
      </div>

      <div className="stack">
        <p className="muted">
          Save common scenario pairs in this browser so you can reopen them without reselecting the two sides.
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

          <div className="buttonRow">
            <button className="primaryButton inlineButton" type="submit" disabled={!currentPairReady}>
              Save current pair
            </button>
            <button className="ghostButton inlineButton" type="button" onClick={clearSavedSets}>
              Clear saved sets
            </button>
          </div>
        </form>

        {savedSets.length === 0 ? (
          <p className="muted">No saved compare sets yet.</p>
        ) : (
          <div className="stack">
            {savedSets.map((savedSet) => {
              const leftLabel =
                scenarioById.get(savedSet.leftScenarioId)?.label || savedSet.leftScenarioLabel || savedSet.leftScenarioId;
              const rightLabel =
                scenarioById.get(savedSet.rightScenarioId)?.label || savedSet.rightScenarioLabel || savedSet.rightScenarioId;
              const compareHref = `/scenarios/compare?left=${encodeURIComponent(
                savedSet.leftScenarioId,
              )}&right=${encodeURIComponent(savedSet.rightScenarioId)}`;

              return (
                <article
                  className="panel"
                  key={savedSet.id}
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
                      {savedSet.createdAt ? savedSet.createdAt.slice(0, 10) : "—"}
                    </span>
                  </div>

                  <div className="buttonRow">
                    <Link className="ghostButton inlineButton" href={compareHref}>
                      Open compare set
                    </Link>
                    <button
                      className="ghostButton inlineButton"
                      type="button"
                      onClick={() => removeSavedSet(savedSet.id)}
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
