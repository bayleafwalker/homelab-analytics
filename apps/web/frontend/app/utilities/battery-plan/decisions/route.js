// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/** @param {Request} request */
export async function POST(request) {
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

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/utilities/battery-plan?error=decision-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/utilities/battery-plan?notice=decision-recorded", request.url),
    { status: 303 }
  );
}
