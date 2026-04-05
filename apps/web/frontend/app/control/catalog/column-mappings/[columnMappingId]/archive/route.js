// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { columnMappingId: string } }} context
 */
export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest(
    "patch",
    "/config/column-mappings/{column_mapping_id}/archive",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: { path: { column_mapping_id: params.columnMappingId } },
      body: {
        archived: String(formData.get("archived") || "true") === "true"
      }
    }
  );
  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=column-mapping-archive-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=column-mapping-archived", request.url),
    { status: 303 }
  );
}
