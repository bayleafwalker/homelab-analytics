// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { extensionRegistrySourceId: string } }} context
 */
export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest(
    "patch",
    "/config/extension-registry-sources/{extension_registry_source_id}",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: {
        path: {
          extension_registry_source_id: params.extensionRegistrySourceId
        }
      },
      body: {
        extension_registry_source_id: String(
          formData.get("extension_registry_source_id") ||
            params.extensionRegistrySourceId ||
            ""
        ),
        name: String(formData.get("name") || ""),
        source_kind: String(formData.get("source_kind") || "path"),
        location: String(formData.get("location") || ""),
        desired_ref: String(formData.get("desired_ref") || "") || null,
        subdirectory: String(formData.get("subdirectory") || "") || null,
        auth_secret_name: String(formData.get("auth_secret_name") || "") || null,
        auth_secret_key: String(formData.get("auth_secret_key") || "") || null,
        enabled: String(formData.get("enabled") || "true") === "true"
      }
    }
  );
  if (!response.ok) {
    return NextResponse.redirect(
      new URL(
        "/control/catalog?error=extension-registry-source-update-failed",
        request.url
      ),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=extension-registry-source-updated", request.url),
    { status: 303 }
  );
}
