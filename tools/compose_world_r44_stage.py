"""R44 stage composition: recorded static work, original owner progress."""
from pathlib import Path
from collections import defaultdict
import argparse,copy,gzip,hashlib,json,re,shutil
import numpy as np
import nbtlib
import compose_world_r40 as prior
import regional_voxels as vox
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/rebuild_r44';SOURCE=ART/'source_world_backup'
REVIEW=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';OUT=ART/'world_composition'
DEST=OUT/'ready/SEELE_R44_STAGE_WORLD'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def stamp(p):
    m=re.search(r'(\d{8}_\d{6})(?:_(\d+))?',p.parent.name)
    assert m,p
    return m.group(1),m.group(2)or'0',str(p)

def inventory():
    paths=[Path(p) for p in json.loads((OUT/'receipt_inventory.json').read_text())]
    paths.sort(key=stamp);cells={};tags={};biomes={};actors=[];conflicts=[];used=[]
    for p in paths:
        folder=p.parent;receipt=json.loads(p.read_text())
        assert Path(receipt['world']).resolve()==REVIEW.resolve()
        if (folder/'delta').is_dir():
            used.append(p)
            for f in sorted((folder/'delta').glob('c.*.npz')):
                _,cx,cz,_=f.name.split('.');cx=int(cx);cz=int(cz)
                with np.load(f) as d:
                    palette=d['palette'];base=int(d['minimum'])
                    for off,bi,ai in zip(d['offsets'],d['before'],d['after']):
                        o=int(off);q=(cx*16+o%16,base+o//256,cz*16+o//16%16);b=str(palette[bi]);a=str(palette[ai])
                        first,before=cells.get(q,(b,b))
                        if before!=b:conflicts.append(dict(kind='block_chain',pos=q,prior=before,next_before=b,receipt=str(p)))
                        cells[q]=(first,a)
            f=folder/'block_entity_deltas.json'
            assert f.exists(),('Missing explicit full-NBT delta file',p)
            for row in json.loads(f.read_text()):
                q=tuple(row['position'])
                if q not in tags:tags[q]=dict(row)
                else:
                    if tags[q]['after']!=row['before']:conflicts.append(dict(kind='nbt_chain',pos=q,receipt=str(p)))
                    tags[q]['after']=row['after']
        elif 'forward_biomes' in receipt:
            # Block work already has a nested Painter receipt. Do not replay
            # this parent summary a second time.
            if receipt['forward_biomes'] not in ('None','',None):
                f=Path(receipt['forward_biomes']);f=f if f.is_absolute() else ROOT/f
                for row in json.loads(f.read_text()):
                    key=(*row['chunk'],row['section_y'])
                    if key in biomes:
                        if nbtlib.parse_nbt(biomes[key]['after_snbt'])!=nbtlib.parse_nbt(row['before_snbt']):conflicts.append(dict(kind='biome_chain',section=key,receipt=str(p)))
                        biomes[key]['after_snbt']=row['after_snbt']
                    else:biomes[key]=copy.deepcopy(row)
        elif receipt.get('blocks_changed')==0 and receipt.get('verified_full_NBT') and 'uuid' in receipt:
            actors.append(dict(receipt=str(p),**receipt))
        else:raise RuntimeError(('Unknown receipt schema',p))
    return paths,used,cells,tags,biomes,actors,conflicts

def preflight():
    guard();OUT.mkdir(exist_ok=True)
    paths,used,cells,tags,biomes,actors,conflicts=inventory()
    report=dict(receipts=len(paths),static_receipts=len(used),unique_cells=len(cells),nbt_records=len(tags),biome_sections=len(biomes),explicit_actor_deltas=actors,conflicts=conflicts)
    (OUT/'chain_preflight.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print({k:report[k] for k in ('receipts','static_receipts','unique_cells','nbt_records','biome_sections')},'conflicts',len(conflicts),flush=True)
    with gzip.open(OUT/'composed_static_chain.jsonl.gz','wt',encoding='utf8') as f:
        for q,(b,a) in sorted(cells.items()):f.write(json.dumps(dict(pos=q,before=b,after=a),ensure_ascii=False)+'\n')
    (OUT/'composed_tag_chain.json').write_text(json.dumps([dict(pos=q,**r) for q,r in tags.items()],ensure_ascii=False),'utf8')
    (OUT/'composed_biome_chain.json').write_text(json.dumps(list(biomes.values()),ensure_ascii=False),'utf8')
    print('Complete chain persisted; no release world written',flush=True)

def check_source():
    guard();source_errors=[];review_errors=[];new_chunks=set();count=0
    def inspect(rows):
        nonlocal count
        if not rows:return
        s=MeasuredWorld(SOURCE);r=MeasuredWorld(REVIEW)
        for row in rows:
            q=tuple(row['pos']);s.box(q,q);r.box(q,q)
        s.load();r.load()
        for row in rows:
            q=tuple(row['pos']);old=s.block(q);actual=r.block(q);count+=1
            if old is None:
                if (q[0]//16,q[2]//16) not in s.status:new_chunks.add((q[0]//16,q[2]//16))
                else:source_errors.append(dict(pos=q,expected=row['before'],actual=None,status=s.status.get((q[0]//16,q[2]//16))))
            elif old!=row['before']:source_errors.append(dict(pos=q,expected=row['before'],actual=old))
            if actual!=row['after']:review_errors.append(dict(pos=q,expected=row['after'],actual=actual))
    current=None;rows=[]
    with gzip.open(OUT/'composed_static_chain.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            row=json.loads(line);cx=row['pos'][0]//16
            if current is not None and cx!=current:inspect(rows);rows=[]
            current=cx;rows.append(row)
        inspect(rows)
    result=dict(cells=count,source_errors=source_errors,review_runtime_differences=review_errors,new_generated_chunks=sorted(new_chunks),world_written=False)
    (OUT/'source_readback_preflight.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('Cells',count,'source mismatches',len(source_errors),'review differences',len(review_errors),'new chunks',len(new_chunks),flush=True)

def compose():
    from query_blocks import dimension_dir
    from transplant_s22_authority import read_region,parse_chunk,build_region,chunk_blob
    from apply_s20_approved_semantic_repairs import atomic_replace
    import sys
    guard()
    proto=json.loads((OUT/'raw_protochunk_preflight.json').read_text())
    pending={tuple(row['chunk']) for row in proto['selected_source_chunks'] if row['status']!='minecraft:full'}
    assert len(pending)==21
    pending_regions=defaultdict(set)
    for cx,cz in pending:pending_regions[f'r.{cx//32}.{cz//32}.mca'].add((cx&31)+(cz&31)*32)
    if DEST.exists():
        assert not (OUT/'composed.json').exists(),'Never overwrite a completed stage world'
        for file in DEST.rglob('*'):
            if file.is_file():
                original=SOURCE/file.relative_to(DEST)
                if file.name=='session.lock':continue
                assert original.is_file(),('Unexpected partial stage file',file)
                if sha(original)==sha(file):continue
                assert file.parent==dimension_dir(DEST,vox.DIM)/'region' and file.name in pending_regions,('Partial stage differs; preserve and inspect before retry',file)
                original_stamps,original_blobs=read_region(original);actual_stamps,actual_blobs=read_region(file)
                _,ready_blobs=read_region(dimension_dir(REVIEW,vox.DIM)/'region'/file.name)
                assert original_stamps==actual_stamps,('Partial region timestamps differ',file)
                assert len(original_blobs)==len(actual_blobs)==len(ready_blobs)==1024
                for slot in range(1024):
                    if actual_blobs[slot]==original_blobs[slot]:continue
                    assert slot in pending_regions[file.name] and actual_blobs[slot]==ready_blobs[slot],('Unexpected partial chunk change',file,slot)
    chain=json.loads((OUT/'chain_preflight.json').read_text());assert not chain['conflicts']
    baseline=json.loads((ART/'baseline.json').read_text());owner=Path(baseline['source'])
    for name,digest in baseline['files'].items():assert sha(owner/name)==digest,('Owner file changed',name)
    excluded={(64,-361,302):'Unverified optional lift display: original and final runtime are AIR; preserve original until its support/maintenance owner is repaired.'}
    authored={}
    receipts=[Path(p) for p in json.loads((OUT/'receipt_inventory.json').read_text())]
    for receipt in sorted(receipts,key=stamp):
        if not (receipt.parent/'delta').is_dir():continue
        f=receipt.parent.parent/'block_entities.json'
        for row in json.loads(f.read_text()):authored[tuple(row['pos'])]=nbtlib.parse_nbt(row['snbt'])
    updates={tuple(row['pos']):row for row in json.loads((OUT/'composed_tag_chain.json').read_text())}
    for q,row in updates.items():
        if row.get('after'):authored[q]=nbtlib.parse_nbt(row['after'])
    generated=json.loads((OUT/'city_archive_closeout/native_initialized_be_candidates.json').read_text())
    assert isinstance(generated,list)
    for row in generated:authored[tuple(row['pos'])]=nbtlib.parse_nbt(row['after_full_nbt'])
    selected=defaultdict(set);wanted=set(authored)|set(updates);final_states={};groups=defaultdict(list);total=changed=0
    with gzip.open(OUT/'composed_static_chain.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            row=json.loads(line);q=tuple(row['pos']);x,y,z=q;total+=1
            if q in wanted:final_states[q]=row['after']
            selected[x//16,z//16].add(y//16)
            if q in excluded or (x//16,z//16) in pending or row['before']==row['after']:continue
            b=sys.intern(row['before']);a=sys.intern(row['after']);groups[(x//16,y,z,b,a)].append(x);changed+=1
    # NBT-only station diagrams may live outside every edited voxel chunk.
    # Read their original complete tags too, before merging explicit fields.
    all_chunks=set(selected)|{(q[0]//16,q[2]//16) for q in wanted}
    lo=(min(x for x,z in all_chunks)*16,-672,min(z for x,z in all_chunks)*16)
    hi=(max(x for x,z in all_chunks)*16+15,319,max(z for x,z in all_chunks)*16+15)
    source_tags=dict(iter_block_entities(SOURCE,vox.DIM,lo,hi,selected_chunks=all_chunks))
    # Brand-new default containers only; never substitute QA inventory content.
    for row in generated:assert tuple(row['pos']) not in source_tags and final_states.get(tuple(row['pos']))==row['after']
    DEST.parent.mkdir(parents=True,exist_ok=True)
    if not DEST.exists():shutil.copytree(SOURCE,DEST)
    if not (DEST/'session.lock').exists():(DEST/'session.lock').write_bytes(bytes.fromhex('e29883'))
    # These chunks existed only as world-generation prototypes in the owner
    # backup. Bring across their actual completed terrain, not QA entities/data.
    by_region=defaultdict(list)
    for cx,cz in pending:by_region[cx//32,cz//32].append((cx,cz))
    proto_proof=[]
    for (rx,rz),chunks in by_region.items():
        target=dimension_dir(DEST,vox.DIM)/f'region/r.{rx}.{rz}.mca';source=dimension_dir(REVIEW,vox.DIM)/'region'/target.name
        stamps,blobs=read_region(target);_,ready=read_region(source);_,original_blobs=read_region(dimension_dir(SOURCE,vox.DIM)/'region'/target.name)
        for cx,cz in chunks:
            slot=(cx&31)+(cz&31)*32;old=parse_chunk(original_blobs[slot]);new=parse_chunk(ready[slot]);assert str(old['Status'])!='minecraft:full' and str(new['Status'])=='minecraft:full'
            assert blobs[slot] in (original_blobs[slot],ready[slot]),('Prototype resume precondition',cx,cz)
            proto_proof.append(dict(chunk=[cx,cz],before_status=str(old['Status']),source_blob_sha256=hashlib.sha256(original_blobs[slot]).hexdigest(),completed_blob_sha256=hashlib.sha256(ready[slot]).hexdigest()))
            blobs[slot]=ready[slot]
        atomic_replace(target,build_region(stamps,blobs))
    vox.WORLD=DEST;vox.OUT=OUT;painter=vox.Painter()
    for (_,y,z,b,a),xs in sorted(groups.items()):
        xs.sort();start=previous=xs[0]
        for x in xs[1:]+[xs[-1]+2]:
            if x!=previous+1:painter.match((start,y,z,previous,y,z),b,a,'r44_stage/recorded_static_delta');start=x
            previous=x
    nbt_fields=[]
    for q,tag in authored.items():
        if q in excluded or (q[0]//16,q[2]//16) in pending:continue
        after=final_states.get(q)
        if after is not None and after.partition('[')[0] in {'minecraft:air','minecraft:cave_air','minecraft:void_air'}:continue
        original=source_tags.get(q);row=updates.get(q)
        if original is not None and row is not None:
            before=nbtlib.parse_nbt(row['before']) if row.get('before') else nbtlib.Compound();updated=nbtlib.parse_nbt(row['after']) if row.get('after') else nbtlib.Compound();merged=copy.deepcopy(original)
            fields=prior.changed_fields(before,updated)
            for key in fields:
                # Native CompoundTag.getBoolean reads an absent AirService as
                # false. These two original airport boards predate that field.
                native_default=(key=='AirService' and str(original.get('id'))=='projectseele:station_departure_board'
                    and key not in original and before.get(key)==nbtlib.Byte(0))
                assert original.get(key)==before.get(key) or native_default,('Owner NBT field conflict',q,key)
                if key in updated:merged[key]=copy.deepcopy(updated[key])
                else:merged.pop(key,None)
            tag=merged;nbt_fields.append(dict(pos=q,fields=sorted(fields)))
        elif original is not None:
            assert original==tag,('Existing complete NBT would be replaced',q)
        if q in final_states:
            painter.block_entities[q]=copy.deepcopy(tag)
        elif row is not None:
            # NBT-only edit on an unchanged original block.
            w=MeasuredWorld(SOURCE);w.box(q,q);w.load();state=w.block(q);assert state is not None
            painter.update_block_entity(q,state,original,tag,'r44_stage/explicit_derived_nbt_fields')
    painter.meta.update(source=str(owner),source_controller_depth=312,no_city_reprojection=True,source_cells=total,
        owner_progress_preserved=True,proto_completion=proto_proof,excluded_cells=[dict(pos=q,reason=s) for q,s in excluded.items()])
    painter.apply('static_world')
    biome_rows=json.loads((OUT/'composed_biome_chain.json').read_text());by_region=defaultdict(list)
    for row in biome_rows:by_region[row['chunk'][0]//32,row['chunk'][1]//32].append(row)
    for (rx,rz),rows in by_region.items():
        file=dimension_dir(DEST,vox.DIM)/f'region/r.{rx}.{rz}.mca';stamps,blobs=read_region(file);chunks=defaultdict(list)
        for row in rows:chunks[tuple(row['chunk'])].append(row)
        for (cx,cz),changes in chunks.items():
            slot=(cx&31)+(cz&31)*32;root=parse_chunk(blobs[slot]);sections={int(s['Y']):s for s in root['sections']}
            for row in changes:
                current=sections[row['section_y']]['biomes'];before=nbtlib.parse_nbt(row['before_snbt']);after=nbtlib.parse_nbt(row['after_snbt'])
                assert current==before or ((cx,cz) in pending and current==after),('Biome source mismatch',cx,cz,row['section_y'])
                sections[row['section_y']]['biomes']=after
            blobs[slot]=chunk_blob(root)
        atomic_replace(file,build_region(stamps,blobs))
    archives=OUT/'city_archive_closeout/candidate_data';files=list(archives.glob('*.dat'));assert len(files)==94
    data_dir=dimension_dir(DEST,vox.DIM)/'data';data_dir.mkdir(exist_ok=True)
    for f in files:assert not (data_dir/f.name).exists();shutil.copy2(f,data_dir/f.name)
    shutil.copy2(REVIEW/'r44_public_station_gates.json',DEST/'r44_public_station_gates.json')
    for name in ('regional_states.json','native_collision_shapes.json','native_state_traits_r44.json'):
        if (REVIEW/name).exists():shutil.copy2(REVIEW/name,DEST/name)
    level=nbtlib.load(DEST/'level.dat');level['Data']['LevelName']=nbtlib.String('Project SEELE R44 阶段验收');level.save()
    report=dict(destination=str(DEST),source=str(owner),unique_static_cells=total,non_proto_changed_cells=changed,
        native_default_new_block_entities=len(generated),proto_completion=proto_proof,biome_sections=len(biome_rows),
        derived_archive_files=94,derived_runtime_metadata=['r44_public_station_gates.json','regional_states.json','native_collision_shapes.json','native_state_traits_r44.json'],
        source_progress_preserved=True,city_depth_preserved=312,nbt_fields=nbt_fields,
        excluded_cells=[dict(pos=q,reason=s) for q,s in excluded.items()],new_story_enabled=False,npc_static_migration_pending=True)
    (OUT/'composed.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('R44 source-progress composition complete',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['inventory','check_source','compose'],default='inventory',nargs='?');args=p.parse_args();globals()[{'inventory':'preflight','check_source':'check_source','compose':'compose'}[args.action]]()
