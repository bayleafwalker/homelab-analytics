// @ts-check

import { NextResponse } from "next/server";

import { backendJsonRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { tokenId: string } }} context
 */
export async function POST(request, { params }) {
  const { response, data, error } = await backendJsonRequest(
    "post",
    "/auth/service-tokens/{token_id}/revoke",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: { path: { token_id: params.tokenId } }
    }
  );
  return NextResponse.json(response.ok ? data ?? {} : error ?? {}, {
    status: response.status
  });
}
