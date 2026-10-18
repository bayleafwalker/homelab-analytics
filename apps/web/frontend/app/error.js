"use client";

import React from "react";

// Route-level error boundary. Server pages throw when a backend request
// fails (lib/backend.ts); without this boundary the whole route became a
// bare 500. Say what failed, offer a retry, keep the way home visible.
function describe(error) {
  const message = String(error?.message || "");
  const backend = /Backend request failed for (\S+): (\d+)/.exec(message);
  if (backend) {
    const [, path, status] = backend;
    if (status === "401" || status === "403") {
      return `The API refused ${path} for your account (${status}). Sign in again or ask an admin for access.`;
    }
    if (status === "404") {
      return `The API has no ${path} endpoint in this deployment (404). The feature may be turned off for this identity mode.`;
    }
    return `The API answered ${path} with ${status}. Check the API logs, then try again.`;
  }
  if (/fetch failed|ECONNREFUSED/i.test(message)) {
    return "The web app couldn't reach the API. Check that the API is running and that the web app is configured with its address.";
  }
  return "Something went wrong while building this page. Try again; if it keeps failing, the details below help with a bug report.";
}

export default function RouteError({ error, reset }) {
  return (
    <main className="standalonePage" id="main-content">
      <a href="/" className="wordmark">
        Kotona
      </a>
      <div className="statePanel" data-tone="error" role="alert">
        <span className="stateMarker" aria-hidden="true" />
        <div className="stateBody">
          <h1 className="stateTitle">This page couldn&apos;t load</h1>
          <div className="stateText">
            <p>{describe(error)}</p>
          </div>
          <div className="stateActions">
            <button type="button" className="primaryButton" onClick={() => reset()}>
              Try again
            </button>
            <a className="ghostButton" href="/">
              Go to dashboard
            </a>
          </div>
        </div>
      </div>
      {error?.message || error?.digest ? (
        <details>
          <summary>Technical details</summary>
          <p>
            <code>{error?.message}</code>
          </p>
          {error?.digest ? <p>Reference: {error.digest}</p> : null}
        </details>
      ) : null}
    </main>
  );
}
