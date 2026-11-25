import importlib
import pathlib
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
package = types.ModuleType("ws_test_package")
package.__path__ = [str(ROOT)]
hass_module = types.ModuleType("appdaemon.plugins.hass")
hass_module.Hass = object
with patch.dict(sys.modules, {
    "ws_test_package": package,
    "appdaemon": types.ModuleType("appdaemon"),
    "appdaemon.plugins": types.ModuleType("appdaemon.plugins"),
    "appdaemon.plugins.hass": hass_module,
}):
    WateringSystem = importlib.import_module("ws_test_package.watering_system").WateringSystem
    Controller = importlib.import_module("ws_test_package.controller").Controller


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.ws = WateringSystem()
        self.data = dict(request_mode="scheduler", devices=["Valve"],
                         target_type="duration", target=600)

    def test_defaults(self):
        request = self.ws.normalize_request(self.data)
        self.assertEqual(request["version"], 1)
        self.assertEqual(request["readings"], {})
        self.assertEqual(request["validators"], {})
        self.assertIsNone(request["tag"])

    def test_capacity_and_future_version(self):
        request = self.ws.normalize_request(dict(self.data, version=2,
                                                  target_type="capacity", target=1.5))
        self.assertEqual(request["target"], 1.5)
        self.assertEqual(request["version"], 2)

    def test_invalid_fields(self):
        for field, value in [
            ("version", True), ("version", 0), ("version", 1.5),
            ("request_mode", "manual"), ("devices", "Valve"),
            ("devices", []), ("devices", ["Valve", "Valve"]),
            ("devices", [" "]), ("devices", [42]),
            ("target_type", "volume"), ("target", True),
            ("target", 0), ("target", -1), ("target", 1.5),
            ("target", float("nan")), ("target", float("inf")),
            ("readings", []), ("readings", {"x": 1}),
            ("validators", None), ("validators", {"x": 1}),
            ("tag", []),
        ]:
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    self.ws.normalize_request(dict(self.data, **{field: value}))

    def test_missing_required_fields(self):
        for field in self.data:
            with self.subTest(field=field):
                data = dict(self.data)
                del data[field]
                with self.assertRaises(ValueError):
                    self.ws.normalize_request(data)

    def test_preflight_never_actuates(self):
        hass, reporter, store, device = Mock(), Mock(), Mock(), Mock()
        device.get_valve_state.return_value = "off"
        device.get_battery.return_value = 80
        device.get_consumption.return_value = 0
        controller = Controller(hass, reporter, store)
        controller.handle_request(self.ws.normalize_request(self.data), device)
        for name in ("set_mode", "set_target", "start", "stop"):
            getattr(device, name).assert_not_called()
        hass.call_service.assert_not_called()
        hass.run_in.assert_not_called()
        store.save.assert_not_called()
        self.assertEqual(reporter.report.call_args.kwargs["code"], "PREPARATION_DISABLED")


if __name__ == "__main__":
    unittest.main()
