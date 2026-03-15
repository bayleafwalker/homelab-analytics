import { proxyUploadRequest } from "@/lib/upload-route";

export async function POST(request) {
  return proxyUploadRequest(request, {
    backendPath: "/ingest/configured-csv",
    failureCode: "configured-upload-failed"
  });
}
