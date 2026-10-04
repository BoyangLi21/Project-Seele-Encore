"""Prepare root launch arguments after a fresh compiled cold lease; do not launch or read regions."""
from __future__ import annotations
import argparse, copy, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/rebuild_r45/lifts_doors_lifecycle_sol_v2'
OLD=ROOT/'artifacts/rebuild_r45/candidate_transport_acceptance_sol_v1'
OWN=[('visual','LiftPassengerR20Review'),('visual','CandidateLiftTripCasesR45'),('client/visual','NervSecurityLifecycleR45'),
     ('world','CommandRoomSlidingDoorDirector')]

def read(path):return json.loads(Path(path).read_text('utf8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf8')

def main(args):
    out=args.out.resolve();assert not out.exists(),'Preserve earlier jobs and receipts'
    binding=read(args.binding);assert binding['schema'] in ('projectseele.city-atomic-native-binding-r45.v2','projectseele.city-atomic-native-binding-r45.v3') and binding['qa_copy']
    assert binding['composition_complete'] and binding['installed_disabled'] and not binding['runtime_enabled']
    assert not Path(binding['preworld_receipt_output']).exists(), 'A consumed or attempted admission needs a new named cold checkpoint and lease'
    epoch=binding['source_epoch'];code=[]
    required=OWN+[('visual','DeviceBatchSequenceR45'),('client/visual','LiftPassengerR20Client')] if args.sequence_devices else OWN
    for package,name in required:
        source=ROOT/f'src/main/java/com/projectseele/{package}/{name}.java'
        compiled=ROOT/f'build/classes/java/main/com/projectseele/{package}/{name}.class'
        assert compiled.is_file(),f'Root must compile the current device consumers: {name}'
        assert any(Path(r['path']).resolve()==source.resolve() and r['sha256']==sha(source) for r in epoch),f'Cold lease omits current device source: {name}'
        assert any(Path(r['path']).name==name+'.class' and r['sha256']==sha(compiled) for r in epoch),f'Cold lease omits current compiled device class: {name}'
        code.append(dict(source=str(source),source_sha256=sha(source),class_sha256=sha(compiled)))
    base=read(args.base_launch);world=Path(binding['world']).resolve();game=Path(base['workingDirectory']).resolve()
    assert world.parent.name=='saves' and world.parent.parent==game,'Base launch must belong to this exact cold copied gameDir'
    command=base['command'];assert Path(command[command.index('--gameDir')+1]).resolve()==game
    assert command[command.index('--quickPlaySingleplayer')+1]==world.name
    classes=[Path(s.split('%%',1)[1])for s in base['environment']['MOD_CLASSES'].split(';')if s.startswith('projectseele%%')]
    for package,name in required:
        compiled=ROOT/f'build/classes/java/main/com/projectseele/{package}/{name}.class'
        assert any((d/f'com/projectseele/{package}/{name}.class').is_file() and sha(d/f'com/projectseele/{package}/{name}.class')==sha(compiled)for d in classes),f'Frozen runtime classpath is stale: {name}'
    lease_sha=sha(args.binding)
    lifts=read(OLD/'all90_candidate_lift_trip_cases.UNBOUND.json');interfaces=read(args.interfaces)
    assert len(interfaces)==7 and sum(len(r['landings'])for r in interfaces)==24
    measured={tuple(s['controller']):(r['id'],tuple(s['cabin_centre']))for r in interfaces for s in r['landings']}
    for case in lifts['cases']:
        for side in ('from','to'):
            assert measured[tuple(case[side+'_controller'])]==(case['group'],tuple(case[side+'_cabin'])),'Fresh measured controller/cabin identity differs; recapture pairs'
    security=read(args.security_job)
    for job in (lifts,security):
        assert job['world_id']==binding['world_id'] and int(job['world_seed'])==int(binding['world_seed'])
        job.update(bound=True,world=str(world),candidate_binding=str(args.binding.resolve()),candidate_binding_sha256=lease_sha)
    lifts.update(interfaces_file=str(args.interfaces.resolve()),interfaces_sha256=sha(args.interfaces),reason='Root prepared current compiled cold copied candidate')
    out.mkdir(parents=True)
    write(out/'all90_lift_trip_cases.bound.json',lifts);write(out/'all5_nerv_reader_cases.bound.json',security)
    props_base=[f'-Dprojectseele.nativeReviewWorld={world.name}',f'-Dprojectseele.nativeCandidateBindingR45={args.binding.resolve()}',
                f'-Dprojectseele.nativeCandidateBindingR45SHA256={lease_sha}',f'-Dprojectseele.nativeCandidateAdmissionR45={binding["preworld_receipt_output"]}',
                '-Dprojectseele.r45DeviceControlTrace=true','-Dprojectseele.r45TransportTrace=true']
    retire=('-Dprojectseele.regionalBuild=','-Dprojectseele.photo','-Dprojectseele.r45CityCreateDistrict=','-Dprojectseele.r45CityRigidQuality=',
            '-Dprojectseele.r45NervSecurity','-Dprojectseele.r45Lift','-Dprojectseele.r44LiftInterfaces=','-Dprojectseele.r44AccessReview=',
            '-Dprojectseele.nativeCandidate','-Dprojectseele.nativeReviewWorld=','-Dprojectseele.nativeSessionStopFileR45=')
    specs=[]
    for kind in ('lifts90','security5'):
        spec=copy.deepcopy(base);cmd=[s for s in command if not s.startswith(retire)]
        if kind=='lifts90':
            properties=props_base+['-Dprojectseele.regionalBuild=r44-lifts',f'-Dprojectseele.r45LiftTripCases={out/"all90_lift_trip_cases.bound.json"}',
                f'-Dprojectseele.r44LiftInterfaces={args.interfaces.resolve()}',f'-Dprojectseele.r45LiftOutput={out/"lifts90.native.json"}',
                '-Dprojectseele.r45LiftLifecyclePhase=current_native_function','-Dprojectseele.r40LiftStart=0','-Dprojectseele.r41LiftEnd=90']
        else:
            properties=props_base+['-Dprojectseele.regionalBuild=r45-nerv-security','-Dprojectseele.r45NervSecurityReview=true',
                f'-Dprojectseele.r45NervSecurityCases={out/"all5_nerv_reader_cases.bound.json"}',f'-Dprojectseele.r45NervSecurityOutput={out/"security5.native.json"}']
        cmd[1:1]=properties;spec['command']=cmd;write(out/(kind+'.launch.json'),spec);specs.append(dict(kind=kind,launch=str(out/(kind+'.launch.json')),properties=properties))
    if args.sequence_devices:
        spec=copy.deepcopy(base);cmd=[s for s in command if not s.startswith(retire)]
        combined=props_base+['-Dprojectseele.regionalBuild=r44-lifts','-Dprojectseele.r45DeviceSequence=true',
            f'-Dprojectseele.r45LiftTripCases={out/"all90_lift_trip_cases.bound.json"}',f'-Dprojectseele.r44LiftInterfaces={args.interfaces.resolve()}',
            f'-Dprojectseele.r45LiftOutput={out/"lifts90.native.json"}','-Dprojectseele.r40LiftStart=0','-Dprojectseele.r41LiftEnd=90',
            '-Dprojectseele.r45NervSecurityReview=true',f'-Dprojectseele.r45NervSecurityCases={out/"all5_nerv_reader_cases.bound.json"}',
            f'-Dprojectseele.r45NervSecurityOutput={out/"security5.native.json"}']
        if args.after_city_quality:
            assert args.city_control, 'A real City quality predecessor also needs its explicit real control job'
            quality,control=read(args.after_city_quality),read(args.city_control)
            for cityjob in (quality,control):
                assert cityjob['candidate_binding_sha256']==lease_sha and Path(cityjob['candidate_binding']).resolve()==args.binding.resolve()
                assert Path(cityjob['world']).resolve()==world and cityjob['world_id']==binding['world_id'] and int(cityjob['world_seed'])==int(binding['world_seed'])
            assert quality['mode'] in ('travel','resume') and quality['stop_server_when_done'] is False
            predecessor=Path(quality['output']).resolve()/'complete.json'
            assert not predecessor.exists() and not (predecessor.parent/'failed.json').exists(), 'City predecessor must be fresh in this same combined process'
            combined += [f'-Dprojectseele.r45CityCreateDistrict={args.city_control.resolve()}',f'-Dprojectseele.r45CityRigidQuality={args.after_city_quality.resolve()}',
                f'-Dprojectseele.r45DeviceAfterCityReceipt={predecessor}',f'-Dprojectseele.r45DeviceAfterCityDepth={quality["endpoint_depth"]}']
        cmd[1:1]=combined;spec['command']=cmd;write(out/'city_optional_lifts90_security5.sequence.launch.json',spec)
        specs.append(dict(kind='same_JVM_sequence',launch=str(out/'city_optional_lifts90_security5.sequence.launch.json'),properties=combined,
                          source_epoch='Root must apply/compile the sequence patch before this option is accepted'))
    write(out/'prepared_root_suite.json',dict(launches=specs,code=code,world_written=False,java_mc_gradle_launched=False,
        preworld_helper_unchanged=True,lease_admission_output=binding['preworld_receipt_output'],
        sequential_run_requires_new_cold_checkpoint_and_new_admission_receipt=True,
        ready_to_launch_only_one_selected_launch_with_this_lease=True,
        full_lifecycle_pass=False,qa_progress_must_not_ship=True))
    print('Prepared two alternative root launch specs. Use only ONE per fresh cold lease; rebind after normal close. No process launched.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binding',type=Path,required=True);p.add_argument('--base-launch',type=Path,required=True)
    p.add_argument('--interfaces',type=Path,required=True);p.add_argument('--security-job',type=Path,default=ART/'security_job_v3/nerv_security_native_job.json')
    p.add_argument('--out',type=Path,required=True);p.add_argument('--sequence-devices',action='store_true')
    p.add_argument('--after-city-quality',type=Path);p.add_argument('--city-control',type=Path);main(p.parse_args())
