// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { policyId: string } }} context
 */
export async function POST(request, { params }) {
  const response = await backendRequest("delete", "/control/policies/{policy_id}", {
    cookieHeader: request.headers.get("cookie") || "",
    params: { path: { policy_id: params.policyId } }
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/policies?error=delete-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/policies?notice=policy-deleted", request.url),
    { status: 303 }
  );
}
