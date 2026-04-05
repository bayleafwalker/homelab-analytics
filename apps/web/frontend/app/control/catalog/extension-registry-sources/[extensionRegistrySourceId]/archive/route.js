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
    "/config/extension-registry-sources/{extension_registry_source_id}/archive",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: {
        path: {
          extension_registry_source_id: params.extensionRegistrySourceId
        }
      },
      body: {
        archived: String(formData.get("archived") || "true") === "true"
      }
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
