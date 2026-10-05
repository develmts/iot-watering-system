class WateringDevice:

    def __init__(self, hass, reporter, device_id):
        self.hass = hass
        self.reporter = reporter
        self.device_id = device_id
        self.valve_entity = None
        self.battery_entity = None
        self.consumption_entity = None
        self.target_entity = None
        self.mode_entity = None

        self.scan_entities()

    def scan_entities(self):
        entities = self.hass.device_entities(self.device_id)

        for entity_id in entities:
            state = self.hass.get_state(
                entity_id,
                attribute="all"
            )

            if not state:
                continue

            attributes = state.get("attributes", {})
            domain = entity_id.split(".", 1)[0]
            name = entity_id.lower()

            device_class = attributes.get("device_class")
            state_class = attributes.get("state_class")
            unit = attributes.get("unit_of_measurement")
            options = attributes.get("options", [])

            # Battery
            if (
                domain == "sensor"
                and device_class == "battery"
            ):
                self.battery_entity = entity_id

            # Water consumption
            elif (
                domain == "sensor"
                and device_class == "water"
                and state_class == "total_increasing"
            ):
                self.consumption_entity = entity_id

            # Main valve
            elif (
                domain == "switch"
                and name.endswith("_state")
            ):
                self.valve_entity = entity_id

            # Irrigation mode
            elif (
                domain == "select"
                and "duration" in options
                and "capacity" in options
            ):
                self.mode_entity = entity_id

            # Irrigation target
            elif (
                domain == "number"
                and (
                    "irrigation_target" in name
                    or unit == "seconds or litres"
                )
            ):
                self.target_entity = entity_id

        self.log_discovery()

    def log_discovery(self):
        self.reporter.report(
            level="INFO",
            code="DEVICE_DISCOVERY",
            message=(
                "WateringDevice discovery:\n"
                f"  valve       = {self.valve_entity}\n"
                f"  battery     = {self.battery_entity}\n"
                f"  consumption = {self.consumption_entity}\n"
                f"  target      = {self.target_entity}\n"
                f"  mode        = {self.mode_entity}"
            ),
            tag=None
        )        

    def get_battery(self):
        if self.battery_entity is None:
            return None

        state = self.hass.get_state(self.battery_entity)

        if state in (None, "unknown", "unavailable"):
            return None

        return float(state)


    def get_consumption(self):
        if self.consumption_entity is None:
            return None

        state = self.hass.get_state(self.consumption_entity)

        if state in (None, "unknown", "unavailable"):
            return None

        return float(state)


    def get_valve_state(self):
        if self.valve_entity is None:
            return None

        return self.hass.get_state(self.valve_entity)


    def get_mode(self):
        if self.mode_entity is None:
            return None

        return self.hass.get_state(self.mode_entity)


    def get_target(self):
        if self.target_entity is None:
            return None

        state = self.hass.get_state(self.target_entity)

        if state in (None, "unknown", "unavailable"):
            return None

        return float(state)

    def start(self):
        if self.valve_entity is None:
            raise RuntimeError("Valve entity not available")

        self.hass.call_service(
            "switch/turn_on",
            entity_id=self.valve_entity
        )


    def stop(self):
        if self.valve_entity is None:
            raise RuntimeError("Valve entity not available")

        self.hass.call_service(
            "switch/turn_off",
            entity_id=self.valve_entity
        )

