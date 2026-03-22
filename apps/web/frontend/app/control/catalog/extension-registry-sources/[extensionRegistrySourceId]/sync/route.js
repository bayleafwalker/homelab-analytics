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
    "/config/extension-registry-sources/{extension_registry_source_id}/sync",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: {
        path: {
          extension_registry_source_id: params.extensionRegistrySourceId
        }
      },
      body: {
        activate: String(formData.get("activate") || "false") === "true"
      }
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
