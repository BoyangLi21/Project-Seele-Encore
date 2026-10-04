"""Recover the artist's actual hand triangles/UVs; no hulls, boxes or remeshing.

Candidate only. Shared source vertices receive shared skin weights, including
the wrist boundary. Subdivision adds hinge samples without moving the surface.
"""
from pathlib import Path
import argparse,collections,hashlib,json,sys
import numpy as np
from scipy.spatial.transform import Rotation
import make_tiger_unit01_pack as tiger

ROOT=Path(__file__).resolve().parents[1]
SOURCES={0:'external-assets/work/unit00_audit/source_extracted/Unit00.obj',
         1:'external-assets/work/unit01/source-expanded/Unit01.obj',
         2:'external-assets/work/unit02_audit/source_extracted/Unit02.obj'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--rig',type=int,choices=range(3),required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);source=ROOT/SOURCES[a.rig]
    raw=source.read_text('utf8');vertices,uv,normals,triangles=tiger.parse_obj(raw)
    tiger.CLEAN_GRIP_FINGERS=False
    face_bones,_,_=tiger.discover_finger_rig(vertices,triangles)
    owners=tiger.complete_face_owners(vertices,triangles,face_bones)
    geo=ROOT/f'run/resourcepacks/eva_real_model/assets/projectseele/geo/eva_unit0{a.rig}.geo.json'
    bones={b['name']:b for b in json.loads(geo.read_text())['minecraft:geometry'][0]['bones']}
    def key(v):return tuple(round(float(x),6)for x in v)
    adjoining=collections.defaultdict(set)
    for i,tri in enumerate(triangles):
        for ref in tri:adjoining[key(vertices[ref[0]])].add(owners[i])
    cache={}
    def bind(name):
        if name in cache:return cache[name]
        b=bones[name];pivot=np.asarray(b['pivot'])*[-1,1,1]/16
        x,y,z=np.radians(np.asarray(b.get('rotation',[0,0,0]))*[-1,-1,1]);r=Rotation.from_rotvec([0,0,z]).as_matrix()@Rotation.from_rotvec([0,y,0]).as_matrix()@Rotation.from_rotvec([x,0,0]).as_matrix()
        m=np.eye(4);m[:3,:3]=r;m[:3,3]=pivot-r@pivot
        if b.get('parent'):m=bind(b['parent'])@m
        cache[name]=m;return m
    minimum=min(v[1]for v in vertices);scale=192/(max(v[1]for v in vertices)-minimum)
    export=dict(format_version=1,model_height=192,stride=8,source='Original Tigerar1 source hand surfaces, CC BY-SA; local derivative',parts={},jointSkins={},r37_mouth={'preserve_auto_joint_seams':True})
    receipt=[]
    for side in ['l','r']:
        selected=[i for i in range(len(triangles))if owners[i]=='hand_'+side or owners[i].startswith('finger_')and owners[i].endswith('_'+side)]
        palette=sorted(set(n for i in selected for ref in triangles[i]for n in adjoining[key(vertices[ref[0]])]if n in bones and n.endswith('_'+side)))
        assert 'hand_'+side in palette and selected
        packed=[];weights=[];original_area=0.;expanded_area=0.
        for i in selected:
            tri=triangles[i];xyz=np.asarray([vertices[r[0]]for r in tri]);tex=np.asarray([uv[r[1]] if r[1]>=0 else [0,0]for r in tri]);ns=np.asarray([normals[r[2]]if r[2]>=0 else tiger.face_normal(xyz)for r in tri]);ws=np.zeros((3,len(palette)))
            for j,ref in enumerate(tri):
                names=[n for n in adjoining[key(vertices[ref[0]])]if n in palette]
                for n in names:ws[j,palette.index(n)]=1/len(names)
            # Affine subdivision preserves the source surface and UV layout.
            pieces=[(xyz,tex,ns,ws)]
            for _ in range(2):
                next_pieces=[]
                for arrays in pieces:
                    mids=[(x+np.roll(x,-1,axis=0))*.5 for x in arrays]
                    for ids in [(0,3,5),(3,1,4),(5,4,2),(3,4,5)]:
                        next_pieces.append(tuple(np.concatenate([x,m])[list(ids)]for x,m in zip(arrays,mids)))
                pieces=next_pieces
            original_area+=np.linalg.norm(np.cross(xyz[1]-xyz[0],xyz[2]-xyz[0]))*.5
            anchor=np.asarray(bones['hand_'+side]['pivot'])
            for ps,ts,ns,ws in pieces:
                expanded_area+=np.linalg.norm(np.cross(ps[1]-ps[0],ps[2]-ps[0]))*.5
                for pos,t,n,w in zip(ps,ts,ns,ws):
                    point=np.array([pos[0]*scale,(pos[1]-minimum)*scale,-pos[2]*scale])-anchor
                    normal=n/np.linalg.norm(n);normal=normal*[1,1,-1]
                    packed.extend([*point,t[0]*.5,1-t[1],*normal]);weights.append(w)
        assert abs(expanded_area-original_area)<1e-8,'Subdivision changed original surface area'
        w=np.asarray(weights);assert np.max(abs(w.sum(1)-1))<1e-8
        name='hand_'+side;export['parts'][name]=dict(pivot=bones[name]['pivot'],vertices=np.round(packed,7).tolist())
        export['jointSkins'][name]=dict(influences={n:np.round(w[:,j],7).tolist()for j,n in enumerate(palette)},inverseBindColumnMajor={n:np.linalg.inv(bind(n)).T.reshape(-1).tolist()for n in palette})
        receipt.append(dict(side=side,original_faces=len(selected),exported_triangles=len(packed)//24,original_surface_area=original_area,exported_surface_area=expanded_area,controls=palette,source_triangle_ids=selected))
    name=f'eva_unit0{a.rig}_original_hands_r45.mesh.json';(out/name).write_text(json.dumps(export,separators=(',',':')),'utf8')
    (out/'provenance.json').write_text(json.dumps(dict(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),rig_sha256=hashlib.sha256(geo.read_bytes()).hexdigest(),hands=receipt,original_surface_and_uv_preserved=True,geometry_replacement=False,installed=False,native_passed=False),indent=2),'utf8')
    print('Recovered original artist hands',a.rig,[(r['side'],r['original_faces'],r['exported_triangles'])for r in receipt])

if __name__=='__main__':main()
