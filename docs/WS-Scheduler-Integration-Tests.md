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

## Automated regression — 2026-11-26

Runner revision df646e9b4203e3d3ecbc3a30ef469d0c2158273b: selected cases 01 and 06 passed, followed by full regression 7/7 PASS, zero PARTIAL, zero FAIL, restoration_errors empty. Full run triggers 13:23–13:35 local time. Trace 01 confirms failed_conditions with authorization off; trace 06 confirms invalid JSON, notification service invocation and explicit error stop. All seven next-run and valve-off checks passed. Physical preparation remains disabled. Legacy scheduler suspension and restoration completed without reported errors; report does not independently record its original/final state. Raw reports are not archived here. Runner selection and automatic trace verification accepted.
