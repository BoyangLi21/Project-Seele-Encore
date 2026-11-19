"""Prepare region-sized GeoFront edge patches from stopped world copies.

The R63 region headers define the saved footprint. The formal copy supplies all
old states. Completed reference terrain supplies surface samples where the formal copy
has no finished terrain. Carvers-stage edits require a matching fully generated reference.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import zlib

import nbtlib
import numpy as np
from scipy import ndimage

from write_deep_cells import REGION, decode

BAND, SIGMA, HALO = 64, 14, 80
EMPTY = -32768
AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
PLANT = {
    "minecraft:" + x
    for x in (
        "grass",
        "short_grass",
        "tall_grass",
        "fern",
        "large_fern",
        "dandelion",
        "poppy",
        "azure_bluet",
        "oxeye_daisy",
        "cornflower",
        "sweet_berry_bush",
        "dead_bush",
    )
}
SOIL = {
    "minecraft:" + x
    for x in (
        "grass_block",
        "dirt",
        "coarse_dirt",
        "podzol",
        "rooted_dirt",
        "stone",
        "andesite",
        "diorite",
        "granite",
        "tuff",
        "gravel",
        "moss_block",
    )
}
WATER = {"minecraft:" + x for x in ("water", "seagrass", "tall_seagrass", "kelp", "kelp_plant")}
GRASS = "minecraft:grass_block[snowy=false]"
SQUARE = np.ones((3, 3), bool)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), "utf8")


def coords(mask, x0, z0):
    zs, xs = np.nonzero(mask)
    return [(int(x + x0), int(z + z0)) for x, z in zip(xs, zs)]


def groups(cells):
    result = defaultdict(list)
    for x, z in cells:
        result[x >> 5, z >> 5].append((x, z))
    return result


def region_bytes(folder, rx, rz):
    path = folder / f"r.{rx}.{rz}.mca"
    return path.read_bytes() if path.is_file() else b""


def raw_chunk(buf, x, z):
    i = 4 * ((x & 31) + 32 * (z & 31))
    off = int.from_bytes(buf[i : i + 3], "big") * 4096
    if not off:
        return None
    n = int.from_bytes(buf[off : off + 4], "big")
    if buf[off + 4] != 2 or n < 2 or off + 4 + n > len(buf):
        raise ValueError(f"Invalid region payload at chunk {x} {z}")
    return zlib.decompress(buf[off + 5 : off + 4 + n])


def full(raw):
    # Fast path for indexing. Block data is parsed and status rechecked before use.
    return raw is not None and b"\x08\x00\x06Status\x00\x0eminecraft:full" in raw


def terrain_stage(raw):
    if not raw:
        return 0
    token = b"\x08\x00\x06Status"
    offset = raw.index(token) + len(token)
    size = int.from_bytes(raw[offset : offset + 2], "big")
    name = raw[offset + 2 : offset + 2 + size].decode().split(":")[-1]
    if name == "full":
        return 1
    if name in {"features", "initialize_light", "light", "spawn"}:
        return 3
    return 4 if name == "carvers" else 2


def writable(kinds):
    formal = kinds[:, :, 0]
    return (formal == 1) | (formal == 3) | ((formal == 4) & (kinds[:, :, 1] == 1))


def chunk(raw, x, z, allow_terrain=False):
    c = nbtlib.File.parse(io.BytesIO(raw))
    if (not allow_terrain and c["Status"] != "minecraft:full") or (c["xPos"], c["zPos"]) != (x, z):
        raise ValueError(f"Unexpected chunk at {x} {z}")
    return c


def build_geometry(args):
    saved = []
    for f in (args.r63 / REGION).glob("r.*.mca"):
        rx, rz = map(int, f.stem.split(".")[1:])
        with f.open("rb") as stream:
            header = stream.read(4096)
        for idx, (word,) in enumerate(struct.iter_unpack(">I", header)):
            if word:
                saved.append((32 * rx + idx % 32, 32 * rz + idx // 32))
    xx, zz = np.array(saved).T
    x0, z0 = int(xx.min()) - 12, int(zz.min()) - 12
    footprint = np.zeros((zz.max() - z0 + 13, xx.max() - x0 + 13), bool)
    footprint[zz - z0, xx - x0] = True
    outer = ndimage.binary_dilation(footprint, SQUARE, iterations=4) & ~footprint
    want = (footprint & ndimage.binary_dilation(~footprint, SQUARE, iterations=9)) | outer
    kinds = np.zeros((*footprint.shape, 3), np.uint8)
    for (rx, rz), cells in groups(coords(want, x0, z0)).items():
        for side, folder in enumerate((args.world / REGION, args.generated / REGION)):
            buf = region_bytes(folder, rx, rz)
            for x, z in cells:
                raw = raw_chunk(buf, x, z)
                kinds[z - z0, x - x0, side] = terrain_stage(raw)
        for source_id, alternate in enumerate(args.extra, 1):
            pending = [
                (x, z) for x, z in cells if kinds[z - z0, x - x0, 0] == 4 and kinds[z - z0, x - x0, 1] != 1
            ]
            if not pending:
                break
            buf = region_bytes(alternate / REGION, rx, rz)
            for x, z in pending:
                if full(raw_chunk(buf, x, z)):
                    kinds[z - z0, x - x0, 1:] = [1, source_id]
    np.savez_compressed(
        args.out / "geometry.npz",
        a=footprint,
        K=kinds,
        x0=x0,
        z0=z0,
        outer=outer,
        edgein=footprint & ndimage.binary_dilation(~footprint),
    )


def load_geometry(args):
    g = np.load(args.out / "geometry.npz")
    a, kinds = g["a"], g["K"]
    candidates = a & writable(kinds) & ndimage.binary_dilation(~a, SQUARE, iterations=4)
    return a, kinds, int(g["x0"]), int(g["z0"]), candidates


def category(state):
    name = state.partition("[")[0]
    if name in AIR or name in PLANT:
        return 0
    if name in SOIL:
        return 1
    return 2 if name in WATER else 3


def surface(c):
    h = np.full((16, 16), EMPTY, np.int16)
    k = np.zeros((16, 16), np.uint8)
    for sec in sorted(c["sections"], key=lambda s: int(s["Y"]), reverse=True):
        bs = sec.get("block_states")
        if bs is None:
            continue
        sy = int(sec["Y"]) * 16
        cat = np.array([category(str(p["Name"])) for p in bs["palette"]], np.uint8)
        if not cat.any():
            continue
        if len(cat) == 1:
            open_cells = k == 0
            h[open_cells] = sy + 15
            k[open_cells] = cat[0]
        else:
            ids, _ = decode(bs)
            cube = cat[ids].reshape(16, 16, 16)
            ly = 15 - (cube[::-1] != 0).argmax(axis=0)
            top = np.take_along_axis(cube, ly[None, :, :], axis=0)[0]
            use = (k == 0) & (top != 0)
            k[use] = top[use]
            h[use] = (sy + ly)[use]
        if k.all():
            break
    return h, k


def cache_surfaces(args):
    _, kinds, x0, z0, candidates = load_geometry(args)
    support = ndimage.binary_dilation(candidates, SQUARE, iterations=4)
    jobs = groups(coords(support & (writable(kinds) | (kinds[:, :, 1] == 1)), x0, z0))
    cache = args.out / "surfaces"
    cache.mkdir(exist_ok=True)
    for index, ((rx, rz), cells) in enumerate(sorted(jobs.items()), 1):
        outfile = cache / f"r.{rx}.{rz}.npz"
        if outfile.exists():
            continue
        h = np.full((512, 512), EMPTY, np.int16)
        k = np.zeros((512, 512), np.uint8)
        bufs = [region_bytes(s / REGION, rx, rz) for s in (args.world, args.generated, *args.extra)]
        for x, z in cells:
            stage, ref_stage, ref_id = kinds[z - z0, x - x0]
            current = stage in (1, 3, 4)
            side = 0 if current else 1 + int(ref_id)
            raw = raw_chunk(bufs[side], x, z)
            y, kind = surface(chunk(raw, x, z, allow_terrain=current))
            if stage == 4:
                # Features can still add trees and structures. Compare with
                # the fully generated copy, including its two-column keep-out.
                if ref_stage != 1:
                    kind.fill(0)
                else:
                    gy, gk = surface(chunk(raw_chunk(bufs[1 + int(ref_id)], x, z), x, z))
                    kind[(gy != y) | (gk != kind)] = 3
            j, i = (z & 31) * 16, (x & 31) * 16
            h[j : j + 16, i : i + 16], k[j : j + 16, i : i + 16] = y, kind
        np.savez_compressed(outfile, h=h, k=k)
        if index % 10 == 0:
            print(f"surface regions {index}/{len(jobs)}", flush=True)


def regional_window(folder, rx, rz):
    """The halo exceeds both the distance band and the finite Gaussian support."""
    size = 512 + 2 * HALO
    height = np.full((size, size), EMPTY, np.int16)
    kind = np.zeros((size, size), np.uint8)
    x0, z0 = rx * 512 - HALO, rz * 512 - HALO
    for i in range(rx - 1, rx + 2):
        for j in range(rz - 1, rz + 2):
            f = folder / f"r.{i}.{j}.npz"
            if not f.exists():
                continue
            xx, zz = max(x0, i * 512), max(z0, j * 512)
            xe, ze = min(x0 + size, i * 512 + 512), min(z0 + size, j * 512 + 512)
            dest = np.s_[zz - z0 : ze - z0, xx - x0 : xe - x0]
            src = np.s_[zz - j * 512 : ze - j * 512, xx - i * 512 : xe - i * 512]
            with np.load(f) as data:
                height[dest], kind[dest] = data["h"][src], data["k"][src]
    return height, kind, x0, z0


def smoothstep(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def desired_ground(args, shape, kinds, cx0, cz0, rx, rz):
    h, k, x0, z0 = regional_window(args.out / "surfaces", rx, rz)
    zz, xx = np.ogrid[z0 : z0 + h.shape[0], x0 : x0 + h.shape[1]]
    ci, cj = (xx >> 4) - cx0, (zz >> 4) - cz0
    within = (ci >= 0) & (ci < shape.shape[1]) & (cj >= 0) & (cj < shape.shape[0])
    ci = np.clip(ci, 0, shape.shape[1] - 1)
    cj = np.clip(cj, 0, shape.shape[0] - 1)
    survey = within & shape[cj, ci]
    formal = within & writable(kinds)[cj, ci]
    dist, nearest = ndimage.distance_transform_edt(survey, return_indices=True)
    j, i = nearest
    edge_out = ndimage.binary_dilation(survey) & ~survey
    # Retain batch 539 in full, including its originally unmodified taper.
    pilot = (xx >= -304) & (xx <= 559) & (zz >= -1552) & (zz < -1488)
    live_front = ndimage.binary_dilation(survey & formal & ~pilot) & edge_out & (k != 0) & (k != 2)
    dead_front = edge_out & ~live_front
    taper = smoothstep(ndimage.distance_transform_edt(~dead_front)[j, i] / 32) if dead_front.any() else 1
    # Hard roofs, canopy tops and water levels do not contribute ground heights.
    samples = k == 1
    weights = ndimage.gaussian_filter(samples.astype(np.float32), SIGMA)
    g = ndimage.gaussian_filter(np.where(samples, h, 0).astype(np.float32), SIGMA) / np.maximum(
        weights, 1e-6
    )
    protected = ndimage.binary_dilation(k != 1, SQUARE, iterations=2)
    factor = smoothstep(1 - dist / BAND) * taper
    target = h + factor * (g - h)
    # At a continuous land interface, a blend must not introduce a step. Keep
    # the normal component inside the measured interval to the exterior. Release
    # this constraint smoothly over the next sixteen map-side blocks.
    ref = h[j, i]
    bounded = np.clip(target, np.minimum(h, ref), np.maximum(h, ref))
    bounded = np.where(k[j, i] == 1, bounded, target)
    release = smoothstep((dist - 1) / 16)
    target = bounded + release * (target - bounded)
    # At a corner more than one face can touch exterior ground. Intersect all
    # face intervals; opposite constraints correctly leave its height intact.
    for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        axis = (0, 1)
        exterior = ~np.roll(survey, (-dz, -dx), axis)
        ground = np.roll(k, (-dz, -dx), axis) == 1
        other = np.roll(h, (-dz, -dx), axis)
        use = survey & exterior & ground
        target = np.where(use, np.clip(target, np.minimum(h, other), np.maximum(h, other)), target)
    goal = np.rint(target).astype(np.int16)
    eligible = survey & formal & ~pilot & ~protected & (dist <= BAND) & live_front[j, i] & (goal != h)
    cut = np.s_[HALO:-HALO, HALO:-HALO]
    return h[cut], goal[cut], eligible[cut], dist[cut], k[cut]


class ColumnBlocks:
    def __init__(self, c):
        self.states = {int(s["Y"]): s["block_states"] for s in c["sections"] if "block_states" in s}
        self.cache = {}

    def at(self, x, y, z):
        sy = y >> 4
        if sy not in self.states:
            return None
        if sy not in self.cache:
            self.cache[sy] = decode(self.states[sy])
        ids, palette = self.cache[sy]
        return palette[ids[((y & 15) * 16 + (z & 15)) * 16 + (x & 15)]]


def column_rows(blocks, x, z, h, goal):
    get = lambda y: blocks.at(x, y, z)
    plants = {}
    for y in (h + 1, h + 2):
        old = get(y)
        if old is None or old in AIR:
            break
        if old.partition("[")[0] not in PLANT:
            return [], h, "obstacle"
        plants[y] = "minecraft:air"
    step = 1 if goal > h else -1
    magnitude = min(8, abs(goal - h))
    while magnitude:
        nh = h + step * magnitude
        edits = dict(plants)
        if nh < h:
            edits.update((y, "minecraft:air") for y in range(nh + 1, h + 1))
        else:
            edits.update((y, "minecraft:dirt") for y in range(h, nh))
        edits[nh] = GRASS
        rows = []
        for y, new in sorted(edits.items()):
            old = get(y)
            if old is None:
                return [], h, "absent_section"
            if (y <= h and old.partition("[")[0] not in SOIL) or (
                y > h and old not in AIR and old.partition("[")[0] not in PLANT
            ):
                return [], h, "buried_or_overhead_obstacle"
            if old != new:
                rows.append([x, y, z, old, new])
        if len(rows) <= 8:
            return rows, nh, "changed"
        magnitude -= 1
    return [], h, "cell_limit"


def plan(args):
    a, kinds, cx0, cz0, candidates = load_geometry(args)
    # Outside the complete chunk footprint, every reference chunk within four
    # chunks of any writable column must have a FULL source.
    needed_out = ~a & ndimage.binary_dilation(candidates, SQUARE, iterations=4)
    absent = needed_out & (kinds[:, :, 0] != 1) & (kinds[:, :, 1] != 1)
    if absent.any():
        raise ValueError(f"Missing {absent.sum()} outside reference chunks")
    roads = set()
    for file in args.roads:
        for r in json.loads(file.read_text("utf8")):
            roads.add(tuple(r[:3]))
    out = args.out / "rows"
    grids = args.out / "grids"
    out.mkdir(exist_ok=True)
    grids.mkdir(exist_ok=True)
    batches = []
    for (rx, rz), cells in sorted(groups(coords(candidates, cx0, cz0)).items()):
        h, goal, eligible, distance, kind = desired_ground(args, a, kinds, cx0, cz0, rx, rz)
        after = h.copy()
        buf = region_bytes(args.world / REGION, rx, rz)
        rows = []
        reasons = Counter()
        for cx, cz in cells:
            sx, sz = (cx & 31) * 16, (cz & 31) * 16
            zlist, xlist = np.nonzero(eligible[sz : sz + 16, sx : sx + 16])
            if not len(zlist):
                continue
            blocks = ColumnBlocks(chunk(raw_chunk(buf, cx, cz), cx, cz, allow_terrain=True))
            final_blocks = None
            if kinds[cz - cz0, cx - cx0, 0] == 4:
                sid = int(kinds[cz - cz0, cx - cx0, 2])
                reference = (args.generated, *args.extra)[sid]
                future = raw_chunk(region_bytes(reference / REGION, rx, rz), cx, cz)
                final_blocks = ColumnBlocks(chunk(future, cx, cz))
            for dz, dx in zip(zlist.tolist(), xlist.tolist()):
                x, z = cx * 16 + dx, cz * 16 + dz
                j, i = sz + dz, sx + dx
                edits, nh, why = column_rows(blocks, x, z, int(h[j, i]), int(goal[j, i]))
                if final_blocks is not None and any(final_blocks.at(*r[:3]) != r[3] for r in edits):
                    reasons["pending_generation_changes"] += 1
                    continue
                if any(tuple(r[:3]) in roads for r in edits):
                    reasons["road_conflict"] += 1
                    continue
                reasons[why] += 1
                rows.extend(edits)
                after[j, i] = nh
        image = f"r.{rx}.{rz}"
        rec = dict(
            region=[rx, rz],
            candidate_chunks=len(cells),
            considered_columns=int(eligible.sum()),
            columns=int((after != h).sum()),
            max_height_delta=int(np.abs(after - h).max()),
            cells=len(rows),
            filter_counts=dict(reasons),
        )
        if rows:
            file = out / (image + ".json")
            write_json(file, rows)
            rec.update(file=str(file.name), md5=hashlib.md5(file.read_bytes()).hexdigest())
            np.savez_compressed(
                grids / (image + ".npz"),
                before=h,
                after=after,
                distance=distance.astype(np.float16),
                kind=kind,
            )
        batches.append(rec)
        print(image, rec["columns"], len(rows), flush=True)
    write_json(args.out / "batches.json", batches)
    print("planned", sum(r["cells"] for r in batches), "cells", flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("world", "r63", "generated", "out"):
        p.add_argument("--" + arg, required=True, type=Path)
    p.add_argument("--extra", nargs="*", type=Path, default=[])
    p.add_argument("--roads", nargs="*", type=Path, default=[])
    p.add_argument("--stage", choices=["all", "geometry", "surfaces", "rows"], default="all")
    args = p.parse_args()
    if args.out.exists() and args.stage == "all" and any(args.out.iterdir()):
        p.error("Use a fresh output directory for a new plan")
    args.out.mkdir(exist_ok=True, parents=True)
    if args.stage in ("all", "geometry"):
        build_geometry(args)
    if args.stage in ("all", "surfaces"):
        cache_surfaces(args)
    if args.stage in ("all", "rows"):
        plan(args)


if __name__ == "__main__":
    main()
