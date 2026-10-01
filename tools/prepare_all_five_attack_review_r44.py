"""Freeze all five completed V4 full-body attack exports for native review."""
from pathlib import Path
import hashlib,json,shutil

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44/combat'
OUT=ART/'all_five_attack_runtime_v4_stable_planes';OUT.mkdir(parents=True,exist_ok=True)
BASE=ART/'attack_runtime_unit01_v4_stable_planes';OTHER=ART/'all_attack_contact_v4_stable_planes/runtime_profiles'
FILES={};rows=[]
for rig,actor in enumerate(('eva_unit00','eva_unit01','eva_unit02','eva_prototype','eva_un01')):
    name=f'eva_gameplay_r44_{rig}.json';source=(BASE if rig==1 else OTHER)/name;profile=json.loads(source.read_text('utf8'))
    receipt=ART/('complete_attack_contact_unit01_v4_stable_planes'if rig==1 else'all_attack_contact_v4_stable_planes/'+actor)/'current_attack_export_receipt.json';record=json.loads(receipt.read_text('utf8'))
    digest=hashlib.sha256(source.read_bytes()).hexdigest();assert digest==record['sha256']and profile['rig_key']==rig
    new=profile['r44_complete_attack_authoring']['newly_authored_clips'];assert set(new)=={'r32_guard','r32_jab','r32_cross','r32_hook','r32_heavy'}
    shutil.copy2(source,OUT/name);FILES[name]=digest
    rows.append(dict(rig=rig,actor=actor,sha256=digest,newly_authored=new,inherited_unapproved=profile['r44_complete_attack_authoring']['inherited_unverified_clips'],native_current_scope='Unit01 V4 normals only; visual FAIL'if rig==1 else'No V4 native run yet'))
name='sachiel_gameplay_r44.json';shutil.copy2(BASE/name,OUT/name);FILES[name]=hashlib.sha256((OUT/name).read_bytes()).hexdigest()
identity=hashlib.sha256(json.dumps(FILES,sort_keys=True,separators=(',',':')).encode()).hexdigest()
manifest=dict(revision=44,bundle_id='R44-FIVE-ATTACK-PRIVATE-'+identity[:16],files=FILES,status='PRIVATE_UNAPPROVED_NATIVE_TARGET_PLANE_CANDIDATE',newly_authored_scope='All five independent guard/jab/cross/hook/heavy exports; inherited low-target/crouch/prone/weapon/jump/reaction/finisher remain FAIL/unverified',default_promoted=False)
(OUT/'combat_bundle_r44.json').write_text(json.dumps(manifest,indent=2),'utf8');(OUT/'coverage_contract.json').write_text(json.dumps(dict(rigs=rows,sachiel_gameplay='Inherited unapproved, not C6 skin binding; active fall/recovery still FAIL',captured_locomotion='V19 separate complete profiles exist but this directory does not enable them',quality='No visual/native acceptance inferred from completed source/export counts',numeric_balance_changed=False),indent=2),'utf8')
print(json.dumps(dict(path=str(OUT),manifest=manifest['bundle_id'],rig_sha256={r['rig']:r['sha256']for r in rows}),indent=2))
