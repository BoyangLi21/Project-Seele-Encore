"""Author the requested standing roles into the actual delivered library, without QA copies."""
from pathlib import Path
import copy,json,shutil,sys
import numpy as np
from scipy.spatial.transform import Rotation
from decode_gameplay_gltf_r32 import decode
from prepare_mesh2motion_eva_r45 import human
from author_mesh2motion_roles_r45 import capture,hulls
from author_combat_r35 import Actor
import author_combat_performance_r36 as performance

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r47/runtime/projectseele-local-maps'
SOURCE=Path('C:/Users/liboy/AppData/Roaming/.minecraft/versions/Project_SEELE_Encore_R46_20261004/projectseele-local-maps')
ASSETS=ROOT/'artifacts/rebuild_r47/assets/assets/projectseele'

def main():
    if not OUT.exists():shutil.copytree(SOURCE,OUT)
    decoded=ROOT/'artifacts/rebuild_r47/motion/decoded'
    source=ROOT/'external-assets/incoming/mesh2motion-r45/mesh2motion-app/static/animations/human-base-animations.glb'
    for name in [None,'Melee_Hook','Melee_Hook_Rec','Sword_Block','Zombie_Idle','Idle_Shield','Shield_OneShot','Idle_Shield_Break']:
        target=decoded/'base'/((name or 'REST_BIND')+'.npz')
        if not target.exists():decode(name,60,source,decoded/'base')
    human_sources=OUT.parent.parent/'motion/sources';human_sources.mkdir(parents=True,exist_ok=True)
    captures={name:human(decoded/'base',name,human_sources) for name in ['Melee_Hook+Melee_Hook_Rec','Sword_Block','Zombie_Idle','Idle_Shield','Shield_OneShot','Idle_Shield_Break']}
    reports=[]
    for rig in range(3):
        file=OUT/f'eva_gameplay_r44_{rig}.json';profile=json.loads(file.read_text(encoding='utf-8'));actor=Actor(rig)
        hand=json.loads((ASSETS/f'hand_rigs/unit0{rig}/hand_rig_contract.json').read_text(encoding='utf-8'))
        actor.rig.anatomical_hand_basis_r45={}
        for side,h in hand['hands'].items():
            across=np.asarray(h['digits']['index']['joints'][0]['head_bind'])-np.asarray(h['digits']['little']['joints'][0]['head_bind'])
            actor.rig.anatomical_hand_basis_r45[side]=dict(longitudinal_bind=h['longitudinal_bind'],across_bind=across.tolist())
        points,_=hulls(rig)
        roles=[('heavy','Melee_Hook+Melee_Hook_Rec',False)]
        if rig==0:roles.extend([('shield_idle','Idle_Shield',True),('shield_brace','Shield_OneShot',False),('shield_hit','Idle_Shield_Break',False)])
        if rig==1:roles.append(('berserk_guard','Zombie_Idle',True))
        if rig==2:roles.append(('sword_guard','Sword_Block',False))
        for role,name,loop in roles:
            h,meta=captures[name];clip,report=capture(actor,h,meta,role,loop,points)
            if role=='heavy':
                # Keep the released heavy's duration/damage envelope. Only its
                # full standing performance and contact phase are replaced.
                old=profile['clips']['r32_heavy'];duration=old.get('source_duration_seconds',old['duration_seconds'])
                clip['source_duration_seconds']=duration;clip['duration_seconds']=duration
            elif role=='sword_guard':
                # Hold a standing parry at the block's peak. No attack plays
                # repeatedly while waiting, and the existing sword owns its grip.
                frame=copy.deepcopy(clip['frames'][round((len(clip['frames'])-1)*.48)])
                clip['frames']=[copy.deepcopy(frame) for _ in range(61)]
                clip['trajectory_m']=[[0,0,0] for _ in range(61)]
                clip['step_contacts']=[[True,True] for _ in range(61)]
                clip['duration_seconds']=clip['source_duration_seconds']=3.;clip['loop']=True
            profile['clips']['r32_'+role]=clip
            profile.setdefault('sources',{})[role]=dict(meta,adaptation='R47 whole-body standing performance on the existing per-unit anatomical rig',user_accepted=False)
            reports.append(dict(rig=rig,role=role,source=name,frames=len(clip['frames'])))
        profile['delivery_revision_r47']=1
        file.write_text(json.dumps(profile,separators=(',',':')),encoding='utf-8')
    (OUT.parent.parent/'motion/authoring_r47.json').write_text(json.dumps({'roles':reports,'model_geometry_changed':False,'visual_acceptance':'user'},indent=2),encoding='utf-8')
    print(json.dumps(reports),flush=True)

if __name__=='__main__':main()
