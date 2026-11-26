"""Simulate only the explicitly named Virtual GiEX entities."""
import asyncio
import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

import websockets

PREFIX = "virtual_giex_"
VALVE = "switch." + PREFIX + "state"
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


async def set_text(name, value):
    await service("text", "set_value", "text." + PREFIX + name, value=value)


async def set_consumption(value):
    await service("virtual", "set", "sensor." + PREFIX + "water_consumed",
                  value=str(round(value, 3)))


async def last_seen():
    await set_text("last_seen", datetime.now(timezone.utc).isoformat())


async def cycle():
    mode = await state("select." + PREFIX + "mode")
    target = float(await state("number." + PREFIX + "irrigation_target"))
    if mode not in ("duration", "capacity") or not 0 < target <= 43200:
        raise ValueError("Invalid virtual irrigation target or mode")
    duration = target if mode == "duration" else target / FLOW
    await set_consumption(0)
    await set_text("irrigation_start_time", datetime.now().strftime("%H:%M:%S"))
    await last_seen()
    start = time.monotonic()
    print(f"START {mode} {target}", flush=True)
    try:
        while True:
            elapsed = min(time.monotonic() - start, duration)
            if elapsed >= duration:
                await set_consumption(target if mode == "capacity" else duration * FLOW)
                await service("switch", "turn_off", VALVE)
                break
            await asyncio.sleep(min(INTERVAL, duration - elapsed))
            if await state(VALVE) != "on":
                break
            await set_consumption(min(time.monotonic() - start, duration) * FLOW)
            await last_seen()
    finally:
        elapsed = min(time.monotonic() - start, duration)
        await set_consumption(elapsed * FLOW)
        await set_text("irrigation_end_time", datetime.now().strftime("%H:%M:%S"))
        await set_text("last_irrigation_duration", str(timedelta(seconds=int(elapsed))).zfill(8))
        await last_seen()
        print(f"STOP after {elapsed:.2f}s", flush=True)


async def main():
    load_env()
    if await state(VALVE) != "off":
        raise RuntimeError("Virtual valve must be off before starting simulator")
    url = os.environ["HA_URL"].rstrip("/").replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    task = None
    async with websockets.connect(url + "/api/websocket") as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": os.environ["HA_TOKEN"]}))
        if json.loads(await ws.recv())["type"] != "auth_ok":
            raise RuntimeError("HA authentication failed")
        await ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"}))
        if not json.loads(await ws.recv()).get("success"):
            raise RuntimeError("Subscription failed")
        print("Virtual GiEX simulator ready", flush=True)
        try:
            async for raw in ws:
                if task is not None and task.done():
                    task.result()
                    task = None
                data = json.loads(raw).get("event", {}).get("data", {})
                if data.get("entity_id") != VALVE:
                    continue
                old = (data.get("old_state") or {}).get("state")
                new = (data.get("new_state") or {}).get("state")
                if old == "off" and new == "on" and task is None:
                    task = asyncio.create_task(cycle())
                elif old == "on" and new == "off" and task is not None:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    task = None
        finally:
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            if await state(VALVE) == "on":
                await service("switch", "turn_off", VALVE)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
