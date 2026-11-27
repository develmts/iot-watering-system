import time


class Controller:

    PREPARATION_DEVICES = frozenset({"d975f716f5837b082a07d17b9bde1207"})
    CONFIRM_TIMEOUT = 10
    CONFIRM_INTERVAL = 1

    def __init__(self, hass, reporter, context_store):
        self.hass = hass
        self.reporter = reporter
        self.context_store = context_store
        self.preparing = set()

    def handle_request(self, request, device):
        tag = request["tag"]

        valve_state = device.get_valve_state()

        if valve_state is None:
            self.reporter.report(
                level="ERROR",
                code="VALVE_UNAVAILABLE",
                message="Valve state is unavailable",
                tag=tag
            )
            return

        if valve_state != "off":
            self.reporter.report(
                level="DENIED",
                code="VALVE_NOT_OFF",
                message=f"Valve is not OFF (state={valve_state})",
                tag=tag
            )
            return

        #self.hass.log("Preflight: valve is OFF")

        battery = device.get_battery()

        if battery is None:
            self.reporter.report(
                level="ERROR",
                code="BATTERY_UNAVAILABLE",
                message="Battery level is unavailable",
                tag=tag
            )
            return

        if battery < 15:
            self.reporter.report(
                level="DENIED",
                code="BATTERY_LOW",
                message=f"Battery too low ({battery} %, minimum 15 %)",
                tag=tag
            )
            return

        #self.hass.log(f"Preflight: battery OK ({battery} %)")

        # mode_state = device.get_mode()

        # if mode_state is None:
        #     self.reporter.report(
        #         level="ERROR",
        #         code="MODE_UNAVAILABLE",
        #         message="Irrigation mode is unavailable",
        #         tag=tag
        #     )
        #     return

        # if mode_state != "duration":
        #     self.reporter.report(
        #         level="ERROR",
        #         code="INVALID_MODE",
        #         message=f"Irrigation mode is '{mode_state}', expected 'duration'",
        #         tag=tag
        #     )
        #     return

        #self.hass.log("Preflight: irrigation mode is duration")

        consumption = device.get_consumption()

        if consumption is None:
            self.reporter.report(
                level="ERROR",
                code="CONSUMPTION_UNAVAILABLE",
                message="Water consumption is unavailable",
                tag=tag
            )
            return
        # Everything's ok
        self.reporter.report(
            level="INFO",
            code="PREFLIGHT_OK",
            message="Conditions met",
            tag=tag
        )
        
        if device.device_id not in self.PREPARATION_DEVICES:
            self.reporter.report(
                level="INFO", code="PREPARATION_DISABLED",
                message="Preparation is not authorized for this device",
                tag=tag
            )
            return

        if device.device_id in self.preparing:
            self.reporter.report(level="DENIED", code="PREPARATION_BUSY",
                                 message="Preparation already running", tag=tag)
            return

        self.preparing.add(device.device_id)
        try:
            device.validate_target(request["target_type"], request["target"])
            self.prepare_step(request, device, "mode")
        except Exception as error:
            self.finish_preparation(request, device, error)

    def prepare_step(self, request, device, step):
        if device.get_valve_state() != "off":
            raise RuntimeError("Valve is not OFF")
        desired = request["target_type"] if step == "mode" else request["target"]
        getter = getattr(device, "get_" + step)
        setter = getattr(device, "set_" + step)
        if getter() == desired:
            self.advance_preparation(request, device, step)
            return
        if not setter(desired):
            raise RuntimeError(f"Cannot set {step}")
        self.hass.run_in(self.verify_step, self.CONFIRM_INTERVAL,
                         request=request, device=device, step=step,
                         deadline=time.monotonic() + self.CONFIRM_TIMEOUT)

    def verify_step(self, kwargs):
        request, device, step = (kwargs[k] for k in ("request", "device", "step"))
        try:
            if device.get_valve_state() != "off":
                raise RuntimeError("Valve is not OFF")
            desired = request["target_type"] if step == "mode" else request["target"]
            if getattr(device, "get_" + step)() == desired:
                self.advance_preparation(request, device, step)
            elif time.monotonic() >= kwargs["deadline"]:
                raise RuntimeError(f"Timeout confirming {step}: {desired}")
            else:
                self.hass.run_in(self.verify_step, self.CONFIRM_INTERVAL, **kwargs)
        except Exception as error:
            self.finish_preparation(request, device, error)

    def advance_preparation(self, request, device, step):
        self.reporter.report(level="INFO", code=f"PREPARATION_{step.upper()}_OK",
                             message=f"{step.capitalize()} confirmed", tag=request["tag"])
        if step == "mode":
            self.prepare_step(request, device, "target")
        else:
            if device.get_valve_state() != "off" or device.get_mode() != request["target_type"]:
                raise RuntimeError("Final preparation verification failed")
            self.finish_preparation(request, device)

    def finish_preparation(self, request, device, error=None):
        self.preparing.discard(device.device_id)
        self.reporter.report(
            level="ERROR" if error else "INFO",
            code="PREPARATION_FAILED" if error else "PREPARATION_READY",
            message=str(error) if error else "Device prepared; START disabled",
            tag=request["tag"]
        )
