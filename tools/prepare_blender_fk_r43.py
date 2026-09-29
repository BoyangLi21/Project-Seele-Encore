"""Paired-rig interoperability fixture from the actual local bones, meshes and clips."""
from pathlib import Path
import json
import numpy as np
import author_first_battle_r10 as b
from author_combat_r35 import Actor
from preview_first_battle_r12 import angel_pose

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/repair_r43/blender_interop'
C=np.array([[1.,0,0],[0,0,-1],[0,1,0]])
SAMPLES=[0,86,165,225,295,315,332,390,465,500,550,690]


def main():
    OUT.mkdir(parents=True,exist_ok=True);actors=[];eva=Actor(1)
    for label,file,shift in [('before',ROOT/'run/projectseele-local-maps/first_battle_r42.json',-75),('candidate',ROOT/'artifacts/repair_r43/first_battle/first_battle_r43.json',75)]:
        clip=json.loads(file.read_text('utf8'))
        for hero in (True,False):
            role='eva' if hero else 'angel';names=list(eva.P) if hero else list(b.ANGEL.names)
            pivots=eva.P if hero else b.ANGEL.P;parents={n:eva.rig.rig[n].get('parent') for n in names} if hero else b.ANGEL.parents
            basis=np.eye(4);basis[:3,:3]=C@np.diag(b.HEROMIRROR if hero else [1,1,1])*b.UNIT;inverse=np.linalg.inv(basis)
            if hero:
                verts=[];ids=[];uv=[]
                for n,part in b.eva.mesh['parts'].items():
                    if n not in names or n in ('cannon','knife','lance','n2','entry_plug'):continue
                    a=np.asarray(part['vertices']).reshape(-1,8);pts=(a[:,:3]+part['pivot'])*[-1,1,1]
                    verts.extend(pts);uv.extend(a[:,3:5]);ids.extend([[names.index(n)]]*len(pts))
                verts=np.asarray(verts);faces=np.arange(len(verts)).reshape(-1,3);weights=np.ones((len(verts),1))
            else:
                mesh=json.loads((b.eva.PACK/'mesh/sachiel.mesh.json').read_text());a=np.asarray(mesh['parts']['root']['vertices']).reshape(-1,8)
                _,indices=np.unique(np.round(a[:,:3]*[-1,1,1],6),axis=0,return_inverse=True)
                verts=b.ANGEL.vertices;faces=indices.reshape(-1,3);ids=b.ANGEL.ids;weights=b.ANGEL.weights;uv=a[:,3:5]
            vertices=(verts@basis[:3,:3].T).tolist();poses=[]
            for index in SAMPLES:
                p=b.eva.decode(clip[role]['frames'][index],clip[role]['bones']) if hero else angel_pose(clip[role]['frames'][index],clip[role]['bones'])
                poses.append(dict(frame=index+1,time=index/30,root=(C@np.asarray(clip[role]['root_blocks'][index])+[shift,0,0]).tolist(),
                                  deform=[(basis@p.matrix(n)@inverse).tolist() for n in names]))
            bones=[dict(name=n,parent=parents.get(n),head=(basis[:3,:3]@pivots[n]).tolist()) for n in names]
            actors.append(dict(name=role+'_'+label,bones=bones,vertices=vertices,faces=np.asarray(faces).tolist(),
                influences=np.asarray(ids).tolist(),weights=np.asarray(weights).tolist(),uv=np.asarray(uv).tolist(),poses=poses,
                texture=str(b.eva.PACK/'textures/entity'/('eva_unit01.png' if hero else 'sachiel.png')),
                weighting_scope='Rigid part FK only; native EVA dual-quaternion seam corrections are excluded' if hero else 'Existing authored four-weight linear skinning; cached late envelopment excluded'))
    (OUT/'fixture.json').write_text(json.dumps(dict(actors=actors,samples=SAMPLES,units='Minecraft blocks; current EVA height 60',scope='Small FK/mesh evaluation and export-readback experiment, not artistic acceptance'),separators=(',',':')),'utf8')
    print('Prepared four actor rigs and',len(SAMPLES),'shared-clock samples')


if __name__=='__main__':main()
