import { redirect } from "next/navigation";
import { backendRequest } from "@/lib/backend";

export async function POST(request) {
  const form = await request.formData();
  const counterparty_name = form.get("counterparty_name");
  const category = form.get("category");
  const res = await backendRequest(
    `/categories/overrides/${encodeURIComponent(counterparty_name)}?category=${encodeURIComponent(category)}`,
    { method: "PUT" }
  );
  if (res.ok) {
    redirect(`/review?notice=Category+updated`);
  } else {
    redirect(`/review?error=Failed+to+set+category`);
  }
}
