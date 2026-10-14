"""Pure layout and animation helpers for the cartridge carousel."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Shell:
    """Describe a cartridge's silhouette and plastic colour."""

    name: str
    aspect: float
    color: tuple[int, int, int]


SHELLS = {
    "GB": Shell("GAME BOY", 168 / 156, (173, 179, 164)),
    "GBC": Shell("GAME BOY COLOR", 168 / 156, (104, 89, 139)),
    "GBA": Shell("GAME BOY ADVANCE", 106 / 180, (73, 77, 98)),
}
GENERIC = Shell("CARTRIDGE", 0.85, (105, 113, 116))

# Keep timing shared by the interactive launch hook and the demo recorder.
SHRINK_SECONDS = 0.24
APPROACH_SECONDS = 0.32
CONTACT_SECONDS = 0.18
PUSH_SECONDS = 0.22
CONTACT_START = SHRINK_SECONDS + APPROACH_SECONDS
PUSH_START = CONTACT_START + CONTACT_SECONDS
INSERT_SECONDS = PUSH_START + PUSH_SECONDS


def shell_for(system):
    """Choose the shell without requiring ROM files or artwork."""
    return SHELLS.get(str(system).upper(), GENERIC)


def ease(progress):
    """Ease a clamped time fraction with a smooth stop at each end."""
    t = min(max(progress, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def visible_slots(position, count):
    """Return nearby (index, distance) pairs, drawing short collections only once."""
    if count <= 0:
        return []
    nearest = {}
    middle = math.floor(position)
    for slot in range(middle - 2, middle + 4):
        index, distance = slot % count, slot - position
        if index not in nearest or abs(distance) < abs(nearest[index]):
            nearest[index] = distance
    return sorted(nearest.items(), key=lambda item: abs(item[1]), reverse=True)


@dataclass(frozen=True)
class Geometry:
    """Fit a cartridge stage above a console slot anchored to the bottom edge."""

    width: int
    height: int
    top: int

    @property
    def scale(self):
        """Use the theme's 640x480 design scale, including portrait panels."""
        return min(self.width / 640, self.height / 480)

    @property
    def dock_rect(self):
        """Fill the screen's foot, keeping the slot wide enough for portrait carts."""
        share = 0.60 if self.height > self.width else 0.35
        width = max(self.width, round(self.width * share * 720 / 252))
        height = max(1, round(width * 58 / 720))
        return ((self.width - width) // 2, self.height - height, width, height)

    @property
    def slot_y(self):
        """Match the opening in the back/front sprites, with no footer below it."""
        _, top, _, height = self.dock_rect
        return top + round(height * 24 / 58)

    def browse_width(self, shell):
        """Make the focused cartridge large, with neighbours peeking at the sides."""
        room = max(self.slot_y - self.top - round(48 * self.scale), 1)
        share = 0.84 if self.height > self.width else 0.58
        return max(1, round(min(self.width * share, room / shell.aspect)))

    @property
    def stage_centre(self):
        """Centre the browsing art above the slot, independent of shell shape."""
        return (self.top + self.slot_y) / 2

    def browse_rect(self, shell, distance=0):
        """Grow each cartridge as it rotates into focus, keeping short shelves unique."""
        base = self.browse_width(shell)
        factor = max(0.50, 1 - abs(distance) * 0.22)
        width = max(1, round(base * factor))
        height = max(1, round(width * shell.aspect))
        pitch = min(
            self.width * (0.64 if self.height > self.width else 0.53), base * 0.92
        )
        return (
            round(self.width / 2 + distance * pitch - width / 2),
            round(self.stage_centre - height / 2),
            width,
            height,
        )

    def inserted_width(self, shell):
        """Fit the physical opening with a small clearance at both edges."""
        opening = self.dock_rect[2] * 252 / 720
        return max(1, round(min(self.browse_width(shell), opening * 0.98)))

    def launch_rect(self, shell, progress):
        """Shrink, approach, hold against the opening, then push firmly inside."""
        elapsed = min(max(progress, 0), 1) * INSERT_SECONDS
        start_width = self.browse_width(shell)
        fitted_width = self.inserted_width(shell)
        width = round(
            start_width
            + (fitted_width - start_width) * ease(elapsed / SHRINK_SECONDS)
        )
        height = round(width * shell.aspect)
        y = self.stage_centre - height / 2
        if elapsed >= SHRINK_SECONDS:
            contact_y = self.slot_y - height
            y += (contact_y - y) * ease(
                (elapsed - SHRINK_SECONDS) / APPROACH_SECONDS
            )
            if elapsed >= PUSH_START:
                y = contact_y + (height + 5) * ease(
                    (elapsed - PUSH_START) / PUSH_SECONDS
                )
        return (
            round(self.width / 2 - width / 2),
            round(y),
            width,
            height,
        )
