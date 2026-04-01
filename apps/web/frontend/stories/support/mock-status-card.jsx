import React, { useEffect, useState } from "react";

export function MockStatusCard({ endpoint = "/storybook/status" }) {
  const [state, setState] = useState({ loading: true, payload: null, error: null });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await fetch(endpoint);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = await response.json();
        if (!cancelled) {
          setState({ loading: false, payload, error: null });
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            loading: false,
            payload: null,
            error: error instanceof Error ? error.message : "unknown error",
          });
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [endpoint]);

  return (
    <article className="panel section">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">MSW Fixture</div>
          <h2>Story Status Probe</h2>
        </div>
        <span className="statusPill">
          {state.loading ? "Loading" : state.error ? "Error" : "Ready"}
        </span>
      </div>
      {state.loading ? <p className="muted">Waiting for mocked response...</p> : null}
      {state.error ? <p className="errorBanner">Mock failed: {state.error}</p> : null}
      {state.payload ? (
        <>
          <p className="lede">{state.payload.message}</p>
          <div className="cards" style={{ marginBottom: 0 }}>
            <section className="panel metricCard">
              <div className="metricLabel">Contract</div>
              <div className="metricValue">{state.payload.contract}</div>
            </section>
            <section className="panel metricCard">
              <div className="metricLabel">Mode</div>
              <div className="metricValue">{state.payload.mode}</div>
            </section>
          </div>
        </>
      ) : null}
    </article>
  );
}
