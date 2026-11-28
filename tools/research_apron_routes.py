"""Extend the existing GeoFront guidance graph out of the research gallery onto the new apron walk."""

import gzip
import json
import math
from pathlib import Path
from research_apron_access import ramp_eighths

DIRECTORY = "r53_personnel_walking_graph.json.gz"
GUIDE = "nerv_routes_r24.json.gz"
LIFTS = "nearest_lift_paths_r44.json.gz"


def approaches():
    north = [(275, math.floor(ramp_eighths(z) / 8), z) for z in range(550, 531, -1)]
    rear = [(x, -460, 532) for x in range(274, 199, -1)]
    lobby = [(x, -466, 593) for x in range(275, 260, -1)]
    return [
        north + rear + [(200, -460, 531)],
        [(232, -460, 532), (232, -460, 531)],
        lobby + [(261, -466, z) for z in range(594, 598)],
    ]


def append_routes(source, out):
    if source.resolve() == out.resolve() or source.resolve() in out.resolve().parents:
        raise ValueError("Choose an offline output directory")
    guide, walk, lifts = [
        json.loads(gzip.decompress((source / p).read_bytes()))
        for p in (GUIDE, DIRECTORY, LIFTS)
    ]
    if (
        not len(guide["nodes"])
        == len(guide["node_active"])
        == len(walk["nodes"])
        == len(lifts["nodes"])
        == len(lifts["node_floor_keys"])
    ):
        raise ValueError("Mismatched source route tables")
    n = len(guide["nodes"])
    index = {
        tuple(v[:3]): i for i, v in enumerate(guide["nodes"]) if guide["node_active"][i]
    }
    all_positions = {tuple(v[:3]) for v in guide["nodes"]}
    existing = {tuple(v[:2]) for v in walk["walking_edges"]}
    for route in approaches():
        parent = index[route[0]]
        for pos in route[1:]:
            if pos in index:
                child = index[pos]
            else:
                if pos in all_positions:
                    raise ValueError(("Inactive geometry at new public route", pos))
                child = len(guide["nodes"])
                index[pos] = child
                all_positions.add(pos)
                guide["nodes"].append([*pos, *([parent] * len(guide["goals"]))])
                guide["node_active"].append(True)
                walk["nodes"].append(list(pos))
                parent_floor = lifts["node_floor_keys"][parent]
                lifts["node_floor_keys"].append(parent_floor)
                nearest = lifts["nodes"][parent]
                if nearest is None:
                    lifts["nodes"].append(None)
                    lifts["unresolved_coordinates"].append(list(pos))
                else:
                    previous = guide["nodes"][parent][:3]
                    lifts["nodes"].append(
                        dict(
                            nearest,
                            next=previous,
                            walking_metres=nearest["walking_metres"]
                            + math.dist(previous, pos),
                        )
                    )
            distance = math.dist(guide["nodes"][parent][:3], pos)
            if not 0 < distance <= math.sqrt(2):
                raise ValueError(("Nonwalking step", parent, child))
            for edge in ((parent, child), (child, parent)):
                if edge not in existing:
                    walk["walking_edges"].append([*edge, round(distance, 3)])
                    existing.add(edge)
            parent = child
    out.mkdir(parents=True, exist_ok=True)
    # This descriptive legacy field is not part of the game's nearest-lift loader.
    lifts.pop("graph_sha256", None)
    for filename, table in ((GUIDE, guide), (DIRECTORY, walk), (LIFTS, lifts)):
        with gzip.open(out / filename, "wt", encoding="utf8", compresslevel=4) as f:
            json.dump(table, f, separators=(",", ":"), ensure_ascii=False)
    return len(guide["nodes"]) - n


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    print(append_routes(args.source, args.out), "new guidance nodes")
