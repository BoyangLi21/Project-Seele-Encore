"""Bake the GeoFront cavity far-view silhouette from installed Anvil chunks.

python bake_geofront_dome.py <geofront region dir> <out.bin.gz> [--cell 8] [--workers 20] [--max-quads 250000]

Reads the GeoFront cavity of a cold copy of the world (never the live save), turns it into CELL-sized blocks, keeps
only the faces that look into the cavity's own air (the floor, the lake, the dome's inner surface and the hanging
city; not the inside of the rock or of closed rooms), merges neighbouring faces of the same block in each plane, and
writes a compressed mesh the client draws beyond the vanilla render distance (GeoFrontDomeFarViewR65).

The face budget is 250,000 quads (16 MB of vertices on the GPU; the client refuses more than 400,000). On the R65
world (batch 699) 8-block cells give 246,685 quads in 0.98 MB; 4-block cells give 748,892, over the budget.

Each face keeps the block that shows on that side: the top block of the cell for upward faces, the bottom block for
downward faces, the middle block for side faces. The client colours a face with that block's map colour, so the bake
needs no colour table of its own.

The output is a private build product (it is derived from the map): it is installed into the pack's jar at
assets/projectseele/geofront/dome_far_r65.bin.gz and never committed.

Format (little-endian, gzip): b"SGDM", u8 version (1), u8 cell, i32 x0, y0, z0, u16 palette count, palette
(u16 length + UTF-8 block id each), u32 quad count, quads of 13 bytes: i16 x, y, z (the solid cell, in cells from the
origin), u16 du, dv (extent in cells along the face's in-plane axes), u8 face (0 -X, 1 +X, 2 -Y, 3 +Y, 4 -Z, 5 +Z),
u16 palette index. In-plane axes: X faces (y, z), Y faces (x, z), Z faces (x, y).
"""
from __future__ import annotations

import argparse
import gzip
import struct
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inspect_map_assets import decode_modern_section, palette_name, region_chunks  # noqa: E402

# The cavity measured for the R64 area maps (half-open, with a margin past the grass rim), and the height band from
# below the deepest floor to above the flat ceiling (the canonical roof top is the surface datum 68 minus 16).
X0, X1, Z0, Z1 = -1888, 1952, -1600, 2240
Y0, Y1 = -528, 64

AIR_KEYS = {"air", "cave_air", "void_air", "light", "barrier", "structure_void"}
PLANT_WORDS = ("grass", "fern", "flower", "sapling", "tulip", "vine", "lily", "carpet", "dandelion", "poppy",
               "orchid", "allium", "cornflower", "mushroom", "torch", "button", "tripwire", "seagrass", "kelp",
               "bush", "sign", "banner", "rail", "lantern", "chain", "pressure_plate", "lever", "candle", "snow")
SOLID_FRACTION = 0.25


def see_through(name: str) -> bool:
    key = name.split(":", 1)[-1]
    if key in AIR_KEYS:
        return True
    if key in ("grass_block", "tall_seagrass"):
        return key != "grass_block"
    return any(word in key for word in PLANT_WORDS) and not key.endswith(("_block", "_leaves", "_log", "_planks"))


