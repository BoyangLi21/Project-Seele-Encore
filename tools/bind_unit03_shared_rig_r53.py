"""Bind the privately supplied Unit-03 surface to the existing Unit-01 rig.

Creates a review candidate only. No world, installed pack, or entity is changed.
Input NPZ files retain the OBJ author's X/Y-up/+Z-front coordinates.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import numpy as np
from PIL import Image, ImageDraw
from scipy.interpolate import RBFInterpolator
from scipy.spatial import cKDTree


def read(path):
    return json.loads(path.read_text("utf8"))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf8")


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Use a fresh candidate directory")
    mesh = read(args.reference / "mesh/eva_unit01.mesh.json")
    geo = read(args.reference / "geo/eva_unit01.geo.json")
    bones = {b["name"]: b for b in geo["minecraft:geometry"][0]["bones"]}
    points = {n: np.asarray(b["pivot"], float) for n, b in bones.items()}
    components = read(args.source / "COMPONENTS.json")
    inputs = [np.load(args.source / row["geometry"]) for row in components]
    # The two forearm objects are exact duplicates with different material
    # aliases. Keep the one whose material actually names the arm texture.
    assert all(np.array_equal(inputs[1][key], inputs[2][key]) for key in inputs[1].files)
    selected = [(components[0], inputs[0], 0), (components[2], inputs[2], 1)]

    anchors, goals = [], []
    def anchor(source, target):
        anchors.append(source)
        goals.append(target)
    for side, sign in [("l", 1), ("r", -1)]:
        anchor([sign*.49, .32, -.07], points["foot_"+side])
        anchor([sign*.315, 1.57, -.07], points["shin_"+side]+[0,11.4,0])
        anchor([sign*.18, 2.66, -.04], points["leg_"+side])
        anchor([sign*.45, 3.57, -.09], points["arm_"+side])
        anchor([sign*.54, 2.95, -.13], [sign*23.489652,123.435069,7.737214])
        anchor([sign*.585, 2.242, -.09], points["hand_"+side]+[sign*1.2,2.2,.8])
        anchor([sign*.45, 4.38564682, -.18], [sign*19.7,192,7.9])
        anchor([sign*.50, -.004059, .10], [sign*15.4,0,-4.8])
    anchor([0,3.75,.015], points["neck"])
    anchor([0,4.10,.10], [0,181,-4.6])
    anchor([0,2.72,0], [0,116,0])
    anchor([0,3.25,0], [0,139,0])
    warp = RBFInterpolator(np.array(anchors), np.array(goals),
                           kernel="thin_plate_spline", smoothing=0)
    hand_mesh=read(args.reference/"mesh/eva_unit01_anatomical_hands_r45.mesh.json")
    hand_contract=read(args.reference/"hand_rigs/unit01/hand_rig_contract.json")
    hand_warps={}
    hand_reference={}
    for side in ("l","r"):
        name="hand_"+side
        part=hand_mesh["parts"][name]
        values=np.asarray(part["vertices"]).reshape(-1,8)
        skin=hand_mesh["jointSkins"][name]
        hand_reference[side]=(cKDTree(values[:,:3]+part["pivot"]),skin)

    finger_landmarks={
        "index":[[.623,2.129,-.006],[.626,2.065,-.004],[.595,1.990,.022],[.540,1.912,.065]],
        "middle":[[.590,2.125,-.040],[.601,2.055,-.030],[.568,1.980,-.011],[.490,1.888,.025]],
        "ring":[[.560,2.125,-.090],[.568,2.056,-.100],[.536,1.980,-.060],[.462,1.894,-.017]],
        "little":[[.526,2.125,-.135],[.533,2.060,-.133],[.497,1.990,-.105],[.455,1.938,-.070]],
    }
    for side,sign in [("l",1),("r",-1)]:
        src=[[sign*.585,2.242,-.090]]
        dst=[points["hand_"+side]+[sign*1.2,2.2,.8]]
        for digit,positions in dict(finger_landmarks,thumb=[
                [.560,2.215,-.010],[.543,2.187,.010],[.501,2.112,.055],[.480,2.055,.089]]).items():
            joints=hand_contract["hands"][side]["digits"][digit]["joints"]
            targets=[np.array(j["head_bind"])*[-16,16,16]for j in joints]
            targets.append(np.array(joints[-1]["tip_bind"])*[-16,16,16])
            for position,target in zip(positions,targets):
                src.append(np.array(position)*[sign,1,1])
                dst.append(target)
        raw_hand=inputs[2]["vertices"]
        wrist=raw_hand[(raw_hand[:,0]*sign>0)&(raw_hand[:,1]>=2.2398259)&(raw_hand[:,1]<=2.2441)]
        wrist=np.unique(wrist.round(7),axis=0)
        boundary=warp(wrist)
        src.extend(wrist);dst.extend(boundary)
        hand_warps[side]=RBFInterpolator(np.array(src),np.array(dst),
                                        kernel="thin_plate_spline",smoothing=0)
    reference = {}
    for name, part in mesh["parts"].items():
        if name not in bones:
            continue
        values = np.asarray(part["vertices"]).reshape(-1,8)
        reference[name] = np.unique((values[:,:3]+part["pivot"]).round(5), axis=0)

    def region(group, arm_object, raw):
        lo, hi = np.array(group["bounds"])
        side = "l" if raw[:,0].mean() > 0 else "r"
        if arm_object:
            if lo[1] >= 2.23:
                return ["forearm_"+side]
            return ["hand_"+side]+[n for n in reference
                                   if n.startswith("finger_") and n.endswith("_"+side)]
        if hi[1] < .5:
            return ["foot_"+side]
        if hi[1] < 1.78:
            return ["shin_"+side]
        if hi[1] < 2.73 and lo[1] >= 1.5:
            return ["leg_"+side]
        if lo[1] >= 3.66 and max(abs(lo[0]),abs(hi[0])) < .16:
            return ["head"]
        if hi[1] > 4.2 or lo[1]>3.3 and min(abs(lo[0]),abs(hi[0]))>.275 and lo[2]<-.27:
            return ["pylon_"+side]
        if lo[1]>2.9 and max(abs(lo[0]),abs(hi[0]))>.53:
            return ["arm_"+side]
        if group["id"] == 2113:
            return ["torso_lower","torso_upper","head"]
        return ["torso_upper"] if lo[1]>2.8 else ["torso_lower"]

    assets = args.out / "assets/projectseele"
    texture_dir = assets / "textures/entity"
    texture_dir.mkdir(parents=True)
    atlas = Image.new("RGBA",(1024,512))
    for i, name in enumerate(["e03_201.png","w03_001.png"]):
        source = Image.open(args.source/"unpacked"/name).convert("RGB").convert("RGBA")
        atlas.paste(source,(i*512,0))
    parts, skins, support = {}, {}, {}
    rows, all_geometry, eye_faces = [], [], []
    for document, source, material in selected:
        raw = source["vertices"].copy()
        source_normals = source["normals"].copy()
        xyz = warp(raw)
        faces = source["triangles"]
        uv = source["uv"].copy()
        uv[:,:,0] = (uv[:,:,0]+material)*.5
        uv[:,:,1] = 1-uv[:,:,1]
        epsilon=1e-5
        jacobian=np.stack([(warp(raw+np.eye(3)[axis]*epsilon)-warp(raw-np.eye(3)[axis]*epsilon))/(2*epsilon)
                           for axis in range(3)],axis=2)
        if material == 1:
            # Source fingers are already curled and the palm faces the other
            # way. Calibrate their actual joints before transferring weights;
            # applying straight-bind rotations to that curl doubles the bend.
            for group in document["groups"]:
                if group["bounds"][1][1] > 2.245:
                    continue
                ids=np.flatnonzero(source["components"]==group["id"])
                transform=hand_warps["l" if raw[ids,0].mean()>0 else "r"]
                xyz[ids]=transform(raw[ids])
                jacobian[ids]=np.stack([
                    (transform(raw[ids]+np.eye(3)[axis]*epsilon)-transform(raw[ids]-np.eye(3)[axis]*epsilon))/(2*epsilon)
                    for axis in range(3)],axis=2)
        if np.any(np.linalg.det(jacobian)>=0):
            raise ValueError("The source-to-native handedness must stay consistent; skin folds rejected")
        normal_map=np.linalg.inv(jacobian).transpose(0,2,1)
        normals=np.einsum("fvij,fvj->fvi",normal_map[faces],source_normals)
        normals/=np.linalg.norm(normals,axis=2,keepdims=True)
        weights={}
        for group in document["groups"]:
            ids=np.flatnonzero(source["components"]==group["id"])
            allowed=region(group,material==1,raw[ids])
            if material==1 and group["bounds"][1][1] <= 2.245:
                side="l" if raw[ids,0].mean()>0 else "r"
                tree,skin=hand_reference[side]
                distance,index=tree.query(xyz[ids],k=8)
                strength=1/np.maximum(distance,.05)**3
                strength/=strength.sum(1,keepdims=True)
                for name,values in skin["influences"].items():
                    weights.setdefault(name,np.zeros(len(raw)))[ids]=(np.asarray(values)[index]*strength).sum(1)
            elif material==0 and group["id"]==2113:
                y=raw[ids,1]
                head=np.clip((y-3.70)/.14,0,1)
                upper=np.clip((y-2.85)/.35,0,1)*(1-head)
                for name,value in [("head",head),("torso_upper",upper),("torso_lower",1-head-upper)]:
                    weights.setdefault(name,np.zeros(len(raw)))[ids]=value
            elif len(allowed)==1:
                weights.setdefault(allowed[0],np.zeros(len(raw)))[ids]=1
            else:
                clouds=np.concatenate([reference[n]for n in allowed])
                labels=np.concatenate([np.full(len(reference[n]),i)for i,n in enumerate(allowed)])
                distance,index=cKDTree(clouds).query(xyz[ids],k=8)
                strength=1/np.maximum(distance,.05)**3
                strength/=strength.sum(1,keepdims=True)
                for i,name in enumerate(allowed):
                    weights.setdefault(name,np.zeros(len(raw)))[ids]=(strength*(labels[index]==i)).sum(1)
        if material==1:
            wrist=(raw[:,1]>=2.2398259)&(raw[:,1]<=2.2441)
            xyz[wrist]=warp(raw[wrist])
            for side,sign in [("l",1),("r",-1)]:
                seam=wrist&(raw[:,0]*sign>0)
                for values in weights.values():values[seam]=0
                for name in ("hand_"+side,"forearm_"+side):
                    weights.setdefault(name,np.zeros(len(raw)))[seam]=.5
        palette=list(weights)
        total=np.stack([weights[n]for n in palette],axis=1)
        assert np.allclose(total.sum(1),1)
        face_owner=np.argmax(total[faces].sum(1),axis=1)
        if material==1:
            hand_groups=[g["id"]for g in document["groups"]if g["bounds"][1][1]<=2.245]
            hand_faces=np.isin(source["components"][faces[:,0]],hand_groups)
            for side,sign in [("l",1),("r",-1)]:
                face_owner[hand_faces&(raw[faces].mean(1)[:,0]*sign>0)]=palette.index("hand_"+side)
        for owner_index,name in enumerate(palette):
            mask=face_owner==owner_index
            if not mask.any():
                continue
            f=faces[mask]
            values=np.concatenate([xyz[f]-points[name],uv[mask],normals[mask]],axis=2).reshape(-1,8)
            if name not in parts:
                parts[name]={"pivot":points[name].tolist(),"vertices":[]}
                skins[name]={"influences":{}}
            old_count=len(parts[name]["vertices"])//8
            parts[name]["vertices"].extend(values.round(6).ravel().tolist())
            influences=skins[name]["influences"]
            for bone in set(influences)|set(palette):
                values_for_bone=weights.get(bone,np.zeros(len(raw)))[f].ravel()
                influences.setdefault(bone,[0.]*old_count)
                influences[bone].extend(values_for_bone.round(8).tolist())
            support.setdefault(name,[]).extend(xyz[f].reshape(-1,3).tolist())
        if material==0:
            center=raw[faces].mean(1)
            mask=(center[:,1]>3.85)&(abs(center[:,0])<.13)&(center[:,2]>.13)
            eye_faces.extend(uv[mask].tolist())
        all_geometry.append(dict(source=document["name"],points=xyz.tolist()))
        rows.append(dict(source=document["name"],triangles=len(faces),
                         minimum_jacobian_determinant=float(np.linalg.det(jacobian).min()),
                         maximum_jacobian_determinant=float(np.linalg.det(jacobian).max())))
    for part in skins.values():
        part["influences"]={n:w for n,w in part["influences"].items()if max(w)>0}
    for skin in skins.values():
        inverse={}
        for name in skin["influences"]:
            value=np.eye(4).ravel().tolist()
            for side in ("l","r"):
                value=hand_reference[side][1]["inverseBindColumnMajor"].get(name,value)
            inverse[name]=value
        skin["inverseBindColumnMajor"]=inverse
    eyes=Image.new("L",atlas.size)
    draw=ImageDraw.Draw(eyes)
    for uv in eye_faces:
        draw.polygon([(u*1024,v*512)for u,v in uv],fill=255)
    rgba=np.array(atlas)
    rgb=rgba[:,:,:3].astype(float)
    mask=(np.array(eyes)>0)&(rgb[:,:,0]>120)&(rgb[:,:,1]>110)&(rgb[:,:,2]<rgb[:,:,1]*.7)
    emissive=rgba.copy()
    emissive[:,:,3]=np.where(mask,255,0)
    Image.fromarray(emissive).save(texture_dir/"eva_un01_eyes.png")
    rgba[mask,:3]=[5,5,2]
    Image.fromarray(rgba).save(texture_dir/"eva_un01.png")
    result=dict(format_version=1,stride=8,model_height=192,
                source="User supplied Unit-03; private candidate, existing Unit-01 hierarchy",
                parts=parts,jointSkins=skins,triangleCount=sum(r["triangles"]for r in rows))
    new_geo=copy.deepcopy(geo)
    definition=new_geo["minecraft:geometry"][0]
    definition["description"].update(identifier="geometry.eva_un01",texture_width=1024,texture_height=512)
    for bone in definition["bones"]:
        bone.pop("cubes",None)
    write(assets/"mesh/eva_un01.mesh.json",result)
    write(assets/"geo/eva_un01.geo.json",new_geo)
    hands=copy.deepcopy(result)
    hands["parts"]={n:p for n,p in parts.items()if n in ("hand_l","hand_r")}
    hands["jointSkins"]={n:s for n,s in skins.items()if n in hands["parts"]}
    hands["triangleCount"]=sum(len(p["vertices"])//24 for p in hands["parts"].values())
    write(assets/"mesh/eva_un01_anatomical_hands_r53.mesh.json",hands)
    write(args.out/"support.json",{n:np.unique(np.array(v).round(5),axis=0).tolist()for n,v in support.items()})
    write(args.out/"bind_report.json",dict(status="Candidate; not installed or visually accepted",
        source_groups=rows,triangles=result["triangleCount"],duplicates_removed=718,
        eye_pixels=int(mask.sum()),shared_rig="Exact Unit-01 geo hierarchy and joint pivots",
        landmarks=[dict(source=a,target=np.asarray(g).tolist())for a,g in zip(anchors,goals)],
        source_sha256={str(args.source/row["geometry"]):hashlib.sha256((args.source/row["geometry"]).read_bytes()).hexdigest()
                       for row in components}))
    print(json.dumps(dict(out=str(args.out),triangles=result["triangleCount"],parts=len(parts),eye_pixels=int(mask.sum()))))


if __name__=="__main__":
    main()
