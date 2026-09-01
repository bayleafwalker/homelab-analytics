// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * Enable or disable one policy.
 *
 * Enable is not a local flag flip: the API re-validates the stored rule's
 * publication references on enable, so this can legitimately fail for a
 * policy that saved cleanly earlier. The two outcomes get distinct error
 * keys so the page can say which one happened.
 *
 * @param {Request} request
 * @param {{ params: { policyId: string } }} context
 */
export async function POST(request, { params }) {
  const formData = await request.formData();
  const enabled = String(formData.get("enabled") || "") === "true";
  const response = await backendRequest("patch", "/control/policies/{policy_id}", {
    cookieHeader: request.headers.get("cookie") || "",
    params: { path: { policy_id: params.policyId } },
    body: { enabled }
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL(
        `/control/policies?error=${enabled ? "enable-failed" : "disable-failed"}`,
        request.url
      ),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL(
      `/control/policies?notice=${enabled ? "policy-enabled" : "policy-disabled"}`,
      request.url
    ),
    { status: 303 }
  );
}
