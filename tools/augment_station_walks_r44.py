"""Keep the frozen497 station walks and add the real onsite cabinet routes.

Native boarding, actual stairs, physical cabinet use and certification remain
separate evidence. Neither paths nor reaching the site set certified=true.
"""
from pathlib import Path
import copy, hashlib, json, math
from collections import deque
from audit_facility_transit_r44 import Geometry
from install_coordination_field_r44 import cabinet_cells
from measure_world_r40 import MeasuredWorld

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/rebuild_r44/facility_transit_r44/native_transit_cases/station_walk_cases.json"
SITE = ROOT / "artifacts/rebuild_r44/facility_transit_r44/technical_centre_retest_site.json"
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/station_walk_cases_v3"


def final_cabinet_approach(path, site):
    """Compose the real owned cabinet before connecting its public operator bay."""
    owned = cabinet_cells()
    floor = site["device_site"]["feet_y"]
    lo = (min(p[0] for p in owned) - 3, floor, min(p[2] for p in owned) - 2)
    hi = (max(p[0] for p in owned) + 3, floor, max(p[2] for p in owned) + 2)
    world = MeasuredWorld(ROOT / "run/saves/SEELE_FIELD_R44_REVIEW")
    world.box((lo[0]-1, floor-2, lo[2]-1), (hi[0]+1, floor+4, hi[2]+1));world.load()
    actual_get = world.get
    for point, expected in owned.items():
        actual = world.block(point)
        if actual not in (expected, "minecraft:air"):
            raise RuntimeError(("Cabinet geometry changed; preserve actual component and remeasure", point, actual, expected))
    world.get = lambda x, y, z: owned.get((math.floor(x), math.floor(y), math.floor(z)), actual_get(x, y, z))
    geometry = Geometry(world)
    def inside(p):
        return p[1] == floor and lo[0] <= p[0] <= hi[0] and lo[2] <= p[2] <= hi[2]
    points = [tuple(map(math.floor, p)) for p in path]
    first = len(points)-1
    while first > 0 and inside(points[first-1]):first -= 1
    start, goal = points[first], points[-1]
    if not inside(start) or geometry.standing(start)["status"] != "STATIC_STANDING":
        raise RuntimeError(("No actual public alcove entrance", start))
    if geometry.standing(goal)["status"] != "STATIC_STANDING":
        raise RuntimeError(("Operator space obstructed", goal))
    queue, previous = deque([start]), {start: None}
    while queue and goal not in previous:
        q = queue.popleft()
        for dx, dz in ((1,0),(-1,0),(0,1),(0,-1)):
            n = (q[0]+dx, floor, q[2]+dz)
            if n in previous or not inside(n) or geometry.standing(n)["status"] != "STATIC_STANDING" or not geometry.edge_clear(q,n):continue
            previous[n] = q;queue.append(n)
    if goal not in previous or geometry.unknown:
        raise RuntimeError(("Final cabinet has no measured connected operator access", sorted(geometry.unknown)))
    chain = [goal]
    while previous[chain[-1]] is not None:chain.append(previous[chain[-1]])
    replacement = [[q[0]+.5, floor, q[2]+.5] for q in reversed(chain)]
    final = copy.deepcopy(path[:first]) + replacement
    return final, dict(original_terminal_nodes=len(path)-first, final_terminal_nodes=len(replacement),
                      alcove_entry=path[first], unchanged_operator=path[-1], unchanged_prefix=first,
                      exact_composed_cabinet_cells=len(owned), candidate_floor=floor, world_written=False)


def main():
    original = json.loads(BASE.read_text(encoding="utf8"))
    if len(original) != 497:
        raise RuntimeError("Frozen original station denominator changed")
    site = json.loads(SITE.read_text(encoding="utf8"))
    result = copy.deepcopy(original)
    added = [];reconciled = []
    for row in site["paths"]:
        path, proof = final_cabinet_approach(row["path"], site);reconciled.append({"platform":row["platform"],**proof})
        case = {"id": "r44/technical_centre_field_cabinet/from_" + row["platform"],
            "station_id": site["station_id"], "source_platform": row["platform"],
            "path": path,
            "actualUseBlock": [-1074, 120, 571], "use_block_facing": "north",
            "onsite_operation": "UNVERIFIED actual player use; walking arrival does not certify",
            "native_stairs": "UNVERIFIED actual overbridge ascent/descent; no rail crossing or NPC teleport"}
        added.append(case)
        added.append({**case, "id": case["id"] + "/return", "path": case["path"][::-1],
            "actualUseBlock": None, "onsite_operation": "Return walking scope; no remote cabinet operation"})
    result.extend(added)
    if len({case["id"] for case in result}) != len(result):
        raise RuntimeError("Whole-station case IDs collide")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "station_walk_cases.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    (OUT / "technical_centre_cases.json").write_text(json.dumps(added, ensure_ascii=False, indent=2), encoding="utf8")
    (OUT / "composed_cabinet_access.json").write_text(json.dumps(reconciled, ensure_ascii=False, indent=2), encoding="utf8")
    (OUT / "contract.json").write_text(json.dumps({"frozen497_source": str(BASE),
        "frozen497_sha256": hashlib.sha256(BASE.read_bytes()).hexdigest(), "frozen_original_cases": len(original),
        "added_actual_site_paths": len(added), "whole_station_path_obligations": len(result),
        "site_source": str(SITE), "site_source_sha256": hashlib.sha256(SITE.read_bytes()).hexdigest(),
        "grounded_cabinet_button": [-1074,120,571],
        "actual_platform_routes": [{"platform": r["platform"], "nodes": len(r["path"]),
            "staging": r["staging"], "operator": r["path"][-1]} for r in site["paths"]],
        "status": "All501 paths still native obligations; exact2 platform rides and actual cabinet use required separately. No certification or world mutation."}, ensure_ascii=False, indent=2), encoding="utf8")
    print("Whole station paths:", len(original), "+", len(added), "=", len(result), "; native/action certification unchanged", flush=True)


if __name__ == "__main__":
    main()
