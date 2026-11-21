"""Sample the locally archived GSI elevation tiles in the existing Hakone map projection."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates

from plan_outer_boundary import lonlat_of


def sample(tile_dir, out):
    step, xmin, zmin = 8, -4608, -4096
    x = np.arange(xmin, 7168 + 1, step)
    z = np.arange(zmin, 6144 + 1, step)
    lon, lat = lonlat_of(x, z)
    n = 256 * (1 << 12)
    px = (lon + 180) / 360 * n - 0.5
    py = (1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) * n / 2 - 0.5
    x0, x1 = int(px.min()) // 256, (int(px.max()) + 1) // 256
    z0, z1 = int(py.min()) // 256, (int(py.max()) + 1) // 256
    source = np.full(((z1 - z0 + 1) * 256, (x1 - x0 + 1) * 256), np.nan, np.float32)
    tiles = json.loads((tile_dir / "manifest.json").read_bytes())["tiles"]
    for tx in range(x0, x1 + 1):
        for tz in range(z0, z1 + 1):
            if tiles.get(f"{tx}/{tz}") != "png":
                continue
            with Image.open(tile_dir / str(tx) / f"{tz}.png") as image:
                rgb = np.asarray(image.convert("RGB"), np.int32)
            values = (rgb[:, :, 0] << 16) | (rgb[:, :, 1] << 8) | rgb[:, :, 2]
            # GSI encodes signed centimetres; 0x800000 means no elevation (including open sea).
            metres = np.where(values >= 0x800000, values - 0x1000000, values) * 0.01
            metres[values == 0x800000] = np.nan
            i, j = (tx - x0) * 256, (tz - z0) * 256
            source[j:j + 256, i:i + 256] = metres
    coordinates = np.meshgrid(py - 256 * z0, px - 256 * x0, indexing="ij")
    # Do not project water or missing measurements onto dry ground near the shoreline.
    height = map_coordinates(source, coordinates, order=1, prefilter=False)
    world_y = (80 + (height - 647.1) / 4).astype(np.float32)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, h=world_y, x0=xmin, z0=zmin, step=step)
    print(json.dumps(dict(points=world_y.size, measured_land=int(np.isfinite(world_y).sum()),
                          world_bounds=[int(x[0]), int(x[-1]), int(z[0]), int(z[-1])])))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tile-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    sample(args.tile_dir, args.out)
