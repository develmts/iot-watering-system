from appdaemon.plugins.hass import Hass
from datetime import datetime
import uuid
import math
from .watering_device import WateringDevice
from .controller import Controller
from .reporter import Reporter
from .context_store import ContextStore

class WateringSystem(Hass):

    def initialize(self):
        self.context_store = ContextStore()
        self.reporter = Reporter(self, self.context_store)
        self.reporter.report(
            level="INFO",
            code="SYSTEM_STARTING",
            message="WateringSystem initializing",
            tag=None
        )         


        self.controller = Controller(self, self.reporter, self.context_store)

        self.listen_event(
            self.request_received,
            "irrigation_request"
        )

        self.reporter.report(
            level="INFO",
            code="SYSTEM_READY",
            message="WateringSystem ready",
            tag=None
        )  

    def request_received(self, event_name, data, kwargs):
        self.reporter.report(
            level="INFO",
            code="REQUEST_RECEIVED",
            message=f"Request received: {data}",
            tag=None
        )

        try:
            request = self.normalize_request(data)
        except ValueError as error:
            self.reporter.report(
                level="ERROR",
                code="INVALID_REQUEST",
                message=f"Invalid request: {error}",
                tag=data.get("tag") if isinstance(data.get("tag"), str) else None
            )
            return

        self.dispatch_request(request)

    def normalize_request(self, data):
        version = data.get("version", 1)
        mode = data.get("request_mode")
        devices = data.get("devices")
        target_type = data.get("target_type")
        target = data.get("target")
        readings = data.get("readings", {})
        validators = data.get("validators", {})
        tag = data.get("tag")

        if type(version) is not int or version <= 0:
            raise ValueError("version must be a positive integer")
        if mode not in ("scheduler", "oneTime"):
            raise ValueError(f"Invalid request_mode: {mode}")
        if not isinstance(devices, list) or len(devices) != 1:
            raise ValueError("Phase 1 requires exactly one device in a list")
        if not isinstance(devices[0], str) or not devices[0].strip():
            raise ValueError("Device name must be a non-empty string")
        if target_type not in ("duration", "capacity"):
            raise ValueError(f"Invalid target_type: {target_type}")
        if type(target) not in (int, float) or target <= 0:
            raise ValueError("target must be a positive number")
        if isinstance(target, float) and not math.isfinite(target):
            raise ValueError("target must be finite")
        if target_type == "duration" and type(target) is not int:
            raise ValueError("Duration target must be an integer in seconds")
        for name, value in (("readings", readings), ("validators", validators)):
            if not isinstance(value, dict) or value:
                raise ValueError(f"{name} must be an empty dictionary in phase 1")
        if tag is not None and not isinstance(tag, str):
            raise ValueError("tag must be a string")

        return {
            "request_id": uuid.uuid4().hex[:12],
            "received_at": datetime.now().astimezone().isoformat(),
            "version": version,
            "request_mode": mode,
            "devices": devices,
            "target_type": target_type,
            "target": target,
            "readings": readings,
            "validators": validators,
            "tag": tag,
        }

    def resolve_device_id(self, device):
        self.reporter.report(
            level="INFO",
            code="DEVICE_RESOLVE",
            message=f"Resolving device: {device!r}",
            tag=None
        )
        device_id = self.device_id(device)

        if not device_id:
            raise ValueError(f"Device not found: {device}")

        return device_id

    def dispatch_request(self, request):
        self.reporter.report(
            level="INFO",
            code="REQUEST_NORMALIZED",
            message="Normalized request: "
                    f"request_id={request['request_id']}, "
                    f"received_at={request['received_at']}, "
                    f"version={request['version']}, "
                    f"request_mode={request['request_mode']}, "
                    f"target_type={request['target_type']}, "
                    f"target={request['target']}, "
                    f"devices={request['devices']}, "
                    f"readings={request['readings']}, "
                    f"validators={request['validators']}, "
                    f"tag={request['tag']}",
            tag=None
        )

        for device_id in request["devices"]:
            self.dispatch_device(device_id, request)

    def dispatch_device(self, device, request):
        
        try:
            device_id = self.resolve_device_id(device)
        except ValueError as error:
            self.reporter.report(
                level="ERROR",
                code="DEVICE_NOT_FOUND",
                message=str(error),
                tag=request["tag"]
            )
            return

        self.reporter.report(
            level="INFO",
            code="DEVICE_RESOLVED",
            message=f"Exploring watering device: {device} -> {device_id}",
            tag=None
        )

        #watering_device = WateringDevice(self, device_id)
        watering_device = WateringDevice(
            self,
            self.reporter,
            device_id
        )

        self.controller.handle_request(request, watering_device)
