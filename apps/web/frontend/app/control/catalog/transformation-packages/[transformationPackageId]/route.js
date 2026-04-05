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
    "/config/transformation-packages/{transformation_package_id}",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: {
        path: { transformation_package_id: params.transformationPackageId }
      },
      body: {
        transformation_package_id: String(
          formData.get("transformation_package_id") ||
            params.transformationPackageId ||
            ""
        ),
        name: String(formData.get("name") || ""),
        handler_key: String(formData.get("handler_key") || ""),
        version: Number.parseInt(String(formData.get("version") || "1"), 10) || 1,
        description: String(formData.get("description") || "") || null
      }
    }
  );

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=transformation-package-update-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=transformation-package-updated", request.url),
    { status: 303 }
  );
}
