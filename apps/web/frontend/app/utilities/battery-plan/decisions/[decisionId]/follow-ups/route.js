// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * datetime-local inputs carry no offset; interpret them in the server's
 * timezone and send an explicit UTC timestamp, so the ledger never stores a
 * naive time.
 * @param {string} value
 */
function toAwareTimestamp(value) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toISOString();
}

/**
 * @param {Request} request
 * @param {{ params: { decisionId: string } }} context
 */
export async function POST(request, { params }) {
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

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/utilities/battery-plan?error=follow-up-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/utilities/battery-plan?notice=follow-up-recorded", request.url),
    { status: 303 }
  );
}
