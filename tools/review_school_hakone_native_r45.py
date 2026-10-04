"""Root execution wrapper for exact current school/Hakone native groups.

Default only prepares launch instructions. --run is the explicit root action.
No builds. Freeze compiled runtime at execution, after root's current build.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from school_hakone_patch_r45 import ROOT, ART, sha

WORLD=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW'
PREPARED=ROOT/'artifacts/rebuild_r45/school_hakone_readonly_followup/native_lifecycle_v7'
CLIENT_GROUPS={
    'school_doors':'10_school_all32_doors_client',
    'school_rooms':'20_school_whole20_rooms_client',
    'school_stairs':'30_school_all_stairs_roof_client',
    'school_other':'22_school_current_occupied_routes_client',
    'pool':'32_school_pool_client',
    'pool_approaches':'33_school_pool_actual_campus_approaches_client',
    'pool_sports':'34_school_pool_sports_field_connections_client',
    'hakone_personnel':'40_hakone_all16_personnel_doors_client',
    'hakone_walks':'43_hakone_current122_journeys_client',
    'hakone_rooms':'44_hakone_whole6_service_rooms_client',
}
PHYSICS_GROUPS={
    'school_doors_physics':'11_school_all32_doors_physics',
    'school_other_physics':'21_school_corridors_gym_field_physics',
    'school_floor_width_physics':'23_school_all_declared_public_floor_rows_physics',
    'school_stairs_physics':'31_school_stairs_physics',
    'hakone_personnel_physics':'41_hakone_all16_personnel_doors_physics',
    'hakone_walks_physics':'42_hakone_current_entries_service_transfers_physics',
}


def read(path):return json.loads(Path(path).read_text('utf8'))
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf8')


def progression_snapshot(out):
    directory=out/'player_progress_before';directory.mkdir()
    rows=[]
    for folder in ['playerdata','stats','advancements']:
        source=WORLD/folder
        if not source.exists():continue
        for path in sorted(source.rglob('*')):
            if not path.is_file():continue
            relative=path.relative_to(WORLD);target=directory/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
            rows.append(dict(relative=relative.as_posix(),before_sha256=sha(path),backup=str(target.resolve())))
    write(out/'player_progress_before.json',rows)
    return rows


def restore_progress_files(out,rows):
    # Root calls this only after its own launched process and integrated server
    # have stopped. Never restore MTR/SavedData progress or overwrite geometry.
    from release_combat_r36 import guard
    guard()
    before={r['relative']:r for r in rows};actual={}
    for folder in ['playerdata','stats','advancements']:
        if not (WORLD/folder).exists():continue
        for p in (WORLD/folder).rglob('*'):
            if p.is_file():actual[p.relative_to(WORLD).as_posix()]=p
    for relative in actual.keys()-before.keys():
        # Native reviews must never manufacture a new player identity.
        raise RuntimeError(('New progression file appeared; retained for root inspection, no deletion',relative))
    receipt=[]
    for relative,row in before.items():
        target=WORLD/relative;after_sha=sha(target) if target.exists() else None
        backup=Path(row['backup']);assert sha(backup)==row['before_sha256']
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(backup,target)
        assert sha(target)==row['before_sha256']
        receipt.append(dict(relative=relative,review_after_sha256=after_sha,restored_sha256=sha(target),full_original_bytes=True))
    write(out/'root_player_progress_full_byte_restore.json',receipt)


def require_compiled(spec,names):
    directories=[]
    for entry in spec.get('environment',{}).get('MOD_CLASSES','').split(';'):
        if entry.startswith('projectseele%%'):directories.append(Path(entry.split('%%',1)[1]))
    evidence=[]
    for name in names:
        source=ROOT/'src/main/java/com/projectseele/client/visual'/name
        relative=Path('com/projectseele/client/visual')/(source.stem+'.class')
        found=[p/relative for p in directories if (p/relative).exists()]
        assert found,('Root must compile new helper before execution',name)
        assert max(p.stat().st_mtime for p in found)>=source.stat().st_mtime,('Compiled helper predates current source',name)
        evidence.append(dict(source=str(source.resolve()),source_sha256=sha(source),
            compiled=[dict(path=str(p.resolve()),sha256=sha(p)) for p in found]))
    return evidence


def prepare_client(args,out):
    kind=args.suite;prepared=args.prepared
    required=[]
    if kind in CLIENT_GROUPS:
        cases=prepared/'groups'/(CLIENT_GROUPS[kind]+'.json');data=read(cases)
        if kind in ['school_rooms','hakone_rooms']:assert not any(r.get('disconnected_supported_cells') for r in data),'Current complete room has unresolved standable islands; root inspection is required'
        if args.run:
            source=ROOT/'src/main/java/com/projectseele/client/visual/SchoolPoolLifecycleR45.java'
            assert 'private static void acknowledgeRestoration(' in source.read_text('utf8'),'Root must merge/compile actual restoration acknowledgment before school native actions'
        start=args.start if args.start is not None else 0;end=args.end if args.end is not None else len(data)
        assert 0<=start<end<=len(data)
        mode='r45-school-pool-client';result=out/'native_result.json';snapshot=out/'cases.json';shutil.copy2(cases,snapshot)
        flags=['-Dprojectseele.r45SchoolPoolReview=true','-Dprojectseele.r45SchoolPoolCases='+snapshot.resolve().as_posix(),
               '-Dprojectseele.r45SchoolPoolOutput='+result.resolve().as_posix(),
               f'-Dprojectseele.r45SchoolPoolStart={start}',f'-Dprojectseele.r45SchoolPoolEnd={end}']
        required=['SchoolPoolLifecycleR45.java']
    elif kind=='hakone_gates':
        order=read(prepared/'native_order.json');ranges=order['hakone_gate_ranges'];assert 0<=args.index<len(ranges)
        window=ranges[args.index];start,end=window['start'],window['end']
        cases=prepared/'groups/50_all160_gate_denominator_hakone16_ranges.json';data=read(cases);assert len(data)==160
        snapshot=out/'cases.json';shutil.copy2(cases,snapshot);mode='r44-public-gate-client';result=WORLD/'r44_public_gate_client_review.json'
        flags=['-Dprojectseele.r44PublicGateReview=true','-Dprojectseele.r44PublicGateCases='+snapshot.resolve().as_posix(),
               f'-Dprojectseele.r44PublicGateStart={start}',f'-Dprojectseele.r44PublicGateEnd={end}']
        required=['PublicStationGateReviewR44.java']
    else:
        assert kind in ['hakone_transit','hakone_apg']
        if kind=='hakone_transit':
            windows=read(prepared/'native_order.json')['hakone_direction_windows'];assert 0<=args.index<len(windows)
            window=windows[args.index];cases=prepared/'groups/60_all38_current_transit_denominator.json'
        else:
            windows=read(prepared/'184_exact_native_APG_journey_windows.json');assert 0<=args.index<len(windows)
            window=windows[args.index];cases=Path(window['cases'])
        start,end=window['start'],window['end'];data=read(cases);assert len(data['cases'])==38
        snapshot=out/'cases.json';shutil.copy2(cases,snapshot);mode='r44-transit-all';result=WORLD/'r44_transit_review.json'
        flags=['-Dprojectseele.r44TransitCases='+snapshot.resolve().as_posix(),f'-Dprojectseele.r44TransitStart={start}',f'-Dprojectseele.r44TransitEnd={end}']
        required=['RegionalTransitR44Checks.java']
        if kind=='hakone_apg':
            required.append('HakonePlatformLifecycleR45.java')
            source=ROOT/'src/main/java/com/projectseele/client/visual/RegionalTransitR44Checks.java'
            if args.run:assert 'var selected=HakonePlatformLifecycleR45.select(mc,v,current);' in source.read_text('utf8'), 'Root must merge exact APG hook patch first'
    template=ROOT/'.Codex/client-r42-interiors-photos.json';spec=copy.deepcopy(read(template))
    command=[v for v in spec['command'] if not v.startswith('-Dprojectseele.')]
    command[1:1]=['-Dprojectseele.regionalBuild='+mode,'-Dprojectseele.nativeReviewWorld='+WORLD.name,
                  '-Dprojectseele.r45TransportTrace=true','-Dprojectseele.r45DeviceControlTrace=true',*flags]
    command[command.index('--quickPlaySingleplayer')+1]=WORLD.name;spec['command']=command
    write(out/'root_launch_before_runtime_freeze.json',spec)
    write(out/'scope.json',dict(suite=kind,start=start,end=end,index=args.index,world=str(WORLD.resolve()),
        input=str(cases.resolve()),input_sha256=sha(cases),source_required=required,
        prepared_only=not args.run,compiled_by_agent=False,launched_by_agent=False,
        result=str(result.resolve()),actual_UUID_and_full_NBT_required=True,
        player_progression_files_restored_by_root_after_shutdown=True,MTR_progress_rewound=False,
        ordinary_APG_useDoor_forbidden=True,native_or_visual_pass=False))
    if not args.run:return
    from release_combat_r36 import guard
    from freeze_native_r44 import freeze
    guard();write(out/'compiled_source_witness.json',require_compiled(spec,required))
    spec=freeze(spec,out);launch=out/'launch.json';write(launch,spec)
    previous=progression_snapshot(out);began=time.time();cfg=ROOT/'run/config/oculus.properties';config_bytes=cfg.read_bytes()
    # Client physics lifecycle uses existing native no-shader settings; art has
    # its independent root photography and must use the final shader epoch.
    cfg.write_text(config_bytes.decode('utf8').replace('enableShaders=true','enableShaders=false'),'utf8')
    process=None
    try:
        with (out/'native.log').open('w',encoding='utf8') as log:
            process=subprocess.Popen([sys.executable,'-X','utf8','tools/launch_rendered_client_r17.py','--prepared-file',str(launch)],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            code=process.wait(timeout=args.timeout)
        assert result.is_file() and result.stat().st_mtime>=began,'No fresh actual native result'
        receipt=read(result)
        if result.resolve()!=(out/'native_result.json').resolve():shutil.copy2(result,out/'native_result.json')
        write(out/'root_result_status.json',dict(process_exit=code,error=receipt.get('error'),
            actual_result_cases=len(receipt.get('cases',[])),expected_window_cases=end-start,
            native_result_sha256=sha(out/'native_result.json'),art_accepted=False,cold_reload='UNVERIFIED'))
        assert code==0 and not receipt.get('error'),receipt.get('error')
        assert len(receipt.get('cases',[]))==end-start,'Result scope does not cover requested window'
    finally:
        cfg.write_bytes(config_bytes)
        # On timeout do not silently destroy the integrated server. Root must
        # stop this exact child safely and then run --restore-progress-only.
        if process is not None and process.poll() is not None:restore_progress_files(out,previous)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--suite',choices=[*CLIENT_GROUPS,*PHYSICS_GROUPS,'hakone_gates','hakone_transit','hakone_apg'])
    ap.add_argument('--prepared',type=Path,default=PREPARED);ap.add_argument('--index',type=int,default=0)
    ap.add_argument('--start',type=int);ap.add_argument('--end',type=int);ap.add_argument('--timeout',type=int,default=7200)
    ap.add_argument('--run',action='store_true');ap.add_argument('--out',type=Path);ap.add_argument('--restore-progress-only',type=Path)
    args=ap.parse_args()
    if args.restore_progress_only:
        assert args.run,'Root execution must be explicit';restore_progress_files(args.restore_progress_only,read(args.restore_progress_only/'player_progress_before.json'));return
    assert args.suite
    out=args.out or ART/'native_runs'/args.suite/time.strftime('%Y%m%d_%H%M%S')
    followup=ROOT/'artifacts/rebuild_r45/school_hakone_readonly_followup'
    assert any(p.resolve() in out.resolve().parents for p in [ART,followup]) and not out.exists();out.mkdir(parents=True)
    if args.suite in PHYSICS_GROUPS:
        cases=args.prepared/'groups'/(PHYSICS_GROUPS[args.suite]+'.json')
        data=read(cases);start=args.start if args.start is not None else 0;end=args.end if args.end is not None else len(data)
        assert 0<=start<end<=len(data);bounded=out/'cases.json';write(bounded,data[start:end])
        command=[sys.executable,'-X','utf8','tools/review_walks_r45.py',str(bounded),'--name','school_hakone_'+args.suite+f'_{start}_{end}','--timeout',str(args.timeout)]
        write(out/'root_command.json',dict(command=command,world_written_by_preparer=False,actual_client_input=False))
        if args.run:subprocess.run(command,cwd=ROOT,check=True)
    else:prepare_client(args,out)
    print('Root native group',args.suite,'executed' if args.run else 'prepared only',out,flush=True)


if __name__=='__main__':main()
