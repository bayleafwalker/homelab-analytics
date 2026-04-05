// @ts-check

import { NextResponse } from "next/server";

import { backendJsonRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { actionId: string } }} context
 */
export async function POST(request, { params }) {
  const { response } = await backendJsonRequest(
    "post",
    "/api/ha/actions/proposals/{action_id}/dismiss",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: { path: { action_id: params.actionId } }
    }
  );

  if (!response.ok) {
    return NextResponse.redirect(
      new URL(
        `/retro/operations?notice=approval-resolution-failed&action_id=${encodeURIComponent(params.actionId)}`,
        request.url
      ),
      { status: 303 }
    );
  }

  return NextResponse.redirect(
    new URL(
      `/retro/operations?notice=approval-dismissed&action_id=${encodeURIComponent(params.actionId)}`,
      request.url
    ),
    { status: 303 }
  );
}
