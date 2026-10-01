"""One measured hangar frame and private reference ledger; no world writes.

Python reproduces the pinned canonical kinematic equations to conservatively
reserve the complete dock-to-socket sweep. Runtime canonical transforms remain
authoritative; this artifact is not a native operating or visual acceptance.
"""
from __future__ import annotations
import copy
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation, Slerp
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
from verify_main_r20 import entities

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/"run/saves/SEELE_FIELD_R44_REVIEW"
OUT=ROOT/"artifacts/rebuild_r44/facility_transit_r44/hangar_tv_calibration_v2"
ATTACHMENTS=Path("C:/Users/liboy/.codex/codex-remote-attachments/01a06f62-c70f-7b41-904c-d33fc1e86924/385A93C8-DF4F-4CB3-A80D-DE69A174A312")


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def unit(v):return np.asarray(v,dtype=float)/np.linalg.norm(v)
def orientation(outward):
    z=unit(outward);y=unit(np.array([0.,1.,0.])-z*z[1]);x=unit(np.cross(y,z))
    return Rotation.from_matrix(np.stack([x,y,z],axis=1))
def bounds(p,r,centre=(0,0,5),half=(1.2,1.2,5.15)):
    points=np.array([np.array(centre)+np.array(sign)*half for sign in itertools.product((-1,1),repeat=3)])
    pts=r.apply(points)+p
    return np.stack([pts.min(axis=0),pts.max(axis=0)])
def frame(origin,rotation):return {"origin":list(map(float,origin)),"quaternion_xyzw":list(map(float,rotation.as_quat()))}


