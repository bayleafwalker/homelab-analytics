"use client";

import { useRouter } from "next/navigation";

export function ArchiveScenarioButton({ scenarioId }) {
  const router = useRouter();

  async function handleArchive() {
    const res = await fetch(`/api/scenarios/${scenarioId}`, { method: "DELETE" });
    if (res.ok) {
      router.refresh();
    }
  }

  return (
    <button className="ghostButton" type="button" onClick={handleArchive}>
      Archive
    </button>
  );
}
