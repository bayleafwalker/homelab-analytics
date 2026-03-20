import { proxyUploadRequest } from "@/lib/upload-route";

export async function POST(request) {
  return proxyUploadRequest(request, {
    backendPath: "/ingest/loan-repayments",
    failureCode: "loan-upload-failed"
  });
}
