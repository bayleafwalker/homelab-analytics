import { proxyUploadRequest } from "@/lib/upload-route";

export async function POST(request) {
  return proxyUploadRequest(request, {
    backendPath: "/ingest/contract-prices",
    failureCode: "contract-price-upload-failed"
  });
}
