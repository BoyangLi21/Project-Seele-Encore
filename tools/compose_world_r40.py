"""Compose only recorded static R40 deltas onto the untouched owner save.

Never copy the review's players, entities, mission progress or transit database.
This first pass inventories/preflights the receipt chain; applying is explicit.
"""
from pathlib import Path
from collections import defaultdict
import argparse,json,hashlib,shutil,copy
import numpy as np
import nbtlib
import regional_voxels as v
from query_blocks import iter_selected_sections,iter_block_entities

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/world_combat_r40';REVIEW=ROOT/'run/saves/SEELE_FIELD_R40_REVIEW'
OUT=ART/'world_composition';SOURCE=ART/'source_world_backup'


def inventory():
    receipts=[]
    for p in ART.rglob('receipt.json'):
        if 'source_world_backup' in p.parts or 'world_composition' in p.parts:continue
        row=json.loads(p.read_text('utf8'))
        if Path(row.get('world','')).resolve()==REVIEW.resolve():receipts.append(p)
    receipts.sort(key=lambda p:p.parent.name)
    cells={};nbt={};conflicts=[]
    for receipt in receipts:
        folder=receipt.parent
        for path in sorted((folder/'delta').glob('c.*.npz')):
            _,cx,cz,_=path.name.split('.');cx=int(cx);cz=int(cz)
            with np.load(path) as d:
                for off,b,a in zip(d['offsets'],d['palette'][d['before']],d['palette'][d['after']]):
                    off=int(off);q=(cx*16+off%16,int(d['minimum'])+off//256,cz*16+off//16%16)
                    if q in cells:
                        first,prior=cells[q]
                        if prior!=b:conflicts.append(dict(kind='chain',pos=q,prior=prior,next_before=str(b),receipt=str(receipt)))
                    else:first=str(b)
                    cells[q]=(first,str(a))
        for row in json.loads((folder/'block_entity_deltas.json').read_text('utf8')):
            q=tuple(row['position'])
            if q not in nbt:nbt[q]=dict(row)
            else:nbt[q]['after']=row['after']
    return receipts,cells,nbt,conflicts


def states(world,positions):
    selected=defaultdict(set)
    for x,y,z in positions:selected[x//16,z//16].add(y//16)
    result={}
    bysection=defaultdict(list)
    for q in positions:bysection[q[0]//16,q[2]//16,q[1]//16].append(q)
    for cx,cz,sy,palette,indices in iter_selected_sections(world,v.DIM,selected):
        for q in bysection[cx,cz,sy]:result[q]=palette[int(indices[((q[1]&15)<<8)|((q[2]&15)<<4)|(q[0]&15)])]
    return result


def entities(world,positions):
    lo=tuple(min(p[i] for p in positions) for i in range(3));hi=tuple(max(p[i] for p in positions) for i in range(3))
    chunks={(p[0]//16,p[2]//16) for p in positions}
    return {p:t for p,t in iter_block_entities(world,v.DIM,lo,hi,selected_chunks=chunks) if p in positions}


def changed_fields(original,after):
    return {k for k in set(original)|set(after) if original.get(k)!=after.get(k)}


def main(apply=False):
    OUT.mkdir(parents=True,exist_ok=True)
    receipts,cells,nbt,conflicts=inventory();measured=states(SOURCE,set(cells)|set(nbt))
    for q,(before,_) in cells.items():
        if measured.get(q)!=before:conflicts.append(dict(kind='baseline',pos=q,expected=before,actual=measured.get(q)))
    report=dict(receipts=[str(p) for p in receipts],unique_cells=len(cells),changed_cells=sum(a!=b for a,b in cells.values()),
                nbt_only=len(nbt),conflicts=conflicts)
    (OUT/'preflight.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('receipts','conflicts')},ensure_ascii=False),'conflicts',len(conflicts),flush=True)
    if conflicts:raise RuntimeError('Static receipt preflight failed; see preflight.json')
    if not apply:return
    destination=OUT/'ready/SEELE_R31_WORLD';assert not (OUT/'composed.json').exists(),'Do not overwrite a completed composition'
    allpos=set(cells)|set(nbt);before_tags=entities(SOURCE,allpos);review_tags=entities(REVIEW,allpos)
    block_changes={q:pair for q,pair in cells.items() if pair[0]!=pair[1]}
    p=v.Painter();v.WORLD=destination;v.OUT=OUT
    for q,(before,after) in sorted(block_changes.items()):
        p.match((*q,*q),before,after,'r40/frozen_static_composition')
        if q in review_tags:
            assert q not in before_tags or str(before_tags[q].get('id')) in ('projectseele:station_departure_board','minecraft:sign'),('Existing device needs an explicit merge',q)
            p.block_entities[q]=copy.deepcopy(review_tags[q])
    nbt_diffs=[]
    for q,row in nbt.items():
        if q in block_changes:continue
        old=nbtlib.parse_nbt(row['before']) if row['before'] else nbtlib.Compound();new=nbtlib.parse_nbt(row['after'])
        original=before_tags.get(q);merged=copy.deepcopy(original) if original is not None else nbtlib.Compound()
        fields=changed_fields(old,new)
        for k in fields:
            assert original is None or original.get(k)==old.get(k),('NBT field changed from owner baseline',q,k)
            if k in new:merged[k]=copy.deepcopy(new[k])
            else:merged.pop(k,None)
        if original is None:
            # NBT was intentionally added to an already existing board/block.
            merged=copy.deepcopy(new)
        state=measured[q]
        p.update_block_entity(q,state,original,merged,'r40/frozen_static_nbt_fields')
        nbt_diffs.append(dict(position=q,fields=sorted(fields)))
    # Everything outside the selected chunk block arrays / explicit metadata
    # remains byte-for-byte from the owner's cold source.
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        for original in SOURCE.rglob('*'):
            if original.is_file():
                target=destination/original.relative_to(SOURCE)
                assert target.is_file() and hashlib.sha256(target.read_bytes()).digest()==hashlib.sha256(original.read_bytes()).digest(),('Prior staging already changed',target)
    else:shutil.copytree(SOURCE,destination)
    if not (destination/'session.lock').exists():(destination/'session.lock').write_bytes(bytes.fromhex('e29883'))
    p.meta.update(source=str(SOURCE),review=str(REVIEW),receipts=[str(r) for r in receipts],nbt_fields=nbt_diffs,
                  preserved='playerdata, entities, mission SavedData, MTR files and all unrelated source files')
    p.apply('static_world')
    metadata=['battlefield_r21.json','surface_lift_access_r40.json','un_air_reception_r40.json','regional_states.json','native_collision_shapes.json']
    for name in metadata:shutil.copy2(REVIEW/name,destination/name)
    catalogue={r['id']:r for r in json.loads((REVIEW/'quality_walk_cases.json').read_text('utf8'))}
    evidence={r['id']:r for r in json.loads((ART/'full_walk_merged.json').read_text('utf8'))}
    for path in [ART/'post_port_walk_raw.json',ART/'reception_review/bypass_walk_results.json']:
        for row in json.loads(path.read_text('utf8')):
            if row['status']!='pass':continue
            evidence[row['id']]=row
            if row['id'] not in catalogue:
                catalogue[row['id']]={k:row[k] for k in ('id','path','start','end','dimension') if k in row}
    for key,row in catalogue.items():
        assert key in evidence and evidence[key]['status']=='pass',key
        for field in ('path','start','end'):
            if field in row:assert row[field]==evidence[key].get(field),('Route differs from its native proof',key,field)
    (destination/'quality_walk_cases.json').write_text(json.dumps(list(catalogue.values()),ensure_ascii=False),'utf8')
    (destination/'quality_native_walk_results.json').write_text(json.dumps([evidence[k] for k in catalogue],ensure_ascii=False),'utf8')
    permitted=set(metadata)|{'quality_walk_cases.json','quality_native_walk_results.json'}
    region_prefix='dimensions/projectseele/geofront/region/'
    preserved=0
    for path in SOURCE.rglob('*'):
        if not path.is_file():continue
        name=path.relative_to(SOURCE).as_posix()
        if name in permitted or name.startswith(region_prefix):continue
        assert hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256((destination/name).read_bytes()).digest(),('Unrelated original changed',name)
        preserved+=1
    report.update(destination=str(destination),native_routes=len(catalogue),unchanged_source_files_checked=preserved,metadata=metadata)
    (OUT/'composed.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('Preserved world composed',len(catalogue),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
