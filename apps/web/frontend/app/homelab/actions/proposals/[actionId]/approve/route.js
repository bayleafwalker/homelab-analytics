// @ts-check

import { NextResponse } from "next/server";

import { backendJsonRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { actionId: string } }} context
 */
export async function POST(request, { params }) {
  const { response, data } = await backendJsonRequest(
    "post",
    "/api/ha/actions/proposals/{action_id}/approve",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: { path: { action_id: params.actionId } }
    }
  );

  if (!response.ok) {
    return NextResponse.redirect(
      new URL(
        `/homelab?notice=approval-resolution-failed&action_id=${encodeURIComponent(params.actionId)}`,
        request.url
      ),
      { status: 303 }
    );
  }

  const resolvedActionId = data?.action_id || params.actionId;
  return NextResponse.redirect(
    new URL(
      `/homelab?notice=approval-approved&action_id=${encodeURIComponent(resolvedActionId)}`,
      request.url
    ),
    { status: 303 }
  );
}
