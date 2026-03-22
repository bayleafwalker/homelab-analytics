// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { userId: string } }} context
 */
export async function POST(request, { params }) {
  const formData = await request.formData();
  const roleValue = String(formData.get("role") || "reader");
  const role =
    roleValue === "admin" || roleValue === "operator" || roleValue === "reader"
      ? roleValue
      : "reader";
  const response = await backendRequest("patch", "/auth/users/{user_id}", {
    cookieHeader: request.headers.get("cookie") || "",
    params: { path: { user_id: params.userId } },
    body: {
      role,
      enabled: String(formData.get("enabled") || "true") === "true"
    }
  });

  if (!response.ok) {
    return NextResponse.redirect(new URL("/control?error=update-failed", request.url), {
      status: 303
    });
  }
  return NextResponse.redirect(new URL("/control?notice=user-updated", request.url), {
    status: 303
  });
}
