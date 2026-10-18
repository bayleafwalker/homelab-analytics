// @ts-check

import { createScheduleDispatchRetryHandler } from "@/lib/execution-dispatch-routes";

export const POST = createScheduleDispatchRetryHandler({
  failureLocation: () => "/retro/control/execution?error=schedule-dispatch-retry-failed",
  successLocation: () => "/retro/control/execution?notice=schedule-dispatch-retried"
});
