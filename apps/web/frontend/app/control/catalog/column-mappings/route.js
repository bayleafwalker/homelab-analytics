import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";
import { parseRulesSpec } from "@/lib/config-spec";

export async function POST(request) {
  const formData = await request.formData();
  let rules = [];
  try {
    rules = parseRulesSpec(formData.get("rules_spec"));
  } catch {
    return NextResponse.redirect(
      new URL("/control/catalog?error=column-mapping-failed", request.url),
      { status: 303 }
    );
  }
  const response = await backendRequest("/config/column-mappings", {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || "",
    contentType: "application/json",
    body: JSON.stringify({
      column_mapping_id: String(formData.get("column_mapping_id") || ""),
      source_system_id: String(formData.get("source_system_id") || ""),
      dataset_contract_id: String(formData.get("dataset_contract_id") || ""),
      version: Number.parseInt(String(formData.get("version") || "1"), 10) || 1,
      rules
    })
  });
  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=column-mapping-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=column-mapping-created", request.url),
    { status: 303 }
  );
}
