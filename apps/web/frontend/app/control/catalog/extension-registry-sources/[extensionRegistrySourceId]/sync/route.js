import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest(
    `/config/extension-registry-sources/${params.extensionRegistrySourceId}/sync`,
    {
      method: "POST",
      cookieHeader: request.headers.get("cookie") || "",
      contentType: "application/json",
      body: JSON.stringify({
        activate: String(formData.get("activate") || "false") === "true"
      })
    }
  );
  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=extension-registry-source-sync-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=extension-registry-source-synced", request.url),
    { status: 303 }
  );
}
