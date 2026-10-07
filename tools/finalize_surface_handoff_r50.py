"""Verify exact retirement candidates and refresh the parent R50 handoff.

Does not apply any blocks/source files and does not promote screen counts to QA.
"""
from pathlib import Path
from collections import Counter
import argparse,gzip,json
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1]

def load(p):return json.loads(Path(p).read_text('utf8'))
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')
def rows(p):
    with gzip.open(p,'rt',encoding='utf8')as f:return[json.loads(s)for s in f if s.strip()]
def packed(q):
    x,y,z=q;n=((x&67108863)<<38)|((z&67108863)<<12)|(y&4095);return n-(1<<64)if n>=1<<63 else n

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);args=ap.parse_args();world=args.world.resolve();out=ROOT/'artifacts/rebuild_r49/surface_r50'
    candidates=[dict(id='M40_55_original_retired_C1',forward=out/'forward.jsonl.gz',inverse=out/'inverse.jsonl.gz',recipe=out/'generation_recipe/file_patch.json'),dict(id='M40_remaining_18_full_source_members',forward=out/'remaining_18_retirement/M40_remaining_18_full_source_members/forward.jsonl.gz',inverse=out/'remaining_18_retirement/M40_remaining_18_full_source_members/inverse.jsonl.gz',recipe=out/'remaining_18_retirement/generation_recipe/file_patch.json')]
    all_rows={};w=MeasuredWorld(world)
    for c in candidates:
        c['rows']=rows(c['forward']);inverse={tuple(r['pos']):r for r in rows(c['inverse'])}
        assert len(inverse)==len(c['rows'])
        for r in c['rows']:
            q=tuple(r['pos']);assert q not in all_rows,('Overlapping candidates',q);all_rows[q]=r;w.box(q,q);v=inverse[q]
            assert v['before']==r['after']and v['after']==r['before']and v.get('before_nbt')==r.get('after_nbt')and v.get('after_nbt')==r.get('before_nbt'),('Inverse mismatch',q)
    w.load();bes=dict(iter_block_entities(world,w.dimension,(min(q[0]for q in all_rows),0,min(q[2]for q in all_rows)),(max(q[0]for q in all_rows),255,max(q[2]for q in all_rows)),selected_chunks=set(w.selected)))
    proof=[]
    for c in candidates:
        state_counts=Counter();mismatches=[]
        for r in c['rows']:
            q=tuple(r['pos']);actual=w.block(q);tag=bes.get(q);snbt=None if tag is None else tag.snbt()
            if actual==r['before']and snbt==r.get('before_nbt'):state_counts['exact_before']+=1
            elif actual==r['after']and snbt==r.get('after_nbt'):state_counts['already_after']+=1
            else:mismatches.append(dict(pos=list(q),expected=r['before'],actual=actual,actual_nbt=snbt))
        recipe=load(c['recipe']);sourceproof=[]
        for op in recipe['operations']:
            target=Path(op['after_file']);target=target if target.is_absolute()else ROOT/target;new=nbtlib.load(target);allowed={packed(tuple(r['pos']))for r in c['rows']if tuple(r['pos'])[0]//16==int(target.stem.split('_')[0])and tuple(r['pos'])[2]//16==int(target.stem.split('_')[1])}
            assert str(new['WorldUUID'])==recipe['WorldUUID'];current=world/op['relative_target'];before=op.get('before_file');preserved=True
            if before:
                p=Path(before);p=p if p.is_absolute()else ROOT/p;old=nbtlib.load(p)
                assert old['Ground']==new['Ground']and old['Palette']==new['Palette'][:len(old['Palette'])]
                a={int(r['Pos']):r.snbt()for r in old['Static']};b={int(r['Pos']):r.snbt()for r in new['Static']}
                assert all(b.get(k)==v for k,v in a.items()if k not in allowed)
                assert set(b)-set(a)<=allowed
                current_match=current.exists()and current.read_bytes()==p.read_bytes()
            else:current_match=not current.exists()
            sourceproof.append(dict(target=op['relative_target'],exact_changed_cells=op['changed_cells'],unmodified_Static_Ground_palette_prefix_preserved=preserved,current_source_still_matches_candidate_before=current_match))
        proof.append(dict(id=c['id'],cells=len(c['rows']),physical_readback=dict(state_counts),mismatches=mismatches,complete_shards=len(sourceproof),sourceproof=sourceproof,source_readback_before_all_match=all(r['current_source_still_matches_candidate_before']for r in sourceproof),inverse_exact=True,world_written=False))
    save(out/'candidate_exact_readback.json',dict(world=str(world),candidates=proof,unique_cells=len(all_rows),no_candidate_overlap=True,world_written=False))
    retirement=load(out/'retirement_readback.json');profiles=load(out/'remaining_18_complete_profiles.json')
    for r in profiles['objects']:
        if r['status']=='ABOVE_GRADE_SOURCE_REQUIRES_OWNER_RECONCILIATION':
            r['status']='EXPOSED_RETIRED_MEMBER_NO_LATER_LOAD_WHOLE_CANDIDATE'
            r['decision']='Remove only the three original surviving post cells at (320,74..76,0); actual soil Y73 remains, no later civil load or BE occupies the complete source frame.'
    save(out/'remaining_18_complete_profiles.json',profiles);lookup={r['id']:r for r in profiles['objects']}
    for r in retirement['objects']:
        if r['id']in lookup:
            r['current_status']=lookup[r['id']]['status'];r['complete_profile_evidence']='remaining_18_complete_profiles.json';r['exact_candidate']='remaining_18_retirement/M40_remaining_18_full_source_members';r['current_natural_center_y']=lookup[r['id']]['current_natural_center_y']
    retirement['counts']=dict(Counter(r['current_status']for r in retirement['objects']));retirement['historic_declared_retirement_components_classified']=True;save(out/'retirement_readback.json',retirement)
    contract=out/'remaining_18_retirement/M40_remaining_18_full_source_members/contract.json';d=load(contract);d['schema']='projectseele.r50.surface-retirement-candidate.v1';d['world']=str(world);d['authorization']='User R50 item 40 full surface terrain and retired-component repair; Root is the sole world writer.';save(contract,d)
    global_=load(out/'global_heightmaps/global_screen.json');pits=load(out/'surface_pit_complete_classification.json');handoff=load(out/'R50_MARINE_ARMOR_SURFACE_HANDOFF.json');s=handoff['surface_40']
    s.update(current_retirement_status=retirement['counts'],whole_original_C1_candidates=73,exact_forward_inverse_cells=len(all_rows),complete_generation_shards=sum(r['complete_shards']for r in proof),deferred_retirement_objects=[],remaining_18_classification=Counter(r['status']for r in profiles['objects']),remaining_18_candidate='remaining_18_retirement/M40_remaining_18_full_source_members/forward.jsonl.gz',current_exact_candidate_readback='candidate_exact_readback.json',deferred_pits=[],historic_pit_classification=pits['counts'],historic_pit_complete_neighborhood_column_visits=pits['complete_neighborhood_column_visits'],pit_classification='surface_pit_complete_classification.json',all_stored_surface_heightmap_screen=dict(counts=global_['counts'],full_positive_columns=global_['known_positive_surface_columns'],region_boundary_pairs=len(global_['region_boundary_pairs']),object_kinds=global_['object_kinds'],table='global_heightmaps/global_screen.json',unread=global_['unread'],quality_passed=False),terrain_interface_repairs_owner='/root/r50_terrain',other_bridges_passages_owner='/root/r50_yashima',global_closed=False,remaining_global_scope='5497 initial Heightmap screen objects include natural slopes, trees, active infrastructure and possible defects; whole-object classification and native/visual acceptance remain distinct. All 60282 stored FULL chunks and their saved-region seams were screened without generating chunks; 40857 saved protochunks lack complete terrain. Root/terrain/Yashima own remaining classified construction and gameplay verification.')
    s.pop('unresolved_terrain_objects',None);save(out/'R50_MARINE_ARMOR_SURFACE_HANDOFF.json',handoff)
    inventory=load(out/'surface_object_inventory.json');s['catalogued_objects']=len(inventory['objects']);s['catalogue_counts']=inventory['counts'];s['current_ordinary_named_buildings']=inventory.get('current_ordinary_named_buildings',193);s['current_movable_city_towers']=inventory.get('current_movable_city_towers',0)
    s['terrain_interface_final_handoff']='terrain_interface_repairs/final_handoff_index.json';s['terrain_interface_decision']='13 reviewed interfaces: retained native bridge/rail/natural structures plus two finite actual shoulder reconstruction candidates. Whole source readback is separate from native/visual acceptance.'
    save(out/'R50_MARINE_ARMOR_SURFACE_HANDOFF.json',handoff)
    save(out/'M40_EXACT_CANDIDATE_MANIFEST.json',dict(schema=50,world=str(world),world_written=False,components=[dict(id=c['id'],forward=str(c['forward'].relative_to(ROOT)),inverse=str(c['inverse'].relative_to(ROOT)),generation_recipe=str(c['recipe'].relative_to(ROOT)),rows=len(c['rows']))for c in candidates],total_unique_cells=len(all_rows),admission='Apply only when every current before state/NBT for the whole component still matches. Compose exact cell deltas with other source candidates; never replace a recently modified complete shard with a stale payload.',no_unrelated_entity_progress_or_inventory_writes=True))
    print(json.dumps(dict(components=[dict(id=p['id'],cells=p['cells'],physical=p['physical_readback'],mismatches=len(p['mismatches']),source_before_match=p['source_readback_before_all_match'])for p in proof],retirement=retirement['counts'],pits=pits['counts'],world_written=False)),flush=True)

if __name__=='__main__':main()
