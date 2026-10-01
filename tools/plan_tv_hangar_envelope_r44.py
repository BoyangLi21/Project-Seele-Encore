"""Whole existing three-line vessel/transfer/launch skin, with exact inverse.

This is the static shell part of the unified TV contract. Root's matching
mechanical meshes and native workflows are independent required components.
No air/fluid is filled; doors, pits, all devices and all body routes are kept.
"""
from __future__ import annotations
import argparse
import math
import copy
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR, iter_block_entities
from verify_main_r20 import entities
from plan_factory_r20 import guide_y
from hangar_tv_design_r44 import (BLUE, GREEN, EDGE, STRUCT, LIGHT,
    FINISHABLE, FULL_CUBE, wet_faces, wet_finish,
    transfer_faces, transfer_finish, launch_faces, launch_finish)

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/"run/saves/SEELE_FIELD_R44_REVIEW"
OUT=ROOT/"artifacts/rebuild_r44/facility_transit_r44/tv_hangar_envelope_v3"


def plan(world=WORLD,out=OUT, finish_inside_geometry_keepouts=False,
         restore_applied_strip_lights=False):
    world,out=Path(world),Path(out);out.mkdir(parents=True,exist_ok=True)
    if list(out.glob("whole_three_line_tv_skin/applied_*/receipt.json")):raise RuntimeError("Applied stage is immutable; use another revision")
    lo,hi=(-45,-470,-294),(113,96,-16)
    w=MeasuredWorld(world);w.box(lo,hi);w.load()
    tags={p:copy.deepcopy(t) for p,t in iter_block_entities(world,v.DIM,lo,hi)}
    frames=json.loads((ROOT/"artifacts/rebuild_r44/facility_transit_r44/hangar_tv_calibration_v2/semantic_frame.json").read_text(encoding="utf8"))
    actors=entities(world)
    retained_entities=[{"uuid":uid,"snbt":copy.deepcopy(e).snbt()} for uid,e in actors.items()
        if str(e.get("id","")).startswith("projectseele:") and len(e.get("Pos",[]))==3
        and all(lo[i]<=float(e["Pos"][i])<=hi[i] for i in range(3))]
    # Cube-to-cube finishing is the only mutation. Read the actual exported
    # native shapes; no permissive cube fallback for an unknown state.
    shapes=json.loads((world/"native_collision_shapes.json").read_text(encoding="utf8"))
    shape=lambda state:shapes.get(v.canonical_state(state))
    for material in (BLUE,GREEN,EDGE,STRUCT,LIGHT):
        if shape(material)!=FULL_CUBE:raise RuntimeError(("No known full native cube",material,shape(material)))
    changes,held,components={},Counter(),[]
    old_light_seats=set()
    if restore_applied_strip_lights:
        source_plan=ROOT/"artifacts/rebuild_r44/facility_transit_r44/tv_hangar_envelope_v3/whole_three_line_tv_skin"
        if not list(source_plan.glob("applied_*/receipt.json")):
            raise RuntimeError("No actually applied skin source for the original lamp seats")
        for operation in json.load(gzip.open(source_plan/"ops.json.gz","rt",encoding="utf8")):
            if operation["extra"]==[LIGHT]:
                old_light_seats.add(tuple(operation["box"][:3]))
    def whole_native_lift(q):
        return 89<=q[0]<=99 and -446<=q[1]<=-364 and -56<=q[2]<=-48
    def put(q,target,purpose):
        before=w.block(q)
        if q in old_light_seats:target=LIGHT;purpose="restore_whole_original_strip_light"
        if before is None:raise RuntimeError(("Unknown boundary",q))
        if q in tags or whole_native_lift(q) or before.partition("[")[0] not in FINISHABLE:
            held[before.partition("[")[0]]+=1;return
        if before==target:return
        if shape(before)!=shape(target):raise RuntimeError(("Finish changes physical cube shape",q,before,target))
        if q in changes and changes[q][0]!=target:raise RuntimeError(("Conflicting component skin",q,changes[q],target))
        changes[q]=(target,purpose)
    for b in frames["bays"]:
        cx=b["bed"][0]
        wet=wet_faces(cx)
        # Full four facades and roof within the declared wet vessel. Existing
        # view glass, real personnel doors, rear pressure shutter and bearing
        # deck remain their whole components. Air is recorded, never filled.
        for q in sorted(wet):
            old=w.block(q)
            if old is None:raise RuntimeError(("Unmeasured whole wet face",q))
            target=wet_finish(cx,q,old)
            put(q,target,"wet_vessel_blue_pressure_skin")
        components.append({"variant":b["variant"],"component":"whole_wet_pressure_skin","bounds":b["static_shell"],"observed_surface_cells":len(wet),
            "reference":"tv_cage blue-grey enclosing vessel; original four user images' green moving machinery is separate"})
        launch=launch_faces(cx)
        for q in sorted(launch):
            old=w.block(q)
            # The supplied pallet frame establishes a green launch/transfer
            # room, not every metre of the deep catapult shaft. Keep the
            # existing blue shaft hierarchy; only actual indexed collars and
            # rear guide ribs take fabricated green/edge fittings.
            target=launch_finish(cx,q,old)
            put(q,target,"launch_green_guides_and_indexed_shutter_skin")
        components.append({"variant":b["variant"],"component":"whole_launch_guide_skin","bounds":[[cx-17,-410,-53],[cx+17,95,-19]],
            "protected_core":[[cx-15,-411,-51],[cx+15,96,-21]],"reference":"Existing blue catapult shaft retained; supplied TV pallet view supports green transfer hall/vertical guides, no inference that all deep-shaft walls must be green"})
    # R20 actually authors ONE shared transfer hall, not three parallel rooms.
    # Its two outside walls are x=-35/95 and its roof follows guide_y+86.
    # Individual carriage trenches stay independent inside the common hall.
    transfer=transfer_faces(guide_y)
    for q in sorted(transfer):
        old=w.block(q)
        target=transfer_finish(q,old)
        put(q,target,"shared_transfer_green_fabricated_pressure_skin")
    components.append({"component":"ONE actual shared three-trench transfer hall","outside_walls_x":[-35,95],"z":[-212,-54],"roof":"floor(guide_y(z))+86",
        "source":"R20 measured shared hall plus TV fabricated-green machinery; long ramp direction is the retained user SMALL WORLDS constraint"})
    p,inv=v.Painter(),v.Painter();v.WORLD,v.OUT=world,out
    # A same-full-cube finish keeps the physics of a conservative body sweep
    # unchanged. Earlier default keep masks accidentally skipped the existing
    # common roof, even though no AIR was filled. Only an explicit finishing
    # revision may opt out of those fill/retirement masks for exact match ops.
    modes=("new","owned","retire","air") if finish_inside_geometry_keepouts else ()
    for b in frames["bays"]:
        cx=b["bed"][0]
        p.protect((cx-15,-444,-266,cx+15,-362,-214),"wet_machinery_LCL_and_body_clear_core",modes)
        p.protect((cx-15,-445,-212,cx+15,-310,-54),"complete_long_carrier_body_sweep",modes)
        p.protect((cx-15,-412,-51,cx+15,96,-21),"original_31x31_launch_core",modes)
    for q,(target,purpose) in sorted(changes.items()):
        before=w.block(q);p.match((*q,*q),before,target,"r44/tv_hangar/"+purpose);inv.match((*q,*q),target,before,"inverse/r44/tv_hangar/"+purpose)
    report={"world":str(world),"cells":len(changes),"components":components,"held_exact_materials":dict(held),
        "original_strip_light_seats":sorted(old_light_seats),
        "same_shape_finish_inside_fill_keepouts":finish_inside_geometry_keepouts,
        "whole_native_lift_negative":[[89,-446,-56],[99,-364,-48]],
        "preserved_devices_full_nbt":[{"position":q,"snbt":t.snbt()} for q,t in sorted(tags.items())],"preserved_entities_full_nbt":retained_entities,
        "physics":"Every mutation preserves exact full native cube collision shape; zero added air/fluid fills; original glass/doors/rail/equipment/crew floors remain",
        "whole_TV_pending":["root original mechanical meshes and true materials/normals/light", "variant shoulder-contact geometry from full parts bounds",
            "rear foreground rail/capsule interlock", "native wet fill/drain/clamp release/plug/transfer/slope/launch/return workflows", "real whole-cage images and user approval"],
        "status":"STATIC_COMPONENT_CANDIDATE only; shell finishing does not pass whole-TV reconstruction"}
    p.meta.update(report);p.save_plan("whole_three_line_tv_skin");inv.meta.update({"forward":"whole_three_line_tv_skin","cells":len(changes),"full_original_nbt":report["preserved_devices_full_nbt"]});inv.save_plan("inverse_whole_three_line_tv_skin")
    report["ops_sha256"]=hashlib.sha256((out/"whole_three_line_tv_skin/ops.json.gz").read_bytes()).hexdigest()
    (out/"contract.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print("Whole TV static skin:",len(changes),"exact cube cells;",len(tags),"complete device tags retained; no world mutation",flush=True)
    return p


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--world",type=Path,default=WORLD);ap.add_argument("--out",type=Path,default=OUT);a=ap.parse_args();plan(a.world,a.out)
