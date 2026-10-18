// @ts-check

import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/backend";
import {
  isPackAction,
  packActionForm,
  packActionNotice,
  packActionRedirect
} from "@/lib/pack-lifecycle";

/**
 * Apply one pack lifecycle change confirmed from the dry-run preview.
 *
 * The API re-plans the change and refuses it (409, recorded in the history)
 * if anything blocks it; a blank reason or unknown action never leaves here.
 *
 * @param {Request} request
 * @param {{ params: { packKey: string } }} context
 */
export async function POST(request, { params }) {
  const { action, version, reason } = await packActionForm(request);
  if (!isPackAction(action) || !reason) {
    return NextResponse.redirect(
      packActionRedirect(request, packActionNotice(422), params.packKey),
      { status: 303 }
    );
  }
  const response = await backendRequest("post", "/control/packs/{pack_key}/actions", {
    cookieHeader: request.headers.get("cookie") || "",
    params: { path: { pack_key: params.packKey } },
    body: { action, version, reason }
  });
  let refused = false;
  if (response.status === 409) {
    const payload = await response.json().catch(() => null);
    refused = Boolean(payload?.detail?.plan);
  }
  return NextResponse.redirect(
    packActionRedirect(request, packActionNotice(response.status, refused), params.packKey),
    { status: 303 }
  );
}
