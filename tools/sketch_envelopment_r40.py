"""Single isolated silhouette study for TV #02's C-shaped Sachiel enclosure.

No movie/mesh installation. Bend the spine continuously; do not polar-project
the entire character into a cylinder or inflate a hull around the EVA's hands.
"""
from pathlib import Path
import json,hashlib
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.spatial.transform import Rotation as R
import author_first_battle_r10 as battle
import author_eva_rifle_stances_r06 as hero_mesh

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/world_combat_r40/envelopment_study'
UNIT=5/16


def unit(v):
    return v/np.maximum(np.linalg.norm(v,axis=-1,keepdims=True),1e-9)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    clip=ROOT/'artifacts/world_combat_r40/envelopment_native/baseline_first_battle_r24.json'
    if not clip.exists():clip=ROOT/'run/projectseele-local-maps/first_battle_r24.json'
    data=json.loads(clip.read_text());frame=558
    if 'r40_envelopment' in data:raise ValueError('Author from the preserved pre-R40 clip, not the already installed output')
    hero=battle.eva.decode(data['eva']['frames'][frame],data['eva']['bones'])
    root=np.array(data['eva']['root_blocks'][frame])
    centre=battle.hero_world(hero,root,'head')+[0,2,6]
    rig=battle.ANGEL;rest=rig.vertices;P=rig.P
    y0,y1=P['torso_lower'][1],P['head'][1]

    def spine(values):
        s=np.clip((values[:,1]-y0)/(y1-y0),0,1)
        # Arc length equals the measured rest spine. The first blocking draft
        # stretched a 26.7 m torso along a 61 m arc and cannot be shipped.
        sweep=np.deg2rad(160);radius=(y1-y0)*UNIT/sweep
        angle=np.deg2rad(-65)+sweep*s
        path=np.c_[np.zeros(len(values)),radius*np.sin(angle),radius*np.cos(angle)]
        tangent=unit(np.c_[np.zeros(len(values)),np.cos(angle),-np.sin(angle)])
        radial=np.cross(np.tile([1.,0,0],(len(values),1)),tangent)
        depth=(values[:,2]-s*P['head'][2])*UNIT
        return centre+path+np.c_[values[:,0]*UNIT,np.zeros((len(values),2))]+radial*depth[:,None],tangent,radial

    torso,_,_=spine(rest)
    head_at,head_up,head_out=spine(P['head'][None])
    rotation=np.column_stack(([1.,0,0],head_up[0],head_out[0]))
    head=head_at[0]+(rest-P['head'])@rotation.T*UNIT
    targets={'root':torso,'torso_lower':torso,'torso_upper':torso,'neck':head,'head':head}

    def limb(side,arm):
        names=[('arm_' if arm else 'leg_')+side,('forearm_' if arm else 'shin_')+side,('hand_' if arm else 'foot_')+side]
        joints=np.array([P[n] for n in names]);segment=np.diff(joints,axis=0);length=np.linalg.norm(segment,axis=1);total=length.sum()
        candidates=[];distance=[];offset=[]
        for i in range(2):
            t=np.clip((rest-joints[i])@segment[i]/length[i]**2,0,1)
            anchor=joints[i]+t[:,None]*segment[i]
            candidates.append((length[:i].sum()+t*length[i])/total)
            distance.append(np.sum((rest-anchor)**2,axis=1));offset.append(rest-anchor)
        choose=np.argmin(distance,axis=0);t=np.choose(choose,candidates);off=np.where(choose[:,None]==0,offset[0],offset[1])
        sign=-1 if side=='l' else 1
        begin=spine(joints[0][None])[0][0]-centre
        keys=np.array([begin,[sign*16,4,-7],[sign*14,-4,-17],[sign*8,-10,-18]] if arm else
                      [begin,[sign*8,-17,1],[sign*11,-19,-11],[sign*6,-12,-18]],float)
        curve=CubicSpline([0,.34,.7,1],keys,axis=0);path=curve(t);tangent=unit(curve(t,1))
        lateral=np.tile([sign,0.,0.],(len(rest),1));lateral=unit(lateral-tangent*np.sum(lateral*tangent,axis=1)[:,None]);other=np.cross(tangent,lateral)
        rest_tangent=segment[choose]/length[choose,None]
        rest_lateral=np.tile([sign,0.,0.],(len(rest),1));rest_lateral=unit(rest_lateral-rest_tangent*np.sum(rest_lateral*rest_tangent,axis=1)[:,None]);rest_other=np.cross(rest_tangent,rest_lateral)
        x=np.sum(off*rest_lateral,axis=1)*UNIT;y=np.sum(off*rest_other,axis=1)*UNIT
        # Fingers and toes extend beyond the chain endpoints. Dropping their
        # axial component collapsed the distal mesh into spikes/flat fins.
        axial=np.sum(off*rest_tangent,axis=1)*UNIT
        return centre+path+lateral*x[:,None]+other*y[:,None]+tangent*axial[:,None]

    for side in ('l','r'):
        arm=limb(side,True);leg=limb(side,False)
        for prefix in ('arm_','forearm_','hand_'):targets[prefix+side]=arm
        for prefix in ('leg_','shin_','foot_'):targets[prefix+side]=leg
    target=np.zeros_like(rest)
    for index,name in enumerate(rig.names):
        weight=np.where(rig.ids==index,rig.weights,0).sum(axis=1)
        target+=targets[name]*weight[:,None]
    # Preserve the red core as a rigid sphere through the curved tissue.
    core_at,core_up,core_out=spine(rig.core[None]);basis=np.column_stack(([1.,0,0],core_up[0],core_out[0]))
    core=core_at[0]+(rest-rig.core)@basis.T*UNIT
    d=np.linalg.norm((rest-rig.core)*[1,1,.8],axis=1);weight=np.clip((16-d)/5,0,1);weight=weight*weight*(3-2*weight)
    target=target*(1-weight[:,None])+core*weight[:,None]
    for side,sign in [('l',1),('r',-1)]:
        target_hand=core_at[0]+[sign*2.4,-1.8,-.7]
        rotation=R.from_matrix(hero.matrix('hand_'+side)[:3,:3])
        from scipy.spatial import cKDTree
        samples=target[d<10];tree=cKDTree(samples)
        hand_parts=[n for n in hero_mesh.MESH if n.endswith('_'+side) and n.startswith(('hand_','finger_'))]
        for _ in range(10):
            battle.hero_hand(hero,root,side,target_hand,rotation,curl=.35,pole_weight=1)
            hand=np.vstack([hero_mesh.vertices(hero,n) for n in hand_parts])*battle.HEROMIRROR*UNIT+root
            distances,indices=tree.query(hand);near=int(np.argmin(distances));gap=float(distances[near])
            if gap<.25:break
            target_hand+=(samples[indices[near]]-hand[near])*(1-.2/gap)*.65
    source=ROOT/'run/resourcepacks/eva_real_model/assets/projectseele/mesh/sachiel.mesh.json'
    mesh=json.loads(source.read_text());v=np.array(mesh['parts']['root']['vertices']).reshape(-1,8)
    _,inverse=np.unique(np.round(v[:,:3]*[-1,1,1],6),axis=0,return_inverse=True)
    parts=[n for n in hero_mesh.MESH if n not in ['cannon','knife','lance','n2','entry_plug']]
    h=np.vstack([hero_mesh.vertices(hero,n) for n in parts])*battle.HEROMIRROR*UNIT+root
    uv=np.vstack([np.array(battle.eva.mesh['parts'][n]['vertices']).reshape(-1,8)[:,3:5] for n in parts])
    np.savez_compressed(OUT/'target.npz',hero=h,hero_uv=uv,angel=target[inverse],angel_uv=v[:,3:5])
    np.savez_compressed(OUT/'target_unique.npz',angel=target,core=core_at[0],inverse=inverse)
    (OUT/'target_hero_pose.json').write_text(json.dumps(battle.eva.encode(hero,bone_names=data['eva']['bones'])))
    (OUT/'manifest.json').write_text(json.dumps([{'name':'target','time':18.6,'target':[float(centre[0]),float(-centre[2]),float(centre[1]-5)],'scale':85}]))
    (OUT/'study.json').write_text(json.dumps({'status':'isolated silhouette study; no clearance or motion approval',
        'reference':'TV #02, Sakugabooru 301522, viewed at37.824/40.779s',
        'clip_sha256':hashlib.sha256(clip.read_bytes()).hexdigest(),'mesh_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'method':'continuous longitudinal spine bend, rigid head/core, anatomical limb curves; no global radial projection'},indent=2))
    print(OUT,flush=True)


if __name__=='__main__':main()
