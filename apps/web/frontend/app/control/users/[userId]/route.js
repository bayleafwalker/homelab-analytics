import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest(`/auth/users/${params.userId}`, {
    method: "PATCH",
    cookieHeader: request.headers.get("cookie") || "",
    contentType: "application/json",
    body: JSON.stringify({
      role: String(formData.get("role") || "reader"),
      enabled: String(formData.get("enabled") || "true") === "true"
    })
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
