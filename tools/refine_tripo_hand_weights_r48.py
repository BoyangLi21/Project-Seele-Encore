"""Keep cuff/palm vertices out of finger controls and blend each real knuckle."""
from pathlib import Path
import json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]/'artifacts/rebuild_r48/tripo_pipeline'
def smooth(t):t=np.clip(t,0,1);return t*t*(3-2*t)
for name in ('un00','un01'):
    folder=ROOT/name;source=np.load(folder/'lod0_geometry.npz');v=source['vertices'];file=folder/'rig_candidate/smoothed_skin.json'
    data=json.loads(file.read_text());ids=np.array(data['skin_indices']).reshape(-1,4);weights=np.array(data['skin_weights']).reshape(-1,4)
    palette=data['bones'];ix={n:i for i,n in enumerate(palette)}
    rig=json.loads((folder/'rig_candidate/rig_landmarks.json').read_text());segments={s['bone']:s for s in rig['segments']};modified=0
    for side,sign in [('r',1),('l',-1)]:
        hand=ix['hand_'+side];forearm=ix['forearm_'+side]
        members=[i for i,n in enumerate(palette)if (n.startswith('finger_')and n.endswith('_'+side))or n=='hand_'+side]
        owned=np.any(np.isin(ids,members)&(weights>.05),axis=1)
        rows=np.flatnonzero(owned&(v[:,1]<.496)&(v[:,0]*sign> .13))
        for vertex in rows:
            point=v[vertex];best=None
            for digit in ('index','middle','ring','little','thumb'):
                for j in range(3):
                    bone='finger_'+digit+(''if j==0 else '_tip'if j==1 else '_distal')+'_'+side
                    s=segments[bone];a=np.array(s['start']);b=np.array(s['end']);d=b-a;t=np.clip(np.dot(point-a,d)/np.dot(d,d),0,1)
                    distance=np.linalg.norm(point-a-t*d)
                    if digit=='thumb'and point[0]*sign>(.186 if name=='un00'else .214):distance+=.06
                    if best is None or distance<best[0]:best=(distance,bone,j,digit,t)
            _,bone,j,digit,t=best
            if digit=='thumb':
                amount=smooth((.468-point[1])/.016)
            else:amount=smooth((.447-point[1])/.013)
            mix={hand:1-amount,ix[bone]:amount}
            # A narrow parent-child transition follows the authored knuckle,
            # preventing hard Voronoi changes from pulling triangles into spikes.
            if j>0:
                parent='finger_'+digit+(''if j==1 else '_tip')+'_'+side
                part=(1-smooth(t/.27))*.5*amount
                mix[ix[bone]]-=part;mix[ix[parent]]=mix.get(ix[parent],0)+part
            cuff=smooth((point[1]-.479)/.015)
            mix={n:w*(1-cuff)for n,w in mix.items()};mix[forearm]=mix.get(forearm,0)+cuff
            selected=sorted(((n,w)for n,w in mix.items()if w>1e-8),key=lambda p:-p[1])[:4]
            total=sum(w for _,w in selected);ids[vertex]=0;weights[vertex]=0
            for k,(n,w)in enumerate(selected):ids[vertex,k]=n;weights[vertex,k]=w/total
            modified+=1
    data['skin_indices']=ids.ravel().tolist();data['skin_weights']=weights.ravel().tolist()
    data['hand_refinement_r48']={'modified_vertices':modified,'cuff_and_palm_protected':True,'knuckle_blending':True,'visual_review_pending':True}
    file.write_text(json.dumps(data,separators=(',',':')),'utf8');print(name,modified,'hand vertices refined')
