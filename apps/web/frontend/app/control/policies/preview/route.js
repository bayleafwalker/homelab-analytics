// @ts-check

import { NextResponse } from "next/server";

import { backendJsonRequest } from "@/lib/backend";

/**
 * Preview a rule document for the authoring form.
 *
 * JSON rather than form-post-and-redirect: the answer belongs beside the
 * fields being edited, not on a reloaded page that would lose them. The
 * backend's status is passed through so the form can distinguish a rejected
 * rule (422) from an evaluator that is not wired (503).
 *
 * @param {Request} request
 */
export async function POST(request) {
  /** @type {import("@/lib/backend").RequestBodyForMethodPath<"post", "/control/policies/preview">} */
  const payload = await request.json();
  const { response, data, error } = await backendJsonRequest(
    "post",
    "/control/policies/preview",
    {
      cookieHeader: request.headers.get("cookie") || "",
      body: payload
    }
  );
  return NextResponse.json(response.ok ? data ?? {} : error ?? {}, {
    status: response.status
  });
}
