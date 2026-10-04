"""Root-only exact TV personnel bridge installation in the R45 review copy."""
from pathlib import Path
import argparse, copy, hashlib, json, shutil
import regional_voxels as vox
from query_blocks import iter_block_entities
from measure_world_r40 import MeasuredWorld
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW'
OUT=ROOT/'artifacts/rebuild_r45/bridge'
PACKAGE=ROOT/'artifacts/rebuild_r44/hangar_machinery/tv_personnel_platform_package_v5_review_v3'
MODEL=ROOT/'src/main/resources/assets/projectseele/mesh/tv_shoulder_shells_r44.json'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main(apply=False):
    guard();OUT.mkdir(parents=True,exist_ok=True)
    assert not list((OUT/'installed_bridge').glob('applied_*/receipt.json')), 'Already applied; inspect existing review state'
    manifest=json.loads((PACKAGE/'manifest.json').read_text('utf8'))
    expected={r['path'].replace('\\','/'):r['sha256'] for r in manifest['files']}
    for name in ('world/operations.json','world/inverse.json','world/r44_tv_personnel_platforms.json','model/tv_shoulder_shells_r44.json'):
        assert sha(PACKAGE/name)==expected[name],('Frozen input changed',name)
    rows=json.loads((PACKAGE/'world/operations.json').read_text('utf8'))
    inverse={tuple(r['position']):r for r in json.loads((PACKAGE/'world/inverse.json').read_text('utf8'))}
    assert len(rows)==len(inverse)==427
    w=MeasuredWorld(WORLD)
    for row in rows:w.around(row['position'],1)
    w.load();points=[tuple(r['position']) for r in rows]
    lo=tuple(min(q[i] for q in points) for i in range(3));hi=tuple(max(q[i] for q in points) for i in range(3))
    tags=dict(iter_block_entities(WORLD,vox.DIM,lo,hi));conflicts=[]
    for row in rows:
        q=tuple(row['position']);back=inverse[q]
        assert back['before']==row['after'] and back['after']==row['before']
        if w.block(q)!=row['before']:conflicts.append(dict(pos=q,expected=row['before'],actual=w.block(q)))
        assert q not in tags,('Original block entity at bridge cell',q)
    report=dict(world=str(WORLD),cells=427,precondition_conflicts=conflicts,original_touched_block_entities=0,
        model_sha256=manifest['model_sha256'],metadata_sha256=expected['world/r44_tv_personnel_platforms.json'],
        old_candidate_status=manifest['status'],root_authorization='R45 owner explicitly prioritizes full bridge; apply only to a frozen private review copy',
        native_staff_admission_and_motion_validation='PENDING',visual_review='PENDING',world_written=False)
    (OUT/'preapply.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    assert not conflicts,('Inspect fresh-world bridge preconditions',conflicts[:8])
    if not apply:
        print('R45 bridge measured:',len(rows),'cells; no conflicts/BE replacement; native and visual checks remain')
        return
    (OUT/'source_asset_before').mkdir(exist_ok=True)
    shutil.copy2(MODEL,OUT/'source_asset_before'/MODEL.name)
    protected={p.relative_to(WORLD).as_posix():sha(p) for p in WORLD.rglob('*') if p.is_file()
        and any(folder in p.relative_to(WORLD).parts for folder in ('data','playerdata','entities','stats','advancements','mtr'))}
    vox.WORLD=WORLD;vox.OUT=OUT;painter=vox.Painter()
    for row in rows:
        q=tuple(row['position']);painter.match((*q,*q),row['before'],row['after'],'r45/tv_personnel_bridge_exact_component')
    painter.meta.update(root_authored_review=True,source_package=str(PACKAGE),model_sha256=manifest['model_sha256'])
    receipt=painter.apply('installed_bridge')
    shutil.copy2(PACKAGE/'world/r44_tv_personnel_platforms.json',WORLD/'r44_tv_personnel_platforms.json')
    shutil.copy2(PACKAGE/'model/tv_shoulder_shells_r44.json',MODEL)
    shape_path=WORLD/'native_collision_shapes.json';shapes=json.loads(shape_path.read_text('utf8'))
    old=ROOT/'artifacts/rebuild_r44/hangar_machinery'
    for p in old.glob('tv_personnel_*_native_v1/native_union_readback/native_collision_shapes.json'):
        for key,value in json.loads(p.read_text('utf8')).items():
            if key.startswith(('projectseele:tv_personnel_deck_r44','projectseele:tv_personnel_guard_r44')):shapes[key]=value
    shape_path.write_text(json.dumps(shapes,ensure_ascii=False),'utf8')
    assert all(sha(WORLD/name)==digest for name,digest in protected.items()),'Runtime progress or complete entity data changed'
    assert sha(MODEL)==manifest['model_sha256']
    report.update(world_written=True,receipt=receipt,progress_files_unchanged=len(protected))
    (OUT/'installation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('R45 review bridge installed:',len(rows),'cells; protected progress files',len(protected),'unchanged')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args();main(a.apply)
