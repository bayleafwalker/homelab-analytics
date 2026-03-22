// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { sourceAssetId: string } }} context
 */
export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest("patch", "/config/source-assets/{source_asset_id}", {
    cookieHeader: request.headers.get("cookie") || "",
    params: { path: { source_asset_id: params.sourceAssetId } },
    body: {
      source_asset_id: String(formData.get("source_asset_id") || params.sourceAssetId || ""),
      source_system_id: String(formData.get("source_system_id") || ""),
      dataset_contract_id: String(formData.get("dataset_contract_id") || ""),
      column_mapping_id: String(formData.get("column_mapping_id") || ""),
      name: String(formData.get("name") || ""),
      asset_type: String(formData.get("asset_type") || ""),
      transformation_package_id:
        String(formData.get("transformation_package_id") || "") || null,
      description: String(formData.get("description") || "") || null,
      enabled: String(formData.get("enabled") || "true") === "true"
    }
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=source-asset-update-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=source-asset-updated", request.url),
    { status: 303 }
  );
}
