"""Freeze the working body plus selected motion clips and their runtime dependencies.

Do not carry historical higher-priority filenames into the delivery directory.
The two paused UN gameplay profiles are checked against the installed baseline.
"""
from pathlib import Path
import argparse,hashlib,json,re,shutil
from prepare_hand_delivery_r45 import portable

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(exist_ok=False,parents=True)
    target=a.out/'projectseele-local-maps';target.mkdir();rows=[];source=ROOT/'run/projectseele-local-maps'
    selected={'eva_body_r44.json':source/'eva_body_r42.json','first_battle_r44.json':source/'first_battle_r42.json'}
    for rig in range(5):
        file=ROOT/f'artifacts/rebuild_r45/motion/mesh2motion_berserk_v215/eva_gameplay_r42_{rig}.json'
        if rig>=3:assert json.loads(file.read_text())==json.loads((ROOT/f'artifacts/rebuild_r45/motion/stability_baseline_v92/eva_gameplay_r42_{rig}.json').read_text()),'Paused UN motion changed'
        selected[f'eva_gameplay_r44_{rig}.json']=file
    for name in ['sachiel_gameplay_r32.json','articulated_bodies_r35.json','angel_grip_r31.json','eva_recovery_r31.json',
            'eva_dorsal_r30.json','eva_combat_capture_r31.json','eva_combat_capture_r31_un00.json','eva_combat_capture_r31_un01.json',
            'r04_wall_plates.json','sachiel_wrap_r14.bin','nerv_command_left.nbt','tokyo3_skyscraper.nbt',
            'nerv_logo_r04.png','nerv_logo.png','tree_of_life.png','un_emblem.png','un_emblem.svg','un_markings_r11.json']:
        selected[name]=source/name
    for name,file in selected.items():
        assert file.is_file(),file;dest=target/name
        if file.suffix=='.json':
            data=portable(json.loads(file.read_text('utf8')));dest.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),'utf8')
        else:shutil.copy2(file,dest)
        rows.append(dict(source=str(file),source_sha256=sha(file),destination='projectseele-local-maps/'+name,sha256=sha(dest)))
    config=a.out/'config/projectseele-runtime-r45.properties';config.parent.mkdir()
    # No captured high-knee replacement or unconnected draw clips are promoted.
    config.write_text('schema=projectseele.runtime-owners.r45.v1\nweapon_handling=false\ncannon_contact=true\ncaptured_support=false\ncaptured_locomotion_directory=\n'
        'city.union.client.enabled=false\ncity.union.client.required=false\ncity.union.client.create_class_sha256=\ncity.union.client.proof_sha256=\n'
        'city.union.server.enabled=false\ncity.union.server.required=false\ncity.union.server.create_class_sha256=\ncity.union.server.proof_sha256=\n','utf8')
    rows.append(dict(source='root explicit production owner choice',destination='config/projectseele-runtime-r45.properties',sha256=sha(config)))
    (a.out/'manifest.json').write_text(json.dumps(dict(schema='projectseele.selected-motion-delivery.r45.v1',files=rows,
        notes=['Body/ordinary walking/running retain the actually exercised base; no wholesale high-knee replacement.',
               'New Mesh2Motion roles selected explicitly; no higher-priority historical gameplay filenames.',
               'Knife draw/stow lacks the complete current rig/mechanism integration: retain working equipment changes, do not enable the incomplete owner.',
               'TV sprint supplement and complete shield equipment remain uninstalled; source candidates retained separately.',
               'UN profiles equal the installed baseline; no UN model changes.',
               'Server and art acceptance are reserved to the user.'],world_written=False),ensure_ascii=False,indent=2))
    print('Frozen runtime files',len(rows))
if __name__=='__main__':main()
