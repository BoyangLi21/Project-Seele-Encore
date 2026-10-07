"""Selected gameplay poses with the production meshes and anatomical hands."""
from pathlib import Path
import argparse,json
import numpy as np
from scipy.spatial.transform import Rotation as R
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
import author_first_battle_r10 as battle
import author_eva_rifle_stances_r06 as skin
import hand_surface_r49 as hands


def main():
    p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--profiles',type=Path,required=True)
    p.add_argument('--assets',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--body',type=Path);p.add_argument('--gaits',action='store_true')
    a=p.parse_args();a.assets=a.assets.resolve();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
    common.BODY=json.loads((a.body or a.runtime/'eva_body_r44.json').read_text(encoding='utf-8'))
    records=[];steps=[]
    selections={1:[('r32_berserk_down',.45),('r32_knife_forward',.5)],2:[('r32_sword_b',.3)]}
    if a.gaits:selections={k:[('walk',.15),('walk',.65),('run',.15),('run',.65),('dash_run',.15),('dash_run',.65)]for k in range(3)}
    for key,clips in selections.items():
        contract=json.loads((a.assets/f'hand_rigs/unit{key:02}/hand_rig_contract.json').read_text(encoding='utf-8'))
        existing={b['name']for b in common.BODY['rigs'][str(key)]}
        common.BODY['rigs'][str(key)]+=[b for b in contract['new_bones']if b['name']not in existing]
        geo=json.loads((a.assets/f'geo/eva_unit{key:02}.geo.json').read_text(encoding='utf-8'))
        common.BODY['rigs'][str(key)]+=[b for b in geo['minecraft:geometry'][0]['bones']if b['name'].startswith('r37_')and b['name']not in existing]
        common.NAMES=common.BODY['motion']['bones'];actor=Actor(key)
        mesh=json.loads((a.assets/f'mesh/eva_unit{key:02}.mesh.json').read_text(encoding='utf-8'))
        handmesh=json.loads((a.assets/f'mesh/eva_unit{key:02}_anatomical_hands_r45.mesh.json').read_text(encoding='utf-8'))
        parts={n:x for n,x in mesh['parts'].items()if n in actor.rig.rig and n not in ('cannon','knife','lance','n2','entry_plug','plug_hatch_l','plug_hatch_r','r37_red_upper','r37_red_lower','r37_lining')and not n.startswith(('hand_','finger_'))}
        skin.MESH={n:(np.asarray(x['vertices']).reshape(-1,8)[:,:3]+x['pivot'])*[-1,1,1]for n,x in parts.items()};skin.SKIN={}
        for n,x in mesh.get('jointSkins',{}).items():
            if n in parts and x['otherBone']in actor.rig.rig:skin.SKIN[n]=(x['otherBone'],np.asarray(x['weights'])[:,None],skin.MESH[n])
        data=json.loads((a.profiles/f'eva_gameplay_r44_{key}.json').read_text(encoding='utf-8'))
        before=data if a.gaits else json.loads((a.profiles/f'before_{key}.json').read_text(encoding='utf-8'))
        for clipname,clip in data['clips'].items():
            old=np.array([f['rotation_wxyz']for f in before['clips'][clipname]['frames']]);new=np.array([f['rotation_wxyz']for f in clip['frames']])
            if np.max(abs(old-new))<1e-7:continue
            def peak(frames):
                values=[]
                for n in ('arm_l','arm_r','forearm_l','forearm_r'):
                    q=R.from_quat(frames[:,data['bones'].index(n)][:,[1,2,3,0]])
                    values.extend(np.degrees((q[:-1].inv()*q[1:]).magnitude()))
                return float(max(values))
            steps.append(dict(rig=key,clip=clipname,source_peak_degrees=peak(old),selected_peak_degrees=peak(new)))
        for name,fraction in clips:
            active=common.BODY['stance_clips_by_rig'][str(key)]if a.gaits else data
            if name not in active['clips']:continue
            frames=active['clips'][name]['frames'];index=round((len(frames)-1)*fraction);pose=actor.rig.decode(frames[index],active['bones'])
            control='relaxed'if a.gaits else'sword_right'if'sword'in name else'knife'if'knife'in name else'fist'
            hands.apply_controls(pose,contract,'relaxed',control)
            vertices=[skin.vertices(pose,n)for n in parts if n!='head'];uv=[np.asarray(x['vertices']).reshape(-1,8)[:,3:5]for n,x in parts.items()if n!='head']
            for side in ('l','r'):
                v,u=hands.surface(pose,handmesh,'hand_'+side);vertices.append(v);uv.append(u)
            hero=np.vstack(vertices)*battle.HEROMIRROR*battle.UNIT
            label=f'unit{key:02}_{name}'+(f'_{fraction:.2f}'if a.gaits else'');extra={}
            if'knife'in name:
                filename=Path(contract['knife_attachment_r45']['source_mesh']).name
                weapon=json.loads((a.assets/'mesh'/filename).read_text(encoding='utf-8'));v=[];u=[]
                for x in weapon['parts'].values():
                    raw=np.asarray(x['vertices']).reshape(-1,8);rest=(raw[:,:3]+x['pivot'])*[-1,1,1]
                    v.append((np.c_[rest,np.ones(len(rest))]@pose.matrix('knife').T)[:,:3]*battle.HEROMIRROR*battle.UNIT);u.append(raw[:,3:5])
                extra=dict(weapon=np.vstack(v),weapon_uv=np.vstack(u))
            if'sword'in name:
                fit=contract['sword_attachment_r45'];weapon=json.loads((a.assets/'mesh'/Path(fit['source_mesh']).name).read_text(encoding='utf-8'))
                rotation=R.from_quat(fit['rotation_xyzw']).as_matrix();source=np.asarray(fit['source_handle_centre'])*16;target=np.asarray(fit['target_handle_centre'])*16
                v=[];u=[]
                for x in weapon['parts'].values():
                    raw=np.asarray(x['vertices']).reshape(-1,8);rest=(raw[:,:3]+x['pivot'])*[-1,1,1]
                    fitted=(rest-source)@rotation.T+target
                    v.append((np.c_[fitted,np.ones(len(rest))]@pose.matrix('hand_r').T)[:,:3]*battle.HEROMIRROR*battle.UNIT);u.append(raw[:,3:5])
                extra=dict(weapon=np.vstack(v),weapon_uv=np.vstack(u))
            head=skin.vertices(pose,'head')*battle.HEROMIRROR*battle.UNIT;head_uv=np.asarray(parts['head']['vertices']).reshape(-1,8)[:,3:5]
            np.savez_compressed(a.out/(label+'.npz'),hero=hero,hero_uv=np.vstack(uv),head=head,head_uv=head_uv,angel=np.empty((0,3)),angel_uv=np.empty((0,2)),**extra)
            visible=np.vstack([hero,extra['weapon']])if extra else hero
            visible=np.vstack([visible,head])
            records.append(dict(name=label,centre=((visible.min(0)+visible.max(0))/2).tolist(),extent=float(np.ptp(visible,axis=0).max()),hero_texture=f'eva_unit{key:02}.png',weapon_texture='eva02_longsword.png'if'sword'in name else'progressive_knife.png',eyes_state='normal',frame=index))
    (a.out/'manifest.json').write_text(json.dumps(dict(records=records,texture_root=str(a.assets/'textures/entity'),native=False),indent=2),encoding='utf-8')
    (a.out/'CONTINUITY.json').write_text(json.dumps(steps,indent=2),encoding='utf-8')
    print('Prepared',len(records),'actual gameplay surfaces; continuity recorded')


if __name__=='__main__':main()
