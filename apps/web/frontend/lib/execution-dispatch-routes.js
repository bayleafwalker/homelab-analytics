// @ts-check

import { NextResponse } from "next/server";

import { backendJsonRequest, backendRequest } from "@/lib/backend";

/**
 * Shared POST handlers for schedule-dispatch control actions.
 *
 * The modern (/control/execution) and retro (/retro/control/execution) shells
 * issue the same backend calls and differ only in where they redirect the
 * browser afterwards, so each shell passes its own redirect builders.
 */

/** @param {FormDataEntryValue | null} value */
function parseOptionalInteger(value) {
  if (!value) {
    return null;
  }
  const parsed = Number.parseInt(String(value), 10);
  return Number.isNaN(parsed) ? null : parsed;
}

/**
 * @param {Request} request
 * @param {string} location
 */
function redirectTo(request, location) {
  return NextResponse.redirect(new URL(location, request.url), { status: 303 });
}

/**
 * Handler for `POST .../schedule-dispatches` (enqueue one schedule or all due).
 *
 * @param {{ basePath: string }} options base path of the execution page to redirect to
 */
export function createScheduleDispatchHandler({ basePath }) {
  /** @param {Request} request */
  return async function POST(request) {
    const formData = await request.formData();
    const scheduleId = String(formData.get("schedule_id") || "") || null;
    const response = await backendRequest("post", "/control/schedule-dispatches", {
      cookieHeader: request.headers.get("cookie") || "",
      body: {
        schedule_id: scheduleId,
        limit: parseOptionalInteger(formData.get("limit"))
      }
    });

    if (!response.ok) {
      return redirectTo(request, `${basePath}?error=schedule-dispatch-failed`);
    }

    const notice = scheduleId ? "schedule-dispatch-created" : "due-dispatches-enqueued";
    return redirectTo(request, `${basePath}?notice=${notice}`);
  };
}

/**
 * Handler for `POST .../dispatches/[dispatchId]/retry`.
 *
 * @param {{
 *   failureLocation: (dispatchId: string) => string,
 *   successLocation: (dispatchId: string, retriedDispatchId: string | null) => string
 * }} redirects
 */
export function createScheduleDispatchRetryHandler({ failureLocation, successLocation }) {
  /**
   * @param {Request} request
   * @param {{ params: { dispatchId: string } }} context
   */
  return async function POST(request, { params }) {
    const { response, data } = await backendJsonRequest(
      "post",
      "/control/schedule-dispatches/{dispatch_id}/retry",
      {
        cookieHeader: request.headers.get("cookie") || "",
        params: { path: { dispatch_id: params.dispatchId } }
      }
    );

    if (!response.ok) {
      return redirectTo(request, failureLocation(params.dispatchId));
    }

    const retriedDispatchId = data?.dispatch?.dispatch_id || null;
    return redirectTo(request, successLocation(params.dispatchId, retriedDispatchId));
  };
}
