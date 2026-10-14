"""Check launcher refresh and launch cancellation without opening a display."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main-ui"))

from controller.controller import Controller
from controller.controller_inputs import ControllerInput
from devices.device import Device
from display.display import Display
from views.cartridge_geometry import CONTACT_START, INSERT_SECONDS, PUSH_START
from views.cartridge_view import CartridgeView, console_frame
from views.grid_or_list_entry import GridOrListEntry
from views.view import View


class FakeDevice:
    """Supply only the animation preference the launch hook needs."""

    def __init__(self, animations=True):
        self.animations = animations

    def get_system_config(self):
        """Act as the minimal system config."""
        return self

    def animations_enabled(self):
        """Return the selected preference."""
        return self.animations


class CartridgeViewTests(unittest.TestCase):
    """Exercise state that the ROM menu refreshes on every input tick."""

    def setUp(self):
        """Create state without starting any SDL subsystems."""
        self.entries = [GridOrListEntry("Alpha"), GridOrListEntry("Beta")]
        self.view = CartridgeView.__new__(CartridgeView)
        self.view.options = self.entries
        self.view.selected = 1
        self.view._from = 0.25
        self.view._target = 1
        self.view._moved_at = 123
        self.view._labels = {"cached": "label"}

    def test_unchanged_entries_keep_scroll_and_labels(self):
        """Retain an animation when the menu supplies the same entries again."""
        self.view.set_options(list(self.entries))
        self.assertEqual(self.view._from, 0.25)
        self.assertEqual(self.view._moved_at, 123)
        self.assertEqual(self.view._labels, {"cached": "label"})

    def test_filtered_list_keeps_selected_game(self):
        """Rebase a surviving selection to its new position."""
        self.view.set_options([self.entries[1]])
        self.assertEqual(self.view.selected, 0)
        self.assertEqual(self.view._from, self.view._target)
        self.assertEqual(self.view._target, 0)
        self.assertEqual(self.view._labels, {})

    def test_b_cancels_before_launch(self):
        """Return False without changing the selected game."""
        with (
            patch.object(Device, "get_device", return_value=FakeDevice()),
            patch.object(self.view, "_render") as render,
            patch.object(Controller, "get_input", return_value=True),
            patch.object(Controller, "last_input", return_value=ControllerInput.B),
            patch("views.cartridge_view.time.monotonic", return_value=1),
        ):
            self.assertFalse(self.view.prepare_launch())
            render.assert_called_with()
        self.assertEqual(self.view.selected, 1)

    def test_animations_off_draws_final_frame_without_waiting(self):
        """Respect the existing system animation setting."""
        with (
            patch.object(Device, "get_device", return_value=FakeDevice(False)),
            patch.object(self.view, "_render") as render,
            patch.object(Controller, "get_input") as input_poll,
        ):
            self.assertTrue(self.view.prepare_launch())
            render.assert_called_once_with(1)
            input_poll.assert_not_called()

    def test_b_cancels_during_contact_and_push(self):
        """Keep the new resistance pause and final push responsive to cancellation."""
        for elapsed in (CONTACT_START + 0.08, PUSH_START + 0.08):
            with self.subTest(elapsed=elapsed):
                with (
                    patch.object(Device, "get_device", return_value=FakeDevice()),
                    patch.object(self.view, "_render") as render,
                    patch.object(Controller, "get_input", return_value=True),
                    patch.object(Controller, "last_input", return_value=ControllerInput.B),
                    patch(
                        "views.cartridge_view.time.monotonic",
                        side_effect=[0, elapsed, elapsed],
                    ),
                ):
                    self.assertFalse(self.view.prepare_launch())
                    self.assertAlmostEqual(render.call_args_list[0].args[0], elapsed / INSERT_SECONDS)
                    render.assert_called_with()

    def test_standard_view_launches_immediately(self):
        """Keep the launch behaviour of existing list and grid views."""
        self.assertTrue(View().prepare_launch())

    def test_console_frame_restores_footer_after_clear_and_present(self):
        """Keep both theme draw orders from covering the slot, without leaking state."""
        original = Display.bottom_bar.render_bottom_bar
        self.assertNotIn("render_bottom_bar", vars(Display.bottom_bar))
        with console_frame():
            Display.bottom_bar.render_bottom_bar("Confirm")  # clear's bar-first path
            Display.bottom_bar.render_bottom_bar("Confirm")  # present's bar-last path
        self.assertNotIn("render_bottom_bar", vars(Display.bottom_bar))
        self.assertEqual(Display.bottom_bar.render_bottom_bar, original)

    def test_console_frame_restores_existing_override_after_error(self):
        """Restore a caller's footer renderer if cartridge drawing fails."""
        with patch.object(Display.bottom_bar, "render_bottom_bar") as render:
            with self.assertRaisesRegex(RuntimeError, "draw failed"):
                with console_frame():
                    Display.bottom_bar.render_bottom_bar("Confirm")
                    raise RuntimeError("draw failed")
            Display.bottom_bar.render_bottom_bar("Confirm")
            render.assert_called_once_with("Confirm")


if __name__ == "__main__":
    unittest.main()
