"""Run WateringSystem preparation integration tests against Virtual GiEX."""
import argparse
import hashlib
import json
import re
import shlex
import time
import uuid

from ws_integration_runner import ROOT, REMOTE, api, state, set_state, ssh, logs, connect, trace_command

DEVICE_ID = "d975f716f5837b082a07d17b9bde1207"
PHYSICAL = "switch.watering_control_a4f9_state"
REPORT = ROOT / "ws-preparation-report.json"


def safety():
    expected_blobs = {"controller.py": "496d348cb12afe0a4ca7eb3a9d545fe7a05b179c",
                      "watering_device.py": "5df07409c63bf65458a902fffce83fd1b7670a85"}
    for path in sorted((ROOT / "src").glob("*.py")):
        data = path.read_bytes().replace(b"\r\n", b"\n")
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if path.name in expected_blobs and blob != expected_blobs[path.name]:
            raise RuntimeError("Unreviewed source: " + path.name)
        remote = ssh("sha256sum " + shlex.quote(REMOTE.rstrip("/") + "/" + path.name)).split()[0]
        if remote != hashlib.sha256(data).hexdigest():
            raise RuntimeError("Deployed source mismatch: " + path.name)
    if state(PHYSICAL) != "off":
        raise RuntimeError("Physical valve not off")


def discover(ws, name):
    devices = trace_command(ws, 2, {"type": "config/device_registry/list"})
    matches = [d for d in devices if (d.get("name_by_user") or d.get("name")) == name]
    if len(matches) != 1 or matches[0]["id"] != DEVICE_ID:
        raise RuntimeError("Device is not the authorized virtual device")
    entries = trace_command(ws, 3, {"type": "config/entity_registry/list"})
    entries = [e for e in entries if e.get("device_id") == DEVICE_ID]
    if not entries or any(e.get("platform") != "virtual" for e in entries):
        raise RuntimeError("Device is not exclusively virtual")
    roles = {}
    for role, domain in {"state":"switch", "mode":"select", "irrigation_target":"number", "battery":"sensor"}.items():
        found = [e["entity_id"] for e in entries if not e.get("disabled_by")
                 and e["entity_id"].startswith(domain + ".") and e["entity_id"].endswith("_" + role)]
        if len(found) != 1:
            raise RuntimeError("Ambiguous role: " + role)
        roles[role] = found[0]
    return roles


def battery(entity, value):
    api("services/virtual/set", {"entity_id": entity, "value": str(value)})
    if float(state(entity)) != float(value):
        raise RuntimeError("Battery write not confirmed")


def delta(before, after):
    old, new = before.splitlines(), after.splitlines()
    overlap = next((n for n in range(min(len(old), len(new)), 0, -1)
                    if old[-n:] == new[:n]), 0)
    if not overlap:
        raise RuntimeError("Log overlap lost")
    return "\n".join(new[overlap:])


def run(name):
    report = {"tests": [], "restoration_errors": []}
    ws = None
    roles = {}
    original = {}
    try:
        safety()
        ws = connect()
        roles = discover(ws, name)
        ws.close()
        ws = None
        if state(roles["state"]) != "off":
            raise RuntimeError("Virtual valve must be off")
        original = {k: state(roles[k]) for k in ("mode", "irrigation_target", "battery")}
        if any(v in ("unknown", "unavailable") for v in original.values()):
            original = {}
            raise RuntimeError("Cannot snapshot configuration")
        cases = [
            ("01_duration", "capacity", 10, 100, "duration", 120, "PREPARATION_READY"),
            ("02_capacity", "duration", 120, 100, "capacity", 25, "PREPARATION_READY"),
            ("03_already_ready", "duration", 120, 100, "duration", 120, "PREPARATION_READY"),
            ("04_out_of_range", "capacity", 25, 100, "duration", 43201, "PREPARATION_FAILED"),
            ("05_low_battery", "capacity", 25, 10, "duration", 120, "BATTERY_LOW"),
        ]
        for label, initial_mode, initial_target, charge, mode, target, expected in cases:
            print(label, flush=True)
            if state(roles["state"]) != "off" or state(PHYSICAL) != "off":
                raise RuntimeError("Valve not off")
            set_state(roles["mode"], initial_mode)
            set_state(roles["irrigation_target"], initial_target)
            battery(roles["battery"], charge)
            tag = "ws_prep_" + uuid.uuid4().hex[:12]
            before = logs()
            request = dict(version=1, request_mode="oneTime", devices=[name], enabled=True,
                           target_type=mode, target=target, tag=tag, readings={}, validators={})
            api("events/irrigation_request", request)
            # Both confirmation stages may take ten seconds.
            valve_off = True
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                valve_off = valve_off and state(roles["state"]) == "off" and state(PHYSICAL) == "off"
                if not valve_off:
                    raise RuntimeError("Unexpected valve state")
                time.sleep(0.5)
            evidence = delta(before, logs())
            codes = re.findall(r"watering_system: (?:INFO|ERROR|DENIED|WARNING): ([A-Z_]+):", evidence)
            ready = expected == "PREPARATION_READY"
            checks = {
                "request": tag in evidence and codes.count("REQUEST_RECEIVED") == 1,
                "result": expected in codes,
                "mode": state(roles["mode"]) == (mode if ready else initial_mode),
                "target": float(state(roles["irrigation_target"])) == (target if ready else initial_target),
                "valves_off": valve_off and state(roles["state"]) == "off" and state(PHYSICAL) == "off",
                "no_unexpected_ready": ready or "PREPARATION_READY" not in codes,
            }
            if ready:
                checks["sequence"] = all(c in codes for c in ("PREFLIGHT_OK", "PREPARATION_MODE_OK", "PREPARATION_TARGET_OK", "PREPARATION_READY")) and codes.index("PREFLIGHT_OK") < codes.index("PREPARATION_MODE_OK") < codes.index("PREPARATION_TARGET_OK") < codes.index("PREPARATION_READY")
            result = {"name": label, "status": "PASS" if all(checks.values()) else "FAIL",
                      "checks": checks, "request": request, "logs": evidence}
            report["tests"].append(result)
            print(result["status"], flush=True)
            REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except BaseException as exc:
        report["error"] = repr(exc)
    finally:
        if ws:
            ws.close()
        if original:
            try:
                if state(roles["state"]) != "off":
                    raise RuntimeError("Virtual valve not off; refusing configuration restoration")
                set_state(roles["mode"], original["mode"])
                set_state(roles["irrigation_target"], original["irrigation_target"])
                battery(roles["battery"], original["battery"])
            except Exception as exc:
                report["restoration_errors"].append(str(exc))
        REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("Report:", REPORT, flush=True)
    return 0 if len(report["tests"]) == 5 and all(t["status"] == "PASS" for t in report["tests"]) and not report.get("error") and not report["restoration_errors"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True)
    raise SystemExit(run(parser.parse_args().device))
