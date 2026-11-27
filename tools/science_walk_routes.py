"""Retire the elevated science walkway and reconnect its lower landing in the personnel graph."""

import gzip
import hashlib
import json

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import breadth_first_order

from dogma_recommission import AIRS

ROUTES = "nerv_routes_r24.json.gz"
WALKS = "r53_personnel_walking_graph.json.gz"
LIFTS = "nearest_lift_paths_r44.json.gz"
LANDING = [(193, -466, 542), (199, -466, 542)]


def write_table(path, table):
    with gzip.GzipFile(filename=str(path), mode="wb", compresslevel=3, mtime=0) as file:
        file.write(
            json.dumps(table, separators=(",", ":"), ensure_ascii=False).encode()
        )


def lost_floor(point, before, after):
    x, y, z = point
    on_spur = 201 <= x <= 211 and 525 <= z <= 542 and -467 <= y <= -454
    on_bridge = 192 <= x <= 201 and 403 <= z <= 546 and -466 <= y <= -451
    if not on_spur and not on_bridge:
        return False
    if on_bridge and (z >= 541 or z < 409) and y <= -466:
        return False
    if before.get(x, y - 1, z) not in AIRS and after.get(x, y - 1, z) in AIRS:
        return True
    return (x == 201 and 538 <= z <= 542 and y == -460) or (
        192 <= x <= 200 and 409 <= z <= 541 and -460 <= y <= -454
    )


def landing_edges(table, after):
    local = {}
    for i, (row, active) in enumerate(zip(table["nodes"], table["node_active"])):
        x, y, z = row[:3]
        if active and 192 <= x <= 200 and y == -466 and 536 <= z <= 552:
            if (
                after.get(x, y, z) in AIRS
                and after.get(x, y + 1, z) in AIRS
                and after.get(x, y - 1, z) not in (*AIRS, None)
            ):
                local[x, y, z] = i
    return {
        (i, local[q])
        for (x, y, z), i in local.items()
        for q in ((x - 1, y, z), (x + 1, y, z), (x, y, z - 1), (x, y, z + 1))
        if q in local
    }


def reversed_graph(start, end, size):
    return csr_matrix((np.ones(len(start), np.int16), (end, start)), shape=(size, size))


def repair_goal(previous, goal, keep, added_ids, walk_from, walk_to):
    ids = np.arange(len(previous), dtype=np.int32)
    graph = reversed_graph(ids, previous, len(ids))
    reachable = breadth_first_order(graph, goal, return_predecessors=False)
    permitted = np.zeros(len(ids), bool)
    permitted[reachable] = True
    permitted[added_ids] = True
    permitted &= keep
    surviving = permitted & permitted[previous]
    intact = reversed_graph(ids[surviving], previous[surviving], len(ids))
    good = breadth_first_order(intact, goal, return_predecessors=False)
    broken = permitted.copy()
    broken[good] = False
    # A train or elevator edge is admissible only for the goal which used it.
    local = permitted[walk_from] & permitted[walk_to]
    options = reversed_graph(
        np.r_[ids[surviving], walk_from[local]],
        np.r_[previous[surviving], walk_to[local]],
        len(ids),
    )
    _, next_hop = breadth_first_order(options, goal)
    if np.any(next_hop[broken] < 0):
        raise ValueError("A previously reachable occupied floor would lose its route.")
    result = previous.copy()
    result[~keep | ~keep[previous]] = ids[~keep | ~keep[previous]]
    result[broken] = next_hop[broken]
    reached = breadth_first_order(
        reversed_graph(ids, result, len(ids)), goal, return_predecessors=False
    )
    verified = np.zeros(len(ids), bool)
    verified[reached] = True
    if not np.all(verified[permitted]):
        raise ValueError("Repaired routes contain a cycle or disconnected landing.")
    return result


def rewrite_routes(source, dest, before, after):
    packed = (source / ROUTES).read_bytes()
    raw = gzip.decompress(packed)
    original = [hashlib.sha256(buf).hexdigest() for buf in (packed, raw)]
    table = json.loads(raw)
    del raw, packed
    directory = json.loads(gzip.decompress((source / WALKS).read_bytes()))
    if any(tuple(p[:3]) in LANDING for p in table["nodes"]):
        raise ValueError(
            "Expected a route index from before the upper walkway was retired."
        )
    new_ids = np.arange(len(table["nodes"]), len(table["nodes"]) + len(LANDING))
    for i, point in zip(new_ids, LANDING):
        table["nodes"].append([*point, *([int(i)] * len(table["goals"]))])
        table["node_active"].append(True)
    gone = {
        i for i, row in enumerate(table["nodes"]) if lost_floor(row[:3], before, after)
    }
    keep = np.array(table["node_active"], bool)
    keep[list(gone)] = False
    table["node_active"] = keep.tolist()
    edges = landing_edges(table, after)
    coords = np.array(table["nodes"], np.int32)
    ids = np.arange(len(coords), dtype=np.int32)
    start = np.repeat(ids, len(table["goals"]))
    end = coords[:, 3:].ravel()
    nearby = (
        (np.max(abs(coords[start, :3] - coords[end, :3]), axis=1) <= 1)
        & (start != end)
        & keep[start]
        & keep[end]
    )
    directory["walking_edges"] = [
        edge
        for edge in directory["walking_edges"]
        if edge[0] not in gone and edge[1] not in gone
    ]
    existing = {(a, b) for a, b, *_ in directory["walking_edges"] if (a, b) in edges}
    directory["walking_edges"].extend([a, b, 1.0] for a, b in sorted(edges - existing))
    directory["nodes"].extend(LANDING)
    native = np.array(directory["walking_edges"])[:, :2].astype(np.int32)
    walk_from = np.r_[start[nearby], native[:, 0]]
    walk_to = np.r_[end[nearby], native[:, 1]]
    del native, start, end
    for column, goal in enumerate(table["goals"], 3):
        previous = coords[:, column]
        result = repair_goal(previous, goal["node"], keep, new_ids, walk_from, walk_to)
        for i in np.flatnonzero(result != previous):
            table["nodes"][i][column] = int(result[i])
    lifts = json.loads(gzip.decompress((source / LIFTS).read_bytes()))
    digest = lifts["graph_sha256"]
    if digest not in original or any(lifts["nodes"][i] is not None for i in gone):
        raise ValueError(
            "The lift companion does not match this science corridor survey."
        )
    write_table(dest / ROUTES, table)
    packed = (dest / ROUTES).read_bytes()
    lifts["graph_sha256"] = hashlib.sha256(
        packed if digest == original[0] else gzip.decompress(packed)
    ).hexdigest()
    lifts["nodes"].extend([None] * len(LANDING))
    neighbor = next(
        i for i, row in enumerate(table["nodes"]) if row[:3] == [193, -466, 541]
    )
    lifts["node_floor_keys"].extend([lifts["node_floor_keys"][neighbor]] * len(LANDING))
    write_table(dest / WALKS, directory)
    write_table(dest / LIFTS, lifts)
