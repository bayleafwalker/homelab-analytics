// @ts-check

import { NextResponse } from "next/server";

import { backendJsonRequest } from "@/lib/backend";

/** @param {Request} request */
export async function GET(request) {
  const { response, data, error } = await backendJsonRequest(
    "get",
    "/control/terminal/commands",
    {
      cookieHeader: request.headers.get("cookie") || "",
    }
  );

  return NextResponse.json(response.ok ? data ?? {} : error ?? {}, {
    status: response.status,
  });
}