def bake_region(args):
    path, cell = args
    path = Path(path)
    rx, rz = (int(v) for v in path.stem.split(".")[1:3])
    bx0, bz0 = rx * 512, rz * 512
    ny = (Y1 - Y0) // cell
    n = 512 // cell
    solid = np.zeros((n, ny, n), dtype=bool)
    top = np.zeros((n, ny, n), dtype=np.int32)
    bottom = np.zeros((n, ny, n), dtype=np.int32)
    side = np.zeros((n, ny, n), dtype=np.int32)
    names: dict[str, int] = {}
    cx0, cx1 = X0 // 16, (X1 - 1) // 16
    cz0, cz1 = Z0 // 16, (Z1 - 1) // 16
    k = 16 // cell
    for chunk_x, chunk_z, nbt in region_chunks(path, (cx0, cx1, cz0, cz1)):
        root = nbt.get("Level", nbt)
        ox, oz = (chunk_x * 16 - bx0) // cell, (chunk_z * 16 - bz0) // cell
        for section in root.get("sections", root.get("Sections", [])):
            sy = int(section["Y"])
            if sy * 16 < Y0 or sy * 16 >= Y1:
                continue
            palette, indices = decode_modern_section(section)
            if not palette:
                continue
            ids = np.zeros(len(palette), dtype=np.int32)
            for i, entry in enumerate(palette):
                name = palette_name(entry)
                if see_through(name):
                    continue
                ids[i] = names.setdefault(name, len(names) + 1)
            if not ids.any():
                continue
            g = ids[indices].reshape(16, 16, 16)  # y, z, x
            # cells: (cy, vy, cz, vz, cx, vx)
            c = g.reshape(k, cell, k, cell, k, cell)
            s = c > 0
            frac = s.mean(axis=(1, 3, 5))  # cy, cz, cx
            oy = (sy * 16 - Y0) // cell
            ys = slice(oy, oy + k)
            # representative columns: the middle ones of the cell
            mid = cell // 2
            col = c[:, :, :, mid, :, mid]  # cy, vy, cz, cx
            colsolid = col > 0
            anyc = colsolid.any(axis=1)
            hi = cell - 1 - np.argmax(colsolid[:, ::-1], axis=1)
            lo = np.argmax(colsolid, axis=1)
            t = np.take_along_axis(col, hi[:, None], axis=1)[:, 0]
            b = np.take_along_axis(col, lo[:, None], axis=1)[:, 0]
            # cells whose middle column is empty fall back to any solid voxel of the cell
            fallback = c.reshape(k, cell, k, cell, k, cell).transpose(0, 2, 4, 1, 3, 5).reshape(k, k, k, -1).max(axis=3)
            t = np.where(anyc, t, fallback)
            b = np.where(anyc, b, fallback)
            m = c[:, mid, :, mid, :, mid]
            m = np.where(m > 0, m, fallback)
            # write in (x, y, z) order
            solid[ox:ox + k, ys, oz:oz + k] = (frac >= SOLID_FRACTION).transpose(2, 0, 1)
            top[ox:ox + k, ys, oz:oz + k] = t.transpose(2, 0, 1)
            bottom[ox:ox + k, ys, oz:oz + k] = b.transpose(2, 0, 1)
            side[ox:ox + k, ys, oz:oz + k] = m.transpose(2, 0, 1)
    return rx, rz, names, solid, top, bottom, side


