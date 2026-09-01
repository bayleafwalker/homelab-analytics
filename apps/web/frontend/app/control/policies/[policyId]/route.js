// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";
import { ruleDocumentFromForm } from "@/lib/policy-rule-form";

/**
 * @param {Request} request
 * @param {{ params: { policyId: string } }} context
 */
export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest("patch", "/control/policies/{policy_id}", {
    cookieHeader: request.headers.get("cookie") || "",
    params: { path: { policy_id: params.policyId } },
    body: {
      display_name: String(formData.get("display_name") || ""),
      description: String(formData.get("description") || "") || null,
      rule_document: ruleDocumentFromForm(formData)
    }
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/policies?error=update-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/policies?notice=policy-updated", request.url),
    { status: 303 }
  );
}
