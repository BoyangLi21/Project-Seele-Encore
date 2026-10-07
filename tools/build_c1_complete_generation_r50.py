"""Freeze complete original C1 masks to current R50 terminal states for generation.

Physical changes remain the two independently reversible candidates. This
common source also seals the already-removed original mask and preserves later
civil reuse, so a stale Static entry cannot resurrect an omitted Basalt cell.
Never writes a save; Root composes these exact terminal cells with other sources.
"""
from pathlib import Path
from collections import Counter
import argparse,gzip,json
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
from prepare_facilities_r48 import Author

ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(Path(p).read_text('utf8'))
def readrows(p):
    with gzip.open(p,'rt',encoding='utf8')as f:return[json.loads(s)for s in f if s.strip()]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);args=ap.parse_args();world=args.world.resolve();base=ROOT/'artifacts/rebuild_r49/surface_r50';out=base/'c1_complete_generation';out.mkdir(parents=True,exist_ok=True)
    original=load(ROOT/'artifacts/rebuild_r46/stations_terrain/C1_pier_whole_inventory_v3.json')['all_whole_components'];assert len(original)==489
    changes={tuple(r['pos']):r for p in[base/'forward.jsonl.gz',base/'remaining_18_retirement/M40_remaining_18_full_source_members/forward.jsonl.gz']for r in readrows(p)};w=MeasuredWorld(world);owned={};component=[]
    for row in original:
        qlist=[]
        for cell in row['original_constructed_owned_cells']:
            q=tuple(cell['pos']);w.box(q,q);owned.setdefault(q,[]).append(row['id']);qlist.append(q)
        component.append(dict(id=row['id'],complete_original_owned_cells=len(qlist),exact_original_bounds=row['complete_declared_frame']))
    w.load();assert set(w.status.values())=={'full'},('Original C1 masks cross non-FULL storage',Counter(w.status.values()))
    lo=tuple(min(q[k]for q in owned)for k in range(3));hi=tuple(max(q[k]for q in owned)for k in range(3));bes=dict(iter_block_entities(world,w.dimension,lo,hi,selected_chunks=set(w.selected)))
    source=[]
    for q,owners in sorted(owned.items()):
        current=w.block(q);tag=bes.get(q);nbt=None if tag is None else tag.snbt();change=changes.get(q)
        if change:
            assert current in{change['before'],change['after']}and nbt in{change.get('before_nbt'),change.get('after_nbt')},('Physical candidate before no longer admits',q,current)
            after=change['after'];after_nbt=change.get('after_nbt')
        else:after=current;after_nbt=nbt
        source.append(dict(pos=list(q),before=current,after=after,before_nbt=nbt,after_nbt=after_nbt,owner='M40_complete_original_C1_terminal_mask',original_component_owners=owners,reason='Complete original source mask: retain actual AIR/soil/later civil/full NBT or explicit candidate terminal material; prevents omitted legacy Basalt cells from regenerating.',source_only=current==after and nbt==after_nbt))
    with gzip.open(out/'complete_generation_source.jsonl.gz','wt',encoding='utf8')as f:
        for r in source:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    author=Author(world,out);author.all={tuple(r['pos']):r for r in source};author.recipe()
    physical=len([r for r in source if not r['source_only']]);assert set(changes)<=set(owned)
    contract=dict(schema='projectseele.r50.complete-retirement-source.v1',world=str(world),dimension=w.dimension,original_C1_components=489,unique_complete_mask_cells=len(source),physical_candidate_terminal_cells=len(changes),source_only_current_cells=len(source)-physical,complete_mask_not_just_changed_cells=True,actual_full_NBT_preserved=sum(r['after_nbt']is not None for r in source),all_original_masks_full_chunk_preflight=True,components=component,world_written=False,source_written=False,native_verified=False,visual_acceptance=False,composition='Root merges complete_generation_source by exact pos into the latest complete shard; never replace a concurrently edited shard with this payload. Both physical candidates share this common full source, apply source once.')
    (out/'contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),'utf8');(out/'metadata_patch.json').write_text(json.dumps(dict(schema=50,operations=[],world_written=False),indent=2),'utf8')
    manifest=load(base/'M40_EXACT_CANDIDATE_MANIFEST.json');manifest['common_complete_generation_source']=str((out/'complete_generation_source.jsonl.gz').relative_to(ROOT));manifest['complete_original_C1_components']=489;manifest['complete_original_mask_cells']=len(source)
    for c in manifest['components']:c['common_complete_generation_source']=manifest['common_complete_generation_source']
    (base/'M40_EXACT_CANDIDATE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    handoff=load(base/'R50_MARINE_ARMOR_SURFACE_HANDOFF.json');handoff['surface_40'].update(complete_original_C1_generator_source=manifest['common_complete_generation_source'],complete_original_C1_source_components=489,complete_original_C1_source_cells=len(source),changed_only_recipes_superseded_for_composition=True);(base/'R50_MARINE_ARMOR_SURFACE_HANDOFF.json').write_text(json.dumps(handoff,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:contract[k]for k in('original_C1_components','unique_complete_mask_cells','physical_candidate_terminal_cells','source_only_current_cells','actual_full_NBT_preserved','world_written')}),flush=True)

if __name__=='__main__':main()