def runs_2d(grid):
    """Greedy rectangles over a 2D label grid (0 = none): runs along axis 0, merged across axis 1."""
    out = []
    open_runs: dict[tuple[int, int, int], int] = {}
    nu, nv = grid.shape
    for v in range(nv):
        row = grid[:, v]
        if not row.any():
            for (u0, length, label), v0 in open_runs.items():
                out.append((u0, v0, length, v - v0, label))
            open_runs = {}
            continue
        change = np.flatnonzero(np.diff(row)) + 1
        starts = np.concatenate(([0], change))
        ends = np.concatenate((change, [nu]))
        current = {}
        for u0, u1 in zip(starts, ends):
            label = int(row[u0])
            if label:
                key = (int(u0), int(u1 - u0), label)
                current[key] = open_runs.pop(key, v)
        for (u0, length, label), v0 in open_runs.items():
            out.append((u0, v0, length, v - v0, label))
        open_runs = current
    for (u0, length, label), v0 in open_runs.items():
        out.append((u0, v0, length, nv - v0, label))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("region_dir")
    ap.add_argument("out")
    ap.add_argument("--cell", type=int, default=8, choices=(4, 8, 16))
    ap.add_argument("--max-quads", type=int, default=250_000)
    ap.add_argument("--workers", type=int, default=20)
    a = ap.parse_args()
    cell = a.cell
    began = time.time()
    regions = [p for p in sorted(Path(a.region_dir).glob("r.*.mca"))
               if int(p.stem.split(".")[1]) * 512 < X1 and int(p.stem.split(".")[1]) * 512 + 512 > X0
               and int(p.stem.split(".")[2]) * 512 < Z1 and int(p.stem.split(".")[2]) * 512 + 512 > Z0]
    rx0, rz0 = X0 // 512, Z0 // 512
    rx1, rz1 = (X1 - 1) // 512, (Z1 - 1) // 512
    n = 512 // cell
    nx, nz, ny = (rx1 - rx0 + 1) * n, (rz1 - rz0 + 1) * n, (Y1 - Y0) // cell
    solid = np.zeros((nx, ny, nz), dtype=bool)
    tops = np.zeros((nx, ny, nz), dtype=np.int16)
    bottoms = np.zeros_like(tops)
    sides = np.zeros_like(tops)
    palette: dict[str, int] = {}
    with Pool(a.workers) as pool:
        for rx, rz, names, s, t, b, m in pool.imap_unordered(bake_region, [(str(p), cell) for p in regions]):
            remap = np.zeros(len(names) + 1, dtype=np.int32)
            for name, i in names.items():
                remap[i] = palette.setdefault(name, len(palette) + 1)
            x, z = (rx - rx0) * n, (rz - rz0) * n
            solid[x:x + n, :, z:z + n] = s
            tops[x:x + n, :, z:z + n] = remap[t]
            bottoms[x:x + n, :, z:z + n] = remap[b]
            sides[x:x + n, :, z:z + n] = remap[m]
    print(f"read {len(regions)} regions in {time.time() - began:.0f} s; grid {nx}x{ny}x{nz}; {len(palette)} blocks",
          flush=True)
    # The cavity is the largest piece of connected air (by orders of magnitude); closed rooms, rock pockets and the
    # surface air above the roof are left out.
    origin = (rx0 * 512, Y0, rz0 * 512)
    labels, count = ndimage.label(~solid)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    cavity = labels == int(np.argmax(sizes))
    del labels, sizes
    print(f"cavity air: {int(cavity.sum())} of {cavity.size} cells ({count} air pieces)", flush=True)
    quads = []
    axes = {0: (1, 2), 1: (0, 2), 2: (0, 1)}  # normal axis -> (u, v) axes of the stored face extents
    for face in range(6):
        axis, positive = face // 2, face % 2 == 1
        shift = 1 if positive else -1
        neighbour = np.zeros_like(cavity)
        src = [slice(None)] * 3
        dst = [slice(None)] * 3
        if positive:
            src[axis], dst[axis] = slice(1, None), slice(0, -1)
        else:
            src[axis], dst[axis] = slice(0, -1), slice(1, None)
        neighbour[tuple(dst)] = cavity[tuple(src)]
        faces = solid & neighbour
        colour = tops if face == 3 else bottoms if face == 2 else sides
        labelled = np.where(faces, colour, 0)
        u_axis, v_axis = axes[axis]
        before = len(quads)
        for i in range(labelled.shape[axis]):
            plane = np.take(labelled, i, axis=axis)
            if not plane.any():
                continue
            # plane axes are the remaining two in order; arrange as (u, v)
            remaining = [d for d in range(3) if d != axis]
            if remaining != [u_axis, v_axis]:
                plane = plane.T
            for u0, v0, du, dv, label in runs_2d(plane):
                pos = [0, 0, 0]
                pos[axis], pos[u_axis], pos[v_axis] = i, u0, v0
                quads.append((pos[0], pos[1], pos[2], du, dv, face, label - 1))
        print(f"face {face}: {len(quads) - before} quads", flush=True)
    if len(quads) > a.max_quads:
        sys.exit(f"{len(quads)} quads is over the budget of {a.max_quads}; use a larger cell")
    names = [None] * len(palette)
    for name, i in palette.items():
        names[i - 1] = name
    body = bytearray(b"SGDM")
    body += struct.pack("<BBiii", 1, cell, *origin)
    body += struct.pack("<H", len(names))
    for name in names:
        raw = name.encode("utf8")
        body += struct.pack("<H", len(raw)) + raw
    body += struct.pack("<I", len(quads))
    packer = struct.Struct("<hhhHHBH")
    for q in quads:
        body += packer.pack(*q)
    with gzip.open(a.out, "wb", compresslevel=9) as f:
        f.write(body)
    print(f"{len(quads)} quads, {len(names)} blocks, {Path(a.out).stat().st_size} bytes in {time.time() - began:.0f} s")


if __name__ == "__main__":
    main()
