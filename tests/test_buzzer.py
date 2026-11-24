"""Verify electrical polarity/lifecycle without driving desktop hardware."""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from control.buzzer import Buzzer


class BuzzerTests(unittest.TestCase):
    def setUp(self):
        self.chip = MagicMock()
        self.chip.__enter__.return_value = self.chip
        self.chip.get_info.return_value = SimpleNamespace(
            name="gpiochip0", label="pinctrl-bcm2711", num_lines=58)
        self.chip.get_line_info.return_value.name = "GPIO17"
        self.request = self.chip.request_lines.return_value
        self.line = SimpleNamespace(
            Bias=SimpleNamespace(PULL_UP="pull_up"),
            Direction=SimpleNamespace(OUTPUT="output"),
            Value=SimpleNamespace(ACTIVE="active", INACTIVE="inactive"),
        )
        self.gpiod = SimpleNamespace(Chip=MagicMock(return_value=self.chip),
                                     LineSettings=lambda **kwargs: kwargs)
        self.modules = patch.dict(sys.modules, {"gpiod": self.gpiod, "gpiod.line": self.line})
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def test_request_is_active_low_and_initially_off(self):
        buzzer = Buzzer(mock=False, enabled=False)
        settings = self.chip.request_lines.call_args.kwargs["config"][17]
        self.assertEqual(settings, dict(direction="output", active_low=True,
                                        bias="pull_up", output_value="inactive"))
        buzzer.start()
        self.request.set_value.assert_not_called()
        buzzer.close()

    def test_enable_alone_does_not_sound_and_disable_stops(self):
        buzzer = Buzzer(mock=False, enabled=False)
        buzzer.set_enabled(True)
        self.request.set_value.assert_not_called()
        buzzer.start()
        self.request.set_value.assert_called_with(17, "active")
        buzzer.set_enabled(False)
        self.request.set_value.assert_called_with(17, "inactive")
        self.assertFalse(buzzer.is_active)
        buzzer.close()

    def test_close_explicitly_turns_off_and_releases_once(self):
        buzzer = Buzzer(mock=False)
        buzzer.close()
        self.assertEqual(self.request.method_calls,
                         [("set_value", (17, "inactive"), {}), ("release", (), {})])
        buzzer.close()
        buzzer.set_enabled(True)
        buzzer.start()
        self.request.release.assert_called_once()
        self.assertFalse(buzzer.is_active)

    def test_busy_gpio_fails_without_silent_mock_fallback(self):
        self.chip.request_lines.side_effect = OSError("busy")
        with self.assertRaisesRegex(OSError, "busy"):
            Buzzer(mock=False)

    def test_wrong_chip_rejected_before_output_request(self):
        self.chip.get_info.return_value.label = "other-board"
        with self.assertRaises(RuntimeError):
            Buzzer(mock=False)
        self.chip.request_lines.assert_not_called()

    def test_close_releases_gpio_even_when_off_write_fails(self):
        buzzer = Buzzer(mock=False)
        self.request.set_value.side_effect = OSError("device lost")
        with self.assertRaises(OSError):
            buzzer.close()
        self.request.release.assert_called_once()
        self.assertFalse(buzzer.is_active)
        buzzer.close()

    def test_mock_never_opens_gpio(self):
        buzzer = Buzzer(mock=True)
        buzzer.start()
        self.assertTrue(buzzer.is_active)
        buzzer.close()
        self.gpiod.Chip.assert_not_called()


if __name__ == "__main__":
    unittest.main()
