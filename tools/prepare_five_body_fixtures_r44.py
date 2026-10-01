"""All five actual rigs, without copying Unit-01's proportions into the UN pair."""
from pathlib import Path
import json
from prepare_tv_exchange_r44 import fixture,sha

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r44/combat/five_body_contact_calibration'
physics_path=ROOT/'.Codex/r44-combat-query-server/projectseele-local-maps/articulated_bodies_r35.json'
physics=json.loads(physics_path.read_text('utf8'))['models']
source_card=json.loads((ROOT/'artifacts/rebuild_r44/combat/locomotion_sequence_v2/source_card.json').read_text('utf8'))
mapping={'0':'eva_unit00','1':'eva_unit01','2':'eva_unit02','3':'eva_prototype','4':'eva_un01'}
rows=[]
for key,name in mapping.items():
    destination=OUT/name;destination.mkdir(parents=True,exist_ok=True)
    actor=fixture(name,key,physics[key])
    doc=dict(schema='projectseele.actual-body-contact-fixture.r44',actors=[actor],units='Minecraft blocks, Blender Z up, +Y forward',fps=30,duration=source_card['frames']/30,
             physics_sha256=sha(physics_path),source_motion_card=source_card,
             quality='UNAPPROVED. Actual per-rig proportions and neutral mesh measured; shared capture has not yet been verified on this target. No production installation.')
    path=destination/'fixture.json';path.write_text(json.dumps(doc,separators=(',',':')),'utf8')
    rows.append(dict(variant=int(key),actor=name,fixture_sha256=sha(path),geo_sha256=actor['geo_sha256'],mesh_sha256=actor['mesh_sha256'],
                     joints=actor['joints'],actual_boot_neutral_minimum_z={s:actor['toes'][s]['rest_floor'] for s in ('l','r')},
                     bones=len(actor['bones']),vertices=len(actor['vertices']),motion_verified=False,artistic_acceptance=False))
(OUT/'actual_five_body_calibration.json').write_text(json.dumps(dict(rigs=rows,scope='Measured actual private runtime assets; no cross-rig pose copy, no acceptance or installation inferred'),indent=2),'utf8')
print(json.dumps([dict(actor=r['actor'],bones=r['bones'],vertices=r['vertices']) for r in rows]))
