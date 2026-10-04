"""Exact post-install tails, derived metadata and ordered native obligations.

No source-resource or Minecraft-world writes. Root is the sole installer.
The installed v2 school/v5 station are never replayed by this producer.
"""
from pathlib import Path
from collections import Counter
import argparse
import copy
import gzip
import hashlib
import json
import shutil

from school_hakone_patch_r45 import Candidate,ROOT,ART,sha
from measure_world_r40 import properties

WORLD=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW'
SOURCE_SCHOOL=ART/'school_v4'
SOURCE_STATION=ART/'hakone_v5'


def read(p):return json.loads(Path(p).read_text('utf8'))
def rows(p):return [json.loads(s) for s in gzip.open(Path(p)/'forward.jsonl.gz','rt',encoding='utf8')]


def composed_school_canonical(source):
    # Post-install repairs are authoritative target amendments, not fresh
    # world patches. Keep each coordinate's first measured baseline/inverse.
    geometry={tuple(r['pos']):r for r in rows(source)}
    amendments=[]
    for name,installation in [('science_sink_tail_v1','school_science_sink_tail_v1'),
                              ('science_sink_wall_v2','school_science_sink_wall_v2')]:
        receipt=ROOT/'artifacts/rebuild_r45/component_installations'/installation/'installation.json'
        if not receipt.exists() or not read(receipt).get('installed'):continue
        candidate=ART/name
        assert Path(read(receipt)['candidate']).resolve()==candidate.resolve()
        for row in rows(candidate):
            q=tuple(row['pos']);row=copy.deepcopy(row)
            if q in geometry:
                row['before']=geometry[q]['before'];row['before_nbt']=geometry[q]['before_nbt']
            geometry[q]=row
        amendments.append(dict(candidate=str(candidate.resolve()),forward_sha256=sha(candidate/'forward.jsonl.gz'),
                               installed_receipt=str(receipt.resolve()),receipt_sha256=sha(receipt)))
    return [geometry[q] for q in sorted(geometry)],amendments


def correct_pool_connection_records(records):
    result=copy.deepcopy(records)
    name='r45/school/pool/from_school_north_port'
    old=[[233.5,73,-730.5],[233.5,73,-750.5],[277.5,73,-750.5],[277.5,73,-746.5],[277.5,73,-732.5]]
    fixed=[[233.5,73,-730.5],[233.5,73,-749.5],[277.5,73,-749.5],[277.5,73,-746.5],[277.5,73,-732.5]]
    for row in result:
        if row['id'] not in [name,name+'/return']:continue
        before,after=(old,fixed) if row['id']==name else (list(reversed(old)),list(reversed(fixed)))
        assert row['path'] in [before,after],('Independently changed pool connection',row['id'])
        if row['path']==before:row.update(path=after,native_passed=False)
    return result


def file_candidate(out,target,value,label):
    target=Path(target)
    after=out/(label+'.after.json')
    after.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf8')
    before=out/(label+'.before.json')
    exists=target.exists()
    if exists:before.write_bytes(target.read_bytes())
    return dict(target=str(target.resolve()),expected_before_sha256=sha(before) if exists else None,before_file=str(before.resolve()) if exists else None,after_file=str(after.resolve()),after_sha256=sha(after),existing_prefix_or_records_preserved=True,inverse=dict(target=str(target.resolve()),expected_before_sha256=sha(after),bytes_from=str(before.resolve()) if exists else None,remove_only_new_file=not exists),root_only=True)


