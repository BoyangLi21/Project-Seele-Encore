"""Root handling210 scenario against an explicitly selected actual candidate."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,time
from run_r52_c8_targeted_native import sha,read,new_json,new_bytes,properties,atomic_bytes,detached_replace
from build_immutable_r52_candidate import frozen_build_class_pins

ROOT=Path(__file__).resolve().parents[1]
GAME=Path('D:/eva/artifacts/r51_nonmap_release/native_r51/game').resolve()
WORLD=GAME/'saves/SEELE_FIRST_BATTLE_REVIEW_R10'
OUT=ROOT/'artifacts/r52_native_handling_candidate10'
DEFAULT_NATIVE_OUTPUT=OUT
C10=ROOT/'artifacts/r52_unified_candidate10/projectseele-0.1.0-all.jar'
DEFAULT_CANDIDATE=C10.parent
BUILD=C10.parent/'BUILD_RECEIPT.json'
JDK=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin')

def verify(preflight):
 preflight=Path(preflight).resolve();assert preflight.is_relative_to(ROOT/'artifacts');receipt=read(preflight)
 if receipt['schema']=='projectseele.r52.handling210-offline-preflight.v2':
  assert receipt['candidate_qualified'] is True and receipt['scenario']=='C10_UNIT1_HANDLING210' and Path(receipt['actual_candidate']).resolve()==C10.parent
  for n,d in receipt['orchestration_sources'].items():assert sha(ROOT/n)==d,'Prechecked orchestration source changed: '+n
 else:
  assert receipt['schema']=='projectseele.r52.c10-handling-offline-preflight.v1' and receipt['C10_qualified'] is True and C10.parent==DEFAULT_CANDIDATE.resolve(),'A historical C10 preflight cannot qualify another candidate'
 assert receipt['baseline_only'] is False
 assert receipt['protocol']==70
 build=Path(receipt['build_receipt']).resolve();assert build==BUILD and build==C10.parent/'BUILD_RECEIPT.json' and sha(build)==receipt['build_receipt_sha256'] and sha(C10.parent/'SOURCE_BEFORE.json')==receipt['SOURCE_BEFORE_sha256']
 assert frozen_build_class_pins(build,C10)==receipt['required_delivery_classes']
 assert not receipt['reflection_failed'] and receipt['reflection_checks']>=181 and receipt['property_keys_unique'] and receipt['planned_outputs_entirely_new']
 tools=preflight.parent;launch_path=tools/'PLANNED_LAUNCH.json';args_path=tools/'PLANNED_LAUNCH.args';assert sha(launch_path)==receipt['planned_launch_sha256'] and sha(args_path)==receipt['planned_args_sha256'];launch=read(launch_path)
 assert Path(launch['immutable_jar']['path']).resolve()==C10.resolve() and launch['immutable_jar']==receipt['immutable_jar'] and sha(C10)==receipt['immutable_jar']['sha256']
 assert Path(launch['native_output']).resolve()==Path(receipt['expected_native_output']).resolve()==OUT.resolve()
 assert Path(launch['world']).resolve()==WORLD and 'WORLD_R52' not in str(WORLD) and Path(launch['workingDirectory']).resolve()==GAME
 assert Path(launch['staged_jar']['path']).resolve()==GAME/'mods/projectseele-0.1.0-all.jar' and launch['staged_jar']['sha256']==receipt['immutable_jar']['sha256']
 command=launch['command'];assert Path(command[0]).resolve()==(JDK/'java.exe').resolve() and Path(command[command.index('--gameDir')+1]).resolve()==GAME and command[command.index('--quickPlaySingleplayer')+1]==WORLD.name
 props=properties(command);assert launch['properties']=={k.removeprefix('projectseele.'):v for k,v in props.items() if k.startswith('projectseele.')}
 for k,v in dict(regionalBuild='ordinary-motion-r52',ordinaryHandlingOnlyR52='true',ordinaryHandlingC10R52='true',firstBattleThenOrdinaryR52='false',firstBattleThenHandlingR52='false',firstBattleBerserkReviewR52='false',firstBattleMovieOnly='false',firstBattleRuntimeWitnessR52='false').items():assert props['projectseele.'+k]==v,k
 assert Path(props['projectseele.ordinaryMotionOutputR52']).resolve()==OUT/'ordinary' and Path(props['projectseele.r47NativeCommandInbox']).resolve()==OUT/'commands.json'
 assert receipt['sequence']['final_C12_movies']==0 and receipt['sequence']['repeated_ordinary_movie']==0 and receipt['sequence']['ordinary_variants']==[1] and receipt['sequence']['ordinary_ticks']==210
 bundle=Path(launch['bundle_directory']).resolve();assert bundle.is_relative_to(ROOT/'artifacts') and sha(bundle/'combat_bundle_r44.json')==receipt['runtime_contract_sha256']
 for n,d in launch['runtime_fingerprints'].items():assert sha(bundle/n)==d,n
 assert sha(tools/'ordinary_motion_agent.jar')==receipt['tool_agent_sha256']
 assert {n.replace('\\','/') for n in receipt['tool_sources']}=={'tools/java/C10HandlingR52Agent.java','tools/java/C10HandlingR52Attach.java','tools/java/VerifyC10HandlingToolModesR52.java'}
 for n,d in dict(receipt['tool_sources'],**receipt['reviewed_motion_sources']).items():assert sha(ROOT/n)==d,'Prechecked source changed: '+n
 assert (tools/'tool_classes/C10HandlingR52Attach.class').is_file() and (WORLD/'level.dat').is_file() and not(WORLD/'r10_resume_expected.json').exists()
 return receipt,launch,tools,preflight

def stage(preflight):
 receipt,launch,tools,preflight=verify(preflight);OUT.mkdir(parents=True,exist_ok=False);(OUT/'ordinary').mkdir();target=Path(launch['staged_jar']['path']);expected=receipt['immutable_jar']['sha256']
 try:
  assert target.is_file();before=sha(target)
  if before!=expected:
   with target.open('rb') as src,(OUT/'previous_host_jar.jar').open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
   assert sha(OUT/'previous_host_jar.jar')==before
  new_bytes(OUT/'options.before.txt',(GAME/'options.txt').read_bytes());new_bytes(OUT/'fixture.level.dat.before',(WORLD/'level.dat').read_bytes());detached_replace(C10,target,expected)
  launch.update(ready_to_launch=True,staging_pending=False,offline_only=False);new_json(OUT/'launch.json',launch);new_bytes(OUT/'launch.args',(tools/'PLANNED_LAUNCH.args').read_bytes());new_json(OUT/'commands.json',{'seq':1,'commands':[]})
  new_json(OUT/'STAGING_RECEIPT.json',dict(preflight=str(preflight),preflight_sha256=sha(preflight),planned_launch_sha256=receipt['planned_launch_sha256'],planned_args_sha256=receipt['planned_args_sha256'],tool_agent_sha256=receipt['tool_agent_sha256'],immutable_jar=receipt['immutable_jar'],previous_host_jar_sha256=before,staged_jar_sha256=sha(target),detached_atomic_copy=True,original_options_sha256=sha(OUT/'options.before.txt'),output_CREATED_NEW=True,authoritative_world_written=False,game_started=False))
  print('Handling210 staged for',C10.parent.name,'; original options and previous host JAR preserved.',flush=True)
 except BaseException as e:new_json(OUT/'STAGING_FAILURE.json',dict(error=repr(e),game_started=False,evidence_retained=True));raise

def quit_owned(process):
 if process.poll() is not None:return False
 new_bytes(OUT/'commands.before.quit.json',(OUT/'commands.json').read_bytes());atomic_bytes(OUT/'commands.json',(json.dumps({'seq':1000,'commands':[],'quit':True})+'\n').encode())
 try:process.wait(timeout=20);return False
 except subprocess.TimeoutExpired:
  process.terminate()
  try:process.wait(timeout=15)
  except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
  return True

def run(preflight):
 receipt,planned,tools,preflight=verify(preflight);staged=read(OUT/'STAGING_RECEIPT.json');assert staged['preflight_sha256']==sha(preflight) and not(OUT/'RUNNING.json').exists(),'One actual attempt only'
 launch=read(OUT/'launch.json');assert launch['ready_to_launch'] and sha(OUT/'launch.args')==receipt['planned_args_sha256'] and sha(Path(launch['staged_jar']['path']))==receipt['immutable_jar']['sha256']
 original=(OUT/'options.before.txt').read_bytes();assert hashlib.sha256(original).hexdigest()==staged['original_options_sha256'] and (GAME/'options.txt').read_bytes()==original,'Original options changed since staging'
 env=dict(os.environ);env.update(launch.get('environment',{}));process=None;attached=False;forced=False;timed_out=False;failure=None;begin=time.monotonic();log=(OUT/'process.log').open('xb');err=(OUT/'process.error.log').open('xb')
 try:
  process=subprocess.Popen([launch['command'][0],'@'+str(OUT/'launch.args')],cwd=GAME,env=env,stdout=log,stderr=err,creationflags=0x08000000 if os.name=='nt' else 0)
  new_json(OUT/'RUNNING.json',dict(pid=process.pid,started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),immutable_jar=receipt['immutable_jar'],world=str(WORLD),original_options_sha256=staged['original_options_sha256']));print('C10 native PID',process.pid,'Unit1 handling210 only.',flush=True);logged=None;status=0
  while process.poll() is None and time.monotonic()-begin<900:
   # Inspect the owned game's log; do not manipulate another desktop window
   # or repeatedly load an ever-growing logfile to detect login.
   with (OUT/'process.log').open('rb') as current_log:
    current_log.seek(max(0,os.fstat(current_log.fileno()).st_size-262144))
    text=current_log.read().decode('utf8',errors='replace')
   if logged is None and 'logged in with entity id' in text:logged=time.monotonic()
   if not attached and logged is not None and time.monotonic()-logged>=2:
    r=subprocess.run([str(JDK/'java.exe'),'-Xmx256m','-cp',str(tools/'tool_classes'),'C10HandlingR52Attach',str(process.pid),str(tools/'ordinary_motion_agent.jar')],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=30)
    with(OUT/'attach.log').open('x',encoding='utf8') as f:f.write(r.stdout+r.stderr)
    assert r.returncode==0,'Prechecked native attach failed';attached=True;print('Handling-only tool attached.',flush=True)
   if(OUT/'ordinary/FAILURE.json').exists():raise RuntimeError((OUT/'ordinary/FAILURE.json').read_text('utf8'))
   elapsed=time.monotonic()-begin
   if elapsed-status>=25:status=elapsed;print('C10',round(elapsed,1),'seconds;', 'Unit1 handling' if attached else 'boot',flush=True)
   time.sleep(.5)
  timed_out=process.poll() is None
  if timed_out:raise TimeoutError('C10 targeted handling bounded deadline exceeded')
 except BaseException as e:failure=repr(e);new_json(OUT/'RUNNER_FAILURE.json',dict(error=failure,evidence_retained=True,native_acceptance=False))
 finally:
  try:
   if process is not None and process.poll() is None:forced=quit_owned(process)
  finally:
   log.close();err.close();atomic_bytes(GAME/'options.txt',original);new_json(OUT/'OPTIONS_RESTORED.json',dict(before_sha256=hashlib.sha256(original).hexdigest(),after_sha256=sha(GAME/'options.txt'),byte_equal=(GAME/'options.txt').read_bytes()==original,process_exited_before_restore=process is None or process.poll() is not None));print('Original options restored byte-for-byte after process exit.',flush=True)
 complete=read(OUT/'ordinary/CAPTURE_COMPLETE.json') if(OUT/'ordinary/CAPTURE_COMPLETE.json').is_file() else {};actual=read(OUT/'ordinary/ATTACHED.json') if(OUT/'ordinary/ATTACHED.json').is_file() else {}
 functional=bool(process is not None and process.returncode==0 and failure is None and not forced and not timed_out and attached and complete.get('input_sequence_complete') is True and complete.get('native_frames',0)>0 and actual.get('ordinary_variants')==[1] and actual.get('sequence_lengths_ticks')==[210] and not(OUT/'firstbattle').exists() and not(OUT/'ordinary/FIRST_BATTLE_COMPLETED_BEFORE_ORDINARY.json').exists())
 result=dict(pid=process.pid if process else None,elapsed_seconds=time.monotonic()-begin,exit_code=process.returncode if process else None,natural_exit=failure is None and not timed_out and not forced and process is not None and process.returncode==0,attached=attached,timed_out=timed_out,forced_cleanup=forced,failure=failure,functional_capture_complete=functional,ordinary_complete=bool(complete),ordinary_variants=actual.get('ordinary_variants'),ordinary_ticks=actual.get('sequence_lengths_ticks'),immutable_jar=receipt['immutable_jar'],first_battle_movies=0,native_visual_acceptance=False,limits='Natural functional capture alone does not pass guard/support. Read every actual draw/stow outlet/final pose, transition clock/history and original-shoe matrices before acceptance.')
 result.update(actual_candidate=str(C10.parent),scenario='C10_UNIT1_HANDLING210',build_receipt=str(BUILD),build_receipt_sha256=receipt['build_receipt_sha256'],preflight_sha256=sha(preflight),native_output=str(OUT))
 new_json(OUT/'RUN_RESULT.json',result);print(json.dumps(result,indent=2),flush=True);assert functional,'Handling210 capture incomplete; evidence retained, no automatic retry'

def main():
 global C10,OUT,BUILD
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--preflight',required=True,type=Path);ap.add_argument('--actual-candidate',type=Path,default=DEFAULT_CANDIDATE);ap.add_argument('--build-receipt',type=Path);ap.add_argument('--native-output',type=Path);ap.add_argument('--stage',action='store_true');ap.add_argument('--run',action='store_true');a=ap.parse_args()
 candidate=a.actual_candidate.resolve();assert candidate.is_relative_to(ROOT/'artifacts') and candidate!=ROOT/'artifacts'
 if candidate!=DEFAULT_CANDIDATE.resolve():assert a.build_receipt is not None and a.native_output is not None and a.native_output.resolve()!=DEFAULT_NATIVE_OUTPUT.resolve(),'Explicit new candidate build/new capture paths required'
 C10=candidate/'projectseele-0.1.0-all.jar';BUILD=(a.build_receipt or candidate/'BUILD_RECEIPT.json').resolve();OUT=(a.native_output or OUT).resolve()
 assert BUILD==candidate/'BUILD_RECEIPT.json' and OUT.is_relative_to(ROOT/'artifacts') and OUT!=candidate and OUT!=ROOT/'artifacts'
 verify(a.preflight)
 if a.stage:stage(a.preflight)
 if a.run:run(a.preflight)
 if not a.stage and not a.run:print('Actual handling210 candidate/preflight/JAR/source/tool/runtime SHA verified; no staging or game:',candidate,flush=True)
if __name__=='__main__':main()
