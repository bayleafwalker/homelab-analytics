// @ts-check

import { NextResponse } from "next/server";

import { backendJsonRequest } from "@/lib/backend";

/** @param {unknown} error */
function getPreviewErrorMessage(error) {
  if (error && typeof error === "object") {
    if ("error" in error && typeof error.error === "string") {
      return error.error;
    }
    if ("detail" in error && typeof error.detail === "string") {
      return error.detail;
    }
  }
  return "Preview failed.";
}

/** @param {Request} request */
export async function POST(request) {
  /** @type {import("@/lib/backend").RequestBodyForMethodPath<"post", "/config/column-mappings/preview">} */
  const payload = await request.json();
  const { response, data, error } = await backendJsonRequest(
    "post",
    "/config/column-mappings/preview",
    {
      cookieHeader: request.headers.get("cookie") || "",
      body: payload
    }
  );
  if (!response.ok) {
    return NextResponse.json(
      { error: getPreviewErrorMessage(error) },
      { status: response.status }
    );
  }
  return NextResponse.json(data || { preview: null }, { status: response.status });
}
