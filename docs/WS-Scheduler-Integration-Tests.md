# WS Scheduler — Integration tests

2026-11-26. Home Assistant real, WateringSystem phase 1, physical preparation disabled.

| Case | Expected and observed | Final result |
|---|---|---|
| 01 | Global authorization off; no request; manual repeat trace failed_conditions | PASS |
| 02 | Plan disabled; REQUEST_DISABLED | PASS |
| 03 | Outside season; OUTSIDE_SEASON | PASS |
| 04 | Duration 600; PREFLIGHT_OK, PREPARATION_DISABLED | PASS |
| 05 | Capacity 12; PREFLIGHT_OK, PREPARATION_DISABLED | PASS |
| 06 | Invalid devices JSON; no event; trace confirms notification action and error stop | PASS |
| 07 | Updated target 777 before trigger; latest value received | PASS |

Runner report: five PASS, two PARTIAL, zero FAIL; no restoration errors. Cases 01 and 06 were subsequently verified manually (01 by repeating the test). Final functional acceptance: 7/7 PASS. All seven reported valve off and next-run reprogramming. No physical actuation was enabled.

Evidence summarized from the integration session; raw report and traces are not archived here. Notification delivery itself was not independently verified for every case.

## Follow-up

Automate trace verification and allow individual case selection. Before running, disable legacy watering automations that could react to global authorization. Keep physical preparation disabled. Fixed notification tag can accumulate messages; presentation improvements remain pending.
