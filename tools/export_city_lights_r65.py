"""Build sparse exterior night-light points from a cold GeoFront world and its rigid cargo."""

import argparse
from collections import Counter
import gzip
import io
from pathlib import Path
import struct

import nbtlib
import numpy as np

from write_deep_cells import REGION, decode, read_chunk, state_name

DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
LAMP = {
    "minecraft:sea_lantern",
    "minecraft:lantern",
    "minecraft:ochre_froglight",
    "minecraft:pearlescent_froglight",
    "minecraft:verdant_froglight",
    "minecraft:end_rod",
    "minecraft:shroomlight",
    "minecraft:glowstone",
}
AIR = {"minecraft:air", "minecraft:void_air", "minecraft:cave_air"}


def position(n):
    n = int(n)
    return n >> 38, ((n & 4095) ^ 2048) - 2048, (((n >> 12) & 67108863) ^ 33554432) - 33554432


def light_type(state):
    name = state.partition("[")[0]
    if name in AIR:
        return 0
    if "glass" in name and "tinted" not in name:
        return 1
    if (
        name in LAMP
        or ("street" in name and ("light" in name or "lamp" in name))
        or (name == "minecraft:redstone_lamp" and "lit=true" in state)
    ):
        return 2
    if (
        name in {"minecraft:redstone_torch", "minecraft:redstone_wall_torch"}
        and "lit=false" not in state
    ):
        return 3
    return 4


def noise(x, y, z):
    h = (x * 73856093 ^ y * 19349663 ^ z * 83492791) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) * 0x45D9F3B) & 0xFFFFFFFF


def cargo_sources(data_dir, towers):
    rows = []
    for i, tower in enumerate(towers):
        cx, base, cz = position(tower["Centre"])
        buildings = nbtlib.load(data_dir / "city_rigid_generation_r45" / "cargo" / f"{i}.dat")["data"][
            "Buildings"
        ]
        building = next(b for b in buildings if position(b["Centre"]) == (cx, base, cz))
        cells = {position(c["Pos"]): light_type(state_name(c["State"])) for c in building["Cargo"]}
        top = {}
        for (x, y, z), kind in cells.items():
            if kind:
                top[x, z] = max(y, top.get((x, z), -999))
        buckets = {}
        for (x, y, z), kind in cells.items():
            if kind == 3 and y >= int(tower["Height"]) - 4 and y == top[x, z]:
                rows.append((cx + x, base + y, cz + z, 3, 4, i))
            if kind != 1 or y < 3:
                continue
            for face, (dx, dz) in enumerate(DIRECTIONS):
                if top.get((x + dx, z + dz), -999) >= y:
                    continue
                key = (face, (z if dx else x) // 4, y // 6)
                rank = noise(cx + x, base + y, cz + z)
                if key not in buckets or rank < buckets[key][0]:
                    buckets[key] = (rank, (cx + x, base + y, cz + z, 1, face, i))
        rows.extend(point for rank, point in buckets.values() if rank % 5 < 3)
    return rows


def static_sources(region, towers):
    centres = [position(t["Centre"]) for t in towers]
    x0 = min(x for x, _, z in centres) - 48
    z0 = min(z for x, _, z in centres) - 48
    x1 = max(x for x, _, z in centres) + 49
    z1 = max(z for x, _, z in centres) + 49
    low, high = 58, 194
    cube = np.zeros((high - low, z1 - z0, x1 - x0), np.uint8)
    buffers = {}
    for cz in range(z0 >> 4, ((z1 - 1) >> 4) + 1):
        for cx in range(x0 >> 4, ((x1 - 1) >> 4) + 1):
            key = (cx >> 5, cz >> 5)
            if key not in buffers:
                buffers[key] = (region / f"r.{key[0]}.{key[1]}.mca").read_bytes()
            try:
                _, _, _, c = read_chunk(buffers[key], cx, cz)
            except ValueError as ex:
                if "not generated" in str(ex):
                    continue
                raise
            xx, zz = max(x0, cx * 16), max(z0, cz * 16)
            xe, ze = min(x1, cx * 16 + 16), min(z1, cz * 16 + 16)
            for sec in c["sections"]:
                sy = int(sec["Y"]) * 16
                if sy + 16 <= low or sy >= high or "block_states" not in sec:
                    continue
                ids, palette = decode(sec["block_states"])
                cat = np.array([light_type(s) for s in palette], np.uint8)
                y, e = max(low, sy), min(high, sy + 16)
                cube[y - low : e - low, zz - z0 : ze - z0, xx - x0 : xe - x0] = cat[ids].reshape(
                    16, 16, 16
                )[y - sy : e - sy, zz - cz * 16 : ze - cz * 16, xx - cx * 16 : xe - cx * 16]
    heights = np.where(cube.any(axis=0), high - 1 - np.argmax(cube[::-1] != 0, axis=0), low - 1)
    buckets = {}
    for dy, j, i in zip(*np.where((cube > 0) & (cube < 4))):
        y, x, z = int(dy) + low, int(i) + x0, int(j) + z0
        if min(i, j, z1 - z0 - 1 - j, x1 - x0 - 1 - i) < 1:
            continue
        kind = int(cube[dy, j, i])
        if y < 70:
            continue
        faces = [f for f, (dx, dz) in enumerate(DIRECTIONS) if heights[j + dz, i + dx] < y]
        if kind == 1 and not faces:
            continue
        if kind >= 2 and heights[j, i] > y + 1 and not faces:
            continue
        for face in faces if kind == 1 else (4,):
            key = (kind, face, x // 5, y // 5, z // 5)
            rank = noise(x, y, z)
            if key not in buckets or rank < buckets[key][0]:
                buckets[key] = (rank, (x, y, z, kind, face, 255))
    return [row for rank, row in buckets.values() if row[3] != 1 or rank % 5 < 3]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("world", type=Path)
    p.add_argument("resource", type=Path)
    args = p.parse_args()
    reg = args.world / REGION
    dd = reg.parent / "data"
    topo = nbtlib.load(next(dd.glob("projectseele_city_rigid_topology_r45_*.dat")))["data"]
    towers = topo["Towers"]
    rows = sorted(set(cargo_sources(dd, towers) + static_sources(reg, towers)))
    buf = io.BytesIO()
    buf.write(struct.pack(">IHI", 0x4C523635, len(towers), len(rows)))
    for tower in towers:
        _, y, _ = position(tower["Centre"])
        buf.write(struct.pack(">hh", y, int(tower["RetractedBaseY"]) - y))
    for x, y, z, kind, face, owner in rows:
        buf.write(struct.pack(">hhhBBB", x, y, z, kind, face, owner))
    args.resource.parent.mkdir(parents=True, exist_ok=True)
    args.resource.write_bytes(gzip.compress(buf.getvalue(), mtime=0))
    print(
        "moving",
        Counter(r[3] for r in rows if r[5] != 255),
        "static",
        Counter(r[3] for r in rows if r[5] == 255),
        "total",
        len(rows),
    )


if __name__ == "__main__":
    main()