def prepare(world,out):
    world,out=Path(world),Path(out)
    assert ART.resolve() in out.resolve().parents,'Dedicated lifecycle output must stay outside all worlds in the agent artifact directory'
    assert not out.exists(),'Refuse to replace a frozen lifecycle epoch'
    installed_school=ROOT/'artifacts/rebuild_r45/component_installations/school_campus_v2/installation.json'
    installed_station=ROOT/'artifacts/rebuild_r45/component_installations/hakone_station_v5/installation.json'
    assert read(installed_school)['installed'],'Root full school installation receipt is required'
    # Station receipt folder spelling is owned by root; actual current state
    # is independently read below, not inferred from the label.
    station_receipts=list((ROOT/'artifacts/rebuild_r45/component_installations').glob('*hakone*/installation.json'))
    assert station_receipts and any(read(p).get('installed') for p in station_receipts)
    out.mkdir(parents=True)
    sc=read(SOURCE_SCHOOL/'contract.json');st=read(SOURCE_STATION/'contract.json')
    c=Candidate(world,sc['bounds'],'r45/school_tail')
    old={tuple(r['pos']):r for r in rows(ART/'school_v2')}
    wanted={tuple(r['pos']):r for r in rows(SOURCE_SCHOOL)}
    held=[]
    for q,r in wanted.items():
        if q in old and old[q]['after']==r['after'] and old[q]['after_nbt']==r['after_nbt']:continue
        current=c.measured.block(q)
        if current==r['after']:continue
        if current.partition('[')[0]=='minecraft:oak_leaves' and r['after'].partition('[')[0]=='minecraft:oak_leaves':
            actual_props=properties(current);target_props=properties(r['after'])
            actual_props.pop('distance',None);target_props.pop('distance',None)
            if actual_props==target_props:continue  # Native leaf-distance bookkeeping is preserved, never reset.
        expected=old[q]['after'] if q in old else r['before']
        if current!=expected or q in c.tags:
            held.append(dict(pos=list(q),expected=expected,actual=current,original_BE=q in c.tags));continue
        c.put(q,r['after'],'Finite post-school-v2 completion: full field guard / low courtyard planting and original pupil seats')
    assert not held,('Independent current-world change requires root investigation',held[:10])
    # Small native labels attach to actual existing entrance walls. No new
    # display entity, billboard or furniture appears in a circulation lane.
    for q,lines in [((254,74,-680),['第三新东京市立','第一中学','教学楼・保健室','泳池・操场：北侧']),((299,74,-693),['学校体育馆','教学楼：左侧','泳池・操场：北侧','请沿校园通路进入'])]:
        backing=(q[0],q[1],q[2]-1)
        assert c.measured.block(backing).partition('[')[0] in {'minecraft:white_concrete','projectseele:residential_plaster'},('Actual sign backing/ownership conflict',q)
        if q in c.tags:continue  # Preserve current complete existing label NBT.
        assert c.measured.block(q) in {'minecraft:air','minecraft:cave_air'},('Independent entrance fixture change',q)
        c.sign(q,lines,'south')
    c.rooms=read(SOURCE_SCHOOL/'rooms.json')
    c.components=read(SOURCE_SCHOOL/'components.json')
    c.floors=read(SOURCE_SCHOOL/'floor_regions.json')
    c.floors.append(dict(id='r45/school/gym/full_court',feet=73,bounds=[287,-717,307,-695],role='Full playing hall, seating/backboard fixtures separately classified'))
    c.ports=read(SOURCE_SCHOOL/'ports.json')
    c.cases=correct_pool_connection_records(read(SOURCE_SCHOOL/'native_cases.json'))
    c.cameras=read(SOURCE_SCHOOL/'camera_itinerary.json')
    c.foundations=read(SOURCE_SCHOOL/'foundations.json')
    tail=c.export(out/'school_tail',dict(title='Exact current post-v2 school campus completion tail',installed_main=str(installed_school.resolve()),installed_main_sha256=sha(installed_school),installed_main_replay_allowed=False,unverified=['Root applies only this remaining current-state tail','New signs and guards actual native shape/reading views','All dynamic/whole-floor native tests and final installed readback']))
    catalogue=dict(schema=45,world=str(world.resolve()),dimension='projectseele:geofront',installed_main=[dict(name='school_campus_v2',receipt=str(installed_school.resolve()),sha256=sha(installed_school),source=str((ART/'school_v2').resolve())),dict(name='hakone_v5',receipts=[dict(path=str(p.resolve()),sha256=sha(p)) for p in station_receipts],source=str(SOURCE_STATION.resolve()))],school=dict(components=c.components,rooms=c.rooms,floors=c.floors,ports=c.ports),hakone=dict(components=read(SOURCE_STATION/'components.json'),rooms=read(SOURCE_STATION/'rooms.json'),floors=read(SOURCE_STATION/'floor_regions.json'),ports=read(SOURCE_STATION/'ports.json'),boarding=read(SOURCE_STATION/'boarding_interfaces.json')),native_verified=False,visual_approved=False,source_world_progress_copied=False)
    derived=out/'derived';derived.mkdir()
    plans=[file_candidate(derived,world/'r45_school_hakone_components.json',catalogue,'components')]
    # Merge only the dedicated obligations. The current 20k catalogue and all
    # unrelated history/paths survive verbatim as JSON records in the same order.
    before=read(world/'quality_walk_cases.json');after=copy.deepcopy(before)
    index={r['id']:i for i,r in enumerate(after)};assert len(index)==len(after)
    changes=[]
    corrected=correct_pool_connection_records(after)
    for previous,next_record in zip(after,corrected):
        if previous!=next_record:
            changes.append(dict(id=previous['id'],before=copy.deepcopy(previous),after_path=next_record['path'],
                reason='Actual retained school/pool floor is at Z=-750; preserve both endpoints and avoid the absent neighbouring Z=-751 row'))
    after=corrected
    for r in read(SOURCE_STATION/'path_replacements.json'):
        if r['id'] not in index:raise RuntimeError(('Actual route catalogue lacks source obligation',r['id']))
        dst=after[index[r['id']]]
        if dst['path']==r['after_path']:continue
        assert dst['path']==r['before_path'],('Current path changed independently',r['id'])
        changes.append(dict(id=r['id'],before=copy.deepcopy(dst),after_path=r['after_path'],reason=r['reason']))
        dst['path']=r['after_path']
    appended=[]
    for case in c.cases+read(SOURCE_STATION/'native_cases.json'):
        if case['id'] in index:
            assert after[index[case['id']]].get('path')==case.get('path'),('Same actual ID has conflicting route',case['id'])
            continue
        entry=copy.deepcopy(case)
        if entry.get('door'):entry['useDoor']=True
        index[entry['id']]=len(after);after.append(entry);appended.append(entry['id'])
    plans.append(file_candidate(derived,world/'quality_walk_cases.json',after,'quality_walk_cases'))
    navigation=dict(schema=45,source_catalogue_sha256=sha(derived/'components.after.json'),source_route_after_sha256=sha(derived/'quality_walk_cases.after.json'),static_candidate_only=True,native_certified=False,changed_paths=changes,appended_obligation_ids=appended,school_station_journeys=read(ART/'school_v2/inherited_station_journeys.json'),public_gate_maps=read(SOURCE_STATION/'path_replacements.json'),fare_gate_ids_preserved=True,live_traffic_database_modified=False,required_cache_action='After root merges this exact route catalogue, regenerate only affected school/Hakone semantic nodes; bind produced navigation cache hash to actual native tested epoch. This file does not falsely substitute an untested navigation mesh.')
    plans.append(file_candidate(derived,world/'r45_school_hakone_navigation.json',navigation,'navigation'))
    (out/'derived_file_plan.json').write_text(json.dumps(dict(forward=plans,world_written=False,source_written=False,unrelated_records_preserved=len(before),source_records_after=len(after),same_id_changed=len(changes),appended_cases=len(appended),active_r44_walk_job_file_not_changed=True),indent=2),'utf8')
    # A finite, mandatory union input for the global provider agent. The
    # effective world currently uses a fixed source; changing its codec is
    # owned by that agent/root, not by this component metadata producer.
    additions=[dict(bounds=[264,63,-751,308,80,-730],owner='r45/school/pool_changing_and_approach',role='Complete swimming water, basin, foundation, dry deck, changing rooms and public connection'),dict(bounds=[256,70,-780,290,76,-756],owner='r45/school/whole_sports_ground',role='Complete field floor and connected two-high boundary guard'),dict(bounds=[228,71,-711,278,76,-705],owner='r45/school/low_courtyard_landscape',role='Authored low shrubs and pupil seating outside central linking corridor'),dict(bounds=[-1554,104,621,-1406,147,651],owner='r45/hakone/R1_whole_station',role='All hall/room/canopy/native platform and passenger/rail envelopes'),dict(bounds=[-1538,104,661,-1422,135,691],owner='r45/hakone/S1_whole_station',role='All hall/room/canopy/native platform and passenger/rail envelopes')]
    ecology=dict(schema=45,reservations=additions,world_written=False,source_written=False,merge='Append exact unique volumes to each provider own original protected-volume prefix; never transplant source/worldpack settings between them',must_cover_swimming_pool=True,feature_contract='RegionalEcologyBiomeSourceR44.protectedAt and permitsVegetationAt plus complete staged-feature rejection; root must cold-load and verify actual provider equality before future generation/retrofit',upstream_school_existing_reservations=str((SOURCE_SCHOOL/'ecology_reservations.json').resolve()),upstream_school_existing_sha256=sha(SOURCE_SCHOOL/'ecology_reservations.json'),effective_source_not_assumed_regional=True)
    (out/'ecology_additions.json').write_text(json.dumps(ecology,indent=2),'utf8')
    groups=out/'native_groups';groups.mkdir()
    ordered=[]
    def group(order,name,cases,method,required):
        dst=groups/(str(order).zfill(2)+'_'+name+'.json');dst.write_text(json.dumps(cases,ensure_ascii=False,indent=2),'utf8')
        ordered.append(dict(order=order,name=name,path=str(dst.resolve()),sha256=sha(dst),objects=len(cases),method=method,required_evidence=required,verified=False))
    requested=set(read(SOURCE_SCHOOL/'requested_native_states.json'))|set(read(SOURCE_STATION/'requested_native_states.json'))|{r['after'] for r in c.target.values()}
    for port in c.ports:
        requested.update(port[k] for k in ['closed_state','open_state'] if k in port)
    requested.update(s.replace('open=false','open=true') for s in list(requested) if 'fence_gate' in s)
    group(0,'native_shapes',sorted(requested),'Actual block/BE-aware collision and outline capture','All states incl. true/false doors, gates, pool ladders/steps; fixture_part resolved from real owner')
    group(10,'school_room_and_floor_walks',[dict(x,useDoor=True) if x.get('door') else x for x in c.cases if not any(t in x['id'] for t in ['stair','pool/'])],'Root review_walks_r45.py / actual full-room footprint','Actual door use, complete threshold widths, every room and each floor; native client photos separately')
    group(20,'school_stairs_and_roof',[x for x in c.cases if 'stair' in x['id']],'Root review_walks_r45.py native vertical paths','West three level/roof flights, east two flights, both returns and rooftop real aperture')
    group(30,'pool_complete_interfaces',[dict(component='swimming_pool',water_bounds=[280,71,-743,304,72,-734],gates=[[277,73,-747],[278,73,-747]],ladders=[[282,71,-743],[298,71,-743]],shallow_steps=[[304,72,-739],[304,72,-738]],changing_doors=[[275,73,-742],[275,73,-734]],deck_and_changing_cases=[x for x in c.cases if any(t in x['id'] for t in ['pool/','changing'])])],'Actual native player swimming/ladder/gate/container/chair interactions','Enter/exit each ladder and shallow step, deep/shallow swim, closed/open double pool gate, both changing rooms, full dry ring and all edges; save/reload')
    group(40,'hakone_all_gate_banks',[p for p in catalogue['hakone']['ports'] if p.get('kind')=='original_native_ticket_gate'],'Existing full MTR native card/gate reviewer','All eight exact gates, both directions, four public entrances, same fare/service identity; reading map starts outside closed gates')
    group(50,'hakone_service_and_transfers',[dict(x,useDoor=True) if x.get('door') else x for x in read(SOURCE_STATION/'native_cases.json') if '/boarding/' not in x['id'] and '/ground_entrance_' not in x['id']],'Root native walks and actual R1/S1 transfers','Six whole service rooms, both station halls, every original stair/escalator/overbridge, map reading and corrected island aprons')
    group(60,'hakone_all_368_apg_approaches',[dict(platform_id=x['source_platform'],station_id='6131386888082811228',all_actual_door_approaches=x['source']['all_actual_door_approaches'],source_complete_native_interface=x) for x in catalogue['hakone']['boarding']],'Actual MTR station-door and train-door cycles / four-direction journeys','Four IDs preserved; all 104+104+80+80 actual APG points checked for complete open/closed envelope, correct train door, boarding/arrival/return. Static walker is insufficient')
    group(70,'all_actual_shader_photos',c.cameras+read(SOURCE_STATION/'camera_itinerary.json'),'Root review_spaces_r45.py plus full client shader photography','All rooms/floors/roof/gym/pool/changing/field and both station halls/platforms/gates/readers, daytime/night and final correct jar/resource identity')
    group(80,'ecology_cold_load_protection',additions,'Global provider candidate + root actual cold-load/staged-feature controls','Every water/deck/building/guard coordinate protected by actual loaded provider; zero vegetation may overwrite pool or room/rail clearances')
    (out/'native_review_order.json').write_text(json.dumps(dict(groups=ordered,world=str(world.resolve()),world_written=False,all_native_verified=False,root_only_execution=True),indent=2),'utf8')
    template=out/'canonical_templates';template.mkdir()
    for label,src in [('school',SOURCE_SCHOOL),('hakone',SOURCE_STATION)]:
        # Preserve current complete identities in saved-world maintenance;
        # this deterministic desired fabric is used only against matching
        # measured ownership, never as a wholesale progress transplant.
        geometry,amendments=composed_school_canonical(src) if label=='school' else (rows(src),[])
        canonical=dict(schema=45,component=label,source_candidate=str(src.resolve()),source_forward_sha256=sha(src/'forward.jsonl.gz'),geometry=geometry,installed_target_amendments=amendments,original_progress_or_traffic_migration=False,maintenance='Exact before-state/NBT match; skip independently edited coordinates; preserve all current original BE and gate/traffic IDs',retired_generators=['R44 school v22 full replay'] if label=='school' else ['R22 whole station/civil replay','R44 gate seed regeneration'],future_calls='Use author_school_campus_r45.py --repair-current or this lifecycle producer on already installed R45 worlds; fresh construction requires full authored v22 baseline composed with R45 canonical target, never current-world whole replay')
        with gzip.open(template/(label+'.json.gz'),'wt',encoding='utf8') as f:json.dump(canonical,f,ensure_ascii=False)
    result=dict(schema=45,world=str(world.resolve()),school_tail=str(tail.resolve()),derived_file_plan=str((out/'derived_file_plan.json').resolve()),native_review_order=str((out/'native_review_order.json').resolve()),ecology_additions=str((out/'ecology_additions.json').resolve()),root_only_install=True,world_written=False,source_written=False,installed_main_replay=False,traffic_database_modified=False,held=held,current_original_school_BE_preserved=len(c.tags),native_test_completed=False,visual_approved=False)
    result['files']={p.relative_to(out).as_posix():dict(path=str(p.resolve()),sha256=sha(p)) for p in out.rglob('*') if p.is_file()}
    (out/'handoff.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('R45 lifecycle remaining cells',len(c.target),'current full school BE preserved',len(c.tags),'derived files',len(plans),'added catalogue cases',len(appended),'ordered native groups',len(ordered),flush=True)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,default=WORLD);p.add_argument('--out',type=Path,default=ART/'lifecycle_v1');a=p.parse_args();prepare(a.world,a.out)


if __name__=='__main__':main()
