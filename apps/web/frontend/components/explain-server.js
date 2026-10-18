import React from "react";

import { ExplainBox } from "@/components/explain";
import { loadExplanation } from "@/lib/explain";

// Async server component wrapper around <ExplainBox>. Use it from server
// components; client trees preload with loadExplanation() and pass the result
// to <ExplainBox explanation={…}>.
export async function Explain({ publication, user, confidence, ...rest }) {
  const explanation = await loadExplanation(publication, { user, confidence });
  return <ExplainBox explanation={explanation} {...rest} />;
}
