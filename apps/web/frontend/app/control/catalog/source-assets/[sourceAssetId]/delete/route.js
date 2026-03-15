import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request, { params }) {
  const response = await backendRequest(`/config/source-assets/${params.sourceAssetId}`, {
    method: "DELETE",
    cookieHeader: request.headers.get("cookie") || ""
  });
  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=source-asset-delete-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=source-asset-deleted", request.url),
    { status: 303 }
  );
}
