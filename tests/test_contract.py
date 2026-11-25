from datetime import date
import importlib
import pathlib
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
package = types.ModuleType("ws_test_package")
package.__path__ = [str(ROOT / "src")]
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
                         target_type="duration", target=600, tag="test", enabled=True,
                         season_start="04-01", season_end="10-31")

    def test_defaults(self):
        request = self.ws.normalize_request(self.data)
        self.assertEqual(request["version"], 1)
        self.assertEqual(request["readings"], {})
        self.assertEqual(request["validators"], {})
        self.assertEqual(request["tag"], "test")

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
            ("tag", []), ("tag", None), ("enabled", 1), ("enabled", "on"),
            ("season_start", "02-30"), ("season_end", "4-01"),
            ("season_end", None),
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

    def test_unknown_fields(self):
        self.ws.reporter = Mock()
        self.ws.dispatch_request = Mock()
        data = dict(self.data, foo=1, bar=2, metadata={"origin": "REMOTE"})
        self.ws.request_received("irrigation_request", data, {})
        reports = [call.kwargs for call in self.ws.reporter.report.call_args_list]
        self.assertEqual([r["code"] for r in reports],
                         ["REQUEST_RECEIVED", "UNKNOWN_REQUEST_FIELDS"])
        self.assertEqual(reports[0]["message"], f"Request received: {data}")
        self.assertEqual(reports[1]["level"], "WARNING")
        self.assertEqual(reports[1]["message"], "Ignoring unknown fields: ['bar', 'foo']")
        self.assertIsNone(reports[1]["tag"])
        request = self.ws.dispatch_request.call_args.args[0]
        for field in ("foo", "bar", "metadata"):
            self.assertNotIn(field, request)

    def test_metadata_without_warning(self):
        self.ws.reporter = Mock()
        self.ws.dispatch_request = Mock()
        self.ws.request_received("irrigation_request", dict(self.data, metadata={}), {})
        self.assertEqual(self.ws.reporter.report.call_count, 1)
        self.ws.dispatch_request.assert_called_once()

    def test_unknown_fields_do_not_bypass_validation(self):
        self.ws.reporter = Mock()
        self.ws.dispatch_request = Mock()
        self.ws.request_received("irrigation_request", dict(self.data, foo=1, target=-1), {})
        self.assertEqual(
            [call.kwargs["code"] for call in self.ws.reporter.report.call_args_list],
            ["REQUEST_RECEIVED", "UNKNOWN_REQUEST_FIELDS", "INVALID_REQUEST"]
        )
        self.ws.dispatch_request.assert_not_called()

    def test_device_resolution(self):
        self.ws.reporter = Mock()
        self.ws.read_device_registry = Mock(return_value=[
            {"id": "a", "name": "Original", "name_by_user": "Valve"},
            {"id": "b", "name": "Other"},
        ])
        self.assertEqual(self.ws.resolve_device_id("Valve"), "a")
        with self.assertRaises(ValueError):
            self.ws.resolve_device_id("Original")
        self.ws.read_device_registry.return_value.append({"id": "c", "name": "Valve"})
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            self.ws.resolve_device_id("Valve")

    def test_onetime_ignores_season(self):
        self.ws.reporter = Mock()
        self.ws.dispatch_request = Mock()
        data = dict(self.data, request_mode="oneTime", season_start=None,
                    season_end={"invalid": True})
        self.ws.request_received("irrigation_request", data, {})
        self.assertEqual(self.ws.reporter.report.call_count, 1)
        request = self.ws.dispatch_request.call_args.args[0]
        self.assertNotIn("season_start", request)
        self.assertNotIn("season_end", request)
        del data["season_start"], data["season_end"]
        self.ws.normalize_request(data)
        for field in ("enabled", "tag", "devices", "target", "target_type"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    self.ws.normalize_request({k: v for k, v in data.items() if k != field})

    def test_request_policy(self):
        for mode, enabled, start, end, today, expected in [
            ("scheduler", False, "04-01", "10-31", date(2026, 6, 1), "REQUEST_DISABLED"),
            ("oneTime", False, None, None, date(2026, 6, 1), "REQUEST_DISABLED"),
            ("scheduler", True, "04-01", "10-31", date(2026, 11, 1), "OUTSIDE_SEASON"),
            ("scheduler", True, "04-01", "10-31", date(2026, 4, 1), None),
            ("scheduler", True, "04-01", "10-31", date(2026, 10, 31), None),
            ("scheduler", True, "11-01", "02-28", date(2026, 1, 1), None),
            ("scheduler", True, "11-01", "02-28", date(2026, 6, 1), "OUTSIDE_SEASON"),
            ("oneTime", True, None, None, date(2026, 11, 1), None),
        ]:
            with self.subTest(mode=mode, enabled=enabled, today=today):
                self.ws.reporter = Mock()
                self.ws.dispatch_device = Mock()
                self.ws.date = Mock(return_value=today)
                request = self.ws.normalize_request(dict(self.data, request_mode=mode,
                    enabled=enabled, season_start=start, season_end=end))
                self.ws.dispatch_request(request)
                if expected:
                    self.ws.dispatch_device.assert_not_called()
                    self.assertEqual(self.ws.reporter.report.call_args.kwargs["code"], expected)
                    self.assertEqual(self.ws.reporter.report.call_args.kwargs["tag"], "test")
                else:
                    self.ws.dispatch_device.assert_called_once_with("Valve", request)
                if mode == "oneTime":
                    self.ws.date.assert_not_called()

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
