// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";
import { resolutionRedirect, resolutionReason } from "@/lib/agent-proposal-resolution";

/**
 * Approve one proposal from the agent inbox, recording the operator's reason.
 *
 * The API refuses a second resolution (409) and refuses machine principals
 * (403); both come back as distinct notices so the inbox can say why.
 *
 * @param {Request} request
 * @param {{ params: { actionId: string } }} context
 */
export async function POST(request, { params }) {
  const reason = await resolutionReason(request);
  const response = await backendRequest(
    "post",
    "/api/actions/proposals/{action_id}/approve",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: { path: { action_id: params.actionId } },
      body: { reason }
    }
  );
  return NextResponse.redirect(
    resolutionRedirect(request, "approved", response.status, params.actionId),
    { status: 303 }
  );
}
