"""Run one cold, explicitly bound QA client with normal bounded shutdown.

Consumes a prepared full Create classpath and a verified shared-session
manifest. Never invokes Gradle, moves a player, or runs a photo itinerary.
"""
from pathlib import Path
import argparse, hashlib, json, os, subprocess, sys, time
from release_combat_r36 import guard
from launch_rendered_client_r17 import java_environment

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--complete',type=Path,required=True)
    p.add_argument('--failed',type=Path,required=True);p.add_argument('--timeout',type=int,default=420)
    p.add_argument('--jvm-diagnostics',action='store_true',help='Record JFR and GC/safepoint logs in the private run output')
    p.add_argument('--observation-fact',type=Path,help='Stop normally after a fresh stock-blocking fact and bounded face observation; never a city completion pass')
    p.add_argument('--execute-root',action='store_true');a=p.parse_args();guard()
    assert a.execute_root and 30<=a.timeout<=1800
    m=json.loads(a.manifest.read_text('utf8'));assert m['role']=='QA_ONLY_NOT_A_RELEASE_SOURCE'
    out=a.out.resolve();assert out.is_relative_to(ROOT/'artifacts/rebuild_r45') and not out.exists();out.mkdir(parents=True)
    checker=ROOT/'artifacts/rebuild_r45/candidate_transport_acceptance_sol_v1/preflight_shared_session.py'
    classifications=('qa_inflight_checkpoint','qa_settled_checkpoint','qa_inflight_move1_checkpoint','qa_ground_compensated_checkpoint')
    assert sum(bool(m.get(k))for k in classifications)<=1,'Checkpoint classification must be unambiguous'
    if any(m.get(k)for k in classifications):
        row=m['preflight_tool'];checker=Path(row['path']).resolve()
        assert checker.is_relative_to(ROOT/'artifacts/rebuild_r45') and sha(checker)==row['sha256']
        assert not m.get('unplaced_fault_recovery'),'An in-flight or settled state cannot use unplaced cancellation'
    subprocess.run([sys.executable,'-X','utf8',str(checker),str(a.manifest.resolve()),'--out',str(out/'cold_preflight.json')],check=True,cwd=ROOT)
    check=json.loads((out/'cold_preflight.json').read_text());assert check['ready']
    prepared=a.manifest.parent/m['prepared_launch'];assert sha(prepared)==m['prepared_launch_sha256']
    spec=json.loads(prepared.read_text());game=Path(m['gameDir']).resolve()
    assert Path(spec['workingDirectory']).resolve()==game
    command=spec['command'];assert Path(command[command.index('--gameDir')+1]).resolve()==game
    assert command[command.index('--quickPlaySingleplayer')+1]==m['logical_basename']
    for signal in (a.complete,a.failed):assert not signal.exists(),'Fresh native output required'
    controllers=[]
    for entry in spec['environment']['MOD_CLASSES'].split(';'):
        if entry.startswith('projectseele%%'):
            file=Path(entry.split('%%',1)[1])/'com/projectseele/client/visual/NativeSessionControlR45.class'
            if file.is_file():controllers.append(dict(path=str(file),sha256=sha(file)))
    assert controllers,'Prepared frozen classes lack the graceful QA session controller'
    stop=out/'request_normal_stop.signal'
    binding=json.loads(Path(m['city_native_binding']['path']).read_text('utf8'))
    observation=None;observation_faces=None;observed=False
    if a.observation_fact:
        observation=a.observation_fact.resolve()
        assert m.get('qa_inflight_move1_checkpoint'),'This observation is scoped to the admitted MOVE1 recovery-free diagnostic'
        assert observation.parent==Path(m['city_native_binding']['path']).resolve().parent
        observation_faces=observation.with_name(observation.name+'.faces.json')
        assert not observation.exists() and not observation_faces.exists(),'Fresh observation outputs required'
    admission=Path(binding['preworld_receipt_output']).resolve()
    assert admission.is_relative_to(ROOT/'artifacts/rebuild_r45') and not admission.exists()
    command=[s for s in command if not s.startswith(('-Xmx','-Xms','-Dprojectseele.regionalBuild=','-Dprojectseele.photoCaptureHoldTicks=','-Dprojectseele.nativeSessionStopFileR45=','-Dprojectseele.nativeCandidateBindingR45=','-Dprojectseele.nativeCandidateBindingR45SHA256=','-Dprojectseele.nativeCandidateAdmissionR45='))]
    command[1:1]=['-Xms1G','-Xmx6G','-Dprojectseele.regionalBuild=r45-city-native',
        '-Dprojectseele.nativeSessionStopFileR45='+stop.as_posix(),
        '-Dprojectseele.nativeCandidateBindingR45='+str(Path(m['city_native_binding']['path']).resolve()),
        '-Dprojectseele.nativeCandidateBindingR45SHA256='+m['city_native_binding']['sha256'],
        '-Dprojectseele.nativeCandidateAdmissionR45='+admission.as_posix()]
    if a.jvm_diagnostics:
        # Relative paths avoid Windows drive-colon ambiguity in -Xlog syntax.
        # Output is private QA data and is never included in delivery packages.
        diagnostic_dir=Path(os.path.relpath(out,game)).as_posix()
        command[1:1]=[
            '-XX:StartFlightRecording=name=SEELE_READY,settings=profile,dumponexit=true,maxsize=128m,filename='+diagnostic_dir+'/runtime.jfr',
            '-Xlog:gc*,safepoint:file='+diagnostic_dir+'/gc.log:time,uptime,level,tags:filecount=2,filesize=16m']
    spec['command']=command;(out/'launch.json').write_text(json.dumps(spec,indent=2),'utf8')
    def quoted(value):
        assert not any(c in value for c in '\r\n\0')
        return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'
    argfile=out/'launch.args';argfile.write_text('\n'.join(quoted(s)for s in command[1:]),'utf8')
    env=java_environment()[1];env.update(spec['environment']);started=time.monotonic();forced=False;reason=''
    with (out/'native.log').open('w',encoding='utf8')as log:
        process=subprocess.Popen([command[0],'@'+str(argfile)],cwd=game,env=env,
            stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/'process.json').write_text(json.dumps(dict(pid=process.pid,world_role=m['role'],manifest_sha256=sha(a.manifest),controllers=controllers)),encoding='utf8')
        while process.poll() is None:
            admission_failed=admission.is_file() and not json.loads(admission.read_text('utf8')).get('passed',False)
            if observation and observation.is_file() and observation_faces.is_file():
                try:
                    fact=json.loads(observation.read_text('utf8'));faces=json.loads(observation_faces.read_text('utf8'))
                    observed=bool(fact.get('stock_blocked_return') and fact.get('saved_before_stop') and fact.get('world_written') is False and faces.get('world_written') is False)
                except (OSError,json.JSONDecodeError):
                    observed=False  # CREATE_NEW can become visible before its write completes.
            reason='preworld_admission_failed'if admission_failed else'native_failed'if a.failed.exists()else'native_complete'if a.complete.exists()else'observation_captured'if observed else'timeout'if time.monotonic()-started>a.timeout else''
            if reason:
                stop.write_text(reason,encoding='utf8')
                try:process.wait(timeout=45)
                except subprocess.TimeoutExpired:forced=True;process.terminate();process.wait(timeout=15)
                break
            time.sleep(.5)
    success=process.returncode==0 and a.complete.is_file()and not a.failed.exists()and not forced
    receipt=dict(process_exit=process.returncode,stop_reason=reason,forced_termination=forced,seconds=time.monotonic()-started,
        preworld_receipt=str(admission),
        complete_present=a.complete.is_file(),failure_present=a.failed.is_file(),process_and_output_gate=success,
        observation_requested=observation is not None,observation_captured=observed,
        observation_is_not_city_completion=True,
        world_role=m['role'],qa_progress_must_not_ship=True,native_result_scope_requires_separate_inspection=True,
        jvm_diagnostics_requested=a.jvm_diagnostics,jfr_present=(out/'runtime.jfr').is_file(),gc_log_present=(out/'gc.log').is_file(),
        declared_launcher_changes=['6G test heap, 1G initial; server package remains separate20G','Disable unrelated old photo itinerary','Opt-in pause/shutdown controller; no pose, camera or gameplay input override'])
    (out/'process_receipt.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt))
    if not success and not(process.returncode==0 and reason=='observation_captured' and not forced):
        raise SystemExit('Preserve native failure/log and current QA checkpoint; do not promote')


if __name__=='__main__':main()
