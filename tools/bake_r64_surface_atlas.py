"""Draw the fixed surface overview from the installed Xaero leaf colours, north up."""

import argparse
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
from PIL import Image
from scipy.ndimage import median_filter, minimum_filter

from xaero_cache_codec import Cache, unpack_heights


# The authored Hakone/Odawara landscape, offshore facilities, and a strip of exterior terrain.
MIN_X, MAX_X, MIN_Z, MAX_Z = -4096, 6144, -3072, 4608
REGION_SIZE, TILE_SIZE, BLOCKS_PER_PIXEL = 512, 64, 4


def save_png(image, destination):
    with NamedTemporaryFile(dir=destination.parent, suffix=".png", delete=False) as tmp:
        temp_path = Path(tmp.name)
    try:
        image.save(temp_path, compress_level=5)
        with Image.open(temp_path) as check:
            check.verify()
        os.replace(temp_path, destination)
    finally:
        temp_path.unlink(missing_ok=True)


def bake(map_root, output, regions=None):
    png = output / "assets/projectseele/area_maps/surface.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    bounds = (MIN_X, MAX_X, MIN_Z, MAX_Z)
    size = ((MAX_X - MIN_X) // BLOCKS_PER_PIXEL, (MAX_Z - MIN_Z) // BLOCKS_PER_PIXEL)
    footprint = {(x, z) for x in range(MIN_X // REGION_SIZE, MAX_X // REGION_SIZE)
                 for z in range(MIN_Z // REGION_SIZE, MAX_Z // REGION_SIZE)}
    wanted = footprint
    if regions is None:
        atlas = Image.new("RGB", size)
    else:
        with Image.open(png) as previous:
            if previous.size != size or previous.mode != "RGB":
                raise ValueError("The previous atlas does not match the current projection")
            atlas = previous.copy()
        wanted = footprint.intersection(regions)
    tile_pixels = TILE_SIZE // BLOCKS_PER_PIXEL
    elevations = np.empty((size[1], size[0]), dtype=np.int16)
    for rx, rz in sorted(footprint):
        candidates = list((map_root / "cache_1").glob(f"{rx}_{rz}.xwmc*"))
        if len(candidates) != 1:
            raise ValueError(f"Expected one Xaero surface cache at {rx},{rz}: {candidates}")
        leaf = Cache.open(candidates[0])
        for tx in range(8):
            for tz in range(8):
                tile = leaf.tiles.get(tx * 16 + tz)
                if tile is None:
                    raise ValueError(f"Unbaked map tile at {rx},{rz}/{tx},{tz}")
                x = (rx * REGION_SIZE + tx * TILE_SIZE - MIN_X) // BLOCKS_PER_PIXEL
                z = (rz * REGION_SIZE + tz * TILE_SIZE - MIN_Z) // BLOCKS_PER_PIXEL
                if (rx, rz) in wanted:
                    # The fourth native byte carries light. It must not become PNG transparency.
                    colour = tile.image().convert("RGB")
                    atlas.paste(colour.resize((tile_pixels, tile_pixels), Image.Resampling.BOX), (x, z))
                # Pool the top surface, including water, rather than the sea bed.
                top = unpack_heights(tile.top_heights)
                pooled = top.reshape(tile_pixels, BLOCKS_PER_PIXEL, tile_pixels, BLOCKS_PER_PIXEL).max(axis=(1, 3))
                if np.any(pooled == -32768):
                    raise ValueError(f"Unbaked Xaero surface elevation at {rx},{rz}/{tx},{tz}")
                elevations[z:z + tile_pixels, x:x + tile_pixels] = pooled
    # Bridge decks, shafts and narrow towers can differ greatly from street elevation.
    # Keep nearby streets on the surface atlas; deeper transit uses its own surveyed floor.
    bottom = minimum_filter(median_filter(elevations, size=5), size=9).astype(np.int32) - 56
    packed = (bottom + 32768).astype(np.uint16)
    encoded = np.zeros((*bottom.shape, 3), dtype=np.uint8)
    encoded[:, :, 0] = packed >> 8
    encoded[:, :, 1] = packed & 255
    save_png(atlas, png)
    preview = atlas.copy()
    preview.thumbnail((384, 384), Image.Resampling.LANCZOS)
    save_png(preview, png.with_name("surface_preview.png"))
    save_png(Image.fromarray(encoded), png.with_name("surface_bottom.png"))
    # HUD framing includes both northern lake groups, the western installation,
    # Odawara, the offshore base and the southern relief. The whole survey is
    # retained for world-map panning and trips beyond the authored area.
    layer = dict(id="surface", label="箱根 · 小田原", texture="projectseele:area_maps/surface.png",
                 minX=MIN_X, maxX=MAX_X, minZ=MIN_Z, maxZ=MAX_Z,
                 hudFrame=dict(minX=-3456, maxX=4736, minZ=-2496, maxZ=3904),
                 minY=-30000000, maxY=30000000, priority=0,
                 bottom="projectseele:area_maps/surface_bottom.png",
                 preview="projectseele:area_maps/surface_preview.png")
    (output / "surface.json").write_text(json.dumps(layer, ensure_ascii=False, indent=2), encoding="utf8")
    return dict(regions_drawn=len(wanted), bounds=bounds, size=size, blocks_per_pixel=BLOCKS_PER_PIXEL)


if __name__ == "__main__":
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--map-root", required=True, type=Path)
    args.add_argument("--out", required=True, type=Path)
    args.add_argument("--regions", type=Path, help="Refresh only these region pairs on an existing atlas")
    options = args.parse_args()
    updates = None if options.regions is None else {tuple(p) for p in json.loads(options.regions.read_bytes())}
    print(json.dumps(bake(options.map_root, options.out, updates)))
