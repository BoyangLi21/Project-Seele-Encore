"""Read-only pinned whole-car/bogie source checks against the exact ghost tube."""
from pathlib import Path
from collections import defaultdict, Counter
import argparse, json, hashlib, zipfile, math
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from query_blocks import iter_selected_sections, AIR


def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument("--candidate-directory",type=Path,required=True);ap.add_argument("--world",type=Path,required=True);ap.add_argument("--mtr",type=Path,required=True);a=ap.parse_args();base=a.candidate_directory.resolve()
    read=lambda n:json.loads((base/n).read_text("utf8"));geo=read("NATIVE_GEOMETRY.json");ss={g["id"]:g for g in geo};candidate=read("CANDIDATE.json");plans=read("PROPOSAL.json");patch=read("member_patch/PATCH_MANIFEST.json")
    identity=read("NATIVE_BINARY_VERIFICATION.json");assert identity["vehicles_exact_original_identity_and_saved_state"]==40
    mask=np.load(base/"COMPLETE_CIVIL_CANDIDATE/POSITIVE_MASK_EXACT_STATES.npz");names=list(mask["states"]);target={tuple(q):str(names[i]) for q,i in zip(mask["positions"].tolist(),mask["after"])}
    bounds={};sources=[]
    with zipfile.ZipFile(a.mtr) as z:
        for name in ("eidan_9000","bogie_1","bogie_2","bogie_3"):
            member="assets/mtr/models/vehicle/"+name+".bbmodel";raw=z.read(member);model=json.loads(raw);points=[]
            for e in model["elements"]:
                lo,hi=e["from"],e["to"];v=np.array([[x,y,z] for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])]);origin=np.asarray(e.get("origin",[0,0,0]));points.extend(Rotation.from_euler("xyz",e.get("rotation",[0,0,0]),degrees=True).apply(v-origin)+origin)
            v=np.asarray(points)/16+[0,1,0];bounds[name]=np.stack((v.min(0),v.max(0)));sources.append(dict(member=member,sha256=hashlib.sha256(raw).hexdigest()))
    # Pinned operating car length includes source bogie and coupling allowances.
    body=bounds["eidan_9000"].copy();body[:,2]+=[-68/16,68/16]
    frames=read("NATIVE_WHOLE_CAR_ALL_POSES.json")["frames"]
    new_cloud=np.concatenate([np.asarray(g["points"]) for g in geo]);tree=cKDTree(new_cloud)
    boxes=[];missing=set();wire_metrics=dict(body_max_horizontal=0,body_min_vertical=1e9,bogie_max_horizontal=0,bogie_min_vertical=1e9)
    axes=np.eye(3)
    for f in frames:
        for ci,car in enumerate(f["cars"]):
            pairs=np.asarray(car["native_position_pairs"]);b0=pairs[0].mean(0);b1=pairs[-1].mean(0);forward=b1-b0;forward/=np.linalg.norm(forward);side=np.cross([0,1,0],forward);side/=np.linalg.norm(side);up=np.cross(forward,side);R=np.asarray([side,up,forward]);origin=b0-forward*car["bogie1"]
            if tree.query(origin)[0]>14:continue
            for label,lohi,anchor,rot in [("body",body,origin,R)]+[("bogie",bounds["bogie_1"],pair.mean(0),None) for pair in pairs]:
                if rot is None:
                    pair=next(p for p in pairs if np.linalg.norm(p.mean(0)-anchor)<1e-9);fw=pair[1]-pair[0];fw/=np.linalg.norm(fw);sd=np.cross([0,1,0],fw);sd/=np.linalg.norm(sd);rot=np.asarray([sd,np.cross(fw,sd),fw])
                center=anchor+lohi.mean(0)@rot;half=(lohi[1]-lohi[0])/2
                vertices=center+np.asarray([[x,y,z] for x in (-half[0],half[0]) for y in (-half[1],half[1]) for z in (-half[2],half[2])])@rot
                low=np.floor(vertices.min(0)).astype(int);high=np.floor(vertices.max(0)).astype(int)
                cells=np.asarray([[x,y,z] for x in range(low[0],high[0]+1) for y in range(low[1],high[1]+1) for z in range(low[2],high[2]+1)],np.int32)
                for q in cells.tolist():
                    k=tuple(q)
                    if k not in target:missing.add(k)
                boxes.append((label,center,half,rot,cells,f["vehicle_id"],f["progress"],ci))
    # Only finite cells under actual source boxes are read outside the ghost mask.
    selected=defaultdict(set);groups=defaultdict(list)
    for q in missing:
        x,y,z=q;selected[x//16,z//16].add(y//16);groups[x//16,z//16,y//16].append(q)
    for cx,cz,sy,pal,idx in iter_selected_sections(a.world,"projectseele:geofront",selected):
        for q in groups[cx,cz,sy]:
            x,y,z=q;target[q]=pal[int(idx[((y&15)<<8)|((z&15)<<4)|(x&15)])]
    assert missing.issubset(target)
    full={"projectseele:nerv_wall_panel","projectseele:nerv_floor_panel","projectseele:nerv_structural_panel","minecraft:gravel","minecraft:stone","minecraft:deepslate","minecraft:dirt","minecraft:grass_block","minecraft:black_concrete","minecraft:deepslate_bricks","minecraft:smooth_stone"}
    contacts=[];unknown=Counter();checked=Counter()
    for label,center,half,R,cells,vehicle,progress,ci in boxes:
        solid=[]
        for q in cells.tolist():
            state=target[tuple(q)];name=state.partition("[")[0]
            if name in full:solid.append(q)
            elif name not in AIR and name not in {"minecraft:water","minecraft:light","projectseele:nerv_strip_light"}:unknown[name]+=1
        checked[label]+=1
        if not solid:continue
        q=np.asarray(solid);delta=q+.5-center;hit=np.ones(len(q),bool)
        separating=np.concatenate((axes,R,np.asarray([np.cross(u,v) for u in axes for v in R])))
        for axis in separating:
            if np.dot(axis,axis)<1e-12:continue
            radius=np.abs(R@axis)@half+.5*np.abs(axis).sum()
            hit &= np.abs(delta@axis)<radius-1e-6
        if hit.any():
            for p in q[hit]:contacts.append(dict(part=label,pos=p.tolist(),state=target[tuple(p)],vehicle=vehicle,progress=progress,car=ci))
    unique={(c["part"],tuple(c["pos"]),c["state"]) for c in contacts}
    contact_cells=[dict(part=part,pos=list(q),state=state) for part,q,state in sorted(unique)]
    (base/"TRAIN_CONSERVATIVE_CONTACT_CELLS.json").write_text(json.dumps(contact_cells,indent=2)+"\n","utf8")
    (base/"TRAIN_CONSERVATIVE_CONTACT_FRAMES.json").write_text(json.dumps(contacts)+"\n","utf8")
    report=dict(schema="projectseele.direct-hq-actual-source-train-r53.v1",world_written=False,
                candidate_sha256=hashlib.sha256((base/"CANDIDATE.json").read_bytes()).hexdigest(),
                source_whole_consist_frames=len(frames),source_parts=sources,actual_source_bounds={k:v.tolist() for k,v in bounds.items()},
                four_car_body_and_native_bogie_boxes_checked=dict(checked),sample_step_metres=.5,
                precise_full_cell_OBB_contact_frames=len(contacts),unique_full_cell_contacts=len(unique),contacts=contacts[:100],unknown_partial_shape_candidate_counts=dict(unknown),
                original40_ids_and_all_other_saved_tokens_verified=True,unchanged34_original_head_positions_exact=True,
                native_maximum_grade=max(g["maximum_sampled_grade"] for g in geo),
                limits=["Actual source bounding boxes conservatively include empty body corners; positive contacts need exact parts/native shape review.","This is a read-only native geometry/source screen. Installed motion, riding and appearance remain required."])
    (base/"ACTUAL_SOURCE_TRAIN_CONTACT_SCREEN.json").write_text(json.dumps(report,indent=2)+"\n","utf8")
    print(json.dumps({k:v for k,v in report.items() if k in ("source_whole_consist_frames","four_car_body_and_native_bogie_boxes_checked","precise_full_cell_OBB_contact_frames","unique_full_cell_contacts","unknown_partial_shape_candidate_counts","native_maximum_grade")}),flush=True)


if __name__=="__main__":main()
