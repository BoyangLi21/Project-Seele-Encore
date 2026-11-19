"""Export conservative eight-block surface heights between the installed city and Yashima lookout."""

import argparse
import gzip
from pathlib import Path
import struct
import zlib

import numpy as np

from write_deep_cells import REGION, read_chunk, decode


def calculate_tiles(chunk):
    tiles = np.full((2, 2), -1344, dtype=int)
    for section in reversed(sorted(chunk.get("sections", []), key=lambda s: int(s["Y"]))):
        if (tiles > -1344).all():
            break
        states = section.get("block_states")
        if states is None:
            continue
        ids, palette = decode(states)
        solid = np.array(
            [
                name.split("[")[0]
                not in {
                    "minecraft:air",
                    "minecraft:void_air",
                    "minecraft:cave_air",
                    "minecraft:light",
                    "minecraft:structure_void",
                }
                and "_leaves" not in name
                for name in palette
            ]
        )
        if not solid.any():
            continue
        found = solid[ids].reshape(16, 2, 8, 2, 8).any(axis=(2, 4))
        for z, x in np.argwhere((tiles == -1344) & found.any(axis=0)):
            tiles[z, x] = 16 * int(section["Y"]) + 16 - np.argmax(found[::-1, z, x])
    return tiles


def survey(world, output):
    # Aligned sixteen-block bounds cover the approach from the gun through the full city.
    x0, z0, x1, z1 = -1440, -1584, 384, 656
    step = 8
    heights = np.full(((z1 - z0) // step, (x1 - x0) // step), 32767, dtype=">i2")
    indices = np.arange(256)
    key = b"\x0c\x00\x19MOTION_BLOCKING_NO_LEAVES"
    for rz in range(z0 // 512, (z1 - 1) // 512 + 1):
        for rx in range(x0 // 512, (x1 - 1) // 512 + 1):
            region = world / REGION / f"r.{rx}.{rz}.mca"
            if not region.exists():
                continue
            raw = region.read_bytes()
            for cz in range(max(z0 // 16, rz * 32), min(z1 // 16, (rz + 1) * 32)):
                for cx in range(max(x0 // 16, rx * 32), min(x1 // 16, (rx + 1) * 32)):
                    i = 4 * ((cx & 31) + (cz & 31) * 32)
                    offset = 4096 * int.from_bytes(raw[i : i + 3], "big")
                    if offset == 0 or raw[offset + 4] != 2:
                        continue
                    size = int.from_bytes(raw[offset : offset + 4], "big")
                    data = zlib.decompress(raw[offset + 5 : offset + 4 + size])
                    tag = data.find(key)
                    z = (16 * cz - z0) // step
                    x = (16 * cx - x0) // step
                    if tag < 0:
                        chunk = read_chunk(raw, cx, cz)[3]
                        if str(chunk.get("Status", "")) == "minecraft:full":
                            heights[z : z + 2, x : x + 2] = calculate_tiles(chunk)
                        continue
                    start = tag + len(key)
                    if struct.unpack_from(">I", data, start)[0] != 52:
                        continue
                    # The installed dimension has min_y=-1344, height=1664, five 11-bit entries per long.
                    words = np.frombuffer(data, dtype=">u8", count=52, offset=start + 4).astype("uint64")
                    cols = (
                        ((words[indices // 5] >> ((indices % 5) * 11).astype("uint64")) & 2047).astype(
                            "int32"
                        )
                        - 1344
                    ).reshape(2, 8, 2, 8)
                    heights[z : z + 2, x : x + 2] = cols.max(axis=(1, 3))
    output.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack(">IhhHHH", 0x48523635, x0, z0, heights.shape[1], heights.shape[0], step)
    output.write_bytes(gzip.compress(header + heights.tobytes(), mtime=0))
    print(
        f"{heights.size} terrain tiles, {(heights==32767).sum()} unknown, {output.stat().st_size} compressed bytes"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("world", type=Path)
    p.add_argument("resource", type=Path)
    args = p.parse_args()
    survey(args.world, args.resource)
