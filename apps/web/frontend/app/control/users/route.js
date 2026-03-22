// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/** @param {Request} request */
export async function POST(request) {
  const formData = await request.formData();
  const roleValue = String(formData.get("role") || "reader");
  const role =
    roleValue === "admin" || roleValue === "operator" || roleValue === "reader"
      ? roleValue
      : "reader";
  const response = await backendRequest("post", "/auth/users", {
    cookieHeader: request.headers.get("cookie") || "",
    body: {
      username: String(formData.get("username") || ""),
      password: String(formData.get("password") || ""),
      role
    }
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
