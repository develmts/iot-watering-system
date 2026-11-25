class Reporter:

    def __init__(self, hass, context_store):
        self.hass = hass
        self.context_store = context_store
        self.messages = {}

    def report(self, level, code, message, tag=None):
        level = level.upper()

        self._log(level, code, message)

        if tag is not None:
            self._notify(message, tag)

    def get_messages(self, tag):
        if tag is None:
            return []

        return list(self.messages.get(tag, []))

    def _log(self, level, code, message):
        log_level = {
            "SUCCESS": "INFO",
            "INFO": "INFO",
            "WARNING": "WARNING",
            "DENIED": "WARNING",
            "ERROR": "ERROR",
        }.get(level, "INFO")

        self.hass.log(
            f"{level}: {code}: {message}",
            level=log_level
        )

    def _notify(self, message, tag):
        if tag not in self.messages:
            self.messages[tag] = []

        self.messages[tag].append(message)

        notification_message = "\n".join(self.messages[tag])

        self.hass.call_service(
            "persistent_notification/create",
            title="Watering cycle",
            message=notification_message,
            notification_id=tag
        )

    def clear(self, tag):
        self.messages.pop(tag, None)