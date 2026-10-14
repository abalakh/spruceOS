"""Render optional, attributed cartridge sprites with crisp pixel sampling.

The prepared art is in assets/cartridges/ beside PyUI. It has separate license
and source notices; this renderer does not depend on Pillow or generate files.
"""

from pathlib import Path

import sdl2

from display.display import Display
from display.font_purpose import FontPurpose
from display.render_mode import RenderMode
from display.resize_type import ResizeType

ROOT = Path(__file__).resolve().parents[1] / "assets" / "cartridges"
PANELS = {
    "GB": (46 / 312, 98 / 337, 220 / 312, 195 / 337),
    "GBC": (45 / 312, 110 / 337, 223 / 312, 199 / 337),
    "GBA": (48 / 360, 50 / 212, 264 / 360, 136 / 212),
}


def pixel_image(path, rect):
    """Create/cache a nearest-neighbour texture, restoring PyUI's default hint."""
    previous = sdl2.SDL_GetHint(sdl2.SDL_HINT_RENDER_SCALE_QUALITY)
    sdl2.SDL_SetHint(sdl2.SDL_HINT_RENDER_SCALE_QUALITY, b"0")
    try:
        x, y, width, height = map(round, rect)
        return Display.render_image(
            str(path), x, y, RenderMode.TOP_LEFT_ALIGNED, width, height, ResizeType.FIT
        )
    finally:
        sdl2.SDL_SetHint(sdl2.SDL_HINT_RENDER_SCALE_QUALITY, previous or b"1")


class CartridgeArt:
    """Find the small reusable sprite pack once per view, not once per ROM."""

    def __init__(self):
        self.shells = {
            system: ROOT / f"shell-{system.lower()}.png" for system in PANELS
        }
        self.shells = {
            system: path for system, path in self.shells.items() if path.is_file()
        }
        self.slots = {layer: ROOT / f"slot-{layer}.png" for layer in ("front", "back")}
        self.has_slot = all(path.is_file() for path in self.slots.values())

    def cartridge(self, system, entry, rect, selected):
        """Draw a complete demo cartridge, or a reusable shell with visible artwork."""
        face = getattr(entry.get_value(), "cartridge_face", None)
        if face and pixel_image(face, rect)[0]:
            return True
        shell = self.shells.get(system)
        if shell is None or not pixel_image(shell, rect)[0]:
            return False
        image = entry.get_image_path_selected() if selected else entry.get_image_path()
        if not image:
            image = entry.get_image_path()
        x, y, width, height = rect
        left, top, panel_width, panel_height = PANELS[system]
        panel = (
            x + width * left,
            y + height * top,
            width * panel_width,
            height * panel_height,
        )
        if image and pixel_image(image, panel)[0]:
            return True
        left, top, width, height = map(round, panel)
        Display.render_box((214, 205, 183), left, top, width, height)
        Display.render_text(
            entry.get_primary_text(),
            left + width // 2,
            top + height // 2,
            (40, 36, 31),
            FontPurpose.DESCRIPTIVE_LIST_DESCRIPTION,
            RenderMode.MIDDLE_CENTER_ALIGNED,
            crop_w=width,
            crop_h=height,
        )
        return True

    def slot(self, geometry, front):
        """Align the slot's two artist-drawn layers around the insertion opening."""
        if not self.has_slot:
            return False
        pixel_image(self.slots["front" if front else "back"], geometry.dock_rect)
        return True
