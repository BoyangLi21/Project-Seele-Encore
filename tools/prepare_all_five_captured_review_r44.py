"""Freeze independent V19 captures; no runtime loader property or install."""
from pathlib import Path
import json,hashlib,shutil

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44/combat';OUT=ART/'all_five_captured_locomotion_v19_stable';OUT.mkdir(parents=True,exist_ok=True);body=json.loads((ROOT/'.Codex/r44-network-client/projectseele-local-maps/eva_body_r43.json').read_text('utf8'));rows=[]
for rig,actor in enumerate(('eva_unit00','eva_unit01','eva_unit02','eva_prototype','eva_un01')):
    directory=ART/('locomotion_floor_contact_full_v19'if rig==1 else'all_body_contact_v19/'+actor);name=f'eva_locomotion_capture_r44_{rig}.json';source=directory/name;receipt=json.loads((directory/'captured_runtime_export_receipt.json').read_text('utf8'));digest=hashlib.sha256(source.read_bytes()).hexdigest();assert digest==receipt['sha256'];profile=json.loads(source.read_text('utf8'));assert profile['rig_key']==rig and profile['rig_contract_r44']==body['rigs'][str(rig)]
    assert all(n in profile['clips']for n in('idle','walk','run','stand_to_walk','walk_to_run','brake','to_prone','prone_hold','crawl','from_prone','stand'))
    shutil.copy2(source,OUT/name);rows.append(dict(rig=rig,actor=actor,file=name,sha256=digest,clip_frames={n:len(c['frames'])for n,c in profile['clips'].items()},missing=profile['missing'],state='UNAPPROVED complete capture export, native/artist untested'))
manifest=dict(schema='projectseele.private-capture-review.r44',rigs=rows,enabled_in_game=False,default_promoted=False,loader_property='projectseele.capturedLocomotionDirectory',scope='Private complete independently authored V19 profiles. Crouch walking/reverse/turning/weapon grips and actual native support remain open. File presence is not active clip coverage.')
(OUT/'capture_review_manifest.json').write_text(json.dumps(manifest,indent=2),'utf8');print(json.dumps(dict(path=str(OUT),rigs={r['rig']:r['sha256']for r in rows}),indent=2))
