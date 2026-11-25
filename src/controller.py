class Controller:

    def __init__(self, hass, reporter, context_store):
        self.hass = hass
        self.reporter = reporter
        self.context_store = context_store

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
        
        # Development interlock: preparation and execution are not enabled.
        self.reporter.report(
            level="INFO",
            code="PREPARATION_DISABLED",
            message=f"Physical actions disabled; requested {request['target_type']} target: {request['target']}",
            tag=tag
        )
