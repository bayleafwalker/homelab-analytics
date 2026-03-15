import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest(`/auth/users/${params.userId}/password`, {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || "",
    contentType: "application/json",
    body: JSON.stringify({
      password: String(formData.get("password") || "")
    })
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
