"""Actual public entrance thresholds and pinned MTR gates, exact candidates.

The seed stage uses named authored entrance/exit paths. Physical plans require
the actual32-state native export and exact collision geometry; no cube/model
fallback, fare/balance mutation, NERV reader reuse or world apply entry point.
"""
from pathlib import Path
from collections import Counter
import argparse, copy, hashlib, json, math

import regional_voxels as v
from measure_world_r40 import MeasuredWorld, properties
from query_blocks import AIR, iter_block_entities
from audit_facility_transit_r44 import Geometry

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"
ART = ROOT / "artifacts/rebuild_r44/facility_transit_r44"
OUT = ART / "public_station_gates_v1"
WALKS = ART / "station_walk_cases_v2/station_walk_cases.json"
TRANSIT = ART / "native_transit_cases/cases.json"
CATALOGUE = ROOT / "artifacts/repair_r43/facility_catalogue/catalogue.json"
NORMAL = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def seeds(out=OUT):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    stations = read(CATALOGUE)["stations"]
    # The real arrival hall and old east link were commissioned as one
    # station approach by the R44 whole-component receipt. MTR's historic
    # metadata rectangle omits that existing public concourse; expand only
    # this manifest's finite ownership boundary, not the native station.
    arrival_contract = ART / "unified_arrival_hall/contract.json"
    if arrival_contract.is_file():
        arrival = read(arrival_contract)
        if not list((arrival_contract.parent / "complete_original_arrival_hall").glob("applied_*/receipt.json")):
            # The saved plan name is checked from its actually applied folder.
            if not list(arrival_contract.parent.glob("*/applied_*/receipt.json")):
                raise RuntimeError("Extended station ownership requires the actual applied whole arrival-hall receipt")
        station = next(s for s in stations if s["id"] == "8756332890045065166")
        for box in (arrival["source_original_hall"], arrival["declared_original_east_link"]):
            station["bounds"] = [[min(station["bounds"][0][i], box[i]) for i in range(3)], [max(station["bounds"][1][i], box[i + 3]) for i in range(3)]]
        station["bounds_authority"] = {"whole_arrival_component": str(arrival_contract), "sha256": hashlib.sha256(arrival_contract.read_bytes()).hexdigest()}
    by_platform = {p["id"]: station for station in stations for p in station["platforms"]}
    walks, transit = read(WALKS), read(TRANSIT)
    result, used = [], set()
    for case in walks:
        if "/ground_entrance_" not in case["id"] or "/return" in case["id"]:
            continue
        pid = case["id"].split("/")[2]
        station = by_platform[pid]
        a, b = case["path"][:2]
        if abs(a[1] - b[1]) > .01:
            raise RuntimeError(("Named public entrance segment is not a level threshold", case["id"]))
        travel = (int(math.copysign(1, b[0] - a[0])) if b[0] != a[0] else 0,
                  int(math.copysign(1, b[2] - a[2])) if b[2] != a[2] else 0)
        if sum(abs(t) for t in travel) != 1:
            raise RuntimeError(("Native gate needs one cardinal entry axis", case["id"]))
        point = [(a[i] + b[i]) / 2 for i in range(3)]
        key = tuple(map(math.floor, point))
        if key in used:
            continue
        used.add(key)
        result.append({"station_id": station["id"], "station_name": station["name"], "station_bounds": station["bounds"],
                       "platform": pid, "source_case": case["id"], "source_path": case["path"],
                       "threshold": key, "travel": travel, "authority": "Named original ground_entrance path; not a guessed empty room"})
    covered = {item["station_id"] for item in result}
    # Underground/terminal regions retain their actual concourse interface.
    # Each real platform exit is separate; shared coordinates are deduplicated.
    for case in transit["cases"]:
        source = case["source"]
        if source["station_id"] in covered:
            continue
        station = by_platform[case["source_platform"]]
        path = source["exit_path"]
        if not path:
            raise RuntimeError(("Native origin has no authored exit path", case["id"]))
        selected = None
        for a, b in zip(reversed(path[:-1]), reversed(path[1:])):
            delta = [b[i] - a[i] for i in range(3)]
            if abs(delta[1]) > .01 or math.hypot(delta[0], delta[2]) < .99:
                continue
            travel = (int(math.copysign(1, delta[0])) if abs(delta[0]) > .01 else 0,
                      int(math.copysign(1, delta[2])) if abs(delta[2]) > .01 else 0)
            if sum(abs(t) for t in travel) != 1:
                continue
            q = tuple(map(math.floor, a))
            lo, hi = station["bounds"]
            if all(lo[i] + (2 if i != 1 else 0) <= q[i] <= hi[i] - (2 if i != 1 else 0) for i in range(3)):
                selected = q, travel
                break
        if selected is None:
            continue
        q, travel = selected
        if q in used:
            continue
        used.add(q)
        result.append({"station_id": station["id"], "station_name": station["name"], "station_bounds": station["bounds"],
                       "platform": case["source_platform"], "source_case": case["id"] + "/whole_exit_path",
                       "source_path": path, "threshold": q, "travel": travel,
                       "authority": "Actual native platform-to-authored-concourse exit path, no rail or aircraft-floor teleport"})
    for site in result:
        candidates = []
        if "/whole_exit_path" in site["source_case"]:
            for a, b in zip(reversed(site["source_path"][:-1]), reversed(site["source_path"][1:])):
                delta = [b[i] - a[i] for i in range(3)]
                if abs(delta[1]) > .01 or math.hypot(delta[0], delta[2]) < .99:
                    continue
                travel = (int(math.copysign(1, delta[0])) if abs(delta[0]) > .01 else 0, int(math.copysign(1, delta[2])) if abs(delta[2]) > .01 else 0)
                q = tuple(map(math.floor, a)); lo, hi = site["station_bounds"]
                if sum(abs(t) for t in travel) == 1 and all(lo[i] <= q[i] <= hi[i] for i in range(3)):
                    candidates.append({"position": q, "travel": travel})
        site["actual_path_threshold_candidates"] = candidates or [{"position": site["threshold"], "travel": site["travel"]}]
    counts = Counter(item["station_id"] for item in result)
    document = {"sites": result, "station_areas": len(stations), "unresolved_station_regions": [
        {"station_id": station["id"], "name": station["name"], "bounds": station["bounds"], "platforms": station["platforms"],
         "reason": "No unambiguous named entrance/concourse threshold yet; investigate complete region, do not mark passed"}
        for station in stations if not counts[station["id"]]],
        "source_walks_sha256": hashlib.sha256(WALKS.read_bytes()).hexdigest(),
        "source_native_cases_sha256": hashlib.sha256(TRANSIT.read_bytes()).hexdigest(),
        "status": "Authored threshold seeds only. Actual floor, complete paired gate footprint, open/closed native geometry and all paths must still validate."}
    (out / "threshold_seeds.json").write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf8")
    print("Original public threshold seeds:", len(result), "in", len(counts), "station regions; unresolved", len(document["unresolved_station_regions"]), flush=True)
    return document


