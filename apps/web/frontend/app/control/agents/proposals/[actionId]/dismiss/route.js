// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";
import { resolutionRedirect, resolutionReason } from "@/lib/agent-proposal-resolution";

/**
 * Reject (dismiss) one proposal from the agent inbox with the operator's
 * reason. Dismissal is final: the proposal cannot be approved afterwards.
 *
 * @param {Request} request
 * @param {{ params: { actionId: string } }} context
 */
export async function POST(request, { params }) {
  const reason = await resolutionReason(request);
  const response = await backendRequest(
    "post",
    "/api/actions/proposals/{action_id}/dismiss",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: { path: { action_id: params.actionId } },
      body: { reason }
    }
  );
  return NextResponse.redirect(
    resolutionRedirect(request, "dismissed", response.status, params.actionId),
    { status: 303 }
  );
}
