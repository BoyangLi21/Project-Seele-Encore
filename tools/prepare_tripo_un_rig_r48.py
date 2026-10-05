"""Measured anatomical candidate; retain all supplied vertices and original UVs."""
from pathlib import Path
import json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
PIPE=ROOT/'artifacts/rebuild_r48/tripo_pipeline'

LANDMARKS={
 'un00':dict(hip=(.056,.553,.008),knee=(.080,.395,-.011),ankle=(.119,.091,.025),toe=(.134,.024,-.055),
             shoulder=(.109,.785,-.009),elbow=(.151,.631,-.020),wrist=(.191,.485,-.043),
             chest=(0,.637,.015),pelvis=(0,.511,.016),neck=(0,.810,.004),head=(0,.878,-.025),
             pylon=(.117,.801,.006),pylon_tip=(.117,.978,.006)),
 'un01':dict(hip=(.063,.543,.010),knee=(.100,.351,-.014),ankle=(.146,.094,.012),toe=(.155,.025,-.065),
             shoulder=(.138,.757,.002),elbow=(.168,.631,-.017),wrist=(.221,.484,-.048),
             chest=(0,.643,.016),pelvis=(0,.504,.014),neck=(0,.801,.010),head=(0,.882,-.021),
             pylon=(.112,.797,.012),pylon_tip=(.112,.978,.012))
}

def main():
 for name,markers in LANDMARKS.items():
    folder=PIPE/name;source=np.load(folder/'lod0_geometry.npz');v=source['vertices'];tri=source['triangles']
    records=[];segments=[]
    def add(bone,parent,p,end=None,kind='body'):
        records.append(dict(name=bone,parent=parent,pivot=list(p),category=kind))
        if end is not None:segments.append(dict(bone=bone,start=list(p),end=list(end),category=kind))
    add('root',None,(0,0,0))
    add('torso_lower','root',markers['pelvis'],markers['chest'],'torso')
    add('torso_upper','torso_lower',markers['chest'],markers['neck'],'torso')
    add('head','torso_upper',markers['neck'],(0,.957,markers['head'][2]),'head')
    for side,sign in [('r',1),('l',-1)]:
        def m(key):return np.array(markers[key])*[sign,1,1]
        add('arm_'+side,'torso_upper',m('shoulder'),m('elbow'),'arm')
        add('forearm_'+side,'arm_'+side,m('elbow'),m('wrist'),'arm')
        add('leg_'+side,'torso_lower',m('hip'),m('knee'),'leg')
        add('shin_'+side,'leg_'+side,m('knee'),m('ankle'),'leg')
        add('foot_'+side,'shin_'+side,m('ankle'),m('toe'),'foot')
        add('pylon_'+side,'torso_upper',m('pylon'),m('pylon_tip'),'pylon')
        wrist=m('wrist');palm=wrist+np.array([-.003*sign,-.035,-.006])
        add('hand_'+side,'forearm_'+side,wrist,palm,'hand')
        # The four fingers spread through depth, not along a guessed flat X row.
        # These are rigging landmarks selected from the actual front/side mesh.
        if name=='un00':
            ys=[.440,.419,.405,.398];xs=[.192,.193,.181,.168];zs=[-.077,-.061,-.046,-.031]
            thumb=[(.180,.478,-.065),(.164,.456,-.064),(.151,.435,-.061),(.150,.429,-.059)]
        else:
            ys=[.444,.419,.394,.380];xs=[.225,.239,.224,.210];zs=[-.090,-.073,-.054,-.035]
            thumb=[(.208,.473,-.083),(.191,.450,-.086),(.180,.426,-.088),(.179,.416,-.086)]
        for digit,z in zip(('index','middle','ring','little'),zs):
            shortening=.008 if digit=='little' else .003 if digit=='ring' else 0
            chain=[np.array([x*sign,y+shortening,z])for x,y in zip(xs,ys)]
            parent='hand_'+side
            for index in range(3):
                key='finger_'+digit+(''if index==0 else '_tip'if index==1 else '_distal')+'_'+side
                add(key,parent,chain[index],chain[index+1],'finger');parent=key
        parent='hand_'+side
        for index in range(3):
            key='finger_thumb'+(''if index==0 else '_tip'if index==1 else '_distal')+'_'+side
            add(key,parent,np.array(thumb[index])*[sign,1,1],np.array(thumb[index+1])*[sign,1,1],'finger');parent=key
    # Segment distance supplies the first assignment. Mesh2Motion's pinned
    # boundary smoother is applied separately; source vertices are never moved.
    distance=[]
    for segment in segments:
        a=np.array(segment['start']);b=np.array(segment['end']);d=b-a
        t=np.clip((v-a)@d/max(1e-9,d@d),0,1);dist=np.linalg.norm(v-a-t[:,None]*d,axis=1)
        bone=segment['bone'];kind=segment['category'];side=1 if bone.endswith('_r') else -1 if bone.endswith('_l') else 0
        if side:dist=np.where(v[:,0]*side<-.002,1e3,dist)
        if kind=='head':dist=np.where((abs(v[:,0])>.073)|(v[:,1]<.788),1e3,dist)
        if kind=='pylon':dist=np.where((v[:,1]<.77)|(abs(v[:,0])<.067),1e3,dist)
        if kind in ('hand','finger'):dist=np.where((v[:,1]>.515)|(abs(v[:,0])<(.135 if name=='un00' else .160)),1e3,dist)
        if kind in ('arm','hand','finger'):dist=np.where((abs(v[:,0])<.085)&(v[:,1]>.51),1e3,dist)
        if kind=='leg':dist=np.where(v[:,1]>.59,1e3,dist)
        if kind=='torso':dist=np.where((v[:,1]<.48)&(abs(v[:,0])>.04),1e3,dist)
        distance.append(dist)
    closest=np.argmin(np.stack(distance,axis=1),axis=1)
    names=[r['name']for r in records];index={n:i for i,n in enumerate(names)}
    labels=np.array([index[segments[i]['bone']]for i in closest]);indices=np.zeros((len(v),4),np.int32);weights=np.zeros((len(v),4),float);indices[:,0]=labels;weights[:,0]=1
    target=folder/'rig_candidate';target.mkdir(exist_ok=True)
    data=dict(source=name,units='source metres',bones=records,segments=segments,vertices=v.tolist(),triangles=tri.tolist(),skin_indices=indices.ravel().tolist(),skin_weights=weights.ravel().tolist(),
              source_geometry_changed=False,requires_finger_landmark_visual_review=True,game_integrated=False)
    (target/'initial_skin.json').write_text(json.dumps(data,separators=(',',':')),'utf8')
    (target/'rig_landmarks.json').write_text(json.dumps(dict(bones=records,segments=segments),indent=2),'utf8')
    print(name,len(v),'unchanged vertices,',len(records),'candidate bones',flush=True)

if __name__=='__main__':main()
