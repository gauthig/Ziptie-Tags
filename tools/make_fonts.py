"""Developer tool: download open-licensed fonts and write static Bold TTFs into ``fonts/``.

Run once (needs internet and ``fonttools``); the generated files are committed.
Usage: python tools/make_fonts.py
"""
from __future__ import annotations

import io
import urllib.request
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

RAW = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
FONTS_DIR = Path(__file__).resolve().parents[1] / "fonts"

# (display name, google/fonts directory, source file name, is_variable)
FONTS = [
    ("Roboto", "roboto", "Roboto[wdth,wght].ttf", True),
    ("Open Sans", "opensans", "OpenSans[wdth,wght].ttf", True),
    ("Lato", "lato", "Lato-Bold.ttf", False),
    ("Montserrat", "montserrat", "Montserrat[wght].ttf", True),
    ("Oswald", "oswald", "Oswald[wght].ttf", True),
    ("Source Sans 3", "sourcesans3", "SourceSans3[wght].ttf", True),
    ("Noto Sans", "notosans", "NotoSans[wdth,wght].ttf", True),
    ("Roboto Condensed", "robotocondensed", "RobotoCondensed[wght].ttf", True),
    ("Poppins", "poppins", "Poppins-Bold.ttf", False),
    ("Inter", "inter", "Inter[opsz,wght].ttf", True),
]


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url.replace("[", "%5B").replace("]", "%5D").replace(",", "%2C")) as r:
        return r.read()


def main() -> None:
    FONTS_DIR.mkdir(exist_ok=True)
    for name, folder, src, variable in FONTS:
        out = FONTS_DIR / (name.replace(" ", "") + "-Bold.ttf")
        font = TTFont(io.BytesIO(fetch(f"{RAW}{folder}/{src}")))
        if variable:
            axes = {"wght": 700}
            if "wdth" in {a.axisTag for a in font["fvar"].axes}:
                axes["wdth"] = 100
            if "opsz" in {a.axisTag for a in font["fvar"].axes}:
                axes["opsz"] = 14
            font = instantiateVariableFont(font, axes)
        font.save(out)
        (FONTS_DIR / f"OFL-{name.replace(' ', '')}.txt").write_bytes(fetch(f"{RAW}{folder}/OFL.txt"))
        print("wrote", out.name)


if __name__ == "__main__":
    main()
