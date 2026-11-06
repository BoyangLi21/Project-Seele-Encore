"""Preserve the GeoFront air gaps when simplifying its stacked facilities."""
from pathlib import Path
import argparse
import re
import tomllib


def configure(game: Path):
    path = game / "config/DistantHorizons.toml"
    text = path.read_text(encoding="utf-8")
    settings = {
        "enableCaveCulling": "false",
        "verticalQuality": '"PIXEL_ART"',
        "enableDistantGeneration": "false",
    }
    for key, value in settings.items():
        text, count = re.subn(
            rf"(?m)^(\s*{key}\s*=\s*)[^\r\n]+", rf"\g<1>{value}", text
        )
        if count != 1:
            raise ValueError(f"Expected one {key}, found {count}")
    path.write_text(text, encoding="utf-8")
    actual = tomllib.loads(path.read_text(encoding="utf-8"))
    graphics = actual["client"]["advanced"]["graphics"]
    assert not graphics["culling"]["enableCaveCulling"]
    assert graphics["quality"]["verticalQuality"] == "PIXEL_ART"
    assert not actual["common"]["worldGenerator"]["enableDistantGeneration"]
    print("LOD configuration read back: cavern gaps retained; background generation off")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("game", type=Path)
    configure(parser.parse_args().game)
