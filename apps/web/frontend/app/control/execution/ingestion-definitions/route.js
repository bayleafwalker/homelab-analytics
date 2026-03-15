import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

function parseOptionalInteger(value) {
  if (!value) {
    return null;
  }
  const parsed = Number.parseInt(String(value), 10);
  return Number.isNaN(parsed) ? null : parsed;
}

export async function POST(request) {
  const formData = await request.formData();
  const response = await backendRequest("/config/ingestion-definitions", {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || "",
    contentType: "application/json",
    body: JSON.stringify({
      ingestion_definition_id: String(formData.get("ingestion_definition_id") || ""),
      source_asset_id: String(formData.get("source_asset_id") || ""),
      transport: String(formData.get("transport") || ""),
      schedule_mode: String(formData.get("schedule_mode") || ""),
      source_path: String(formData.get("source_path") || ""),
      file_pattern: String(formData.get("file_pattern") || "*.csv"),
      processed_path: String(formData.get("processed_path") || "") || null,
      failed_path: String(formData.get("failed_path") || "") || null,
      poll_interval_seconds: parseOptionalInteger(formData.get("poll_interval_seconds")),
      request_url: null,
      request_method: null,
      request_headers: [],
      request_timeout_seconds: null,
      response_format: null,
      output_file_name: null,
      enabled: String(formData.get("enabled") || "true") === "true",
      source_name: String(formData.get("source_name") || "") || null
    })
  });

  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/execution?error=ingestion-definition-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/execution?notice=ingestion-definition-created", request.url),
    { status: 303 }
  );
}
