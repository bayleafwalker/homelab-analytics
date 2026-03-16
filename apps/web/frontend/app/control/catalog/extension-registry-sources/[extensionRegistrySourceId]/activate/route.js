import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest(
    `/config/extension-registry-sources/${params.extensionRegistrySourceId}/activate`,
    {
      method: "POST",
      cookieHeader: request.headers.get("cookie") || "",
      contentType: "application/json",
      body: JSON.stringify({
        extension_registry_revision_id: String(
          formData.get("extension_registry_revision_id") || ""
        )
      })
    }
  );
  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=extension-registry-source-activate-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=extension-registry-source-activated", request.url),
    { status: 303 }
  );
}
