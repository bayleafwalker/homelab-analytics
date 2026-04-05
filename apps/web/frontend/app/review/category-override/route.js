// @ts-check

import { redirect } from "next/navigation";
import { backendRequest } from "@/lib/backend";

/** @param {Request} request */
export async function POST(request) {
  const form = await request.formData();
  const counterpartyName = String(form.get("counterparty_name") || "");
  const category = String(form.get("category") || "");
  if (!category) {
    redirect(`/review?error=Please+select+a+category`);
  }
  const res = await backendRequest("put", "/categories/overrides/{counterparty_name}", {
    params: {
      path: { counterparty_name: counterpartyName },
      query: { category }
    }
  });
  if (res.ok) {
    redirect(`/review?notice=Category+updated`);
  } else {
    redirect(`/review?error=Failed+to+set+category`);
  }
}
