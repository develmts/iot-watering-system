"""Configure a virtual device, run tests, and capture HA state evidence."""
import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import websockets

from virtual_giex_simulator import load_env, api, discover, registry, service, state


async def snapshot(ids):
    return {entity: await asyncio.to_thread(api, "states/" + entity)
            for entity in ids}


async def run_case(case, entities, ids):
    valve = entities["state"]
    result = {"parameters": case}
    try:
        if await state(valve) != "off":
            raise RuntimeError("Valve must be off before test")
        await service("select", "select_option", entities["mode"], option=case["mode"])
        await service("number", "set_value", entities["irrigation_target"], value=case["target"])
        result["before"] = await snapshot(ids)
        start = time.monotonic()
        await service("switch", "turn_on", valve)
        if await state(valve) != "on":
            raise RuntimeError("Valve did not open")
        manual_stop = False
        while True:
            elapsed = time.monotonic() - start
            if await state(valve) == "off":
                break
            if "stop_after" in case and elapsed >= case["stop_after"] and not manual_stop:
                await service("switch", "turn_off", valve)
                manual_stop = True
            if elapsed >= case.get("timeout", 120):
                raise TimeoutError("Valve did not close before timeout")
            await asyncio.sleep(0.25)
        result["elapsed_seconds"] = round(time.monotonic() - start, 3)
        result["manual_stop_sent"] = manual_stop
        await asyncio.sleep(3)
        result["after"] = await snapshot(ids)
        result["status"] = "COMPLETED"
    except Exception as exc:
        result["status"] = "ERROR"
        result["error"] = repr(exc)
        if await state(valve) == "on":
            await service("switch", "turn_off", valve)
        await asyncio.sleep(3)
        result["after"] = await snapshot(ids)
    return result


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True)
    parser.add_argument("--tests", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("virtual-giex-test-report.json"))
    args = parser.parse_args()
    cases = json.loads(args.tests.read_text(encoding="utf-8-sig"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("Tests must be a non-empty JSON array")
    for case in cases:
        if case["mode"] not in ("duration", "capacity") or not 0 < case["target"] <= 43200:
            raise ValueError(f"Invalid test: {case}")
        if case.get("timeout", 120) <= 0 or ("stop_after" in case and case["stop_after"] <= 0):
            raise ValueError(f"Invalid timing: {case}")
    load_env()
    url = os.environ["HA_URL"].rstrip("/").replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    async with websockets.connect(url + "/api/websocket") as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": os.environ["HA_TOKEN"]}))
        if json.loads(await ws.recv())["type"] != "auth_ok":
            raise RuntimeError("HA authentication failed")
        entities = await discover(ws, args.device)
        entries = await registry(ws, 3, "config/entity_registry/list")
        valve_entry = next(e for e in entries if e["entity_id"] == entities["state"])
        ids = sorted(e["entity_id"] for e in entries
                     if e.get("device_id") == valve_entry["device_id"] and not e.get("disabled_by"))
    if await state(entities["state"]) != "off":
        raise RuntimeError("Virtual valve must be off before running tests")
    report = {"device": args.device, "entities": ids, "results": []}
    try:
        for case in cases:
            print(f"Running {case}", flush=True)
            result = await run_case(case, entities, ids)
            report["results"].append(result)
            print(result["status"], flush=True)
            args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    finally:
        if await state(entities["state"]) == "on":
            await service("switch", "turn_off", entities["state"])
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report: {args.output}")
    return int(any(r["status"] == "ERROR" for r in report["results"]))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
