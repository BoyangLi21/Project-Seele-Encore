"""Actual roof-supported runways and complete TV working-layer interfaces.

Plans new fixed structural members only in the explicitly authorized hangar
programme. Air is not a room authority: roof/rail/support coordinates originate
in the measured R20 programme and the agreed R44 wheel/roof frame. No apply CLI.
"""
from pathlib import Path
from collections import Counter
import copy,hashlib,json
import regional_voxels as v
from query_blocks import AIR,iter_block_entities
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
from tv_crane_girder_design_r44 import running_state as crane_running_state_r44

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/"run/saves/SEELE_FIELD_R44_REVIEW";OUT=ROOT/"artifacts/rebuild_r44/facility_transit_r44/hangar_structure_v3"
STRUCT="projectseele:nerv_structural_panel";EDGE="projectseele:nerv_machine_edge";LIGHT="projectseele:nerv_strip_light"


def plan(world=WORLD,out=OUT):
    world,out=Path(world),Path(out);out.mkdir(parents=True,exist_ok=True)
    if list(out.glob("roof_supported_runways/applied_*/receipt.json")):raise RuntimeError("Applied stage immutable")
    w=MeasuredWorld(world);lo,hi=(-35,-399,-273),(96,-352,-213);w.box(lo,hi);w.load();g=Geometry(w)
    tags={p:copy.deepcopy(t) for p,t in iter_block_entities(world,v.DIM,lo,hi)}
    frames=json.loads((ROOT/"artifacts/rebuild_r44/facility_transit_r44/hangar_tv_calibration_v2/semantic_frame.json").read_text(encoding="utf8"))
    changes={};retained=[];components=[];old_other=Counter();old_owned=[]
    def put(q,after,purpose):
        before=w.block(q)
        if before is None:raise RuntimeError(("Unmeasured explicit member",q))
        if q in tags:raise RuntimeError(("Complete device negative",q))
        if before==after:return
        if before.partition("[")[0] not in AIR|{STRUCT,EDGE,LIGHT,"projectseele:nerv_machine_panel","projectseele:nerv_shaft_panel","minecraft:gray_concrete","minecraft:black_concrete"}:
            raise RuntimeError(("Other component in proposed support",q,before,purpose))
        if after not in AIR and g.boxes(after)!=[[0.,0.,0.,1.,1.,1.]] and not (
                after.startswith('projectseele:nerv_crane_girder_r44[') and g.boxes(after)):
            raise RuntimeError(("Unknown structural collision",after))
        if q in changes and changes[q][0]!=after:raise RuntimeError(("Conflicting complete support",q))
        changes[q]=(after,purpose)
    for b in frames["bays"]:
        cx=b["bed"][0];rail=[];brackets=[];hangers=[];bearing=[]
        # R20 old runway owner is EDGE, not every block inside its old prism.
        # Actual current glass/structural/lights in that prism belong elsewhere.
        for x in (cx-4,cx+4):
            for y in [*range(-363,-360),*range(-372,-369)]:
                for z in (range(-270,-214) if -372<=y<=-370 else range(-271,-213)):
                    q=(x,y,z);before=w.block(q)
                    if before==EDGE:put(q,"minecraft:air","retire_whole_old_high_or_r26_shifted_runway_owner");old_owned.append(q)
                    elif before.partition("[")[0] not in AIR:old_other[before]+=1
        for side in (-1,1):
            x=cx+side*4
            for z in range(-266,-215):
                for y in range(-376,-373):
                    q=(x,y,z);put(q,crane_running_state_r44(y,z),"complete_native_profile_running_beam_top_minus373");rail.append(q)
            for z in (-264,-246,-228):
                # Outboard drop and under-rail bracket, never an obstruction
                # standing above the wheel contact on the running rail itself.
                for x in range(min(cx+side*4,cx+side*8),max(cx+side*4,cx+side*8)+1):
                    q=(x,-377,z);put(q,STRUCT,"under_rail_load_bracket");brackets.append(q)
                x=cx+side*8
                for y in range(-377,-355):
                    q=(x,y,z)
                    if w.block(q)==LIGHT:
                        choices=[(x+side*dx,y,z+dz) for dz in (0,-1,1,-2,2) for dx in (1,2,3,4)]
                        dest=next((a for a in choices if w.block(a) in AIR and a not in changes),None)
                        if dest is None:raise RuntimeError(("Complete light relocation has no measured clear adjacent seat",q))
                        put(dest,LIGHT,"relocate_complete_roof_light_beside_hanger")
                    put(q,STRUCT,"outboard_roof_drop");hangers.append(q)
                # Two measured full-cube roof layers are genuine load paths.
                for y in (-355,-354):
                    q=(x,y,z);before=w.block(q)
                    if g.boxes(before)!=[[0.,0.,0.,1.,1.,1.]]:raise RuntimeError(("No actual roof bearing above hanger",q,before))
                    bearing.append({"pos":q,"state":before})
        for q in rail+brackets+hangers:
            # All body work is below -382 under the retained normal-height
            # contract. Capsule full rotation/translation gets its own exact
            # negative, with no guessed neck pitch.
            box=b["capsule_sweep_negative"]
            if all(q[i]+1>box[0][i] and q[i]<box[1][i] for i in range(3)):raise RuntimeError(("Fixed support enters capsule sweep",q,b["variant"]))
            if q[1]<-377:raise RuntimeError(("Member below agreed overhead zone",q))
        # Every actual existing crew lane and high rear gallery cell is kept.
        for x in range(cx-20,cx+21):
            for z in range(-271,-212):
                for fy in (-394,-367):
                    if g.standing((x,fy,z))["status"]=="STATIC_STANDING":
                        for y in (fy-1,fy,fy+1):
                            q=(x,y,z)
                            if q in changes:raise RuntimeError(("Support/retirement would change actual public floor/headroom",q))
        components.append({"variant":b["variant"],"running_surface":-373,"rail_centres_x":[cx-3.5,cx+4.5],"rail_z":[-266,-215],
            "roof_underside":-355,"wheel_path":"Root trolley wheel bottoms localY0, wheel axle X and roll Z", "rail_cells":rail,"brackets":brackets,"hangers":hangers,"roof_bearing":bearing,
            "cargo_clearance":"Existing normal height contract60 has top-382; members start-377, ≥5m above. Final full-model parts bounds/native movement still required."})
    p,inv=v.Painter(),v.Painter();v.WORLD,v.OUT=world,out
    for q,(after,purpose) in sorted(changes.items()):
        before=w.block(q);p.match((*q,*q),before,after,"r44/hangar_structure/"+purpose);inv.match((*q,*q),after,before,"inverse/r44/hangar_structure/"+purpose)
    report={"world":str(world),"cells":len(changes),"components":components,"retired_matching_old_owner_cells":old_owned,"retained_other_old_prism_materials":dict(old_other),
        "original_full_nbt":[{"pos":q,"snbt":t.snbt()} for q,t in sorted(tags.items())],
        "validation":{"actual_existing_public_floor_and_two_metre_headroom":"PRESERVED exact saved shapes/states", "capsule_121pose_negative":"STATIC_NO_INTERSECTION", "root_full_mesh_bounds":"UNVERIFIED", "moving_wheel_contact":"UNVERIFIED", "wholeTV_and_user_art":"UNVERIFIED"}}
    p.meta.update(report);p.save_plan("roof_supported_runways");inv.meta.update({"forward":"roof_supported_runways","cells":len(changes),"original_full_nbt":report["original_full_nbt"]});inv.save_plan("inverse_roof_supported_runways")
    report["sha256"]=hashlib.sha256((out/"roof_supported_runways/ops.json.gz").read_bytes()).hexdigest();(out/"contract.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print("Three actual roof-supported runways:",len(changes),"exact cells, old matching owner",len(old_owned),"full NBT retained",len(tags),flush=True)
    return p


if __name__=="__main__":plan()
