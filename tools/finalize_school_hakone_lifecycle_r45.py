"""Freeze dedicated post-install lifecycle sources and all concrete native objects."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import shutil

from school_hakone_patch_r45 import ROOT,ART,sha


def main():
    p=argparse.ArgumentParser();p.add_argument('--lifecycle',type=Path,default=ART/'lifecycle_v2');a=p.parse_args();out=a.lifecycle
    assert ART.resolve() in out.resolve().parents
    handoff=json.loads((out/'handoff.json').read_text('utf8'))
    assert not (out/'source_epoch').exists(),'Already frozen; create a fresh lifecycle epoch after changes'
    inventory=out/'object_inventory'
    station_file=inventory/'hakone_all_actual_doors.json';doors=json.loads(station_file.read_text('utf8'))
    for door in doors:
        if door['actual_state'].startswith('mtr:'):
            door['kind']='actual_automated_MTR_APG_leaf'
            door['required']=['actual_train_arrival','native_APG_train_open_close_sync','actual_supported_boarding','correct_direction_arrival_and_return','preserve_full_state_and_identity_after_saved_lifecycle']
            door['personnel_useDoor_operation_allowed']=False
    station_file.write_text(json.dumps(doors,ensure_ascii=False,indent=2),'utf8')
    actual=json.loads((inventory/'school_all_actual_doors.json').read_text('utf8'));threshold=[]
    for door in actual:
        for suffix,points in [('in',[door['front'],door['rear']]),('out',[door['rear'],door['front']])]:
            threshold.append(dict(id=door['id']+'/actual_threshold/'+suffix,path=points,door=door['position'],useDoor=True,closeDoorAfter=True,native_passed=False,source_actual_closed_state=door['actual_state'],source_actual_upper_state=door['actual_upper_state']))
    assert len(threshold)==64
    dst=out/'native_groups/11_school_all_32_actual_door_pairs.json';dst.write_text(json.dumps(threshold,indent=2),'utf8')
    portfile=inventory/'hakone_all_368_boarding_ports.json';portrows=json.loads(portfile.read_text('utf8'))
    dst_ports=out/'native_groups/61_hakone_368_individual_ports.json';dst_ports.write_text(json.dumps(portrows,indent=2),'utf8')
    order_file=out/'native_review_order.json';order=json.loads(order_file.read_text('utf8'))
    order['groups'].extend([dict(order=11,name='school_all_32_actual_door_pairs',path=str(dst.resolve()),sha256=sha(dst),objects=32,cases=64,method='Native use + open threshold + close + both returns, all actual paired doors including courtyard and roof hatch',required_evidence='Before state and full NBT restored; no sampled door denominator',verified=False),dict(order=61,name='hakone_368_individual_ports',path=str(dst_ports.resolve()),sha256=sha(dst_ports),objects=368,method='Actual MTR APG/train-door arrival/open/board/ride/arrive/exit/return and cold reload per concrete native endpoint',required_evidence='Four actual platform identities and complete 104/104/80/80 endpoint counts',verified=False)])
    order['groups'].sort(key=lambda g:g['order']);order_file.write_text(json.dumps(order,ensure_ascii=False,indent=2),'utf8')
    afterfile=out/'derived/quality_walk_cases.after.json';routes=json.loads(afterfile.read_text('utf8'));ids={r['id'] for r in routes}
    routes.extend(r for r in threshold if r['id'] not in ids)
    afterfile.write_text(json.dumps(routes,ensure_ascii=False,indent=2)+'\n','utf8')
    navfile=out/'derived/navigation.after.json';nav=json.loads(navfile.read_text('utf8'));nav['source_route_after_sha256']=sha(afterfile);nav['appended_obligation_ids'].extend(r['id'] for r in threshold if r['id'] not in ids);navfile.write_text(json.dumps(nav,ensure_ascii=False,indent=2)+'\n','utf8')
    planfile=out/'derived_file_plan.json';plan=json.loads(planfile.read_text('utf8'))
    for row in plan['forward']:
        row['after_sha256']=sha(row['after_file']);row['inverse']['expected_before_sha256']=row['after_sha256']
    plan['source_records_after']=len(routes);plan['appended_cases']+=sum(r['id'] not in ids for r in threshold);planfile.write_text(json.dumps(plan,indent=2),'utf8')
    folder=out/'source_epoch';folder.mkdir()
    files=[ROOT/'tools'/n for n in ['author_school_campus_r45.py','author_hakone_station_r45.py','school_hakone_patch_r45.py','prepare_school_hakone_lifecycle_r45.py','catalogue_school_hakone_objects_r45.py','finalize_school_hakone_lifecycle_r45.py','school_hakone_lifecycle_guard_r45.py','plan_formal_school_entry_r44.py','rebase_school_installed_tokyo_r44.py','solve_school_current_road_datum_r44.py','audit_school_hakone_r45.py']]+[ROOT/'docs/SCHOOL_HAKONE_R45.md']
    sources=[]
    for i,source in enumerate(files):
        target=folder/(str(i).zfill(2)+'_'+source.name);shutil.copy2(source,target);sources.append(dict(original_path=str(source.resolve()),frozen_path=str(target.resolve()),sha256=sha(target)))
    handoff.update(source_epochs=sources,all_actual_school_door_pairs=32,all_actual_hakone_personnel_door_pairs=16,all_actual_hakone_APG_lower_leaves=368,all_individual_368_ports=str(portfile.resolve()),actual_object_inventory=str((inventory/'inventory.json').resolve()),final_active_artifact=True,retired_first_delivery_manifest=str((ART/'delivery_manifest.json').resolve()),source_shared_files_modified=False,dedicated_old_school_producers_guarded=True,dynamic_current_world_states_and_progress_copied=False)
    handoff['files']={f.relative_to(out).as_posix():dict(path=str(f.resolve()),sha256=sha(f)) for f in out.rglob('*') if f.is_file() and f.name!='handoff.json'}
    (out/'handoff.json').write_text(json.dumps(handoff,ensure_ascii=False,indent=2),'utf8')
    print('Frozen lifecycle tail236 / original school BE313; native school door pairs32, station personnel16/APG368; derived route cases',len(routes),'root group count',len(order['groups']),flush=True)


if __name__=='__main__':main()
