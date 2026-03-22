// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { userId: string } }} context
 */
export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest("post", "/auth/users/{user_id}/password", {
    cookieHeader: request.headers.get("cookie") || "",
    params: { path: { user_id: params.userId } },
    body: {
      password: String(formData.get("password") || "")
    }
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control?error=password-reset-failed", request.url),
      {
        status: 303
      }
    );
  }
  return NextResponse.redirect(new URL("/control?notice=password-reset", request.url), {
    status: 303
  });
}
