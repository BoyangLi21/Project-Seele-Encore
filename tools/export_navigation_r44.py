"""Measured HQ walking graph and a separate arrival-hall wayfinding graph.

The remote arrival hall connects to HQ by an actual train, not a walking or
teleport edge. Only --apply installs the derived HQ file into the world; the
root coordinator owns that final mutation and hashes the delivered copy.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path

import plan_pyramid_navigation_r22 as nav
from audit_transport_facilities_r45 import floor_key,walking_fallback

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/navigation"
INTERFACES = ROOT / "artifacts/rebuild_r44/facility_transit_r44/measured_interfaces_v3/lifts.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def nearest_lift_paths(folder, data):
    """Walking cost to a real landing; no borrowed elevator hop to find one."""
    import numpy as np
    from scipy.sparse import csr_matrix, coo_matrix
    from scipy.sparse.csgraph import dijkstra
    from scipy.spatial import cKDTree
    with np.load(folder / "walkable_graph.npz") as saved:
        coords = saved["coords"]
        graph = csr_matrix((saved["weights"], saved["indices"], saved["indptr"]), shape=(len(coords), len(coords)))
    tree = cKDTree(coords)
    landings = np.asarray(data["lift_landings"], dtype=int)
    if not len(landings):
        return None
    distance, indices = tree.query(landings)
    if np.any(distance > .01):
        raise RuntimeError("Measured lift landing coordinate did not survive graph export")
    removed = set()
    for edge in json.loads((folder / "destination_connectivity.json").read_text(encoding="utf8"))["lift_edges"]:
        _, a = tree.query(edge["a"])
        _, b = tree.query(edge["b"])
        removed.update((int(a) * len(coords) + int(b), int(b) * len(coords) + int(a)))
    coo = graph.tocoo()
    keep = ~np.isin(coo.row.astype(np.int64) * len(coords) + coo.col, list(removed))
    walking = coo_matrix((coo.data[keep], (coo.row[keep], coo.col[keep])), shape=graph.shape).tocsr()
    walking_all = walking
    # Local stair thresholds remain part of their commissioned use floor.
    # Cross-floor stairs cannot choose another level's closer lift landing.
    flat = walking.tocoo()
    floor_keys = np.asarray([floor_key(q) for q in coords])
    keep = floor_keys[flat.row] == floor_keys[flat.col]
    walking = coo_matrix((flat.data[keep], (flat.row[keep], flat.col[keep])), shape=graph.shape).tocsr()
    costs, predecessors, sources = dijkstra(walking, directed=True, indices=indices, min_only=True, return_predecessors=True)
    metres = np.full(len(coords), np.inf)
    metres[indices] = 0.
    for index in np.argsort(costs):
        if not np.isfinite(costs[index]):
            break
        parent = int(predecessors[index])
        if parent >= 0:
            if not np.isfinite(metres[parent]):
                raise RuntimeError("Nearest-lift predecessor is not an acyclic walking route")
            metres[index] = metres[parent] + float(np.linalg.norm(coords[index] - coords[parent]))
    _, exported = tree.query(np.asarray(data["nodes"], dtype=int)[:, :3])
    source_to_landing = {int(i): landings[k].tolist() for k, i in enumerate(indices)}
    table, unresolved = [], []
    for node, index in enumerate(exported):
        source = int(sources[index])
        if source < 0 or not np.isfinite(costs[index]):
            unresolved.append(data["nodes"][node][:3])
            table.append(None)
            continue
        next_index = int(predecessors[index])
        if next_index < 0:
            next_index = int(index)
        table.append({"nearest_landing": source_to_landing[source], "floor_key": str(floor_keys[index]), "walking_cost": float(costs[index]),
                      "walking_metres": float(metres[index]),
                      "next": coords[next_index].tolist()})
    export_coords=np.asarray(data["nodes"],dtype=int)[:,:3]
    export_index={tuple(q):i for i,q in enumerate(export_coords)}
    local=walking_all[exported][:,exported].tocsr();all_edges=local.tocoo()
    stair_edges=[(int(i),int(j),float(w))for i,j,w in zip(all_edges.row,all_edges.col,all_edges.data)
                 if abs(export_coords[i,1]-export_coords[j,1])==1]
    fallback=walking_fallback(export_coords,np.ones(len(export_coords),dtype=bool),
        lambda a,b:local[export_index[tuple(a)],export_index[tuple(b)]]>0,
        data["lift_landings"],table,stair_edges)
    unresolved=[export_coords[i].tolist()for i,row in enumerate(table)if row is None]
    payload = {"graph_sha256": digest(folder / "nerv_routes_r24.json.gz"), "same_floor": True, "same_floor_schema": 3,
               "node_floor_keys": [floor_key(q[:3]) for q in data["nodes"]], "nodes": table,
               "unresolved_coordinates": unresolved,
               "walking_stair_fallback_rows":fallback,
               "scope": "Prefer current commissioned use-floor landing; when unavailable explicitly label existing walking/stair transfer. Elevator hops excluded; actual equipment and permissions UNVERIFIED"}
    file = folder / "nearest_lift_paths.json.gz"
    with gzip.open(file, "wt", encoding="utf8") as stream:
        json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
    return {"file": str(file.resolve()), "sha256": digest(file), "unresolved_nodes": len(unresolved)}


def component(world, out, bounds, goals, groups):
    out.mkdir(parents=True, exist_ok=True)
    nav.WORLD = world
    nav.LO, nav.HI = bounds
    nav.PUBLIC_DOMAINS = nav.PUBLIC_PATHS = None
    nav.GOALS, nav.LIFT_GROUPS = goals, groups
    nav.RAIL_CURVES = json.loads((world / "native_transit_r28.json").read_text(encoding="utf8"))["curves"]
    nav.LIFT_BOARD_COST, nav.LIFT_VERTICAL_COST = 4., .12
    nav.LIFT_DIRECT, nav.STAIR_COST = True, 4.
    file = out / "nerv_routes_r24.json.gz"
    nav.main(False, out, file)
    with gzip.open(file, "rt", encoding="utf8") as stream:
        data = json.load(stream)
    data["source"] = "R44 measured actual floors/whole corridor width and collision boundaries; operating lifts/doors are explicit, not an air-derived room permit."
    data["verification"] = "Derived geometry only; native equipment, permissions and whole-facility passes remain separate."
    with gzip.open(file, "wt", encoding="utf8") as stream:
        json.dump(data, stream, ensure_ascii=False, separators=(",", ":"))
    nearest = nearest_lift_paths(out, data)
    manifest = {"world": str(world.resolve()), "bounds": bounds, "nodes": len(data["nodes"]),
                "output": str(file.resolve()), "sha256": digest(file),
                "native_shapes_sha256": digest(world / "native_collision_shapes.json"),
                "native_transit_sha256": digest(world / "native_transit_r28.json"),
                "status": "UNVERIFIED actual walks/lift operations/reader visibility/restart and installed copy"}
    if nearest:
        manifest["nearest_lift"] = nearest
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
    return file, manifest


def main(world=WORLD, out=OUT, interfaces=INTERFACES, apply=False, parts=("hq", "arrival")):
    world, out, interfaces = Path(world), Path(out), Path(interfaces)
    outputs = {}
    if "hq" in parts:
        bounds = ((-90, -574, -310), (340, -310, 625))
        rows = json.loads(interfaces.read_text(encoding="utf8"))
        groups = []
        for lift in rows:
            points = [tuple(l["handoff"]) for l in lift["landings"]
                      if all(bounds[0][i] <= l["handoff"][i] <= bounds[1][i] for i in range(3))]
            if len(points) > 1:
                groups.append({"id": lift["id"], "points": points})
        if len(groups) != 5:
            raise RuntimeError(("Expected the five multi-stop HQ walking interfaces", groups))
        goals = [("command", "指挥室入口", (28, -406, 269)), ("hangars", "机库登机通道", (90, -394, -255)),
                 ("station", "总部火车站", (30, -466, 451)), ("pyramid_station", "金字塔接驳站", (30, -466, 518)),
                 ("launch_station", "发射区车站", (150, -442, -28)), ("observation", "机库观景走廊", (90, -367, -221)),
                 ("dogma", "终极教条前厅", (30, -566, 280)), ("low_plant", "机库低层检修厅", (-40, -442, -286))]
        file, manifest = component(world, out / "hq", bounds, goals, groups)
        manifest["native_interface_source"] = str(interfaces.resolve())
        manifest["native_interface_sha256"] = digest(interfaces)
        if apply:
            target = world / "nerv_routes_r24.json.gz"
            if target.exists():
                shutil.copy2(target, out / "hq/nerv_routes_before.json.gz")
            shutil.copy2(file, target)
            if digest(target) != manifest["sha256"]:
                raise RuntimeError("Installed derived HQ navigation hash mismatch")
            manifest["derived_installed_sha256"] = digest(target)
            nearest_target = world / "nearest_lift_paths_r44.json.gz"
            shutil.copy2(out / "hq/nearest_lift_paths.json.gz", nearest_target)
            if digest(nearest_target) != manifest["nearest_lift"]["sha256"]:
                raise RuntimeError("Installed nearest-lift table hash mismatch")
            manifest["nearest_lift_installed_sha256"] = digest(nearest_target)
        (out / "hq/manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
        outputs["hq"] = manifest
    if "arrival" in parts:
        # This component deliberately never becomes the NPC's HQ walking
        # graph. Its train directions point to the actual local station port.
        bounds = ((-406, -470, 707), (-276, -450, 808))
        station = (-335, -466, 771)
        goals = [("station", "地下都市站 · U1", station), ("command", "指挥室 · 乘 U1", station),
                 ("hangars", "机库登机层 · 乘 U1 换 U2", station),
                 ("surface_exit", "地面 NERV 入口 · 大直梯", (-360, -466, 738)),
                 ("arrival_service", "到达服务 · 通行咨询", (-388, -466, 735))]
        file, manifest = component(world, out / "arrival", bounds, goals, [])
        manifest["transport_required"] = {"command": "TRAIN/U1", "hangars": "TRAIN/U1 then TRAIN/U2"}
        manifest["npc_walk_file"] = False
        manifest["station_interpretation"] = "Local station entrance/boarding approach; live train door alignment and actual ride remain UNVERIFIED"
        if apply:
            shutil.copy2(file, world / "arrival_wayfinding_r44.json.gz")
            if digest(world / "arrival_wayfinding_r44.json.gz") != manifest["sha256"]:
                raise RuntimeError("Installed arrival wayfinding hash mismatch")
            manifest["derived_installed_sha256"] = manifest["sha256"]
        (out / "arrival/manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
        outputs["arrival"] = manifest
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf8")
    print({name: entry["nodes"] for name, entry in outputs.items()}, flush=True)
    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", type=Path, default=WORLD)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--interfaces", type=Path, default=INTERFACES)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--parts", choices=("hq", "arrival", "both"), default="both")
    args = parser.parse_args()
    selected = ("hq", "arrival") if args.parts == "both" else (args.parts,)
    main(args.world, args.out, args.interfaces, args.apply, selected)
