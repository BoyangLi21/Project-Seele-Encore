"""Replay verified R41 static deltas, preserving the owner's actual R40 progress."""
from pathlib import Path
import argparse,copy,gzip,hashlib,json,shutil
import nbtlib
import compose_world_r40 as prior
import regional_voxels as v

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41'
SOURCE=ART/'source_world_backup';REVIEW=ROOT/'run/saves/SEELE_FIELD_R41_REVIEW'
OUT=ART/'world_composition';DEST=OUT/'ready/SEELE_R41_WORLD'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main(apply=False):
    OUT.mkdir(parents=True,exist_ok=True)
    prior.ART=ART;prior.SOURCE=SOURCE;prior.REVIEW=REVIEW;prior.OUT=OUT
    receipts,cells,tags,conflicts=prior.inventory();measured=prior.states(SOURCE,set(cells)|set(tags))
    conflicts += [dict(kind='baseline',pos=q,expected=b,actual=measured.get(q)) for q,(b,a) in cells.items() if measured.get(q)!=b]
    report=dict(receipts=[str(r) for r in receipts],unique_cells=len(cells),changed_cells=sum(a!=b for a,b in cells.values()),nbt_only=len(tags),conflicts=conflicts)
    (OUT/'preflight.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    assert not conflicts,('Static receipt chain differs from owner baseline',conflicts[:5])
    if not apply:print({k:v for k,v in report.items() if k not in ('receipts','conflicts')});return
    from release_combat_r36 import guard
    guard();assert not DEST.exists() and not (OUT/'composed.json').exists(),'Never overwrite a composed release'
    acceptance=json.loads((ART/'native_acceptance.json').read_text('utf8'));assert acceptance['passed']
    allpos=set(cells)|set(tags);owner_tags=prior.entities(SOURCE,allpos);review_tags=prior.entities(REVIEW,allpos)
    v.WORLD=DEST;v.OUT=OUT;p=v.Painter();fields=[]
    changed={q:(b,a) for q,(b,a) in cells.items() if b!=a}
    for q,(before,after) in sorted(changed.items()):
        p.match((*q,*q),before,after,'r41/owner_static_composition')
        if q in review_tags:
            assert q not in owner_tags or str(owner_tags[q].get('id')) in ('projectseele:station_departure_board','minecraft:sign'),('Unexpected device replacement',q)
            p.block_entities[q]=copy.deepcopy(review_tags[q])
    for q,row in tags.items():
        if q in changed:continue
        old=nbtlib.parse_nbt(row['before']) if row['before'] else nbtlib.Compound();after=nbtlib.parse_nbt(row['after'])
        original=owner_tags.get(q);merged=copy.deepcopy(original) if original is not None else nbtlib.Compound()
        names=prior.changed_fields(old,after)
        for name in names:
            assert original is None or original.get(name)==old.get(name),('Owner NBT field changed',q,name)
            if name in after:merged[name]=copy.deepcopy(after[name])
            else:merged.pop(name,None)
        if original is None:merged=copy.deepcopy(after)
        p.update_block_entity(q,measured[q],original,merged,'r41/derived_wayfinding_fields');fields.append(dict(pos=q,fields=sorted(names)))
    shutil.copytree(SOURCE,DEST)
    if not (DEST/'session.lock').exists():(DEST/'session.lock').write_bytes(bytes.fromhex('e29883'))
    p.meta.update(source=str(SOURCE),receipts=[str(r) for r in receipts],preserved='Original player/entity/mission/MTR state; no review progress copied',nbt_fields=fields)
    p.apply('static_world')
    metadata=['nerv_routes_r24.json.gz','regional_states.json','native_collision_shapes.json']
    for name in metadata:shutil.copy2(REVIEW/name,DEST/name)
    # Only actual public passages belong in the navigation/regression catalogue;
    # perimeter probes intentionally pointing into voids remain separate.
    catalogue=json.loads((ART/'final_public_passages.json').read_text('utf8'))
    evidence=json.loads((ART/'final_passage_evidence.json').read_text('utf8'));by_id={r['id']:r for r in evidence}
    for route in catalogue:
        proof=by_id[route['id']];assert proof['status']=='pass',route['id']
        for key in ('path','start','end'):
            if key in route:assert proof[key]==route[key],('Unverified final route',route['id'],key)
    (DEST/'quality_walk_cases.json').write_text(json.dumps(catalogue,ensure_ascii=False),'utf8')
    (DEST/'quality_native_walk_results.json').write_text(json.dumps(evidence,ensure_ascii=False),'utf8')
    manifest=json.loads((ART/'navigation/navigation_manifest.json').read_text('utf8'))
    assert sha(DEST/manifest['file'])==manifest['sha256'],'Delivered navigation must match the measured candidate'
    with gzip.open(DEST/manifest['file'],'rt',encoding='utf8') as f:nav=json.load(f)
    assert len(nav['nodes'])==manifest['nodes']
    actual=prior.states(DEST,set(changed));assert all(actual[q]==after for q,(_,after) in changed.items()),'Delivered geometry differs from recorded repair'
    # Give the independent save a clear visible name without changing any
    # other level.dat field, including player position and completed missions.
    level=nbtlib.load(DEST/'level.dat');before=copy.deepcopy(level['Data']);level['Data']['LevelName']=nbtlib.String('Project SEELE R41');level.save()
    reread=nbtlib.load(DEST/'level.dat')['Data'];reread['LevelName']=before['LevelName'];assert reread.snbt()==before.snbt()
    allowed=set(metadata)|{'quality_walk_cases.json','quality_native_walk_results.json','level.dat'}
    prefix='dimensions/projectseele/geofront/region/';preserved=0
    for path in SOURCE.rglob('*'):
        if not path.is_file():continue
        name=path.relative_to(SOURCE).as_posix()
        if name in allowed or name.startswith(prefix):continue
        assert sha(path)==sha(DEST/name),('Unrelated owner file changed',name);preserved+=1
    report.update(destination=str(DEST),native_routes=len(catalogue),unchanged_source_files_checked=preserved,metadata=metadata,delivered_navigation=manifest,level_name_only=True)
    (OUT/'composed.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('Composed verified owner world',report['changed_cells'],len(catalogue),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
