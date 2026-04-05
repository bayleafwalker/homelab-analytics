// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/** @param {unknown} error */
function getDryRunErrorMessage(error) {
  if (error && typeof error === "object") {
    if ("error" in error && typeof error.error === "string") {
      return error.error;
    }
    if ("detail" in error && typeof error.detail === "string") {
      return error.detail;
    }
  }
  return "Dry-run preview failed.";
}

/** @param {Request} request */
export async function POST(request) {
  const formData = await request.formData();
  const dryRunPath = "/ingest/dry-run";
  const httpMethod = "POST";
  if (!formData.get("file")) {
    return NextResponse.json(
      { error: "multipart request must include file" },
      { status: 400 }
    );
  }

  const response = await backendRequest(dryRunPath, {
    method: httpMethod,
    cookieHeader: request.headers.get("cookie") || "",
    body: formData
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    return NextResponse.json(
      { error: getDryRunErrorMessage(payload) },
      { status: response.status }
    );
  }

  return NextResponse.json(payload || { preview: null }, { status: response.status });
}
