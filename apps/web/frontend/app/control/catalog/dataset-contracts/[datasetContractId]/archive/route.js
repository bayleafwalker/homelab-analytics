// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

/**
 * @param {Request} request
 * @param {{ params: { datasetContractId: string } }} context
 */
export async function POST(request, { params }) {
  const formData = await request.formData();
  const response = await backendRequest(
    "patch",
    "/config/dataset-contracts/{dataset_contract_id}/archive",
    {
      cookieHeader: request.headers.get("cookie") || "",
      params: { path: { dataset_contract_id: params.datasetContractId } },
      body: {
        archived: String(formData.get("archived") || "true") === "true"
      }
    }
  );
  if (!response.ok) {
    return NextResponse.redirect(
      new URL("/control/catalog?error=dataset-contract-archive-failed", request.url),
      { status: 303 }
    );
  }
  return NextResponse.redirect(
    new URL("/control/catalog?notice=dataset-contract-archived", request.url),
    { status: 303 }
  );
}
