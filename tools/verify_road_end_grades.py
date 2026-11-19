"""Read built TrafficCraft centre lines from a cold GeoFront copy and verify short grades."""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from query_blocks import AIR, iter_selected_sections


def rasterize(points):
    points = np.asarray(points, dtype=float)
    stations = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    samples = np.linspace(0, stations[-1], max(2, math.ceil(stations[-1]) * 4 + 1))
    cells = np.rint(np.column_stack([
        np.interp(samples, stations, points[:, axis]) for axis in range(2)
    ])).astype(int)
    take = np.r_[True, np.any(cells[1:] != cells[:-1], axis=1)]
    return cells[take], samples[take], stations[-1]


def steepest(stations, heights):
    worst = 0.0
    for i, start in enumerate(stations):
        for j in range(i + 1, len(stations)):
            distance = stations[j] - start
            if distance > 17 + 1e-8:
                break
            if distance >= 8 - 1e-8:
                worst = max(worst, abs(heights[j] - heights[i]) / distance)
    return float(worst)


def verify(world, route):
    cells, stations, length = rasterize(route["points"])
    start, end = route["feet"]
    projected = start + (end - start) * stations / length
    required = defaultdict(set)
    for (x, z), h in zip(cells, projected):
        for y in range(math.floor(h) - 5, math.ceil(h) + 7):
            required[int(x) // 16, int(z) // 16].add(y // 16)
    sections = {(cx, sy, cz): (palette, indices)
                for cx, cz, sy, palette, indices in iter_selected_sections(
                    world, "projectseele:geofront", required)}

    def block(x, y, z):
        section = sections.get((x // 16, y // 16, z // 16))
        if section is None:
            return "minecraft:air"
        palette, indices = section
        return palette[indices[(y % 16) * 256 + (z % 16) * 16 + x % 16]]

    heights = []
    for (x, z), expected in zip(cells, projected):
        options = []
        for y in range(math.floor(expected) - 4, math.ceil(expected) + 5):
            material = block(x, y, z)
            if not material.startswith("trafficcraft:asphalt"):
                continue
            if block(x, y + 1, z) not in AIR or block(x, y + 2, z) not in AIR:
                continue
            layers = int(material.split("layers=")[1].split(",")[0].split("]")[0]) if "layers=" in material else 8
            h = y + layers / 8
            options.append((abs(h - expected), h))
        if not options:
            raise ValueError(f"{route['id']} missing carriageway at {(int(x), int(z))}")
        heights.append(min(options)[1])
    grid_distance = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(cells, axis=0), axis=1))]
    return dict(id=route["id"], samples=len(cells), alignment=steepest(stations, heights),
                grid=steepest(grid_distance, heights), adjacent=max(abs(a - b) for a, b in zip(heights, heights[1:])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--centres", type=Path, required=True)
    parser.add_argument("--id", action="append", required=True, dest="ids")
    args = parser.parse_args()
    records = {r["id"]: r for r in json.loads(args.centres.read_text(encoding="utf8"))}
    result = [verify(args.world, records[i]) for i in args.ids]
    print(json.dumps(result))
    return int(any(max(r["alignment"], r["grid"]) > .070001 or r["adjacent"] > .500001 for r in result))


if __name__ == "__main__":
    raise SystemExit(main())
