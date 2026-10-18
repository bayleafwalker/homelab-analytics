// @ts-check

import { createScheduleDispatchRetryHandler } from "@/lib/execution-dispatch-routes";

export const POST = createScheduleDispatchRetryHandler({
  failureLocation: (dispatchId) =>
    `/control/execution/dispatches/${dispatchId}?error=schedule-dispatch-retry-failed`,
  successLocation: (dispatchId, retriedDispatchId) =>
    retriedDispatchId
      ? `/control/execution/dispatches/${retriedDispatchId}?notice=schedule-dispatch-retried&retry_of=${dispatchId}`
      : `/control/execution/dispatches/${dispatchId}`
});
