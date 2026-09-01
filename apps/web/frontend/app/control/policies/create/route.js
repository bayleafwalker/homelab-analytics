// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";
import { ruleDocumentFromForm } from "@/lib/policy-rule-form";

/** @param {Request} request */
export async function POST(request) {
  const formData = await request.formData();
  const response = await backendRequest("post", "/control/policies", {
    cookieHeader: request.headers.get("cookie") || "",
    body: {
      display_name: String(formData.get("display_name") || ""),
      policy_kind: String(formData.get("policy_kind") || "declarative_rule"),
      description: String(formData.get("description") || "") || null,
      rule_schema_version: String(formData.get("rule_schema_version") || ""),
      rule_document: ruleDocumentFromForm(formData)
    }
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/policies?error=create-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/policies?notice=policy-created", request.url),
    { status: 303 }
  );
}
