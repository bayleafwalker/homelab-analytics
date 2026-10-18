// @ts-check

import { createScheduleDispatchHandler } from "@/lib/execution-dispatch-routes";

export const POST = createScheduleDispatchHandler({ basePath: "/control/execution" });
