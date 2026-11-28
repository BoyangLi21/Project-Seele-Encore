"""Retire the science annex underpass and its two landings in an offline R754 GeoFront copy."""

import gzip
import hashlib
import json
import math

import numpy as np

from dogma_recommission import AIR
from science_walk_routes import LIFTS, ROUTES, WALKS, repair_goal, write_table

WEST, EAST = 192, 200
NORTH, SOUTH = 404, 546
EDGE_RAIL = "projectseele:nerv_edge_rail"


def remove_lower_gallery(builder):
    # Native soil on both flanks is three dirt blocks and a grass cap above stone.
    # The original stone remains underneath the later fill along the whole underpass.
    for z in range(NORTH, SOUTH + 1):
        for edge in (WEST - 1, EAST + 1):
            stone = _rock_surface(builder, edge, z)
            if not builder.get(edge, stone + 4, z).startswith("minecraft:grass_block"):
                raise ValueError(
                    ("Unexpected terrain at the gallery boundary", edge, z)
                )
        for x in range(WEST, EAST + 1):
            stone = _rock_surface(builder, x, z)
            for y in range(stone + 1, -455):
                existing = builder.get(x, y, z)
                if z in (NORTH, SOUTH) and y <= -466:
                    if y == -466:
                        east = str(x < EAST).lower()
                        west = str(x > WEST).lower()
                        target = f"{EDGE_RAIL}[east={east},north=false,south=false,west={west}]"
                    elif y == -467:
                        target = "minecraft:smooth_stone"
                    elif y > stone + 4:
                        target = "minecraft:deepslate_bricks"
                    else:
                        target = "minecraft:dirt"
                elif y <= stone + 3:
                    target = "minecraft:dirt"
                elif y == stone + 4:
                    target = "minecraft:grass_block[snowy=false]"
                elif "_leaves[" in existing or "_log[" in existing:
                    continue
                else:
                    target = AIR
                if existing != target:
                    builder.put(x, y, z, target)


def _rock_surface(builder, x, z):
    for y in range(-459, -490, -1):
        if builder.get(x, y, z) == "minecraft:stone":
            return y
    raise ValueError(("No original stone below the underpass", x, z))


def retired(point):
    x, y, z = map(math.floor, point)
    return WEST <= x <= EAST and NORTH <= z <= SOUTH and -475 <= y <= -455


def _read(world, filename):
    return json.loads(gzip.decompress((world / filename).read_bytes()))


def update_lower_routes(source, destination):
    """Use existing legal floor and transport connections. Keep the persistent node IDs."""
    table = _read(source, ROUTES)
    directory = _read(source, WALKS)
    nodes = np.array(table["nodes"], dtype=np.int32)
    removed = np.array([retired(row[:3]) for row in nodes])
    keep = np.array(table["node_active"]) & ~removed
    newly_retired = int(np.count_nonzero(np.array(table["node_active"]) & removed))
    directory["walking_edges"] = [
        row
        for row in directory["walking_edges"]
        if not removed[row[0]] and not removed[row[1]]
    ]
    edges = np.array(directory["walking_edges"])[:, :2].astype(np.int32)
    ids = np.arange(len(nodes), dtype=np.int32)
    starts = np.repeat(ids, len(table["goals"]))
    ends = nodes[:, 3:].ravel()
    short = (
        (np.max(abs(nodes[starts, :3] - nodes[ends, :3]), axis=1) <= 1)
        & (starts != ends)
        & keep[starts]
        & keep[ends]
    )
    walk_from = np.r_[starts[short], edges[:, 0]]
    walk_to = np.r_[ends[short], edges[:, 1]]
    table["node_active"] = keep.tolist()
    for column, goal in enumerate(table["goals"], 3):
        previous = nodes[:, column]
        result = repair_goal(previous, goal["node"], keep, [], walk_from, walk_to)
        for node in np.flatnonzero(result != previous):
            table["nodes"][node][column] = int(result[node])
    lifts = _read(source, LIFTS)
    if any(lifts["nodes"][i] is not None for i in np.flatnonzero(removed)):
        raise ValueError("An active lift route uses the retired underpass")
    lifts["unresolved_coordinates"] = [
        p for p in lifts["unresolved_coordinates"] if not retired(p)
    ]
    old = (source / ROUTES).read_bytes()
    compressed = hashlib.sha256(old).hexdigest() == lifts["graph_sha256"]
    if (
        not compressed
        and hashlib.sha256(gzip.decompress(old)).hexdigest() != lifts["graph_sha256"]
    ):
        raise ValueError("Lift and route tables come from different surveys")
    write_table(destination / ROUTES, table)
    current = (destination / ROUTES).read_bytes()
    lifts["graph_sha256"] = hashlib.sha256(
        current if compressed else gzip.decompress(current)
    ).hexdigest()
    write_table(destination / LIFTS, lifts)
    write_table(destination / WALKS, directory)

    def retired_fixture(point):
        x, y, z = map(math.floor, point)
        return retired(point) or (
            165 <= x <= 200 and 395 <= z <= 403 and -480 <= y <= -455
        )

    for name in ("facility_lighting_r30.json", "quality_walk_cases.json"):
        data = json.loads((source / name).read_bytes())
        if isinstance(data, dict):
            data["constant_lamps"] = [
                p for p in data["constant_lamps"] if not retired_fixture(p)
            ]
        else:

            def touches_retired(row):
                points = row.get("path", []) + [
                    row[k] for k in ("start", "end") if k in row
                ]
                return any(retired_fixture(p) for p in points)

            data = [row for row in data if not touches_retired(row)]
        (destination / name).write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf8"
        )
    return newly_retired
