# Optional cartridge pixel artwork

The shell and slot PNGs are adaptations of artwork from Slot by Brandon Kowalski,
commit `868631d7b131540df87c8e3295638e27445cdba2`:
https://github.com/BrandonKowalski/slot

The artwork is under GPL-3.0. The complete license and original neutral PNGs are
included here. These image files retain their separate license; including them
does not relicense them under PyUI's license.

Adaptation recipe: tint each neutral shell's grayscale with RGB multipliers
(`GBA: 72,77,88`; `GB: 163,164,151`; `GBC: 66,73,77`), divided by 128; reduce
dimensions by two with box filtering; quantize plastic/slot RGB to 20 colors
without dithering; threshold alpha at 128. Draw with nearest-neighbour sampling.
The exact reproducible script is provided in `sources/prepare_cartridge_art.py`
(MIT code). Its input root can be pointed to the corresponding Cheevos asset
source tree, which also contains the demo-only game photographs and labels.

Source and credits for the seven desktop demo cartridges are in the sibling
Cheevos checkout's `assets/cartridges/README.md`; those game sprites are supplied
by the preview harness, and are excluded from the Cheevos device package.
