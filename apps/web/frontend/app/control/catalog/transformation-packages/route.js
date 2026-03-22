// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/** @param {Request} request */
export async function POST(request) {
  const formData = await request.formData();
  const response = await backendRequest("post", "/config/transformation-packages", {
    cookieHeader: request.headers.get("cookie") || "",
    body: {
      transformation_package_id: String(
        formData.get("transformation_package_id") || ""
      ),
      name: String(formData.get("name") || ""),
      handler_key: String(formData.get("handler_key") || ""),
      version: Number.parseInt(String(formData.get("version") || "1"), 10) || 1,
      description: String(formData.get("description") || "") || null
    }
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=transformation-package-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=transformation-package-created", request.url),
    { status: 303 }
  );
}
