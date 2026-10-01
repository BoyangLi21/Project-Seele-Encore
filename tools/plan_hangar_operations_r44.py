"""Three real, wall-backed operation clusters on the retained work layer.

Source binding is installed explicitly by root after the exact patch. The
plan preserves complete devices/actors and both public lanes. No apply CLI.
"""
from pathlib import Path
import copy, hashlib, json
import nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR, iter_block_entities
from audit_facility_transit_r44 import Geometry

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/hangar_working_controls_v1"
BUTTON = "minecraft:polished_blackstone_button[face=wall,facing=east,powered=false]"
PANEL = "projectseele:nerv_direction_panel[facing=east,wayfinding=true]"


def plan(world=WORLD, out=OUT):
    world, out = Path(world), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if list(out.glob("three_worklayer_controls/applied_*/receipt.json")):
        raise RuntimeError("Applied control revision is immutable")
    w = MeasuredWorld(world)
    lo, hi = (-35, -398, -289), (95, -390, -212)
    w.box(lo, hi); w.load(); g = Geometry(w)
    tags = {q: copy.deepcopy(t) for q, t in iter_block_entities(world, v.DIM, lo, hi)}
    current = json.loads((ROOT / "artifacts/rebuild_r44/facility_transit_r44/hangar_tv_calibration_v2/semantic_frame.json").read_text(encoding="utf8"))
    v.WORLD, v.OUT = world, out
    p, inverse = v.Painter(), v.Painter()
    changes, controls, walks = {}, [], []
    labels = (("PREPARE", ["准备出动", "收桥与插栓联锁", "仅待机状态可执行"]),
        ("STATUS", ["湿舱运行状态", "查看真实设备阶段", "本键不改变运行状态"]),
        ("CANCEL", ["取消发射并返回", "仅发射锁定时可执行", "保持返舱与停靠通路净空"]))
    def put(q, target):
        before = w.block(q)
        if before is None or before.partition("[")[0] not in AIR or q in tags:
            raise RuntimeError(("Other installed component at work-layer control", q, before))
        if g.boxes(target) is None:
            raise RuntimeError(("No native exact control shape", target))
        changes[q] = target
    for variant, cx in enumerate((-12, 30, 72)):
        for index, (action, rows) in enumerate(labels):
            q = (cx - 19, -393, -254 + index * 2)
            panel = (q[0], -392, q[2])
            for cell in (q, panel):
                back = (cell[0] - 1, cell[1], cell[2])
                if g.boxes(w.block(back)) != [[0., 0., 0., 1., 1., 1.]]:
                    raise RuntimeError(("No measured complete pressure-wall backing", back, w.block(back)))
            put(q, BUTTON); put(panel, PANEL)
            reader = (cx - 18, -394, q[2])
            route = g.flat_path((-29, -394, -285), reader, radius=180)
            if route is None:
                raise RuntimeError(("Control is not on the actual lift/work-layer path", q))
            # Both lanes and their full length remain actual supported public
            # space. The wall button/panel occupy only their exported thin
            # boundary shape, never a whole cube across a working lane.
            for x in (cx - 19, cx - 18):
                for z in range(-264, -215):
                    if g.standing((x, -394, z))["status"] != "STATIC_STANDING":
                        raise RuntimeError(("Existing complete working lane is not clear", x, z))
            for x in (cx - 19, cx - 18):
                for z in (q[2] - 1, q[2], q[2] + 1):
                    if g.standing((x, -394, z))["status"] != "STATIC_STANDING":
                        raise RuntimeError(("No complete grounded operation approach", x, z))
            tag = nbtlib.Compound({"id": nbtlib.String("projectseele:station_departure_board"),
                "x": nbtlib.Int(panel[0]), "y": nbtlib.Int(panel[1]), "z": nbtlib.Int(panel[2]),
                "Wayfinding": nbtlib.Byte(1), "NativePlatformId": nbtlib.Long(-1),
                "PlatformCentre": nbtlib.Long(0), "Station": nbtlib.String(f"EVA 0{variant} · 湿舱操作"),
                "Route": nbtlib.String("整备与出动"),
                **{f"Row{i}": nbtlib.String(s) for i, s in enumerate(rows)}})
            p.block_entities[panel] = tag
            paths = [[x + .5, y, z + .5] for x, y, z in route]
            ident = f"r44/hangar_control/{variant}/{action.lower()}"
            walks.extend(({"id": ident, "path": paths, "readingBoard": panel,
                "readingWayfinding": True, "button": q, "actualPhysicalUse": "UNVERIFIED"},
                {"id": ident + "/return", "path": paths[::-1]}))
            controls.append({"variant": variant, "action": action, "position": q,
                "reader": reader, "panel": panel, "facing": "east", "rows": rows,
                "measured_backing": [{"position": [cell[0] - 1, cell[1], cell[2]],
                    "state": w.block((cell[0] - 1, cell[1], cell[2]))} for cell in (q, panel)]})
    # Use an overlay of exact native shapes to verify post-placement clearance
    # for every one of the two lanes, not just the chosen operation point.
    original_block = w.block
    original_get = w.get
    def get(x, y, z):
        return changes.get((x, y, z), original_get(x, y, z))
    w.get = get
    for cx in (-12, 30, 72):
        for x in (cx - 19, cx - 18):
            for z in range(-264, -215):
                if g.standing((x, -394, z))["status"] != "STATIC_STANDING":
                    raise RuntimeError(("Proposed actual control shape narrows the public lane", x, z))
    w.get = original_get
    for q, after in sorted(changes.items()):
        before = original_block(q)
        p.match((*q, *q), before, after, "r44/hangar_control/actual_wall_operation")
        inverse.match((*q, *q), after, before, "inverse/r44/hangar_control")
    manifest = {"schema": 44, "dimension": v.DIM, "controls": controls,
        "original_units": [{"variant": b["variant"], "uuid": b["eva_uuid"]} for b in current["bays"]],
        "binding": "Explicit installed source match; existing prepare/status/cancel requests; no new launch or automatic task authority"}
    report = {"world": str(world), "cells": len(changes), "controls": controls,
        "original_full_nbt": [{"position": q, "snbt": t.snbt()} for q, t in sorted(tags.items())],
        "full_two_lane_shape_clearance": "STATIC_PRESERVED", "native_cases": walks,
        "install_manifest": "r44_hangar_operator_interfaces.json only after successful exact apply",
        "function": "UNVERIFIED physical click and complete guarded request lifecycle",
        "visual_and_reload": "UNVERIFIED"}
    p.meta.update(report); p.save_plan("three_worklayer_controls")
    inverse.meta.update({"forward": "three_worklayer_controls", "cells": len(changes),
        "remove_installed_manifest": "r44_hangar_operator_interfaces.json", "original_full_nbt": report["original_full_nbt"]})
    inverse.save_plan("inverse_three_worklayer_controls")
    report["ops_sha256"] = hashlib.sha256((out / "three_worklayer_controls/ops.json.gz").read_bytes()).hexdigest()
    (out / "contract.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    (out / "r44_hangar_operator_interfaces.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
    (out / "native_cases.json").write_text(json.dumps(walks, ensure_ascii=False, indent=2), encoding="utf8")
    print("Three actual work-layer operation clusters:", len(changes), "exact cells;", len(walks), "physical/path cases pending; no world write", flush=True)
    return p


if __name__ == "__main__":
    plan()
