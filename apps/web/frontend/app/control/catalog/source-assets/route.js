import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request) {
  const formData = await request.formData();
  const response = await backendRequest("/config/source-assets", {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || "",
    contentType: "application/json",
    body: JSON.stringify({
      source_asset_id: String(formData.get("source_asset_id") || ""),
      source_system_id: String(formData.get("source_system_id") || ""),
      dataset_contract_id: String(formData.get("dataset_contract_id") || ""),
      column_mapping_id: String(formData.get("column_mapping_id") || ""),
      name: String(formData.get("name") || ""),
      asset_type: String(formData.get("asset_type") || ""),
      transformation_package_id:
        String(formData.get("transformation_package_id") || "") || null,
      description: String(formData.get("description") || "") || null
    })
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=source-asset-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=source-asset-created", request.url),
    { status: 303 }
  );
}