def plan(world=WORLD, out=OUT):
    world, out = Path(world), Path(out)
    if (world/'r44_public_station_gates.json').exists():
        raise RuntimeError("Installed finite public gates require an exact relocation/repair revision; do not regenerate a second set")
    sites = seeds(out)
    export_path = world / "r44_public_station_gate_shapes.json"
    if not export_path.is_file():
        raise RuntimeError("root must export actual pinned MTR32 collision/outline states natively before a physical gate candidate")
    exported = read(export_path)
    if len(exported["collision_shapes"]) != 32 or len(exported["outline_shapes"]) != 32:
        raise RuntimeError("Native gate export must contain all32 states of the two actual installed types")
    if list(out.glob("all_measured_public_gate_pairs/applied_*/receipt.json")):
        raise RuntimeError("Applied gate stage is immutable")
    w = MeasuredWorld(world)
    for site in sites["sites"]:
        for candidate in site["actual_path_threshold_candidates"]:
            w.around(candidate["position"], 8)
    w.load(); g = Geometry(w)
    g.shapes.update({v.canonical_state(key): value for key, value in exported["collision_shapes"].items()})
    original_shapes = read(world / "native_collision_shapes.json")
    merged_shapes = {**original_shapes, **exported["collision_shapes"]}
    tags = {}
    for site in sites["sites"]:
        qs = [item["position"] for item in site["actual_path_threshold_candidates"]]
        low = tuple(min(q[i] for q in qs) - 8 for i in range(3))
        high = tuple(max(q[i] for q in qs) + 8 for i in range(3))
        tags.update((p, copy.deepcopy(t)) for p, t in iter_block_entities(world, v.DIM, low, high))
    changes, gates, pairs, unresolved, cases = {}, [], [], [], []
    base_get = w.get
    station_walks = read(WALKS)

    def open_body_conflicts(rows):
        conflicts = set()
        for row in rows:
            pos = row["position"]
            for box in g.shapes[row["open_state"]]:
                low = [pos[i] + box[i] for i in range(3)]
                high = [pos[i] + box[i + 3] for i in range(3)]
                for case in station_walks:
                    for a, b in zip(case["path"], case["path"][1:]):
                        if any(max(a[i], b[i]) + (.3 if i != 1 else 1.8) <= low[i] or min(a[i], b[i]) - (.3 if i != 1 else 0) >= high[i] for i in range(3)):
                            continue
                        length2 = sum((b[i] - a[i]) ** 2 for i in range(3))
                        t = 0 if length2 == 0 else max(0, min(1, sum(((low[i] + high[i]) / 2 - a[i]) * (b[i] - a[i]) for i in range(3)) / length2))
                        step = min(1., .05 / max(.05, math.sqrt(length2)))
                        # Exact source paths keep their3D elevation. Sampling
                        # the actual capsule sweep avoids a rectangular
                        # diagonal bbox falsely classifying a corner as used.
                        for k in range(-24, 25):
                            sample = max(0, min(1, t + k * step))
                            point = [a[i] + (b[i] - a[i]) * sample for i in range(3)]
                            if all(point[i] + (.3 if i != 1 else 1.8) > low[i] + .001 and point[i] - (.3 if i != 1 else 0) < high[i] - .001 for i in range(3)):
                                conflicts.add(case["id"])
                                break
                        if case["id"] in conflicts:
                            break
        return sorted(conflicts)
    for site in sites["sites"]:
        pair = None
        for candidate in site["actual_path_threshold_candidates"]:
            q, travel = tuple(candidate["position"]), tuple(candidate["travel"])
            face = next(name for name, normal in NORMAL.items() if normal == travel)
            opposite = next(name for name, normal in NORMAL.items() if normal == tuple(-a for a in travel))
            for offset in (0, -1, 1, -2, 2):
                for side in (-1, 1):
                    across = (-travel[1], travel[0])
                    centre = (q[0] + offset * travel[0], q[1], q[2] + offset * travel[1])
                    second = (centre[0] + side * across[0], q[1], centre[2] + side * across[1])
                    positions = [centre, second]
                    rows = []
                    for pos, block, facing in zip(positions, ("mtr:ticket_barrier_entrance_1", "mtr:ticket_barrier_exit_1"), (face, opposite)):
                        closed = v.canonical_state(f"{block}[facing={facing},open=closed]")
                        opened = v.canonical_state(f"{block}[facing={facing},open=open]")
                        if closed not in g.shapes or opened not in g.shapes:
                            raise RuntimeError(("Actual native gate state was not exported", closed))
                        if pos in tags or w.block(pos).partition("[")[0] not in AIR or g.boxes(w.get(pos[0], pos[1] - 1, pos[2])) != [[0., 0., 0., 1., 1., 1.]]:
                            break
                        lo, hi = site["station_bounds"]
                        if not all(lo[i] <= pos[i] <= hi[i] for i in range(3)):
                            break
                        buffers=[(pos[0]+d*travel[0],pos[1],pos[2]+d*travel[1]) for d in range(-3,4)]
                        if any(g.standing(q)["status"]!="STATIC_STANDING" or (
                            w.get(q[0],q[1]-1,q[2]).startswith('mtr:escalator_step[')
                            and properties(w.get(q[0],q[1]-1,q[2])).get('status')=='true') for q in buffers):
                            break
                        rows.append({"position": pos, "block": block, "closed_state": closed, "open_state": opened,
                                     "station_id": site["station_id"], "station_bounds": site["station_bounds"], "source_case": site["source_case"]})
                    if len(rows) != 2 or any(tuple(row["position"]) in changes for row in rows):
                        continue
                    opened_map = {tuple(row["position"]): row["open_state"] for row in rows}
                    w.get = lambda x, y, z: opened_map.get((x, y, z), base_get(x, y, z))
                    valid = all(g.standing(pos)["status"] == "STATIC_STANDING" and g.edge_clear(
                        (pos[0] - travel[0], pos[1], pos[2] - travel[1]), (pos[0] + travel[0], pos[1], pos[2] + travel[1])) for pos in positions)
                    w.get = base_get
                    if valid and not open_body_conflicts(rows):
                        pair = rows
                        break
                if pair:
                    break
            if pair:
                break
        if pair is None:
            unresolved.append({**site, "reason": "No measured pair with two complete3m buffers, grounded native bodies and exact open-shape sweeps; complete threshold redesign required"})
            continue
        gates.extend(pair); pairs.append({"source": site, "actual_gate_pair": pair})
        for row in pair:
            pos = tuple(row["position"])
            changes[pos] = row["closed_state"]
            start = [pos[0] - 3 * travel[0] + .5, pos[1], pos[2] - 3 * travel[1] + .5]
            finish = [pos[0] + 3 * travel[0] + .5, pos[1], pos[2] + 3 * travel[1] + .5]
            ident = f"r44/public_station_gate/{site['station_id']}/{pos[0]}_{pos[1]}_{pos[2]}"
            cases.extend(({"id": ident, "path": [start, finish], "actualAutomaticGate": list(pos), "requiresNativeOpenAndBalanceUnchanged": True},
                          {"id": ident + "/return", "path": [finish, start], "actualAutomaticGate": list(pos), "requiresNativeOpenAndBalanceUnchanged": True}))
    v.WORLD, v.OUT = world, out
    p, inverse = v.Painter(), v.Painter()
    for q, after in sorted(changes.items()):
        before = w.block(q)
        p.match((*q, *q), before, after, "r44/whole_public_station/native_free_gate")
        inverse.match((*q, *q), after, before, "inverse/r44/public_station/native_free_gate")
    manifest = {"schema": 44, "service": "existing_free_public_service", "dimension": v.DIM, "gates": gates}
    report = {"world": str(world), "cells": len(changes), "whole_threshold_pairs": pairs, "unresolved_thresholds": unresolved,
              "unresolved_station_regions": sites["unresolved_station_regions"], "original_complete_nbt": [{"position": q, "snbt": t.snbt()} for q, t in sorted(tags.items())],
              "native_shape_export_sha256": hashlib.sha256(export_path.read_bytes()).hexdigest(),
              "shape_source": exported["source"], "install_after_exact_apply": ["r44_public_station_gates.json", "merge_native_collision_shapes.json"],
              "all501_authored_path_sweeps_clear_of_open_native_gate_bodies": True,
              "native_cases": cases, "negative": "Existing cards/readers/exit controls, all device NBT, floors, train tracks/APG bodies and500+ full journeys retained; no fare/balance/ticket calls",
              "status": "STATIC_PARTIAL_CANDIDATE; remaining thresholds must be reconstructed. All20 regions, real auto opening, occupancy, opposite exits, unchanged balance, closing,501 paths, whole art and cold reload pending"}
    p.meta.update(report); p.save_plan("all_measured_public_gate_pairs")
    inverse.meta.update({"forward": "all_measured_public_gate_pairs", "remove_manifest": "r44_public_station_gates.json", "cells": len(changes)})
    inverse.save_plan("inverse_all_measured_public_gate_pairs")
    for name, data in (("contract.json", report), ("r44_public_station_gates.json", manifest), ("merge_native_collision_shapes.json", merged_shapes), ("native_cases.json", cases)):
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf8")
    print("Exact native public gate pairs:", len(pairs), "; unplaced", len(unresolved), "; no world mutation", flush=True)
    return p


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--world", type=Path, default=WORLD); parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--seed-sites", action="store_true")
    args = parser.parse_args()
    seeds(args.out) if args.seed_sites else plan(args.world, args.out)
