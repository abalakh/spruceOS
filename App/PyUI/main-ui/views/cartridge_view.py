"""Browse cartridge labels and animate a selected cartridge into a console slot.

CARTRIDGE is opt-in through the normal theme view settings. Art is resolved only
for visible entries; missing art still gets a shell and a title label. The launch
animation happens before the device relinquishes the display, through
View.prepare_launch(). No emulator, save-state or game-switcher policy lives here.
"""

import ctypes
import re
import time
from collections import OrderedDict
from contextlib import contextmanager

import sdl2

from controller.controller import Controller
from controller.controller_inputs import ControllerInput
from devices.device import Device
from devices.wifi.wifi_status import WifiStatus
from display.display import Display
from display.font_purpose import FontPurpose
from display.render_mode import RenderMode
from display.resize_type import ResizeType
from themes.theme import Theme
from views.cartridge_art import CartridgeArt
from views.cartridge_geometry import (
    INSERT_SECONDS,
    Geometry,
    ease,
    shell_for,
    visible_slots,
)
from views.selection import Selection
from views.view import View

TITLE = FontPurpose.DESCRIPTIVE_LIST_TITLE
BODY = FontPurpose.DESCRIPTIVE_LIST_DESCRIPTION
MOVE_SECONDS = 0.22


def _omit_bottom_bar(*args, **kwargs):
    """Let the console artwork occupy the footer for this frame."""


@contextmanager
def console_frame():
    """Suppress the theme footer through clear/present, restoring it on exit.

    Themes can draw their bars first or last. Scope the override to one frame
    so other views and popups retain the normal bottom bar, including on errors.
    """
    bar = Display.bottom_bar
    had_override = "render_bottom_bar" in vars(bar)
    previous = bar.render_bottom_bar
    bar.render_bottom_bar = _omit_bottom_bar
    try:
        yield
    finally:
        if had_override:
            bar.render_bottom_bar = previous
        else:
            del bar.render_bottom_bar


def tint(color, amount):
    """Shade plastic with opaque colours (also works on the Mini's SDL driver)."""
    return tuple(min(max(channel + amount, 0), 255) for channel in color)


