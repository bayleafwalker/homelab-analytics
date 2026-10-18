import React from "react";

import { SkeletonLines } from "../components/state-panel";

// Shown while a server page awaits its backend reads. Holds the page column
// so content doesn't jump when it arrives.
export default function Loading() {
  return (
    <main className="standalonePage" id="main-content" aria-busy="true">
      <p className="stateTitle" role="status">
        Loading the latest published figures…
      </p>
      <section className="panel section">
        <SkeletonLines lines={4} />
      </section>
      <section className="panel section">
        <SkeletonLines lines={3} />
      </section>
    </main>
  );
}
