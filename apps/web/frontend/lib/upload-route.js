import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";

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
    return NextResponse.redirect(new URL(`/upload?error=${failureCode}`, request.url), {
      status: 303
    });
  }
  return NextResponse.redirect(
    new URL(`/runs/${payload.run.run_id}?notice=upload-created`, request.url),
    { status: 303 }
  );
}
