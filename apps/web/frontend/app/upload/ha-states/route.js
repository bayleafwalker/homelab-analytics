import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

export async function POST(request) {
  const formData = await request.formData();
  const file = formData.get("file");

  if (!file) {
    return NextResponse.redirect(
      new URL("/upload?error=ha-upload-failed", request.url),
      { status: 303 }
    );
  }

  let states;
  try {
    const text = await file.text();
    states = JSON.parse(text);
  } catch {
    return NextResponse.redirect(
      new URL("/upload?error=ha-upload-failed", request.url),
      { status: 303 }
    );
  }

  // Accept either a raw HA /api/states array or a pre-wrapped { states } object.
  const body = Array.isArray(states) ? { states } : states;

  const response = await backendRequest("/api/ha/ingest", {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || "",
    body: JSON.stringify(body),
    contentType: "application/json",
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/upload?error=ha-upload-failed", request.url),
      { status: 303 }
    );
  }

  return NextResponse.redirect(
    new URL("/homelab?notice=ha-ingested", request.url),
    { status: 303 }
  );
}
