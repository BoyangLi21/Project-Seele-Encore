"""Import the owner's shield unchanged, fitting its actual upper rear handrail."""
from pathlib import Path
import sys,json,copy
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).parent))
from eva_hand_rig_math_r45 import controls,matrices,joint_points
from rebind_anatomical_hand_r45 import dq_pose

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'artifacts/rebuild_r47/models/user_shield_source'
ASSETS=ROOT/'artifacts/rebuild_r47/assets/assets/projectseele'
OUT=ROOT/'artifacts/rebuild_r47/models/user_shield_fitted'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    vertices=[];uvs=[];normals=[];faces=[]
    for line in (SRC/'shield.obj').read_text('utf8',errors='replace').splitlines():
        x=line.split()
        if not x:continue
        if x[0]=='v':vertices.append(list(map(float,x[1:4])))
        elif x[0]=='vt':uvs.append(list(map(float,x[1:3])))
        elif x[0]=='vn':normals.append(list(map(float,x[1:4])))
        elif x[0]=='f':
            corners=[tuple(int(a)-1 for a in item.split('/')) for item in x[1:]]
            for i in range(1,len(corners)-1):faces.append((corners[0],corners[i],corners[i+1]))
    v=np.asarray(vertices);lo=v.min(0);hi=v.max(0)
    # Body height is 60m. A 50m shield remains a full protective silhouette.
    height=50.;world_per_model=5./16.;scale=height/(hi[1]-lo[1])/world_per_model
    c=json.loads((ASSETS/'hand_rigs/unit00/hand_rig_contract.json').read_text('utf8'))
    g=json.loads((ASSETS/'geo/eva_unit00.geo.json').read_text('utf8'))
    h=c['hands']['l'];palm=np.asarray(c['weapon_grip_frames']['l']['palm_bind'])
    longitudinal=np.asarray(h['longitudinal_bind']);longitudinal/=np.linalg.norm(longitudinal)
    normal=np.asarray(h['palmar_normal_bind']);normal-=longitudinal*(longitudinal@normal);normal/=np.linalg.norm(normal)
    y=-longitudinal;z=-normal;x=np.cross(y,z);x/=np.linalg.norm(x);z=np.cross(x,y)
    rotation=np.column_stack((x,y,z))
    # Crossbar centre measured from the preserved disconnected 16-vertex rail.
    handle=np.array([0.,52.799810,2.529035])*scale*[-1,1,1]/16
    selected=controls(c,'knife','l');ms=matrices(g,c,'l',selected)
    joints=joint_points(g,c,'l',selected)
    # Use the measured palm and proximal/distal curl cavity, never the forearm's
    # old approximate centre. The back rail stays in this one hand frame.
    tips=np.asarray([joints[d][2] for d in ('index','middle','ring','little')])
    cavity=(palm+tips.mean(0))*.5
    c['shield_attachment_r47']=dict(source_mesh='yashima_shield.mesh.json',source_handle_centre=handle.tolist(),
        target_handle_centre=cavity.tolist(),rotation_column_major=rotation.T.reshape(-1).tolist(),
        hand='hand_l',source_height=height,original_geometry_preserved=True,user_provided=True)
    raw=[]
    for face in faces:
        for vi,ti,ni in face:
            point=v[vi]*scale
            n=np.asarray(normals[ni])
            raw.extend([*point,uvs[ti][0],1-uvs[ti][1],*n])
    common=dict(format_version=1,stride=8,source='Owner-provided EVA Unit00 Defense Shield; original geometry/UV preserved',
        triangle_count=len(faces),model_height=(hi[1]-lo[1])*scale,owner_provided_r47=True,
        shield_attachment=c['shield_attachment_r47'])
    doc=dict(common,parts={'shield':dict(pivot=[0,0,0],vertices=raw)})
    (ASSETS/'mesh/yashima_shield.mesh.json').write_text(json.dumps(doc,separators=(',',':')),encoding='utf8')
    payload=np.asarray(raw).reshape(-1,8);payload[:,1]-=lo[1]*scale
    payloaddoc=dict(common,parts={'shield':dict(pivot=[0,0,0],vertices=payload.reshape(-1).tolist())})
    (ASSETS/'mesh/yashima_shield_payload.mesh.json').write_text(json.dumps(payloaddoc,separators=(',',':')),encoding='utf8')
    Image.open(SRC/'dun_tex.tga').save(ASSETS/'textures/entity/yashima_shield.png')
    (ASSETS/'hand_rigs/unit00/hand_rig_contract.json').write_text(json.dumps(c,indent=2),encoding='utf8')
    hand=json.loads((ASSETS/'mesh/eva_unit00_anatomical_hands_r45.mesh.json').read_text('utf8'));part=hand['parts']['hand_l'];skin=hand['jointSkins']['hand_l']
    a=np.asarray(part['vertices']).reshape(-1,8);points=(a[:,:3]+part['pivot'])*[-1,1,1]/16
    names=list(skin['influences']);w=np.asarray([skin['influences'][n] for n in names]).T
    inv=[np.asarray(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in names]
    posed=dq_pose(points,w,[ms[n]@iv for n,iv in zip(names,inv)])
    shield=v*scale*[-1,1,1]/16;shield=(shield-handle)@rotation.T+cavity
    np.savez_compressed(OUT/'grip.npz',hand=posed,shield=shield,faces=np.asarray([[a[0] for a in f] for f in faces]),
        texture_uv=np.asarray([[uvs[a[1]][0],1-uvs[a[1]][1]] for f in faces for a in f]))
    report=dict(source_vertices=len(v),source_triangles=len(faces),world_height=height,
        world_width=float((hi[0]-lo[0])*scale*world_per_model),world_thickness=float((hi[2]-lo[2])*scale*world_per_model),
        source_handle_centre_obj=[0,52.799810,2.529035],binding=c['shield_attachment_r47'],
        source_geometry_changed=False,private_asset_not_public_commit=True,native_verified=False)
    (OUT/'IMPORT.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))

if __name__=='__main__':main()
