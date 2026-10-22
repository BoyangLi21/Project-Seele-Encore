"""Read-only, bounded audit of declared intermediate pyramid levels.

Physical surface discovery is diagnostic, never construction permission. Existing
active navigation supplies declared pedestrian seeds; additional reachable floor
and edges stay separately classified until their source ownership is reviewed.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from functools import lru_cache
import gzip
import hashlib
import json
import math
from pathlib import Path

from audit_r53_pyramid_stair_treads import Frozen, run as stair_audit
from prepare_school_hakone_native_r45 import ActualGeometry


BOUNDS = (-90, 150, 207, 447)
LEVELS = (
    ("command_dais", "主指挥台", (-517, -516),
     "personnel_lifts_r52.json: 主指挥台 -516; facility_chairs_r26 and retained command floor"),
    ("command_service", "后方勤务", (-512,),
     "personnel_lifts_r52.json: 后方勤务层 -512"),
    ("command_observation", "指挥室观察廊", (-502,),
     "personnel_lifts_r52.json: 指挥室观察廊 -502; prepare_r53_personnel_access.py original stair bypass"),
    ("commander_reception", "总指挥联络厅", (-482, -481),
     "finish_gallery_roof_r14.py floor X4..52/Z278..363 at -390, R52 Y-93 => feet -482; lift -481"),
    ("commander_upper", "总指挥会客厅及原接梯", (-434, -433, -422),
     "WORLD_REFINEMENT_R14.md: lift -340 then original stair to hall -329, R52 Y-93; apply_commander_office_r01.py X5..55/Z302..352"),
)
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def load(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_text("utf8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Audit:
    def __init__(self, source, world):
        self.m = Frozen(source, world)
        self.g = ActualGeometry(self.m)
        self.g.boxes = lru_cache(None)(self.g.boxes)

    @lru_cache(None)
    def point(self, cell):
        x, y, z = cell
        boxes = self.g.boxes((x, math.floor(y)-1, z))
        if boxes:
            for top in sorted({r[4] for r in boxes}, reverse=True):
                if .01 < top <= 1 and all(any(r[0] <= X <= r[3] and r[2] <= Z <= r[5]
                        and abs(r[4]-top) < .001 for r in boxes)
                        for X in (.25, .5, .75) for Z in (.25, .5, .75)):
                    return (x+.5, math.floor(y)-1+top, z+.5)
        return (x+.5, y, z+.5)

    @lru_cache(None)
    def status(self, cell):
        return self.g.standing(self.point(cell))

    def cross(self, a, b):
        p, q = self.point(a), self.point(b)
        if abs(p[1]-q[1]) > .5001:
            return "STEP_HEIGHT_REQUIRES_STAIR_REVIEW"
        h = max(p[1], q[1])
        return self.g.clear((p[0], h, p[2]), target=(q[0], h, q[2]))

    def drops(self, cell):
        if self.status(cell) != "STATIC_STANDING":
            return []
        x, y, z = cell
        result = []
        p = self.point(cell)
        for dx, dz in DIRS:
            q = (x+dx, y, z+dz)
            if self.status(q) != "NO_FULL_DATUM_BEARING":
                continue
            if self.g.clear(p, target=(p[0]+dx, p[1], p[2]+dz)) != "CLEAR":
                continue
            # Search actual neighbouring support, without snapping to an upper
            # voxel top: half steps must not become false two-metre drops.
            lower = []
            for d in (.5, 1, 1.5, 2, 2.5, 3):
                if self.g.standing((q[0]+.5, p[1]-d, q[2]+.5)) == "STATIC_STANDING":
                    lower.append(d)
            if lower and min(lower) <= .5:
                continue
            result.append(dict(cell=cell, to=q, lower_support_offsets=lower,
                states=[self.m.block((q[0], y+d, q[2])) for d in (-4, -3, -2, -1, 0, 1)],
                construction_authorized=False))
        return result


def regressions(args):
    before = Audit(args.source, args.world)
    after = Audit(args.guard_after, args.world)
    cells = ((6, -541, 258), (6, -541, 259), (7, -541, 259))
    old = [r for q in cells for r in before.drops(q)]
    new = [r for q in cells for r in after.drops(q)]
    assert len(old) == 4 and not new, (old, new)
    path = args.output / "REGRESSION_BURIED_FULL.json"
    stair_audit(args.buried_before, args.world, path)
    report = load(path)
    buried = [r for group in report["flights"]+report["unclassified"] for r in group["buried_first_treads"]]
    wanted = {(3, -528, z) for z in range(266, 269)} | {(56, -528, z) for z in range(266, 269)}
    wanted |= {(x, -486, z) for x in (5, 55) for z in range(268, 271)}
    wanted |= {(x, -458, 301) for x in range(5, 8)}
    wanted |= {(x, -514, z) for x in (7, 52) for z in range(263, 266)}
    assert {tuple(r["first_tread"]) for r in buried} == wanted
    return dict(guard_missing_before=old, guard_missing_after=new,
                buried_flights_and_short_rows=7, buried_cells=len(buried), passed=True,
                permission="Historical known failures only; no world writes")


def classify_existing(args):
    """Resolve diagnostics against authored doors without rerunning the volume."""
    args.output.mkdir(parents=True, exist_ok=False)
    report = load(args.classify_existing)
    audit = Audit(args.source, args.world)
    frame_path = args.world/"r52/headquarters.json"
    frame = load(frame_path)
    doors_path = args.world/frame["command_door_manifest"]
    assert sha(doors_path) == frame["command_door_sha256"]
    command = {tuple(p): row["id"] for row in load(doors_path)["doors"] for p in row["aperture"]}
    lifts = load(args.world/"personnel_lifts_r52.json")
    lift_doors = {tuple(r["pos"]): dict(lift=lift["id"], floor=f["label"], kind=kind)
        for lift in lifts["lifts"] for f in lift["floors"]
        for kind in ("landing_doors", "cabin_doors") for r in f[kind]}

    def blockers(a, b):
        p, q = audit.point(tuple(a)), audit.point(tuple(b))
        lo = (min(p[0],q[0])-.29, p[1]+.015, min(p[2],q[2])-.29)
        hi = (max(p[0],q[0])+.29, p[1]+1.785, max(p[2],q[2])+.29)
        found = []
        for x in range(math.floor(lo[0]),math.floor(hi[0])+1):
            for y in range(math.floor(lo[1]),math.floor(hi[1])+1):
                for z in range(math.floor(lo[2]),math.floor(hi[2])+1):
                    cell=(x,y,z); boxes=audit.g.boxes(cell)
                    if boxes is None:
                        found.append(dict(cell=cell,kind="UNKNOWN_NATIVE_SHAPE")); continue
                    if not any(all(cell[k]+v[k]<hi[k] and cell[k]+v[k+3]>lo[k]
                                   for k in range(3)) for v in boxes): continue
                    state=audit.m.block(cell)
                    kind=("OWNED_COMMAND_DOOR_CLOSED" if cell in command and state=="minecraft:barrier"
                        else "OWNED_LIFT_INTERLOCK_CLOSED" if cell in lift_doors
                        else "ORDINARY_PERSONNEL_DOOR_CLOSED" if "city_personnel_door[" in state and "open=false" in state
                        else "FIXED_NATIVE_OBSTRUCTION")
                    found.append(dict(cell=cell,state=state,kind=kind,
                        owner=command.get(cell,lift_doors.get(cell))))
        return found

    all_guidance=[]; all_drops=[]
    for level in report["levels"]:
        for r in level["blocked_active"]:
            owned=[command[q] for dy in (0,1) if (q:=tuple([r["cell"][0],r["cell"][1]+dy,r["cell"][2]])) in command]
            if owned and "minecraft:barrier" in r["states"]:
                r["classification"]="OWNED_COMMAND_DOOR_CLOSED"
                r["command_door_ids"]=sorted(set(owned))
        for r in level["guidance_failures"]:
            r["blockers"]=blockers(r["cell"],r["next"])
            if r["blockers"] and all(v["kind"].endswith("_CLOSED") for v in r["blockers"]):
                r["classification"]="DYNAMIC_CLOSED_DOOR_REQUIRES_NATIVE_USE_TEST"
                r["static_defect"]=False
            else:
                r["classification"]="FIXED_GUIDANCE_OBSTRUCTION_REVIEW"
                r["static_defect"]=None
            all_guidance.append(r)
        for r in level["separators"]:
            if r["graph_edge_emitted"]:
                r["blockers"]=blockers(r["a"],r["b"])
        for r in level["drops"]:
            a,b=tuple(r["cell"]),tuple(r["to"])
            if a[1] in (-516,-512) and (a[0],a[2]) in ((6,258),(6,259),(7,259)):
                r["ownership_review"]="AUTHORED_CALL_LANDING_MISSING_EDGE_GUARD"
            elif a[1]==-502 and 7<=a[0]<=11 and a[2]==256 and b==(a[0],-502,255):
                r["ownership_review"]="LIFT_THRESHOLD_INSIDE_CLOSED_LANDING_DOOR"
                r["reason"]="Original Z256 threshold lies between registered landing door Z257 and cabin door Z255. A fixed rail would block the authored lift passage. Missing cabin at this parked state is not a static floor defect."
                r["fixed_guard_authorized"]=False
            elif r["use_classification"]!="PHYSICAL_SURFACE_ONLY_USE_UNKNOWN":
                r["ownership_review"]="HOLD_OPERATION_OR_STAIR_INTERFACE_REQUIRES_SPECIFIC_PROOF"
            else:
                r["ownership_review"]="HOLD_PHYSICAL_SURFACE_HAS_NO_PEDESTRIAN_USE_DECLARATION"
            all_drops.append(r)
    report["classification_inputs"]={str(p):sha(p) for p in (args.classify_existing,frame_path,doors_path,args.world/"personnel_lifts_r52.json")}
    report["classification_note"]="Original v1 findings are diagnostic records, not fault counts. Native closed doors are now identified by current authored aperture ownership; static geometry is unchanged."
    write_json=lambda name,value:(args.output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),"utf8")
    write_json("AUDIT_CLASSIFIED.json",report)
    unique={ (tuple(r["cell"]),tuple(r["next"])):r for r in all_guidance
             if r["classification"]=="FIXED_GUIDANCE_OBSTRUCTION_REVIEW" }
    summary=dict(source_audit=str(args.classify_existing),world_written=False,
        guidance_classifications=Counter(r["classification"] for r in all_guidance),
        unique_fixed_guidance_candidates=list(unique.values()),
        drop_ownership=Counter(r["ownership_review"] for r in all_drops),
        unknown_shape_limit=report["unknown_shapes"],
        interpretation="Only the two call-landings have an approved six-cell preview. No full-level acceptance is claimed.")
    write_json("CLASSIFIED_SUMMARY.json",summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    reg = regressions(args)
    (args.output/"REGRESSIONS.json").write_text(json.dumps(reg, ensure_ascii=False, indent=2), "utf8")
    audit = Audit(args.source, args.world)
    nav_path = args.world/"nerv_routes_r24.json.gz"
    nav = load(nav_path)
    walking = load(args.world/"r53_personnel_walking_graph.json.gz")
    nearest = load(args.world/"nearest_lift_paths_r44.json.gz")
    assert nearest["graph_sha256"] == sha(nav_path)
    nodes = [tuple(r[:3]) for r in nav["nodes"]]
    assert nodes == [tuple(r) for r in walking["nodes"]]
    index = {q: i for i, q in enumerate(nodes)}
    active = {q for q, ok in zip(nodes, nav["node_active"]) if ok}
    edges = {(a, b) for a, b, *_ in walking["walking_edges"]}
    xmin, xmax, zmin, zmax = BOUNDS
    reports = []
    for identity, title, ys, evidence in LEVELS:
        print("Auditing", identity, ys, flush=True)
        for y in ys:
            counts = Counter()
            standing, blocked_active, surfaces = set(), [], Counter()
            for x in range(xmin, xmax+1):
                for z in range(zmin, zmax+1):
                    q = (x, y, z)
                    state = audit.status(q)
                    counts[state] += 1
                    if state == "STATIC_STANDING":
                        standing.add(q)
                        surfaces[audit.m.block((x, y-1, z))] += 1
                    elif q in active:
                        present = [audit.m.block((x, y+d, z)) for d in (-1, 0, 1)]
                        kind = ("NATIVE_CLOSED_DOOR" if any("door" in str(s) for s in present)
                                else "SHAPED_STAIR_INTERFACE" if any("_stairs[" in str(s) for s in present)
                                else "UNRESOLVED_REGISTERED_NODE")
                        blocked_active.append(dict(cell=q, status=state, classification=kind, states=present))
            declared = standing & active
            reach = set(declared)
            queue = deque(declared)
            while queue:
                q = queue.popleft()
                for dx, dz in DIRS:
                    p = (q[0]+dx, y, q[2]+dz)
                    if p in standing and p not in reach and audit.cross(q, p) == "CLEAR":
                        reach.add(p)
                        queue.append(p)
            drops, separates, missing_edges = [], [], []
            sweeps = 0
            for q in sorted(standing):
                for finding in audit.drops(q):
                    finding["use_classification"] = ("DECLARED_PEDESTRIAN_NODE" if q in declared
                        else "REACHABLE_FROM_DECLARED_BUT_USE_NOT_PROVED" if q in reach
                        else "PHYSICAL_SURFACE_ONLY_USE_UNKNOWN")
                    drops.append(finding)
                for dx, dz in ((1, 0), (0, 1)):
                    p = (q[0]+dx, y, q[2]+dz)
                    if p not in standing:
                        continue
                    sweeps += 1
                    clear = audit.cross(q, p)
                    a, b = index.get(q, -1), index.get(p, -1)
                    emitted = (a, b) in edges or (b, a) in edges
                    if clear != "CLEAR":
                        separates.append(dict(a=q, b=p, status=clear, graph_edge_emitted=emitted))
                    elif q in declared and p in declared and not emitted:
                        missing_edges.append(dict(a=q, b=p, classification="CLEAR_DECLARED_NODES_NO_WALK_EDGE"))
            directions = []
            for q in sorted(declared):
                i = index[q]
                targets = [("goal/"+g["id"], nav["nodes"][i][3+k]) for k, g in enumerate(nav["goals"])]
                entry = nearest["nodes"][i]
                if entry:
                    targets.append(("nearest_lift", index[tuple(entry["next"])]))
                for destination, j in targets:
                    if i == j:
                        continue
                    p = nodes[j]
                    kind = "PASS"
                    if p not in active:
                        kind = "TARGET_INACTIVE"
                    elif p[1] == y and max(abs(q[0]-p[0]), abs(q[2]-p[2])) <= 1:
                        if audit.cross(q, p) != "CLEAR":
                            kind = "GUIDANCE_CROSSES_FIXED_BODY_OBSTRUCTION"
                    elif p[1] != y:
                        continue  # Existing stair/lift transition keeps its own proof.
                    if kind != "PASS":
                        directions.append(dict(cell=q, destination=destination, next=p, classification=kind))
            reports.append(dict(id=identity, title=title, feet_y=y, source_purpose=evidence,
                survey_bounds=BOUNDS, physical_columns=(xmax-xmin+1)*(zmax-zmin+1), statuses=dict(counts),
                surface_materials=dict(surfaces), declared_standing=len(declared), reachable_standing=len(reach),
                unclassified_standing=len(standing-reach), blocked_active=blocked_active,
                horizontal_body_sweeps=sweeps, separators=separates, drops=drops,
                declared_missing_edges=missing_edges, guidance_failures=directions,
                construction_authorized=False))
    # Preserve the whole-volume original stair inventory. All 38 complete
    # flights and 46 short/decor groups are retained, then tagged by intersection
    # with these declared level bands. The report does not turn decor into stairs.
    stairs = load(args.stair_report)
    levels = {y for _, _, ys, _ in LEVELS for y in ys}
    relevant = [r for r in stairs["flights"] if any(r["bounds"][0][1]-1 <= y <= r["bounds"][1][1]+2 for y in levels)]
    inputs = [args.source, args.guard_after, args.buried_before, args.stair_report,
              nav_path, args.world/"r53_personnel_walking_graph.json.gz",
              args.world/"nearest_lift_paths_r44.json.gz", args.world/"personnel_lifts_r52.json",
              args.world/"native_collision_shapes.json"]
    result = dict(schema="projectseele.r53.intermediate-floors.audit.v1", world_written=False,
        source_geometry="Frozen SOURCE_WIDE before B1 rail repair; no live map was read or modified",
        navigation="Current declared navigation, unchanged special-level geometry; hashes bind exact inputs",
        input_sha256={str(p): sha(p) for p in inputs}, regression_passed=reg["passed"],
        purpose_limit="Every physical column surveyed; only declared nodes are proven pedestrian uses. Newly reachable surfaces remain unclassified. No construction permission inferred.",
        levels=reports, existing_complete_stair_candidates=relevant,
        unknown_shapes=sorted(audit.g.unknown))
    (args.output/"AUDIT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf8")
    summary = [dict(id=r["id"], y=r["feet_y"], standing=r["statuses"].get("STATIC_STANDING", 0),
        declared=r["declared_standing"], reachable=r["reachable_standing"], drops=Counter(d["use_classification"] for d in r["drops"]),
        blocked_active=len(r["blocked_active"]), crossed_edges=sum(s["graph_edge_emitted"] for s in r["separators"]),
        missing_edges=len(r["declared_missing_edges"]), guidance_failures=len(r["guidance_failures"])) for r in reports]
    (args.output/"SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("world", "source", "output"):
        p.add_argument("--"+name, type=Path, required=True)
    for name in ("guard-after", "buried-before", "stair-report", "classify-existing"):
        p.add_argument("--"+name, type=Path)
    a=p.parse_args()
    if a.classify_existing: classify_existing(a)
    else:
        if not all((a.guard_after,a.buried_before,a.stair_report)):
            p.error("Full survey requires --guard-after, --buried-before and --stair-report")
        run(a)
