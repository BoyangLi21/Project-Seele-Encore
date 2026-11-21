"""Resolve conservative train-box candidates with pinned repeated source cubes."""
from pathlib import Path
from collections import defaultdict
import argparse, json, hashlib, zipfile
import numpy as np
from scipy.spatial.transform import Rotation


def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument("--candidate-directory",type=Path,required=True);ap.add_argument("--mtr",type=Path,required=True);ap.add_argument("--clearance-patch",type=Path);a=ap.parse_args();base=a.candidate_directory.resolve()
    overlay={} if a.clearance_patch is None else {tuple(r["pos"]):r["after"] for r in json.loads(a.clearance_patch.read_text("utf8"))["cells"]}
    frames=json.loads((base/"NATIVE_WHOLE_CAR_ALL_POSES.json").read_text("utf8"))["frames"];byframe={(f["vehicle_id"],f["progress"]):f for f in frames}
    contacts=json.loads((base/"TRAIN_CONSERVATIVE_CONTACT_FRAMES.json").read_text("utf8"));groups=defaultdict(set)
    for c in contacts:groups[c["vehicle"],c["progress"],c["car"],c["part"]].add(tuple(c["pos"]))
    sources=[];parts=[];bogies=[]
    with zipfile.ZipFile(a.mtr) as z:
        def load(member):
            raw=z.read(member);sources.append(dict(member=member,sha256=hashlib.sha256(raw).hexdigest()));return json.loads(raw)
        model=load("assets/mtr/models/vehicle/eidan_9000.bbmodel");elements={e["uuid"]:e for e in model["elements"]};named={}
        def ids(n):
            if isinstance(n,str):return [n]
            out=[]
            for child in n.get("children",[]):out.extend(ids(child))
            return out
        for n in model["outliner"]:
            if isinstance(n,dict):assert not any(n.get("rotation",[0,0,0]));named[n["name"]]=ids(n)
        definition=load("assets/mtr/properties/definition/eidan_9000_mini.json");defs={d["name"]:d for d in definition["positionDefinitions"]}
        def cube(e,offset=(0,0,0),flip=False):
            lo,hi=np.array(e["from"])/16,np.array(e["to"])/16;center=(lo+hi)/2;half=(hi-lo)/2;origin=np.array(e.get("origin",[0,0,0]))/16;rotation=Rotation.from_euler("xyz",e.get("rotation",[0,0,0]),degrees=True).as_matrix().T
            center=(center-origin)@rotation+origin;center+=np.asarray(offset)/16
            if flip:
                mirror=np.diag([-1,1,-1]);center=center@mirror;rotation=rotation@mirror
            center += [0,1,0]
            return center,half,rotation,e.get("name",e["uuid"])
        for suffix in ("common","head_1","head_2","end_1","end_2"):
            prop=load("assets/mtr/properties/vehicle/eidan_9000_"+suffix+".json")
            for part in prop["parts"]:
                for name in part["names"]:
                    for key in part["positionDefinitions"]:
                        d=defs.get(key,{"positions":[{"x":0,"y":0,"z":0}],"positionsFlipped":[{"x":0,"y":0,"z":0}]})
                        for flip,kind in ((False,"positions"),(True,"positionsFlipped")):
                            for position in d[kind]:
                                for uuid in named.get(name,[]):parts.append(cube(elements[uuid],[position[k] for k in ("x","y","z")],flip))
        b=load("assets/mtr/models/vehicle/bogie_1.bbmodel")
        for e in b["elements"]:
            bogies.append(cube(e));bogies.append(cube(e,flip=True))
    def transform(car):
        pairs=np.asarray(car["native_position_pairs"]);b0=pairs[0].mean(0);b1=pairs[-1].mean(0);axis=b1-b0;axis/=np.linalg.norm(axis);side=np.cross([0,1,0],axis);side/=np.linalg.norm(side);R=np.asarray([side,np.cross(axis,side),axis]);return pairs,b0-axis*car["bogie1"],R
    actual=[];examined=0
    for (vehicle,progress,ci,label),positions in groups.items():
        car=byframe[vehicle,progress]["cars"][ci];pairs,origin,R=transform(car)
        transforms=[(origin,R,parts)]
        if label=="bogie":
            transforms=[]
            for pair in pairs:
                fw=pair[1]-pair[0];fw/=np.linalg.norm(fw);sd=np.cross([0,1,0],fw);sd/=np.linalg.norm(sd);transforms.append((pair.mean(0),np.asarray([sd,np.cross(fw,sd),fw]),bogies))
        q=np.asarray(list(positions));units=np.eye(3)
        for origin,R,source in transforms:
            centers=np.asarray([p[0] for p in source])@R+origin;halves=np.asarray([p[1] for p in source]);rots=np.asarray([p[2]@R for p in source]);extent=np.einsum("nij,ni->nj",np.abs(rots),halves);low=centers-extent;high=centers+extent
            for cell in q:
                state=overlay.get(tuple(cell));cellhalf=np.array([.5,.5,.5]);cellcenter=cell+.5
                if state=="minecraft:air":continue
                if state is not None:
                    assert state=="minecraft:smooth_stone_slab[type=bottom,waterlogged=false]";cellhalf[1]=.25;cellcenter[1]-=.25
                choice=np.flatnonzero(np.all(high>cellcenter-cellhalf+1e-6,1)&np.all(low<cellcenter+cellhalf-1e-6,1))
                for j in choice:
                    axes=np.concatenate((units,rots[j],np.asarray([np.cross(u,v) for u in units for v in rots[j]])));delta=cellcenter-centers[j];hit=True
                    for axis in axes:
                        if axis@axis<1e-12:continue
                        if abs(delta@axis)>=np.abs(rots[j]@axis)@halves[j]+np.abs(axis)@cellhalf-1e-6:hit=False;break
                    examined+=1
                    if hit:actual.append(dict(part=label,pos=cell.tolist(),source_cube=source[j][3],vehicle=vehicle,progress=progress,car=ci));break
    result=dict(schema="projectseele.direct-hq-source-cube-contact-r53.v1",world_written=False,
                candidate_sha256=hashlib.sha256((base/"CANDIDATE.json").read_bytes()).hexdigest(),conservative_candidate_frames=len(contacts),unique_frame_car_part_groups=len(groups),
                actual_repeated_body_source_cubes=len(parts),actual_bogie_source_cubes=len(bogies),source_cube_OBB_pairs_tested=examined,actual_source_cube_contacts=len(actual),contacts=actual[:100],sources=sources,
                every_common_head_end_property_and_normal_flipped_position_definition_included=True,
                limits=["Checks all pinned source cubes and over-approximates body type/condition combinations. Installed APG dynamic shapes and actual riding remain required."])
    suffix="_AFTER_FINITE_PATCH" if a.clearance_patch else ""
    if a.clearance_patch:result["finite_patch_sha256"]=hashlib.sha256(a.clearance_patch.read_bytes()).hexdigest()
    (base/("ACTUAL_SOURCE_CUBE_CONTACT_REFINEMENT"+suffix+".json")).write_text(json.dumps(result,indent=2)+"\n","utf8")
    (base/("ACTUAL_SOURCE_CUBE_CONTACT_FRAMES"+suffix+".json")).write_text(json.dumps(actual)+"\n","utf8")
    print(json.dumps({k:v for k,v in result.items() if k in ("conservative_candidate_frames","unique_frame_car_part_groups","actual_repeated_body_source_cubes","actual_bogie_source_cubes","source_cube_OBB_pairs_tested","actual_source_cube_contacts")}),flush=True)


if __name__=="__main__":main()