def main(world=WORLD,out=OUT):
    world,out=Path(world),Path(out);out.mkdir(parents=True,exist_ok=True)
    effective=ROOT/"run/projectseele-local-maps/eva_dorsal_r30.json"
    if not effective.is_file():effective=ROOT/"src/main/resources/assets/projectseele/motion/eva_dorsal_r13.json"
    profiles=json.loads(effective.read_text(encoding="utf8"))["profiles"]
    stored=entities(world)
    original={str(e.get("id")):copy.deepcopy(e) for e in stored.values() if str(e.get("id")) in {"projectseele:eva_unit00","projectseele:eva_unit01","projectseele:eva_unit02"}}
    refs=[]
    for n in range(1,5):
        path=ATTACHMENTS/f"{n}-照片-{n}.jpg"
        refs.append({"id":f"user_tv_{n}","file":str(path),"sha256":sha(path),"viewed":True,
            "evidence":"User supplied original frame; no invented episode/timecode; research only, not a shipped asset",
            "features":["cervical socket exposed; two shoulder seats with actuators and hoses; side gantries",
                        "entry plug aligns along one raked axis into the dorsal neck mouth",
                        "circular driven clamp, linked arms and service hoses grip the capsule",
                        "cervical armour closes after insertion; shoulder seats remain external"][n-1]})
    for name,features in (("tv_cage","Blue-grey deep vessel walls, LCL at upper torso, paired side machinery, front mechanical beam and red/black hazard"),
                          ("tv_pallet","Green tall wall panels, diagonal braces, vertical guide slots, overhead hanging gear, upright rear restraint pallets and hoses")):
        path=ROOT/f"artifacts/tv_facilities_r16/references/{name}.png"
        refs.append({"id":name,"file":str(path),"sha256":sha(path),"viewed":True,"features":features,
            "evidence":"Cached frame only; original episode/edition metadata not verified. Not sufficient to claim exact TV dimensions."})
    for name in ("reference_overview","reference_mechanisms"):
        path=ROOT/f"artifacts/world_rebuild_r20/references/{name}.jpg"
        refs.append({"id":name,"file":str(path),"sha256":sha(path),"viewed":True,
            "evidence":"SMALL WORLDS miniature: BV1fsRaBoE6i / b23.tv/3ipjtYS; secondary mechanical routing, never TV main-cage authority",
            "retained_user_constraint":"Existing three lines, long rising transfer direction; no exact-TV claim"})
    bays=[]
    for variant,cx in enumerate((-12,30,72)):
        model=f"eva_unit0{variant}";e=original["projectseele:"+model]
        feet=np.array(list(map(float,e["Pos"])));yaw=float(e["Rotation"][0]);rear=np.array([math.sin(math.radians(yaw)),0,-math.cos(math.radians(yaw))])
        require_pos=np.array([cx+.5,-442.,-239.5])
        if np.linalg.norm(feet-require_pos)>.05 or abs(yaw-180)>.05:raise RuntimeError(("Original bay actor moved; do not derive static works from deployed cargo",model,feet,yaw))
        profile=profiles[model];marker=np.array(profile["centre"])*5/16
        socket_p=feet+rear*marker[2]+np.cross(rear,[0,1,0])*marker[0]+[0,marker[1],0]
        socket_r=orientation(rear*profile["outward"][2]+[0,profile["outward"][1],0])
        hatch=np.array([cx+.5,-392.8,-223.5]);dock_r=orientation(rear*.9659258262890683+[0,.25881904510252074,0])
        dock_p=hatch-dock_r.apply([0,.8,5.8]);approach_p=socket_p+socket_r.apply([0,0,3])
        rotate=Slerp([0,1],Rotation.concatenate([dock_r,socket_r]))
        samples=[];envelope=None
        for linear in np.linspace(0,1,121):
            if linear<=.45:
                t=linear/.45;t=t*t*(3-2*t);p=dock_p*(1-t)+approach_p*t;r=rotate(t)
            elif linear<=.75:
                t=(linear-.45)/.3;t=t*t*(3-2*t);p=approach_p*(1-t)+socket_p*t;r=socket_r
            else:
                t=(linear-.75)/.25;t=t*t*(3-2*t);p=socket_p+socket_r.apply([0,0,-11*t]);r=socket_r*Rotation.from_rotvec([0,0,math.tau*t])
            b=bounds(p,r)
            envelope=b if envelope is None else np.stack([np.minimum(envelope[0],b[0]),np.maximum(envelope[1],b[1])])
            samples.append({"progress":float(linear),"frame":frame(p,r),"body_aabb":b.tolist(),"crane_eye":(p+r.apply([0,0,9.7])).tolist()})
        envelope[0]-=.25;envelope[1]+=.25
        bay={"variant":variant,"eva_uuid":list(map(int,e["UUID"])),"eva_feet":feet.tolist(),"yaw":yaw,
            "bed":[cx,-443,-240],"static_shell":[[cx-20,-443,-267],[cx+20,-355,-213]],
            "legacy_shell_top":-363,"actual_roof_underside":-355,"actual_roof_bearing_layers":[-354,-353],
            "existing_scale":{"render_scale":5,"normal_height_contract":60,"mesh_bound":"UNVERIFIED until current complete parts export; no use of obsolete 48m docs as geometry authority"},
            "front":"-Z; LCL/observation face", "rear":"+Z; plug gantry and transfer gate",
            "socket":frame(socket_p,socket_r),"hatch_dock_world":hatch.tolist(),"capsule_dock":frame(dock_p,dock_r),
            "crane_rail_y":-373,"crane_axis_x":cx+.5,"crane_rail_centres_x":[cx-3.5,cx+4.5],
            "crane_rail_z_extent":[-266,-215],"retired_old_runway":{"base_y":-363,"top_y":-361,"height_mismatch":10},
            "crane_fixed_support":{"beam_block_y":[-376,-374],"outboard_hanger_x":[cx-7.5,cx+8.5],"support_z":[-264,-246,-228],"roof_top":-355},
            "crew_deck_floor":-395,"crew_feet":-394,
            "lcl_nominal_top":-399,"lcl_scope":"Dynamic fluid surface and all fill/drain phases retained; no permanent floor through the vessel",
            "capsule_sweep_negative":envelope.tolist(),"capsule_route_samples":samples,
            "carrier_width_contract":29,"carrier_sweep_negative":[[cx-15,-444,-268],[cx+15,-350,-16]],
            "transfer":{"from":[cx,-443,-212],"to":[cx,-411,-52],"launch":[cx,-411,-36],"source":"User retained SMALL WORLDS routing, secondary to TV vessel form"},
            "TV_components":["deep opaque blue-grey wet-vessel faces","paired shoulder contact mechanisms derived from real body parts",
                "independent rear neck aperture and raked plug route","supported lateral crew galleries and retractable rear opening",
                "connected overhead trolley/reeved cables/chuck","upright back restraint pallet with real foot plinth","green walls/diagonal braces/vertical indexed guide slots","closed contiguous transfer/launch shell"],
            "never_static_fill":["LCL vessel interior","capsule full pose sweep","all 31x31 launch/carrier clear cores","carriage/bridge/pressure-door sweep"],
            "front_beam_distinction":"TV front -Z mechanical beam differs from camera-front rear +Z guardrail. Rear foreground bar must retract/avoid capsule, not become a permanent neck-mouth cover."}
        bays.append(bay)
    lo,hi=(-45,-470,-294),(113,-348,-16)
    w=MeasuredWorld(world);w.box(lo,hi);w.load()
    tags=[{"position":p,"snbt":copy.deepcopy(t).snbt()} for p,t in iter_block_entities(world,"projectseele:geofront",lo,hi)]
    surfaces=[]
    for bay in bays:
        cx=bay["bed"][0]
        for name,positions in (("front",((x,y,-267) for x in range(cx-20,cx+21) for y in range(-442,-355))),
                               ("rear",((x,y,-213) for x in range(cx-20,cx+21) for y in range(-442,-355))),
                               ("sides",((x,y,z) for x in (cx-20,cx+20) for y in range(-442,-355) for z in range(-266,-213))),
                               ("actual_roof",((x,-355,z) for x in range(cx-20,cx+21) for z in range(-267,-212)))):
            from collections import Counter
            counts=Counter(w.block(q) for q in positions)
            if None in counts:raise RuntimeError(("Unmeasured declared whole cage face",cx,name))
            surfaces.append({"variant":bay["variant"],"surface":name,"exact_state_counts":dict(counts)})
    data={"world":str(world),"refs":refs,"bays":bays,"original_complete_block_nbt":tags,"measured_faces":surfaces,
        "authorities":{"world_sources":"facility agent", "mechanical_meshes":"root: PlugGantryRenderer/NervCarrierPlatformRenderer/NervMovingCarrierRenderer/TvFacilityMeshes and dedicated original resources",
            "body_socket_animation":"combat owner; canonical transforms remain sole axis authority"},
        "status":"Measured semantic/interface contract only. Whole-TV map revision, model complete parts, native workflow, actual images and user approval UNVERIFIED."}
    (out/"semantic_frame.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf8")
    (out/"reference_ledger.json").write_text(json.dumps(refs,ensure_ascii=False,indent=2),encoding="utf8")
    print("Three original bay frames;",len(tags),"full NBT tags;",len(surfaces),"whole measured faces; no world changes",flush=True)
    return data


if __name__=="__main__":main()
