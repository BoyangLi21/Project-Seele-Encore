"""Decode the relevant pinned animation families without installing any gameplay assets."""
from pathlib import Path
import argparse,json,hashlib
from decode_gameplay_gltf_r32 import decode

ROOT=Path(__file__).resolve().parents[1]
SELECTED={
    'base':['Idle_A','Walk','Jog','Sprint','Crouch_Idle','Crouch_Walk','Jump_Start','Jump_air','Jump_Land',
            'Roll_RM','Shield_Dash_RM','Hit_Chest','Hit_Head','Hit_Knockback_RM','Death_D','LayToIdle',
            'Idle_Shield','Idle_Shield_Break','Shield_OneShot','Sword_Regular_A','Sword_Regular_A_Rec',
            'Sword_Regular_B','Sword_Regular_B_Rec','Sword_Regular_C','Sword_Regular_C_RM','Sword_Regular_Combo',
            'Sword_Attack_RM','Sword_Block','Idle_Sword','Push','PickUp_Table','Walk_Carry','Zombie_Idle','Zombie_Scratch','Zombie_Walk'],
    'addon':['Crawl RM','Walk_Large','Zombie_Idle_Crouch','Zombie_Walk_2','Zombie Yell','Zombie_Rise',
             'Attack_Ground_Pound','Dodge_left_RM','Dodge_right_RM','Dodge_back_RM','Death_A','Death_B','Death_C',
             'Run_Anime','Power Up','Two-hand Blast','Kneeling Tired','Land_Three_Point'],
    'mocap':['Kick_Breach','Turn_Left_90','Turn_Right_90','Turn_Left_180','Turn_Right_180']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    sources=ROOT/'external-assets/incoming/mesh2motion-r45/mesh2motion-app/static/animations';rows=[]
    for family,clips in SELECTED.items():
        source=sources/f'human-{family}-animations.glb';digest=hashlib.sha256(source.read_bytes()).hexdigest();folder=a.out/family
        for clip in [None,*clips]:
            file=decode(clip,60,source,folder);rows.append(dict(family=family,clip=clip or 'REST_BIND',source=str(source),source_sha256=digest,
                decoded=str(file),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),source_kind='mocap' if family=='mocap' else 'authored animation',game_installed=False))
            print(family,clip or 'REST_BIND',flush=True)
    (a.out/'provenance.json').write_text(json.dumps(dict(sources=rows,license='CC0-1.0',retargeted=False,world_changed=False,accepted=False),indent=2))

if __name__=='__main__':main()