def rounded(color, rect, cut):
    """Fill a bevelled rectangle with three opaque draw calls."""
    x, y, width, height = map(round, rect)
    cut = max(1, min(round(cut), width // 3, height // 3))
    Display.render_box(color, x + cut, y, width - 2 * cut, height)
    Display.render_box(color, x, y + cut, width, height - 2 * cut)
    Display.render_box(color, x + cut // 2, y + cut // 2, width - cut, height - cut)


class CartridgeView(View):
    """Keep controller navigation and a bounded label cache for a cartridge shelf."""

    def __init__(self, top_bar_text, options, selected_index=0):
        super().__init__()
        self.top_bar_text = top_bar_text
        self.options = list(options)
        self.selected = (selected_index or 0) % max(len(self.options), 1)
        self._target = self._from = self.selected
        self._moved_at = 0.0
        self._labels = OrderedDict()
        self.art = CartridgeArt()
        device = Device.get_device()
        self.geometry = Geometry(
            device.screen_width(),
            device.screen_height(),
            Display.get_top_bar_height(),
        )
        self._title_room = self._title_width()

    def _title_width(self):
        """Measure the centred title's room between the clock and status icons."""
        device = Device.get_device()
        purpose = FontPurpose.BATTERY_PERCENT
        left = 0
        if Theme.show_clock():
            clock = re.sub(r"\d", "0", Display.top_bar.get_current_time_hhmm())
            left = (
                Theme.get_top_bar_initial_x_offset()
                + Display.get_text_dimensions(purpose, clock)[0]
            )
        right = self.geometry.width - 20
        if Theme.display_battery_percent():
            right -= Display.get_text_dimensions(purpose, "100")[0] + 10
        icons = []
        if Theme.display_battery_icon():
            icons.append(Theme.get_battery_icon(device.get_charge_status(), 100))
        if device.supports_wifi():
            icons.append(Theme.get_wifi_icon(WifiStatus.GREAT))
        for path in icons:
            if path:
                right -= Display.get_image_dimensions(path)[0] + 10
        centre = self.geometry.width // 2
        return max(2 * (min(centre - left, right - centre) - 10), 1)

    def set_options(self, options):
        """Replace a filtered collection while retaining a valid selection."""
        replacement = list(options)
        if len(replacement) == len(self.options) and all(
            left is right for left, right in zip(replacement, self.options)
        ):
            # The ROM menu re-supplies this list on every tick. Keep an in-flight
            # scroll and fitted labels until entries actually change.
            return
        previous = self.get_selected_option()
        self.options = replacement
        self.selected = next(
            (i for i, entry in enumerate(self.options) if entry == previous), 0
        )
        self._from = self._target = self.selected
        self._labels.clear()

    def get_selected_option(self):
        """Return the real entry, never a repeated carousel placeholder."""
        return self.options[self.selected] if self.options else None

    def _system(self, entry):
        """Read ROM metadata or the desktop preview's explicit console name."""
        value = entry.get_value()
        preview = getattr(value, "cartridge_system", None)
        system = getattr(value, "game_system", None)
        return preview or getattr(system, "system_name", "")

    def _position(self):
        """Sample an interruptible, time-based scroll transition."""
        if not Device.get_device().get_system_config().animations_enabled():
            return float(self._target)
        progress = (time.monotonic() - self._moved_at) / MOVE_SECONDS
        return self._from + (self._target - self._from) * ease(progress)

    def adjust_selected(self, amount, skip_by_letter=False):
        """Move one cartridge or a page, wrapping across the end of the shelf."""
        if not self.options:
            return
        amount = self.calculate_amount_to_move_by(amount, skip_by_letter)
        self._from = self._position()
        self._target += amount
        self.selected = self._target % len(self.options)
        self._moved_at = time.monotonic()

    def _fit(self, value, purpose, width):
        """Fit a stable label once, with a bounded cache for long ROM libraries."""
        key = (str(value), purpose, round(width))
        if key in self._labels:
            self._labels.move_to_end(key)
            return self._labels[key]
        value = str(value)
        if Display.get_text_dimensions(purpose, value)[0] > width:
            low, high = 0, len(value)
            while low < high:
                middle = (low + high + 1) // 2
                if (
                    Display.get_text_dimensions(purpose, value[:middle] + "...")[0]
                    <= width
                ):
                    low = middle
                else:
                    high = middle - 1
            value = value[:low] + "..."
        self._labels[key] = value
        if len(self._labels) > 96:
            self._labels.popitem(last=False)
        return value

    def _text(self, value, y, purpose=BODY):
        """Centre theme text in the page, clear of the screen edges."""
        geometry = self.geometry
        fitted = self._fit(value, purpose, geometry.width - round(32 * geometry.scale))
        Display.render_text(
            fitted,
            geometry.width // 2,
            round(y),
            Theme.text_color(purpose),
            purpose,
            RenderMode.TOP_CENTER_ALIGNED,
        )

    def _cartridge(self, entry, rect, selected):
        """Layer a moulded plastic shell, grip ridges and an artwork label."""
        if self.art.cartridge(self._system(entry), entry, rect, selected):
            return
        x, y, width, height = map(round, rect)
        shell = shell_for(self._system(entry))
        color = shell.color
        rim = max(2, round(width * 0.025))
        cut = max(2, round(width * 0.04))
        rounded(tint(color, -45), (x + 3, y + 5, width, height), cut)
        rounded(tint(color, 27), (x, y, width, height), cut)
        rounded(tint(color, -32), (x, y + rim, width, height - rim), cut)
        rounded(color, (x + rim, y + rim, width - rim * 2, height - rim * 3), cut)
        for index in range(4):
            rib_y = y + round(height * 0.20) + index * max(3, round(width * 0.026))
            for rib_x in (x + rim * 2, x + width - rim * 4):
                Display.render_box(
                    tint(color, -25), rib_x, rib_y, rim * 2, max(1, rim // 2)
                )
        # GB's taller shell has the embossed panel above the label.
        header = 0.23 if shell.aspect > 1 else 0.19
        lx, ly = x + round(width * 0.12), y + round(height * header)
        lw, lh = (
            round(width * 0.76),
            round(height * (0.68 if shell.aspect > 1 else 0.66)),
        )
        rounded(tint(color, -44), (lx - rim, ly - rim, lw + rim * 2, lh + rim * 2), rim)
        rounded((220, 210, 184), (lx, ly, lw, lh), rim)
        image = entry.get_image_path_selected() if selected else entry.get_image_path()
        if not image:
            image = entry.get_image_path()
        shown = (0, 0)
        if image:
            shown = Display.render_image(
                image,
                lx + lw // 2,
                ly + lh // 2,
                RenderMode.MIDDLE_CENTER_ALIGNED,
                max(lw - rim * 2, 1),
                max(lh - rim * 2, 1),
                ResizeType.ZOOM,
            )
        if not shown[0]:
            # A text label stays usable when a ROM has no art, or an image fails to load.
            label = self._fit(entry.get_primary_text(), BODY, lw - rim * 2)
            Display.render_text(
                label,
                lx + lw // 2,
                ly + lh // 2,
                (40, 36, 31),
                BODY,
                RenderMode.MIDDLE_CENTER_ALIGNED,
                crop_h=lh,
            )
        # Small moulding details, kept away from artwork and the contacts.
        screw = max(2, round(width * 0.018))
        Display.render_box(
            tint(color, -35),
            x + width // 2 - screw,
            y + height - rim * 3,
            screw * 2,
            screw,
        )

    def _dock(self, front=False):
        """Draw the slot, then its opaque front lip to hide the sinking cartridge."""
        geometry = self.geometry
        if self.art.slot(geometry, front):
            return
        x, _, width, _ = geometry.dock_rect
        y = geometry.slot_y
        pad = round(7 * geometry.scale)
        if not front:
            rounded(
                (23, 23, 25),
                (x - pad, y - pad, width + 2 * pad, 24 * geometry.scale),
                pad,
            )
            rounded((111, 108, 111), (x, y, width, 16 * geometry.scale), pad // 2)
            rounded(
                (13, 14, 18),
                (x + pad, y + pad // 2, width - 2 * pad, 10 * geometry.scale),
                2,
            )
        else:
            # Cover everything below the slot's opening, including the moving cart's shadow.
            rounded(
                (66, 64, 69),
                (x - pad, y + pad, width + 2 * pad, geometry.height - y - pad),
                pad,
            )
            Display.render_box(
                (145, 140, 144), x, y + pad, width, max(1, round(2 * geometry.scale))
            )

    def _clipped_cartridge(self, entry, rect, selected):
        """Clip the cartridge at the slot opening, restoring the renderer's prior clip."""
        renderer = Display.renderer.sdlrenderer
        previous = sdl2.SDL_Rect()
        clipped = sdl2.SDL_RenderIsClipEnabled(renderer)
        sdl2.SDL_RenderGetClipRect(renderer, ctypes.byref(previous))
        geometry = self.geometry
        stage = sdl2.SDL_Rect(
            0,
            geometry.top,
            geometry.width,
            max(1, geometry.slot_y - geometry.top),
        )
        sdl2.SDL_RenderSetClipRect(renderer, ctypes.byref(stage))
        try:
            self._cartridge(entry, rect, selected)
        finally:
            sdl2.SDL_RenderSetClipRect(
                renderer, ctypes.byref(previous) if clipped else None
            )

    def _render(self, launch_progress=None):
        """Draw the visible shelf or one cartridge sinking behind the slot lip."""
        if Display._screensaver_active:
            return
        with console_frame():
            self._render_frame(launch_progress)

    def _render_frame(self, launch_progress):
        """Keep the selected game's title above a footer made only of console art."""
        geometry = self.geometry
        entry = self.get_selected_option()
        title = entry.get_primary_text() if entry is not None else self.top_bar_text
        Display.clear(
            self._fit(title, FontPurpose.TOP_BAR_TEXT, self._title_room),
            bottom_bar_text="",
        )
        if entry is None:
            self._text("No cartridges", geometry.height // 2, TITLE)
            Display.present()
            return
        shell = shell_for(self._system(entry))
        self._dock()
        if launch_progress is None:
            for index, distance in visible_slots(self._position(), len(self.options)):
                current = self.options[index]
                current_shell = shell_for(self._system(current))
                rect = geometry.browse_rect(current_shell, distance)
                x, _, width, _ = rect
                if x + width < 0 or x > geometry.width:
                    continue
                self._clipped_cartridge(current, rect, index == self.selected)
        else:
            self._clipped_cartridge(
                entry, geometry.launch_rect(shell, launch_progress), True
            )
        self._dock(front=True)
        Display.present()

    def get_selection(self, select_controller_inputs=None):
        """Return standard PyUI selections, preserving the menus' contextual actions."""
        self._render()
        accepted = (
            select_controller_inputs
            if select_controller_inputs is not None
            else [ControllerInput.A]
        )
        animating = abs(self._position() - self._target) > 0.001
        if Controller.get_input(timeout=1 / 60 if animating else 1 / 12):
            pressed = Controller.last_input()
            if pressed in accepted or pressed == ControllerInput.B:
                return Selection(self.get_selected_option(), pressed, self.selected)
            moves = {
                ControllerInput.DPAD_LEFT: -1,
                ControllerInput.DPAD_RIGHT: 1,
                ControllerInput.DPAD_UP: -1,
                ControllerInput.DPAD_DOWN: 1,
                ControllerInput.L1: -3,
                ControllerInput.R1: 3,
                ControllerInput.L2: -3,
                ControllerInput.R2: 3,
            }
            if pressed in moves:
                self.adjust_selected(
                    moves[pressed], pressed in (ControllerInput.L2, ControllerInput.R2)
                )
        return Selection(self.get_selected_option(), None, self.selected)

    def prepare_launch(self):
        """Insert before display handoff; B cancels without changing recents or launching."""
        if not self.options:
            return False
        self._from = self._target
        started = time.monotonic()
        duration = (
            INSERT_SECONDS
            if Device.get_device().get_system_config().animations_enabled()
            else 0
        )
        while duration and time.monotonic() - started < duration:
            self._render(min((time.monotonic() - started) / duration, 1))
            if (
                Controller.get_input(timeout=1 / 60)
                and Controller.last_input() == ControllerInput.B
            ):
                self._render()
                return False
        self._render(1)
        return True

    def render_inserted(self):
        """Hold the final frame for the desktop launch preview."""
        self._render(1)
