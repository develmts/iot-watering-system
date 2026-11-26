import os
import json
import time
import hashlib
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import websocket

ROOT = Path(__file__).resolve().parents[1]
for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
    if line.strip() and not line.lstrip().startswith("#"):
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"'))
URL = os.environ["HA_URL"].rstrip("/")
TOKEN = os.environ["HA_TOKEN"]
SSH = os.environ["HA_SSH"]
REMOTE = os.environ["WS_REMOTE_DIR"]
LOG_CMD = os.environ["WS_LOG_COMMAND"]
GLOBAL = "input_boolean.auto_watering"
NEXT = "sensor.ws_plan_nw_next_run"
FIELDS = {
    "enabled": "switch.ws_plan_nw_enabled",
    "start_time": "text.ws_plan_nw_start_time",
    "season_start": "text.ws_plan_nw_season_start",
    "season_end": "text.ws_plan_nw_season_end",
    "devices": "text.ws_plan_nw_devices",
    "target_type": "select.ws_plan_nw_target_type",
    "target": "number.ws_plan_nw_target",
}
REPORT = ROOT / "ws-test-report.json"

def api(path, data=None):
    req = urllib.request.Request(URL + "/api/" + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)

def state(entity):
    return api("states/" + entity)["state"]

def set_state(entity, value):
    domain = entity.split(".")[0]
    service = ("turn_on" if value == "on" else "turn_off") if domain in ("switch", "input_boolean") else {"text":"set_value","number":"set_value","select":"select_option"}[domain]
    data = {"entity_id": entity}
    if domain == "select":
        data["option"] = value
    elif domain in ("text", "number"):
        data["value"] = float(value) if domain == "number" else value
    api("services/" + domain + "/" + service, data)
    actual = state(entity)
    if (float(actual) != float(value) if domain == "number" else actual != value):
        raise RuntimeError("State write not confirmed: " + entity)

