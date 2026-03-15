import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";
import { parseColumnsSpec } from "@/lib/config-spec";

export async function POST(request) {
  const formData = await request.formData();
  let columns = [];
  try {
    columns = parseColumnsSpec(formData.get("columns_spec"));
  } catch {
    return NextResponse.redirect(
      new URL("/control/catalog?error=dataset-contract-failed", request.url),
      { status: 303 }
    );
  }
  const response = await backendRequest("/config/dataset-contracts", {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || "",
    contentType: "application/json",
    body: JSON.stringify({
      dataset_contract_id: String(formData.get("dataset_contract_id") || ""),
      dataset_name: String(formData.get("dataset_name") || ""),
      version: Number.parseInt(String(formData.get("version") || "1"), 10) || 1,
      allow_extra_columns: String(formData.get("allow_extra_columns") || "false") === "true",
      columns
    })
  });
  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=dataset-contract-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=dataset-contract-created", request.url),
    { status: 303 }
  );
}
