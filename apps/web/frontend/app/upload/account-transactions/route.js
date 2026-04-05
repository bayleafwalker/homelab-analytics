import { proxyUploadRequest } from "@/lib/upload-route";

export async function POST(request) {
  return proxyUploadRequest(request, {
    backendPath: "/ingest/account-transactions",
    failureCode: "account-upload-failed"
  });
}
