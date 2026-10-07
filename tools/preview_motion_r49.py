"""Offline actual-surface authoring stills; never claim native game acceptance."""
from pathlib import Path
import argparse
import json
import struct
import numpy as np
from scipy.spatial.transform import Rotation as Rot
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
import author_first_battle_r10 as b
import author_eva_rifle_stances_r06 as surface
import hand_surface_r49 as hands


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--runtime',type=Path,required=True)
    ap.add_argument('--assets',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--only-neutral',action='store_true')
    ap.add_argument('--clip',type=Path)
    args=ap.parse_args();args.assets=args.assets.resolve();args.runtime=args.runtime.resolve();args.out=args.out.resolve()
    args.out.mkdir(parents=True,exist_ok=True)
    common.BODY=json.loads((args.runtime/'eva_body_r44.json').read_text(encoding='utf-8'))
    geo=json.loads((args.assets/'geo/eva_unit01.geo.json').read_text(encoding='utf-8'))
    known={n['name']for n in common.BODY['rigs']['1']}
    common.BODY['rigs']['1'] += [n for n in geo['minecraft:geometry'][0]['bones']if n['name'].startswith('r37_')and n['name']not in known]
    hand_contract=json.loads((args.assets/'hand_rigs/unit01/hand_rig_contract.json').read_text(encoding='utf-8'))
    hand_mesh=json.loads((args.assets/'mesh/eva_unit01_anatomical_hands_r45.mesh.json').read_text(encoding='utf-8'))
    hands.extend_body(common.BODY,hand_contract)
    common.NAMES=common.BODY['motion']['bones'];actor=Actor(1)
    mesh=json.loads((args.assets/'mesh/eva_unit01.mesh.json').read_text(encoding='utf-8'))
    parts={n:p for n,p in mesh['parts'].items()if n in actor.rig.rig
           and n not in ('cannon','knife','lance','n2','entry_plug','plug_hatch_l','plug_hatch_r')
           and not n.startswith(('hand_','finger_'))}
    surface.MESH={n:(np.asarray(p['vertices']).reshape(-1,8)[:,:3]+p['pivot'])*[-1,1,1]for n,p in parts.items()}
    surface.SKIN={}
    for n,k in mesh.get('jointSkins',{}).items():
        if n in parts and k['otherBone']in actor.rig.rig:
            surface.SKIN[n]=(k['otherBone'],np.asarray(k['weights'])[:,None],surface.MESH[n])
    uv=np.vstack([np.asarray(p['vertices']).reshape(-1,8)[:,3:5]for p in parts.values()])
    movie=json.loads((args.clip or args.runtime/'first_battle_r44.json').read_text(encoding='utf-8'))
    blob=(args.runtime/'sachiel_wrap_r14.bin').read_bytes();start,count,fps,unique,full,base=struct.unpack('>6i',blob[4:28])
    cache_index=np.frombuffer(blob,dtype='>i4',count=full,offset=60)
    cache_uv=np.frombuffer(blob,dtype='>f4',count=full*2,offset=60+full*4).reshape(-1,2)
    cache=np.frombuffer(blob,dtype='>f4',offset=60+full*12).reshape(count,unique,3)
    records=[]
    def hero_surface(pose,left,right,separate_head=False):
        hands.apply_controls(pose,hand_contract,left,right)
        opened=abs(pose.q.get('r37_jaw',Rot.identity()).as_rotvec()[0])>.01
        chosen=[n for n in parts if not(separate_head and n=='head')and(opened or n not in('r37_red_upper','r37_red_lower','r37_lining'))]
        verts=[surface.vertices(pose,n)for n in chosen];tex=[np.vstack([np.asarray(parts[n]['vertices']).reshape(-1,8)[:,3:5]for n in chosen])]
        for side in ('l','r'):
            v,u=hands.surface(pose,hand_mesh,'hand_'+side);verts.append(v);tex.append(u)
        return np.vstack(verts),np.vstack(tex)
    selections=[('press',3.8),('grip',7),('core',14.3),('rise',15.8),('approach',16.85),('wrap',18.1),('quiet',22.8)]if movie.get('r49_grounded_pair')else[('grip',7),('core',440/30),('approach',16),('wrap',505/30),('bound',18.5),('quiet',685/30)]
    for name,seconds in selections:
        index=round(seconds*movie['fps'])
        if args.only_neutral:continue
        pose=actor.rig.decode(movie['eva']['frames'][index],movie['eva']['bones'])
        jaw=.72 if seconds<18.6 else .72*(1-float(np.clip((seconds-18.6)/.6,0,1)))
        pose.setq('r37_jaw',Rot.from_euler('x',-31*jaw,degrees=True));pose.setp('r37_jaw',[0,0,-.8*jaw])
        left,right=('relaxed','relaxed')if seconds>=18.6 else('grab','grab')if seconds>=15.2 else('support','fist')if seconds>=11.05 else('grab','grab')
        vertices,hero_uv=hero_surface(pose,left,right,True)
        hero=vertices*b.HEROMIRROR*b.UNIT+movie['eva']['root_blocks'][index]
        if index>=start and movie.get('surface_deformation_r14'):
            angel=cache[min(index-start,count-1)][cache_index];angel_uv=cache_uv
            if seconds>18.6:angel=np.empty((0,3));angel_uv=np.empty((0,2))
        else:
            from preview_first_battle_r12 import angel_pose
            p=angel_pose(movie['angel']['frames'][index],movie['angel']['bones'])
            a=json.loads((args.assets/'mesh/sachiel.mesh.json').read_text(encoding='utf-8'))
            av=np.asarray(a['parts']['root']['vertices']).reshape(-1,8)
            _,inverse=np.unique(np.round(av[:,:3]*[-1,1,1],6),axis=0,return_inverse=True)
            angel=p.skin()[inverse]*b.UNIT+movie['angel']['root_blocks'][index];angel_uv=av[:,3:5]
            if seconds>18.6:angel=np.empty((0,3));angel_uv=np.empty((0,2))
        eye_vertices=surface.vertices(pose,'head')*b.HEROMIRROR*b.UNIT+movie['eva']['root_blocks'][index]
        head_uv=np.asarray(parts['head']['vertices']).reshape(-1,8)[:,3:5]
        np.savez_compressed(args.out/(name+'.npz'),hero=hero,hero_uv=hero_uv,angel=angel,angel_uv=angel_uv,head=eye_vertices,head_uv=head_uv)
        visible=np.vstack([hero,angel]);centre=(visible.min(0)+visible.max(0))/2
        records.append(dict(name=name,time=seconds,centre=centre.tolist(),extent=float(np.ptp(visible,axis=0).max()),eyes_state='dark'if seconds>=18.6 else'berserk',ground=True))
    doc=common.BODY['stance_clips_by_rig']['1'];profile=json.loads((args.runtime/'eva_gameplay_r44_1.json').read_text(encoding='utf-8'))
    for name,frames,names in [('idle',doc['clips']['idle']['frames'],doc['bones']),
                             ('knife_ready',profile['clips']['r32_knife_draw']['frames'][-1:],profile['bones'])]:
        pose=actor.rig.decode(frames[0],names);v,hero_uv=hero_surface(pose,'relaxed','knife'if name=='knife_ready'else'relaxed');hero=v*b.HEROMIRROR*b.UNIT
        extras={}
        if name=='knife_ready':
            filename=Path(hand_contract['knife_attachment_r45']['source_mesh']).name
            weapon=json.loads((args.assets/'mesh'/filename).read_text(encoding='utf-8'))
            all_parts=[];all_uv=[]
            for part in weapon['parts'].values():
                raw=np.asarray(part['vertices']).reshape(-1,8);rest=(raw[:,:3]+part['pivot'])*[-1,1,1]
                world=(np.c_[rest,np.ones(len(rest))]@pose.matrix('knife').T)[:,:3]*b.HEROMIRROR*b.UNIT
                all_parts.append(world);all_uv.append(raw[:,3:5])
            extras=dict(weapon=np.vstack(all_parts),weapon_uv=np.vstack(all_uv))
        np.savez_compressed(args.out/(name+'.npz'),hero=hero,hero_uv=hero_uv,angel=np.empty((0,3)),angel_uv=np.empty((0,2)),**extras)
        records.append(dict(name=name,time=None,centre=((hero.min(0)+hero.max(0))/2).tolist(),extent=float(np.ptp(hero,axis=0).max())))
    a=json.loads((args.assets/'mesh/sachiel.mesh.json').read_text(encoding='utf-8'))
    av=np.asarray(a['parts']['root']['vertices']).reshape(-1,8)
    _,inverse=np.unique(np.round(av[:,:3]*[-1,1,1],6),axis=0,return_inverse=True)
    neutral_angel=b.ANGEL.pose();neutral_angel.ground();angel=neutral_angel.skin()[inverse]*b.UNIT
    np.savez_compressed(args.out/'sachiel_bind.npz',hero=np.empty((0,3)),hero_uv=np.empty((0,2)),angel=angel,angel_uv=av[:,3:5])
    records.append(dict(name='sachiel_bind',time=None,centre=((angel.min(0)+angel.max(0))/2).tolist(),extent=float(np.ptp(angel,axis=0).max())))
    (args.out/'manifest.json').write_text(json.dumps(dict(records=records,texture_root=str(args.assets/'textures/entity'),
            native=False,limitation='Authoring surface/pose; runtime hands, jaw/eyes, camera, shading and collision remain separate checks'),indent=2),encoding='utf-8')
    print('Prepared',len(records),'offline actual-surface pose snapshots')


if __name__=='__main__':main()
