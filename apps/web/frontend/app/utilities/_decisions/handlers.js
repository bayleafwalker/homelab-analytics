// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * Form-post handlers shared by the decision pages under /utilities. Every
 * handler forwards the session cookie to the decision ledger API (which
 * enforces control.decisions.write) and redirects back to the page that
 * rendered the form. None of them can change a tariff, contract or device.
 */

/**
 * datetime-local inputs carry no offset; interpret them in the server's
 * timezone and send an explicit UTC timestamp, so the ledger never stores a
 * naive time.
 * @param {string} value
 */
export function toAwareTimestamp(value) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toISOString();
}

/**
 * @param {Request} request
 * @param {string} pagePath
 * @param {string} key
 * @param {string} value
 */
function back(request, pagePath, key, value) {
  return NextResponse.redirect(new URL(`${pagePath}?${key}=${value}`, request.url), {
    status: 303
  });
}

/** @param {string} pagePath */
export function createDecisionPost(pagePath) {
  /** @param {Request} request */
  return async function POST(request) {
    const formData = await request.formData();
    const followUpDueOn = String(formData.get("follow_up_due_on") || "");
    const response = await backendRequest("post", "/control/decisions", {
      cookieHeader: request.headers.get("cookie") || "",
      body: {
        decision_key: String(formData.get("decision_key") || ""),
        subject_period: String(formData.get("subject_period") || ""),
        subject_row_ref: String(formData.get("subject_row_ref") || "") || null,
        outcome: String(formData.get("outcome") || ""),
        rationale: String(formData.get("rationale") || ""),
        evidence_gaps_acknowledged: formData
          .getAll("evidence_gaps_acknowledged")
          .map((value) => String(value)),
        uncertainty: String(formData.get("uncertainty") || "") || null,
        follow_up_due_on: followUpDueOn || null
      }
    });
    return response.ok
      ? back(request, pagePath, "notice", "decision-recorded")
      : back(request, pagePath, "error", "decision-failed");
  };
}

/** @param {string} pagePath */
export function createFollowUpPost(pagePath) {
  /**
   * @param {Request} request
   * @param {{ params: { decisionId: string } }} context
   */
  return async function POST(request, { params }) {
    const formData = await request.formData();
    const realizedValue = String(formData.get("realized_value_eur") || "");
    const response = await backendRequest(
      "post",
      "/control/decisions/{decision_id}/follow-ups",
      {
        cookieHeader: request.headers.get("cookie") || "",
        params: { path: { decision_id: params.decisionId } },
        body: {
          observed_at: toAwareTimestamp(String(formData.get("observed_at") || "")),
          realized_result: String(formData.get("realized_result") || ""),
          evidence_effect: String(formData.get("evidence_effect") || ""),
          realized_value_eur: realizedValue || null,
          realized_value_status: String(formData.get("realized_value_status") || "") || null
        }
      }
    );
    return response.ok
      ? back(request, pagePath, "notice", "follow-up-recorded")
      : back(request, pagePath, "error", "follow-up-failed");
  };
}

/** @param {string} pagePath */
export function createStopPost(pagePath) {
  /**
   * @param {Request} request
   * @param {{ params: { decisionId: string } }} context
   */
  return async function POST(request, { params }) {
    const formData = await request.formData();
    const response = await backendRequest("post", "/control/decisions/{decision_id}/stop", {
      cookieHeader: request.headers.get("cookie") || "",
      params: { path: { decision_id: params.decisionId } },
      body: {
        stop_condition_key: String(formData.get("stop_condition_key") || ""),
        reason: String(formData.get("reason") || "")
      }
    });
    return response.ok
      ? back(request, pagePath, "notice", "commitment-stopped")
      : back(request, pagePath, "error", "stop-failed");
  };
}

/** @param {string} pagePath */
export function createReopenPost(pagePath) {
  /**
   * @param {Request} request
   * @param {{ params: { decisionId: string } }} context
   */
  return async function POST(request, { params }) {
    const formData = await request.formData();
    const response = await backendRequest("post", "/control/decisions/{decision_id}/reopen", {
      cookieHeader: request.headers.get("cookie") || "",
      params: { path: { decision_id: params.decisionId } },
      body: { reason: String(formData.get("reason") || "") }
    });
    return response.ok
      ? back(request, pagePath, "notice", "commitment-reopened")
      : back(request, pagePath, "error", "reopen-failed");
  };
}

/**
 * @param {string} pagePath
 * @param {string} decisionKey
 */
export function createEvidenceTracePost(pagePath, decisionKey) {
  /** @param {Request} request */
  return async function POST(request) {
    const response = await backendRequest("post", "/control/decisions/evidence-trace", {
      cookieHeader: request.headers.get("cookie") || "",
      body: { decision_key: decisionKey }
    });
    return response.ok
      ? back(request, pagePath, "notice", "evidence-traced")
      : back(request, pagePath, "error", "trace-failed");
  };
}
