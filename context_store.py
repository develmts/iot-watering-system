import json
import os
from datetime import datetime


class ContextStore:

    BASE_PATH = "/homeassistant/appdaemon/data/watering_system/contexts"
    
    _CONTEXT_SCHEMA = {
        "device_id": str,
        "request_mode": {"scheduler", "oneTime"},
        "phase": {"STARTING", "WATERING", "STOPPING"},
        "started_at": "datetime",
        "tag": (str, type(None)),
        "requested_target": (int, float, str),
        "messages": "string_list",
    }

    def __init__(self):
        os.makedirs(self.BASE_PATH, exist_ok=True)

    def load(self, key):
        path = self._path(key)

        if not os.path.exists(path):
            return None

        with open(path, "r", encoding="utf-8") as file:
            context = json.load(file)

        self._validate(context)

        return context

    def save(self, key, context):
        self._validate(context)

        path = self._path(key)
        temp_path = path + ".tmp"

        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(context, file, indent=2)

        os.replace(temp_path, path)

    def update(self, key, **values):
        context = self.load(key)

        if context is None:
            context = {}

        context.update(values)
        self.save(key, context)

        return context

    def clear(self, key):
        path = self._path(key)

        if os.path.exists(path):
            os.remove(path)

    def _path(self, key):
        return os.path.join(
            self.BASE_PATH,
            f"{key}.json"
        )

    def _validate(self, context):
        for key, value in context.items():

            if key not in self._CONTEXT_SCHEMA:
                raise ValueError(f"Unknown context field: {key}")

            rule = self._CONTEXT_SCHEMA[key]

            if isinstance(rule, set):
                if value not in rule:
                    raise ValueError(
                        f"Invalid value for {key}: {value}"
                    )

            elif rule == "datetime":
                if not isinstance(value, str):
                    raise ValueError(
                        f"Invalid type for {key}: expected ISO 8601 string"
                    )

                try:
                    parsed = datetime.fromisoformat(value)
                except ValueError:
                    raise ValueError(
                        f"Invalid ISO 8601 datetime for {key}: {value}"
                    )

                if parsed.tzinfo is None:
                    raise ValueError(
                        f"Timezone required for {key}: {value}"
                    )

            elif rule == "string_list":
                if (
                    not isinstance(value, list)
                    or not all(isinstance(item, str) for item in value)
                ):
                    raise ValueError(
                        f"Invalid type for {key}: expected list[str]"
                    )

            else:
                # bool is a subclass of int in Python.
                if isinstance(value, bool) and bool not in rule:
                    raise ValueError(
                        f"Invalid type for {key}: bool is not allowed"
                    )

                if not isinstance(value, rule):
                    raise ValueError(
                        f"Invalid type for {key}: "
                        f"expected {rule}, got {type(value).__name__}"
                    )