def ssh(command):
    return subprocess.check_output(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", SSH, command], timeout=40, text=True)

def logs():
    return ssh(LOG_CMD)

def safety():
    import shlex
    # Only accept the exact reviewed read-only controller blob.
    controller = (ROOT / "src/controller.py").read_bytes().replace(b"\r\n", b"\n")
    blob = hashlib.sha1(b"blob " + str(len(controller)).encode() + b"\0" + controller).hexdigest()
    if blob != "2c2a8524a8970658fe6060cf1681f95d74a12376":
        raise RuntimeError("Controller is not the reviewed read-only revision")
    for path in sorted((ROOT / "src").glob("*.py")):
        expected = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        actual = ssh("sha256sum " + shlex.quote(REMOTE.rstrip("/") + "/" + path.name)).split()[0]
        if actual != expected:
            raise RuntimeError("Deployed source mismatch: " + path.name)
    if state("switch.watering_control_a4f9_state") != "off":
        raise RuntimeError("Physical valve is not OFF")

def connect():
    ws = websocket.create_connection(URL.replace("https://","wss://",1).replace("http://","ws://",1) + "/api/websocket", timeout=20)
    json.loads(ws.recv())
    ws.send(json.dumps({"type":"auth","access_token":TOKEN}))
    if json.loads(ws.recv()).get("type") != "auth_ok":
        raise RuntimeError("WebSocket authentication failed")
    ws.send(json.dumps({"id":1,"type":"subscribe_events","event_type":"irrigation_request"}))
    if not json.loads(ws.recv()).get("success"):
        raise RuntimeError("Event subscription failed")
    return ws

def collect(ws, until):
    events = []
    while time.time() < until:
        ws.settimeout(max(0.1, min(2, until-time.time())))
        try:
            msg = json.loads(ws.recv())
        except websocket.WebSocketTimeoutException:
            continue
        if msg.get("type") == "event":
            events.append(msg["event"]["data"])
    return events

def run():
    report = {"tests": [], "restoration_errors": []}
    original = {}
    ws = None
    changed = False
    try:
        safety()
        baseline = logs()
        if "SYSTEM_READY" not in baseline and "REQUEST_RECEIVED" not in baseline:
            raise RuntimeError("Log command did not return recognizable WateringSystem logs")
        zone = ZoneInfo(api("config")["time_zone"])
        scheduler = os.environ.get("WS_SCHEDULER_ENTITY", "automation.ws_scheduler")
        if state(scheduler) != "on":
            raise RuntimeError("Scheduler is not enabled")
        original = {e: state(e) for e in [GLOBAL, *FIELDS.values()]}
        if any(v in ("unknown","unavailable") for v in original.values()):
            raise RuntimeError("Cannot snapshot unavailable configuration")
        ws = connect()
        changed = True
        today = datetime.now(zone).date()
        outside = (today + timedelta(days=1)).strftime("%m-%d")
        cases = [
            ("01_global_off", "off", {}, None),
            ("02_plan_disabled", "on", {"enabled":"off"}, "REQUEST_DISABLED"),
            ("03_outside_season", "on", {"season_start":outside,"season_end":outside}, "OUTSIDE_SEASON"),
            ("04_duration", "on", {}, "PREPARATION_DISABLED"),
            ("05_capacity", "on", {"target_type":"capacity","target":"12"}, "PREPARATION_DISABLED"),
            ("06_invalid_json", "on", {"devices":"invalid-json"}, None),
            ("07_updated_config", "on", {}, "PREPARATION_DISABLED"),
        ]
        for name, authorization, overrides, expected_code in cases:
            print(name, flush=True)
            safety()
            set_state(GLOBAL, "off")
            config = {"enabled":"on","season_start":"01-01","season_end":"12-31",
                      "devices":'["Watering Control a4f9"]',"target_type":"duration","target":"600"}
            config.update(overrides)
            for key, value in config.items():
                set_state(FIELDS[key], value)
            scheduled = (datetime.now(zone) + timedelta(minutes=2)).replace(second=0,microsecond=0)
            set_state(FIELDS["start_time"], scheduled.strftime("%H:%M"))
            time.sleep(2)
            if abs(datetime.fromisoformat(state(NEXT)).timestamp()-scheduled.timestamp()) > 1:
                raise RuntimeError("Next Run does not match requested schedule")
            before = logs()
            last_triggered = api("states/"+scheduler)["attributes"].get("last_triggered")
            set_state(GLOBAL, authorization)
            if name.startswith("07"):
                set_state(FIELDS["target"], "777")
                config["target"] = "777"
            events = collect(ws, scheduled.timestamp()+25)
            after = logs()
            # Require overlap; never mistake old log messages for this run.
            old_lines, new_lines = before.splitlines(), after.splitlines()
            overlap = next((n for n in range(min(len(old_lines),len(new_lines)),0,-1)
                            if old_lines[-n:] == new_lines[:n]), 0)
            delta = "\n".join(new_lines[overlap:]) if overlap else ""
            current_trigger = api("states/"+scheduler)["attributes"].get("last_triggered")
            next_run = datetime.fromisoformat(state(NEXT))
            checks = {"log_overlap":bool(overlap),
                      "next_run":next_run.date() == scheduled.date()+timedelta(days=1) if next_run.tzinfo == zone else next_run.astimezone(zone).date() == scheduled.date()+timedelta(days=1),
                      "valve_off":state("switch.watering_control_a4f9_state")=="off"}
            if expected_code:
                expected = {"version":1,"request_mode":"scheduler","devices":json.loads(config["devices"]),
                    "enabled":config["enabled"]=="on","season_start":config["season_start"],
                    "season_end":config["season_end"],"target_type":config["target_type"],
                    "target":int(config["target"]),"readings":{},"validators":{},"tag":"ws_plan_nw"}
                checks["event"] = len(events)==1 and all(events[0].get(k)==v for k,v in expected.items())
                checks["types"] = len(events)==1 and type(events[0].get("enabled")) is bool and (type(events[0].get("target")) is int if config["target_type"]=="duration" else type(events[0].get("target")) in (int,float))
                checks["appdaemon"] = all(code in delta for code in ("REQUEST_RECEIVED","REQUEST_NORMALIZED",expected_code))
                if expected_code == "PREPARATION_DISABLED":
                    checks["preflight"] = "PREFLIGHT_OK" in delta
            else:
                checks["no_event"] = not events and "REQUEST_RECEIVED" not in delta
                if name.startswith("06"):
                    checks["scheduler_triggered"] = current_trigger != last_triggered
            result = {"name":name,"status":"PASS" if all(checks.values()) else "FAIL","checks":checks,"events":events,"logs":delta,"last_triggered_before":last_triggered,"last_triggered_after":current_trigger,"next_run":str(next_run)}
            if name.startswith(("01","06")) and result["status"]=="PASS":
                result["status"]="PARTIAL"
                result["note"]="Automation trace / error notification requires separate verification."
            report["tests"].append(result)
            print(result["status"], flush=True)
            set_state(GLOBAL, "off")
            if not checks["valve_off"]:
                raise RuntimeError("Valve state changed unexpectedly")
    except BaseException as exc:
        report["error"] = str(exc)
    finally:
        if changed:
            try:
                set_state(GLOBAL, "off")
            except Exception as exc:
                report["restoration_errors"].append(str(exc))
            for entity, value in original.items():
                if entity == GLOBAL:
                    continue
                try:
                    set_state(entity,value)
                except Exception as exc:
                    report["restoration_errors"].append(str(exc))
            if not report["restoration_errors"]:
                try:
                    set_state(GLOBAL,original[GLOBAL])
                except Exception as exc:
                    report["restoration_errors"].append(str(exc))
        if ws:
            ws.close()
        REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
        print("Report:",REPORT)
    return 0 if len(report["tests"])==7 and all(t["status"]=="PASS" for t in report["tests"]) and not report.get("error") and not report["restoration_errors"] else 1

if __name__ == "__main__":
    raise SystemExit(run())
