// @ts-check

/** Maximum reason length accepted by the API (PackActionRequest.reason). */
export const MAX_PACK_REASON_LENGTH = 500;

/** Lifecycle actions the API accepts; anything else is never forwarded. */
export const PACK_ACTIONS = ["install", "upgrade", "rollback", "disable", "enable", "pin", "unpin"];

/** Actions that take an explicit target version from the catalog. */
export const VERSIONED_PACK_ACTIONS = ["install", "upgrade"];

export const PACK_ACTION_LABELS = {
  install: "Install",
  upgrade: "Upgrade",
  rollback: "Roll back",
  disable: "Disable",
  enable: "Enable",
  pin: "Pin version",
  unpin: "Unpin"
};

/**
 * @param {unknown} value
 * @returns {value is "install" | "upgrade" | "rollback" | "disable" | "enable" | "pin" | "unpin"}
 */
export function isPackAction(value) {
  return typeof value === "string" && PACK_ACTIONS.includes(value);
}

/**
 * Read a lifecycle form post. The reason is required by the API, so a blank
 * reason is returned as "" and the route refuses it before calling out.
 *
 * @param {Request} request
 */
export async function packActionForm(request) {
  const formData = await request.formData();
  const action = String(formData.get("action") || "");
  const version = String(formData.get("version") || "").trim();
  const reason = String(formData.get("reason") || "")
    .trim()
    .slice(0, MAX_PACK_REASON_LENGTH);
  return { action, version: version || null, reason };
}

/**
 * Notice/error key for an action outcome, keyed on the API status code.
 *
 * @param {number} status
 * @param {boolean} [refused] the 409 carried a refused plan (vs. a stale-plan conflict)
 */
export function packActionNotice(status, refused = false) {
  if (status >= 200 && status < 300) {
    return { kind: "notice", key: "pack-applied" };
  }
  if (status === 409) {
    return { kind: "error", key: refused ? "pack-refused" : "pack-conflict" };
  }
  if (status === 422) {
    return { kind: "error", key: "pack-invalid" };
  }
  if (status === 403) {
    return { kind: "error", key: "pack-forbidden" };
  }
  return { kind: "error", key: "pack-failed" };
}

/**
 * Redirect target back to /control/packs carrying the outcome and pack.
 *
 * @param {Request} request
 * @param {{ kind: string, key: string }} outcome
 * @param {string} packKey
 */
export function packActionRedirect(request, outcome, packKey) {
  const target = new URL("/control/packs", request.url);
  target.searchParams.set(outcome.kind, outcome.key);
  target.searchParams.set("pack", packKey);
  return target;
}

/**
 * Query string that opens the dry-run preview for one change.
 *
 * @param {string} packKey
 * @param {string} action
 * @param {string | null} [version]
 */
export function packPlanHref(packKey, action, version) {
  const params = new URLSearchParams({ plan: packKey, action });
  if (version) {
    params.set("version", version);
  }
  return `/control/packs?${params.toString()}#plan`;
}
