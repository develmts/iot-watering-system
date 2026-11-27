"""Simulate a selected GiEX device provided by Virtual Components."""
import argparse
import asyncio
import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

import websockets

FLOW = 0.475
INTERVAL = 2.0


def load_env():
    for line in Path(".env").read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


def api(path, data=None):
    request = Request(
        os.environ["HA_URL"].rstrip("/") + "/api/" + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Authorization": "Bearer " + os.environ["HA_TOKEN"],
                 "Content-Type": "application/json"},
    )
    with urlopen(request, timeout=10) as response:
        return json.load(response)


async def state(entity):
    return (await asyncio.to_thread(api, "states/" + entity))["state"]


async def service(domain, action, entity, **data):
    await asyncio.to_thread(api, "services/" + domain + "/" + action,
                            {"entity_id": entity, **data})


async def set_text(entities, name, value):
    await service("text", "set_value", entities[name], value=value)


async def set_consumption(entities, value):
    await service("virtual", "set", entities["water_consumed"],
                  value=str(round(value, 3)))


async def last_seen(entities):
    await set_text(entities, "last_seen", datetime.now(timezone.utc).isoformat())


async def cycle(entities, stopped):
    valve = entities["state"]
    mode = await state(entities["mode"])
    target = float(await state(entities["irrigation_target"]))
    if mode not in ("duration", "capacity") or not 0 < target <= 43200:
        raise ValueError("Invalid virtual irrigation target or mode")
    duration = target if mode == "duration" else target / FLOW
    await set_consumption(entities, 0)
    await set_text(entities, "irrigation_start_time", datetime.now().strftime("%H:%M:%S"))
    await last_seen(entities)
    start = time.monotonic()
    print(f"START {mode} {target}", flush=True)
    try:
        while True:
            elapsed = min(time.monotonic() - start, duration)
            if elapsed >= duration:
                await set_consumption(entities, target if mode == "capacity" else duration * FLOW)
                await service("switch", "turn_off", valve)
                break
            try:
                await asyncio.wait_for(stopped.wait(), min(INTERVAL, duration - elapsed))
                break
            except asyncio.TimeoutError:
                pass
            if await state(valve) != "on":
                break
            await set_consumption(entities, min(time.monotonic() - start, duration) * FLOW)
            await last_seen(entities)
    finally:
        elapsed = min(time.monotonic() - start, duration)
        await set_consumption(entities, elapsed * FLOW)
        await set_text(entities, "irrigation_end_time", datetime.now().strftime("%H:%M:%S"))
        await set_text(entities, "last_irrigation_duration", str(timedelta(seconds=int(elapsed))).zfill(8))
        await last_seen(entities)
        print(f"STOP after {elapsed:.2f}s", flush=True)


ROLES = {
    "state": "switch",
    "mode": "select",
    "irrigation_target": "number",
    "water_consumed": "sensor",
    "irrigation_start_time": "text",
    "irrigation_end_time": "text",
    "last_irrigation_duration": "text",
    "last_seen": "text",
    "battery": "sensor",
}


async def registry(ws, request_id, command):
    await ws.send(json.dumps({"id": request_id, "type": command}))
    response = json.loads(await ws.recv())
    if response.get("id") != request_id or not response.get("success"):
        raise RuntimeError(f"Registry request failed: {command}")
    return response["result"]


async def discover(ws, name):
    devices = await registry(ws, 1, "config/device_registry/list")
    matches = [d for d in devices if (d.get("name_by_user") or d.get("name")) == name]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one device named {name!r}, found {len(matches)}")
    device = matches[0]
    entries = await registry(ws, 2, "config/entity_registry/list")
    entries = [e for e in entries if e.get("device_id") == device["id"]]
    if not entries or any(e.get("platform") != "virtual" for e in entries):
        raise RuntimeError("Selected device must contain only Virtual Components entities")
    entities = {}
    for role, domain in ROLES.items():
        candidates = [
            e["entity_id"] for e in entries
            if not e.get("disabled_by")
            and e["entity_id"].startswith(domain + ".")
            and e["entity_id"].endswith("_" + role)
        ]
        if len(candidates) != 1:
            raise RuntimeError(f"Expected one entity for {role}, found {candidates}")
        entities[role] = candidates[0]
    for role, entity in entities.items():
        if await state(entity) in ("unknown", "unavailable"):
            raise RuntimeError(f"Entity not available: {entity}")
        print(f"{role}: {entity}", flush=True)
    return entities


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, help="Exact HA device name")
    args = parser.parse_args()
    load_env()
    url = os.environ["HA_URL"].rstrip("/").replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    task = None
    stopped = None
    async with websockets.connect(url + "/api/websocket") as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": os.environ["HA_TOKEN"]}))
        if json.loads(await ws.recv())["type"] != "auth_ok":
            raise RuntimeError("HA authentication failed")
        entities = await discover(ws, args.device)
        valve = entities["state"]
        if await state(valve) != "off":
            raise RuntimeError("Virtual valve must be off before starting simulator")
        await ws.send(json.dumps({"id": 3, "type": "subscribe_events", "event_type": "state_changed"}))
        if not json.loads(await ws.recv()).get("success"):
            raise RuntimeError("Subscription failed")
        print(f"GiEX simulator ready: {args.device}", flush=True)
        try:
            async for raw in ws:
                if task is not None and task.done():
                    task.result()
                    task = None
                data = json.loads(raw).get("event", {}).get("data", {})
                if data.get("entity_id") != valve:
                    continue
                old = (data.get("old_state") or {}).get("state")
                new = (data.get("new_state") or {}).get("state")
                if old == "off" and new == "on" and task is None:
                    stopped = asyncio.Event()
                    task = asyncio.create_task(cycle(entities, stopped))
                elif old == "on" and new == "off" and task is not None:
                    stopped.set()
                    await task
                    task = None
        finally:
            if task is not None:
                stopped.set()
                await task
            if await state(valve) == "on":
                await service("switch", "turn_off", valve)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
