import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

function normalizeIssue(issue) {
  return {
    code: String(issue?.code || issue?.type || "upload_error"),
    message: String(issue?.message || issue?.msg || "Upload failed."),
    column: Array.isArray(issue?.loc)
      ? issue.loc.join(".")
      : (issue?.column ?? issue?.loc ?? null),
    row_number: issue?.row_number ?? null
  };
}

function buildUploadFeedback(response, payload, failureCode) {
  const run = payload?.run && typeof payload.run === "object" ? payload.run : null;
  const runIssues = Array.isArray(run?.issues) ? run.issues.map(normalizeIssue) : [];
  const detailIssues = Array.isArray(payload?.detail)
    ? payload.detail.map(normalizeIssue)
    : [];
  return {
    errorCode: failureCode,
    status: response.status,
    runId: typeof run?.run_id === "string" ? run.run_id : null,
    datasetName: typeof run?.dataset_name === "string" ? run.dataset_name : null,
    fileName: typeof run?.file_name === "string" ? run.file_name : null,
    sourceName: typeof run?.source_name === "string" ? run.source_name : null,
    detail:
      typeof payload?.error === "string"
        ? payload.error
        : typeof payload?.detail === "string"
          ? payload.detail
          : null,
    issues: (runIssues.length > 0 ? runIssues : detailIssues).slice(0, 8)
  };
}

function encodeUploadFeedback(feedback) {
  return Buffer.from(JSON.stringify(feedback), "utf-8").toString("base64url");
}

export async function proxyUploadRequest(
  request,
  {
    backendPath,
    failureCode
  }
) {
  const formData = await request.formData();
  const response = await backendRequest(backendPath, {
    method: "POST",
    cookieHeader: request.headers.get("cookie") || "",
    body: formData
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok || !payload?.run?.run_id) {
    const redirectUrl = new URL(`/upload?error=${failureCode}`, request.url);
    const feedback = buildUploadFeedback(response, payload, failureCode);
    if (feedback.detail || feedback.issues.length > 0 || feedback.runId) {
      redirectUrl.searchParams.set("feedback", encodeUploadFeedback(feedback));
    }
    return NextResponse.redirect(redirectUrl, { status: 303 });
  }
  return NextResponse.redirect(
    new URL(`/runs/${payload.run.run_id}?notice=upload-created`, request.url),
    { status: 303 }
  );
}
