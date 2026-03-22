// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { transformationPackageId: string } }} context
 */
export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest(
    "patch",
    "/config/transformation-packages/{transformation_package_id}/archive",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: {
        path: { transformation_package_id: params.transformationPackageId }
      },
      body: {
        archived: String(formData.get("archived") || "true") === "true"
      }
    }
  );

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=transformation-package-archive-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=transformation-package-archived", request.url),
    { status: 303 }
  );
}
