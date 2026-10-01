"""Complete fixed shoulder-work decks and their attached inward guards.

The old side catwalk declaration owns offsets17..19 at floorY-395. Current
actual offsets18/19 already provide two clear lanes; the offset17 guard row
has long AIR stretches beneath it. Restore its real slab lip/load brackets,
not another free-standing railing. This CLI only writes reviewable inverses.
"""
from pathlib import Path
from collections import Counter
import copy,hashlib,json
import regional_voxels as v
from query_blocks import AIR,iter_block_entities
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/"run/saves/SEELE_FIELD_R44_REVIEW";OUT=ROOT/"artifacts/rebuild_r44/facility_transit_r44/working_edges_v1"
STRUCT="projectseele:nerv_structural_panel";FLOOR="projectseele:nerv_floor_panel"


def plan(world=WORLD,out=OUT):
    world,out=Path(world),Path(out);out.mkdir(parents=True,exist_ok=True)
    if list(out.glob("complete_shoulder_deck_lips/applied_*/receipt.json")):raise RuntimeError("Applied stage immutable")
    w=MeasuredWorld(world);lo,hi=(-43,-398,-289),(107,-390,-212);w.box(lo,hi);w.load();g=Geometry(w)
    tags={q:copy.deepcopy(t) for q,t in iter_block_entities(world,v.DIM,lo,hi)}
    p,inv=v.Painter(),v.Painter();v.WORLD,v.OUT=world,out;changes={};components=[];walks=[]
    def put(q,after,purpose):
        before=w.block(q)
        if before is None:raise RuntimeError(("Unmeasured declared side deck",q))
        if q in tags or before.startswith(("mtr:","movingelevators:")):raise RuntimeError(("Whole native device negative",q))
        if before==after:return
        if before not in AIR:raise RuntimeError(("Do not repaint/remove an existing functional slab/member",q,before,purpose))
        if g.boxes(after)!=[[0.,0.,0.,1.,1.,1.]]:raise RuntimeError(("No full native structural cube",after))
        changes[q]=(after,purpose)
    for cx in (-12,30,72):
        for side in (-1,1):
            x=cx+side*17;missing=[];fixed=[]
            for z in range(-264,-215):
                floor=(x,-395,z);guard=(x,-394,z);state=w.block(guard)
                if w.block(floor) in AIR:
                    put(floor,FLOOR,"real_declared_guard_bearing_lip");missing.append(floor)
                else:fixed.append({"position":floor,"state":w.block(floor)})
                # Every actual public lane retains the measured full footprint
                # and the two metres above it. No inferred centreline repair.
                for offset in (18,19):
                    q=(cx+side*offset,-394,z)
                    if g.standing(q)["status"]!="STATIC_STANDING":raise RuntimeError(("Declared two-width lane obstructed",q,g.standing(q)))
            # Sparse 3m cantilever underside brackets join the actual side wall
            # rather than descending through LCL or a moving carrier trench.
            for z in range(-260,-217,10):
                for offset in (17,18,19):
                    q=(cx+side*offset,-396,z)
                    if w.block(q) in AIR:put(q,STRUCT,"cantilever_to_actual_wall")
                wall=(cx+side*20,-396,z)
                if g.boxes(w.block(wall))!=[[0.,0.,0.,1.,1.,1.]]:raise RuntimeError(("No actual wall to carry side deck",wall,w.block(wall)))
            components.append({"cage_x":cx,"side":side,"declared_floor_y":-395,"clear_feet_y":-394,"actual_clear_lanes":[cx+side*18,cx+side*19],
                "guard_x":x,"guard_state_retained":"Complete actual rail row/ports preserved", "missing_guard_bearing":missing,"retained_existing_floor":fixed,
                "equipment_space":"Private mechanical/vessel interior remains inward of offsets17; no public floor through pit"})
            for offset in (18,19):
                for z in (-264,-216):
                    target=(cx+side*offset,-394,z);path=g.flat_path((-29,-394,-285),target,radius=180)
                    if path is None:raise RuntimeError(("Whole fixed lane not connected to original actual lift landing",target))
                    nodes=[[x+.5,y,zz+.5] for x,y,zz in path];ident=f"r44/TV_worklayer/{cx}/{side}/{offset}/{z}"
                    walks.extend(({"id":ident,"path":nodes},{"id":ident+"/return","path":nodes[::-1]}))
    for q,(after,purpose) in sorted(changes.items()):
        before=w.block(q);p.match((*q,*q),before,after,"r44/working_edges/"+purpose);inv.match((*q,*q),after,before,"inverse/r44/working_edges/"+purpose)
    report={"world":str(world),"cells":len(changes),"components":components,"original_complete_nbt":[{"pos":q,"snbt":t.snbt()} for q,t in sorted(tags.items())],
        "original_authority":"EvaHangarBuilder buildRearBoardingGantry / buildShoulderCatwalk offsets EXIT_LANE_HALF_WIDTH+1..SIDE_CATWALK_X =17..19; actual two-width remaining paths measured",
        "negative":"All 31x31 machinery clear cores, fluid/bridge/deployed capsule, actual railing and every currently complete public lane remain",
        "native_cases":walks,"validation":{k:"UNVERIFIED" for k in ("all_six_native_work_decks","guard_visual_attachment","capsule_and_crane_workflow","TV_whole_visual","reload")}}
    p.meta.update(report);p.save_plan("complete_shoulder_deck_lips");inv.meta.update({"forward":"complete_shoulder_deck_lips","cells":len(changes)});inv.save_plan("inverse_complete_shoulder_deck_lips")
    report["sha256"]=hashlib.sha256((out/"complete_shoulder_deck_lips/ops.json.gz").read_bytes()).hexdigest();(out/"contract.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    (out/"native_cases.json").write_text(json.dumps(walks,ensure_ascii=False,indent=2),encoding="utf8")
    print("Six complete real shoulder-deck edges:",len(changes),"exact cells; rail/clear lanes retained",flush=True);return p


if __name__=="__main__":plan()
