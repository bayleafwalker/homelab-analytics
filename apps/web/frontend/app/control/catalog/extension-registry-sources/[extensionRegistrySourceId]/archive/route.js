import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest(
    `/config/extension-registry-sources/${params.extensionRegistrySourceId}/archive`,
    {
      method: "PATCH",
      cookieHeader: request.headers.get("cookie") || "",
      contentType: "application/json",
      body: JSON.stringify({
        archived: String(formData.get("archived") || "true") === "true"
      })
    }
  );
  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=extension-registry-source-archive-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=extension-registry-source-archived", request.url),
    { status: 303 }
  );
}
