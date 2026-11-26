"""Read the original bridge and plan the additional slab edges and relocated hangers of the GS passing tracks.

Inputs: a stopped-world snapshot, the transit package, native samples from SpiralServiceCheck, and the
existing bridge supports catalogued beside this tool. Writes reversible [x, y, z, before, after] rows into the package.
"""

import argparse
import collections
import json
from pathlib import Path

import numpy as np

from query_blocks import AIR, iter_selected_sections


def envelope(rails, width, height):
    """Rasterize each pair of native cross sections as a trapezoid against whole voxel columns."""
    columns = {}
    for rail in rails:
        points = np.asarray(rail["points"])
        points = points[np.r_[True, np.linalg.norm(np.diff(points, axis=0), axis=1) > 1e-6]]
        horizontal = points[:, [0, 2]]
        tangent = np.gradient(horizontal, axis=0)
        tangent /= np.linalg.norm(tangent, axis=1)[:, None]
        left = horizontal + np.column_stack((-tangent[:, 1], tangent[:, 0])) * width
        right = 2 * horizontal - left
        polygons = np.stack((right[:-1], right[1:], left[1:], left[:-1]), axis=1)
        edges = np.roll(polygons, -1, axis=1) - polygons
        first = np.floor(polygons.min(axis=1) + 1e-8).astype(int)
        last = np.ceil(polygons.max(axis=1) - 1e-8).astype(int) - 1
        lower = np.floor(np.minimum(points[1:, 1], points[:-1, 1]) + 1e-8).astype(int)
        upper = np.ceil(np.maximum(points[1:, 1], points[:-1, 1]) + height - 1e-8).astype(int)
        for dx in range((last - first)[:, 0].max() + 1):
            for dz in range((last - first)[:, 1].max() + 1):
                cell = first + [dx, dz]
                delta = cell[:, None, :] + 0.5 - polygons
                # The square misses a convex trapezoid if all four corners fall outside any edge.
                furthest = (
                    edges[:, :, 0] * delta[:, :, 1]
                    - edges[:, :, 1] * delta[:, :, 0]
                    + np.abs(edges).sum(axis=2) * 0.5
                )
                inside = (cell <= last).all(axis=1) & (furthest.min(axis=1) > 1e-9)
                for (x, z), low, high in zip(cell[inside], lower[inside], upper[inside]):
                    key = int(x), int(z)
                    previous = columns.get(key, (int(low), int(high)))
                    columns[key] = min(previous[0], int(low)), max(previous[1], int(high))
    return columns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("world", "package", "samples"):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()

    def read(path):
        return json.loads(path.read_text(encoding="utf8"))

    def key(pair):
        return frozenset(tuple(p) for p in pair)

    changed = {key(endpoints) for endpoints in read(args.package / "passing-rails.json")}
    rails = [
        r
        for r in read(args.samples)
        if key([list(map(int, p.split(","))) for p in r["id"].split("/")]) in changed
    ]
    if len(rails) != 12 or len(changed) != 12:
        raise ValueError("Incomplete samples of the twelve new native rails")
    # Surveyed car width 2.98, height 3.9; the 0.16 lateral margin accommodates the rigid bogie chord.
    body = envelope(rails, 1.65, 3.9)
    deck = envelope(rails, 2.02, 3.9)
    selected = collections.defaultdict(set)
    for (x, z), (lo, hi) in deck.items():
        for cx in range((x - 8) >> 4, ((x + 8) >> 4) + 1):
            for cz in range((z - 8) >> 4, ((z + 8) >> 4) + 1):
                selected[cx, cz].update(range((lo - 7) >> 4, ((hi + 8) >> 4) + 1))
    sections = {
        (cx, sy, cz): (palette, values)
        for cx, cz, sy, palette, values in iter_selected_sections(
            args.world, "projectseele:geofront", selected
        )
    }
    if set(selected) - {(cx, cz) for cx, sy, cz in sections}:
        raise ValueError("Missing passing-loop chunks")

    def old(k):
        x, y, z = k
        data = sections.get((x >> 4, y >> 4, z >> 4))
        return (
            "minecraft:air" if data is None else data[0][data[1][(y % 16) * 256 + (z % 16) * 16 + (x % 16)]]
        )

    def in_body(k):
        x, y, z = k
        return (x, z) in body and body[x, z][0] <= y < body[x, z][1]

    air, beam, chain = (
        "minecraft:air",
        "minecraft:polished_deepslate",
        "minecraft:chain[axis=y,waterlogged=false]",
    )
    updates, reasons = {}, collections.Counter()

    def setcell(k, value, reason):
        if updates.get(k, old(k)) == value:
            return
        updates[k] = value
        reasons[reason] += 1

    obstructions = {
        (x, y, z): old((x, y, z))
        for (x, z), (lo, hi) in body.items()
        for y in range(lo, hi)
        if old((x, y, z)) not in AIR
    }
    # Surveyed subset of the original fit08 bridge construction rows. Extra obstructions could be player edits.
    supports = read(Path(__file__).parent / "plans/geofront_spiral_passing_supports.json")
    owned = {
        (x, y, z): state
        for state, spans in supports.items()
        for x, z, bottom, top in spans
        for y in range(bottom, top + 1)
    }
    if obstructions != owned or set(owned.values()) - {beam, chain, "minecraft:gray_concrete"}:
        raise ValueError("The measured clearances include a block outside the previous viaduct")
    for k in obstructions:
        setcell(k, air, "clear_previous_bridge")
    for (x, z), (lo, hi) in deck.items():
        at = x, lo - 1, z
        if old(at) in AIR:
            setcell(at, beam, "deck_edge")
    # The original suspension stays connected to its roof anchor. Move the obstructed lower length outward
    # and connect it back above the car body and beneath the bearing slab.
    hangers = sorted({(x, z) for (x, y, z), s in obstructions.items() if s == chain})
    for x, z in hangers:
        lo, hi = body[x, z]
        bottom = lo - 2
        # The upper beam joins the retained chain before it reaches the ceiling.
        cap = hi
        while old((x, cap, z)) == air and cap < hi + 5:
            cap += 1
        if old((x, cap, z)) not in (chain, beam):
            raise ValueError(f"Missing upper hanger at {(x,cap,z)}")
        options = []
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dist in range(1, 8):
                tx, tz = x + dx * dist, z + dz * dist
                upright = {(tx, y, tz) for y in range(bottom + 1, cap)}
                caps = {(x + dx * j, y, z + dz * j) for j in range(dist + 1) for y in (bottom, cap)}
                members = upright | caps
                if any(in_body(k) for k in members):
                    continue
                if any(
                    updates.get(k, old(k))
                    not in AIR | {beam, chain, "minecraft:gray_concrete", "minecraft:light_gray_concrete"}
                    for k in members
                ):
                    continue
                if any(updates.get(k, old(k)) == chain for k in upright):
                    continue
                options.append((dist, dx, dz, upright, caps))
                break
        if not options:
            raise ValueError(f"No clear hanger position at {(x,z)}")
        _, dx, dz, upright, caps = min(options, key=lambda r: r[:3])
        for k in upright:
            if updates.get(k, old(k)) in AIR:
                setcell(k, chain, "relocated_lower_hanger")
        for k in caps:
            if updates.get(k, old(k)) in AIR | {chain}:
                setcell(k, beam, "hanger_connection")
    if any(updates.get(k, old(k)) not in AIR for k in obstructions):
        raise ValueError("Remaining clearance obstruction")
    for (x, z), (lo, hi) in deck.items():
        if updates.get((x, lo - 1, z), old((x, lo - 1, z))) in AIR:
            raise ValueError("Gap below track")
    rows = [[*k, old(k), new] for k, new in sorted(updates.items()) if old(k) != new]
    (args.package / "rows.json").write_text(json.dumps(rows, separators=(",", ":")), encoding="utf8")
    summary = dict(
        rails=len(rails),
        columns=len(body),
        hangers=len(hangers),
        edits=len(rows),
        regions=sorted({(r[0] >> 9, r[2] >> 9) for r in rows}),
        reasons=reasons,
    )
    (args.package / "civil-proof.json").write_text(json.dumps(summary, indent=2), encoding="utf8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
