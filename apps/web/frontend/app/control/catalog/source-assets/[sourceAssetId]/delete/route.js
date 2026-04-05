// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { sourceAssetId: string } }} context
 */
export async function POST(request, { params }) {
  const response = await backendRequest("delete", "/config/source-assets/{source_asset_id}", {
    cookieHeader: request.headers.get("cookie") || "",
    params: { path: { source_asset_id: params.sourceAssetId } }
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
