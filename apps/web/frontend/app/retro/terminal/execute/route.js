// @ts-check

import { NextResponse } from "next/server";

import { backendJsonRequest } from "@/lib/backend";

/** @param {Request} request */
export async function POST(request) {
  /** @type {import("@/lib/backend").RequestBodyForMethodPath<"post", "/control/terminal/execute">} */
  const payload = await request.json();
  const { response, data, error } = await backendJsonRequest(
    "post",
    "/control/terminal/execute",
    {
      cookieHeader: request.headers.get("cookie") || "",
      body: payload,
    }
  );

  return NextResponse.json(response.ok ? data ?? {} : error ?? {}, {
    status: response.status,
  });
}
