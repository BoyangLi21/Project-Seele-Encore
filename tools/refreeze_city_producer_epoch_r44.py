"""Fresh immutable execution epochs for an unchanged uninstalled city geometry."""
from pathlib import Path
import argparse,gzip,json,shutil,hashlib,math,ast
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,AIR
from regional_voxels import Painter
from information_fixture_guard_r44 import retained_faces

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);p.add_argument('--revision',default='v2');p.add_argument('--extra-source',type=Path,action='append',default=[]);a=p.parse_args();contract=a.plan/('construction_contract_refrozen_'+a.revision+'.json');assert not contract.exists()
    old=json.loads((a.plan/'construction_contract.json').read_text('utf8'));rows=[json.loads(s) for s in gzip.open(a.plan/'forward.jsonl.gz','rt',encoding='utf8')];w=MeasuredWorld(WORLD);painter=Painter()
    for r in rows:
        q=tuple(r['pos']);w.around(q,0);painter.match((*q,*q),r['before'],r['after'],r['owner'])
        if r.get('after_nbt') is not None:painter.block_entities[q]=nbtlib.parse_nbt(r['after_nbt'])
    w.load();lo=tuple(min(r['pos'][k] for r in rows) for k in range(3));hi=tuple(max(r['pos'][k] for r in rows) for k in range(3));tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    errors=[]
    for r in rows:
        q=tuple(r['pos']);observed=w.block(q);tag=tags[q].snbt() if q in tags else None
        if observed!=r['before'] or tag!=r.get('before_nbt'):errors.append(dict(pos=q,expected=r['before'],observed=observed,expected_nbt=r.get('before_nbt'),observed_nbt=tag))
    faces=retained_faces(painter,WORLD,'projectseele:geofront');conflicts=[]
    for r in rows:
        q=tuple(r['pos']);owner=faces.get((q[0]//16,q[2]//16),{}).get(q)
        if owner and r['after']!=r['before'] and r['after'].split('[')[0] not in AIR|{'minecraft:light'}:conflicts.append(dict(pos=q,retained_information_fixture=owner,after=r['after']))
    folder=a.plan/('source_inputs_refrozen_'+a.revision);folder.mkdir();files=[Path(e['original_path']) for e in old['source_epochs']]
    files.extend([ROOT/'tools/information_fixture_guard_r44.py',Path(__file__)]+[f.resolve() for f in a.extra_source]);files=list(dict.fromkeys(files));seen=set(files);todo=list(files)
    while todo:
        f=todo.pop()
        if f.suffix!='.py':continue
        module=ast.parse(f.read_text('utf8'))
        for node in ast.walk(module):
            modules=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) and node.module else []
            for name in modules:
                for base in [f.parent,ROOT/'tools']:
                    dependency=base/(name.replace('.','/')+'.py')
                    if dependency.exists() and dependency not in seen:seen.add(dependency);files.append(dependency);todo.append(dependency)
    epochs=[]
    for i,f in enumerate(files):
        copy=folder/(str(i).zfill(2)+'_'+f.name);shutil.copy2(f,copy);epochs.append(dict(path=str(copy.resolve()),original_path=str(f.resolve()),sha256=sha(copy),immutable_snapshot=True))
    update=dict(old,source_epochs=epochs,exact_current_preconditions_passed=not errors,exact_errors=errors,retained_wide_fixture_face_guard_passed=not conflicts,retained_fixture_conflicts=conflicts,
        root_may_apply_to_single_review_world=old['static_full_component_passed'] and not errors and not conflicts and old['station_journeys_complete'],
        refrozen_from=str((a.plan/'construction_contract.json').resolve()),refrozen_from_sha256=sha(a.plan/'construction_contract.json'),geometry_rebuilt=False,current_world_written=False)
    if (a.plan/'delta_provenance.json').exists():
        district=json.loads((a.plan/'new_district.json').read_text('utf8'))
        update.update(new_buildings=0,new_occupied_floors=0,complete_existing_building_components_reviewed=len(district['buildings']),complete_existing_floor_planes_reviewed=len(district['floors']),
            scope='Exact current-state repair of complete installed components. Counts describe reviewed existing buildings/floors; no original whole-city forward is replayed.',
            requires_before_apply=[s for s in update['requires_before_apply']if not s.startswith('This forward contains')]+['Only the precise forward/inverse in this contract is authorized; original installed building/city forwards must not be replayed.'])
    contract.write_text(json.dumps(update,ensure_ascii=False,indent=2),'utf8');print(a.plan.name,'fresh immutable epochs',len(epochs),'exact_errors',len(errors),'retained_face_conflicts',len(conflicts),'ready',update['root_may_apply_to_single_review_world'],flush=True)


if __name__=='__main__':main()
