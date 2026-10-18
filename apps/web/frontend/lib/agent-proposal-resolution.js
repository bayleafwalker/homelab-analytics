// @ts-check

/** Maximum reason length accepted by the API (ProposalResolutionModel). */
export const MAX_RESOLUTION_REASON_LENGTH = 500;

/**
 * Read the optional operator reason from a resolution form post.
 *
 * Empty reasons are sent as null so the API records "no reason given" rather
 * than an empty string; long reasons are trimmed to the API bound instead of
 * failing the whole resolution with a 422.
 *
 * @param {Request} request
 * @returns {Promise<string | null>}
 */
export async function resolutionReason(request) {
  const formData = await request.formData();
  const reason = String(formData.get("reason") || "").trim();
  return reason ? reason.slice(0, MAX_RESOLUTION_REASON_LENGTH) : null;
}

/**
 * Notice key for a resolution outcome, keyed on the API status code.
 *
 * @param {"approved" | "dismissed"} resolution
 * @param {number} status
 */
export function resolutionNotice(resolution, status) {
  if (status >= 200 && status < 300) {
    return { kind: "notice", key: `proposal-${resolution}` };
  }
  if (status === 409) {
    return { kind: "error", key: "proposal-already-resolved" };
  }
  if (status === 403) {
    return { kind: "error", key: "proposal-forbidden" };
  }
  if (status === 404) {
    return { kind: "error", key: "proposal-missing" };
  }
  if (status === 502) {
    return { kind: "error", key: "proposal-release-failed" };
  }
  return { kind: "error", key: "proposal-resolution-failed" };
}

/**
 * Redirect target back to the agent inbox carrying the outcome.
 *
 * @param {Request} request
 * @param {"approved" | "dismissed"} resolution
 * @param {number} status
 * @param {string} actionId
 */
export function resolutionRedirect(request, resolution, status, actionId) {
  const { kind, key } = resolutionNotice(resolution, status);
  const target = new URL("/control/agents", request.url);
  target.searchParams.set(kind, key);
  target.searchParams.set("action_id", actionId);
  return target;
}
