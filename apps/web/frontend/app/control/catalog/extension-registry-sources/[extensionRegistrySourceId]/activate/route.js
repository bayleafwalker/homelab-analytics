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
    "post",
    "/config/extension-registry-sources/{extension_registry_source_id}/activate",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: {
        path: {
          extension_registry_source_id: params.extensionRegistrySourceId
        }
      },
      body: {
        extension_registry_revision_id: String(
          formData.get("extension_registry_revision_id") || ""
        )
      }
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
