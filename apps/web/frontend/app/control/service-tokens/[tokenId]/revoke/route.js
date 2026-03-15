import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request, { params }) {
  const response = await backendRequest(`/auth/service-tokens/${params.tokenId}/revoke`, {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || ""
  });
  return NextResponse.json(await response.json(), { status: response.status });
}
