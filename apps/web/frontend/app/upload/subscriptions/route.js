import { proxyUploadRequest } from "@/lib/upload-route";

export async function POST(request) {
  return proxyUploadRequest(request, {
    backendPath: "/ingest/configured-csv",
    failureCode: "subscription-upload-failed",
    fields: {
      upload_path: "/upload/subscriptions",
      source_name: "browser-upload"
    }
  });
}
