import { proxyUploadRequest } from "@/lib/upload-route";

export async function POST(request) {
  return proxyUploadRequest(request, {
    backendPath: "/ingest/configured-csv",
    failureCode: "contract-price-upload-failed",
    fields: {
      upload_path: "/upload/contract-prices",
      source_name: "browser-upload"
    }
  });
}
