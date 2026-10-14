Cartridge view prototype
========================

CARTRIDGE is an optional PyUI view. Select it in Settings > Theme > Game
Selection > View Type, or set gameSelectionViewType to CARTRIDGE in a theme
config. It also works with gameSwitcherViewType: CARTRIDGE. No default theme
config is changed by this prototype.

Left/right and up/down browse; L1/R1 move three entries (or change tabs when
the caller claims them); L2/R2 retain PyUI's skip-by-letter navigation. A uses
the normal ROM launch path. View.prepare_launch() is called for an actual
game file before it is added to recents or the device closes PyUI. The
cartridge view inserts the cartridge first; B during that transition cancels.
Browsing shows large cartridges that grow into focus. On launch, the selected
cartridge shrinks to fit the opening, descends, pauses briefly against the
slot, and then pushes inside. The geometry module owns the phase durations
so interactive playback and the desktop recording use the same timing.
All other views return True immediately from the base hook.

The shell comes from RomInfo.game_system.system_name: GB, GBC, GBA or a
generic shell for other systems. Artwork is looked up for visible entries,
with a text label if no image exists or an image cannot be rendered. The
optional sprite pack in main-ui/assets/cartridges supplies embossed pixel
shells and front/back slot artwork adapted from Slot. Its separate GPL-3.0
license, sources and adaptation notes are included. Fonts, background and
the top bar still come from the theme. The selected game's title appears
at the top; the console slot fills the bottom edge with no button hints or
details below it. The theme footer is suppressed only for cartridge frames.
Nearest-neighbour sampling keeps sprites
sharp. Missing sprite packs retain the SDL primitive fallback. No image
generator or additional runtime dependency is used. Short collections never
repeat entries, and label fitting stays bounded.

Desktop preview from the sibling Cheevos checkout:

    make cartridges RES=752x560 SCALE=1

This uses PyUI's DESKTOP device and seven authentic cartridge prints. Select
cycles GBA/GB/GBC shelves; A inserts; B cancels, returns from the final
preview, or exits from a shelf. The preview never launches a real game.
The fake card is kept inside Cheevos/dev/sdcard-cartridges.
Sources and photo credits are in Cheevos/assets/cartridges/README.md. Pillow
is a development-only dependency for rebuilding art and recording GIFs.
make cartridge-demo records an attributed, shareable desktop concept demo
covering browsing and insertion across all three systems.

Test coverage is in Cheevos/tests/screens/test_cartridge_preview.py; it
uses this source checkout through CHEEVOS_CARTRIDGE_PYUI_DIR, or the sibling
spruceOS checkout by default. It covers browsing, insertion, cancellation,
short collections, wraparound, and four resolutions.
State tests also live in App/PyUI/tests/test_cartridge_view.py and can run
with the Cheevos Python environment from its checkout:

    .venv/bin/python ../spruceOS/App/PyUI/tests/test_cartridge_view.py

Deferred: ejection, remembering a cartridge across the PyUI/game process
handoff, special subfolder launches, theme-specific cartridge assets, and
performance/SDL-driver verification on handhelds. On the Mini, PyUI exits
while the emulator is running; returning ejection must be triggered after
PyUI starts again, before it opens the requested game-switcher view.
