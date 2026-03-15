import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request) {
  const formData = await request.formData();
  const response = await backendRequest("/auth/users", {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || "",
    contentType: "application/json",
    body: JSON.stringify({
      username: String(formData.get("username") || ""),
      password: String(formData.get("password") || ""),
      role: String(formData.get("role") || "reader")
    })
  });

  if (!response.ok) {
    return NextResponse.redirect(new URL("/control?error=create-failed", request.url), {
      status: 303
    });
  }
  return NextResponse.redirect(new URL("/control?notice=user-created", request.url), {
    status: 303
  });
}
