from appdaemon.plugins.hass import Hass
from .watering_device import WateringDevice
from .controller import Controller
from .reporter import Reporter

class WateringSystem(Hass):

    def initialize(self):
        self.reporter = Reporter(self)
        self.reporter.report(
            level="INFO",
            code="SYSTEM_STARTING",
            message="WateringSystem initializing",
            tag=None
        )         


        self.controller = Controller(self, self.reporter)

        self.listen_event(
            self.request_received,
            "irrigation_request"
        )
        self.reporter = Reporter(self)

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
                tag=data.get("tag")
            )
            return

        self.dispatch_request(request)

    def normalize_request(self, data):
        mode = data.get("mode")
        devices = data.get("devices")
        readings = data.get("readings")
        tag = data.get("tag")

        if mode not in ("scheduler", "oneTime"):
            raise ValueError(f"Invalid mode: {mode}")

        if not devices:
            raise ValueError("No watering devices specified")

        if not isinstance(devices, list):
            devices = [devices]

        if readings is None:
            readings = []
        elif not isinstance(readings, list):
            readings = [readings]

        return {
            "mode": mode,
            "devices": devices,
            "readings": readings,
            "tag": tag,
        }

    def resolve_device_id(self, device):
        device_id = self.device_id(device)

        if not device_id:
            raise ValueError(f"Device not found: {device}")

        return device_id

    def dispatch_request(self, request):
        self.reporter.report(
            level="INFO",
            code="REQUEST_NORMALIZED",
            message="Normalized request: "
                    f"mode={request['mode']}, "
                    f"devices={request['devices']}, "
                    f"readings={request['readings']}, "
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

        # self.reporter.report(
        #     level="INFO",
        #     code="DEVICE_RESOLVED",
        #     message=f"Exploring watering device: {device} -> {device_id}",
        #     tag=None
        # )

        #watering_device = WateringDevice(self, device_id)
        watering_device = WateringDevice(
            self,
            self.reporter,
            device_id
        )
        self.controller.handle_request(
            mode=request["mode"],
            device=watering_device,
            readings=request["readings"],
            tag=request["tag"]
        )

