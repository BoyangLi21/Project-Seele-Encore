"""One authorized R10 process: native first begin/movie, then actual ordinary inputs."""
from pathlib import Path
import argparse,ctypes,hashlib,json,os,shutil,subprocess,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
JDK=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin')
JAR=ROOT/'artifacts/r52_unified_candidate7/projectseele-0.1.0-all.jar'
JAR_SHA='6f5bbf3c03c536fe96cd9d3d318f229b3eb5f6b0e23699b51c256bcc65d7d8be'
CLIP=ROOT/'artifacts/r52_finisher_body3f_early_guard1/early_guard_supported_sidestep11.json'
CLIP_SHA='4f58f66a8ce5813efaecac371ccccbc50e0e74b0638283d81868f1ffc23fe61b'
OUT=ROOT/'artifacts/r52_native_combined_candidate7'
TOOLS=ROOT/'artifacts/r52_native_combined_candidate7_tools'
GAME=Path('D:/eva/artifacts/r51_nonmap_release/native_r51/game')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,d):p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2),'utf8')
def quote(v):
 assert not any(c in v for c in '\r\n\0');return '"'+v.replace('\\','\\\\').replace('"','\\"')+'"'
def hide(pid):
 if os.name!='nt':return
 user=ctypes.windll.user32
 @ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
 def each(hwnd,arg):
  owner=ctypes.c_ulong();user.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
  if owner.value==pid:user.ShowWindow(hwnd,0)
  return True
 user.EnumWindows(each,0)
def prepare():
 assert digest(JAR)==JAR_SHA and digest(CLIP)==CLIP_SHA
 assert not (OUT/'RUNNING.json').exists(),'Preserve every attempted native run'
 preflight=json.loads((TOOLS/'EXTENDED_CLASSFILE_REFLECTION_PREFLIGHT.json').read_text('utf8'));assert not preflight['failed']
 assert (TOOLS/'FirstBattleR10Client_verified_handoff.class').is_file()
 spec=json.loads((ROOT/'artifacts/r52_native_ordinary_candidate6_retry1/launch.json').read_text('utf8'))
 world=Path(spec['world']).resolve();assert world==GAME.resolve()/'saves/SEELE_FIRST_BATTLE_REVIEW_R10' and (world/'level.dat').is_file() and 'WORLD_R52' not in str(world)
 assert not(world/'r10_resume_expected.json').exists()
 bundle=Path(spec['bundle_directory']);assert digest(bundle/'eva_body_r44.json')=='cd9ba815c44a6ca60824417ae76b25de9db1936b655ec035b62775fa41d380f9'
 for name,value in spec['runtime_fingerprints'].items():assert digest(bundle/name)==value,name
 destination=GAME/'mods/projectseele-0.1.0-all.jar';assert destination.resolve().parent==(GAME/'mods').resolve()
 before=digest(destination);assert before in {JAR_SHA,'3e84e0f6cfe0544535002f52fc004d457742846cc8cd36d320ad824aae4d7146'}
 temporary=destination.with_suffix('.r52-c7-detached.tmp');assert not temporary.exists();shutil.copyfile(JAR,temporary);assert digest(temporary)==JAR_SHA;os.replace(temporary,destination);assert digest(JAR)==JAR_SHA
 with zipfile.ZipFile(destination) as z:assert 'com/projectseele/entity/EvaOrdinaryStandingSupportR52.class' in z.namelist()
 command=[v for v in spec['command'] if not v.startswith('-Dprojectseele.')]
 properties=dict(regionalBuild='r10-firstbattle',firstBattleMovieOnly='true',firstBattleBerserkReviewR52='true',firstBattleFollowupOrdinaryReviewR52='true',firstBattleControlRecoveryCaptureR52='true',firstBattleCloseViewsR52='true',firstBattleNoFrameCaptureR52='false',firstBattleKeyFramesR52='false',firstBattleFrameMetadataR52='false',firstBattleRuntimeWitnessR52='true',firstBattleReviewClip=str(CLIP),firstBattleCaptureOutputR52=str(OUT/'firstbattle/frames'),firstBattleRuntimeWitnessR52Output=str(OUT/'firstbattle/native.jsonl'),firstBattleThenOrdinaryR52='true',ordinaryMotionWorldR52=str(world),ordinaryMotionOutputR52=str(OUT/'ordinary'),r47NativeCommandInbox=str(OUT/'commands.json'),combatBundleDirectory=str(bundle))
 command[1:1]=['-Dprojectseele.'+k+'='+v for k,v in properties.items()]
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'firstbattle').mkdir(exist_ok=True);(OUT/'ordinary').mkdir(exist_ok=True)
 spec.update(command=command,staged_jar=dict(path=str(destination),sha256=JAR_SHA),immutable_jar=dict(path=str(JAR),sha256=JAR_SHA),review_clip=str(CLIP),candidate_sha256=CLIP_SHA,properties=properties,ready_to_launch=True)
 write('launch.json',spec);(OUT/'launch.args').write_text('\n'.join(quote(v) for v in command[1:])+'\n','utf8');write('commands.json',dict(seq=1,commands=[]));write('STAGING_RECEIPT.json',dict(previous_host_jar_sha256=before,detached_atomic_copy=True,immutable_source_jar_sha256=JAR_SHA,review_clip_sha256=CLIP_SHA,review_override_only=True,permanent_clip_bundle_modified=False,fixture_reused=True,world_directory_copies=0,authoritative_world_access=False,src_main_modified=False))
 print('Prepared one combined native run; JAR/clip/reflection/QA exit handoff verified.',flush=True)
def run():
 assert not(OUT/'RUNNING.json').exists();spec=json.loads((OUT/'launch.json').read_text('utf8'));assert digest(JAR)==JAR_SHA and digest(Path(spec['staged_jar']['path']))==JAR_SHA and digest(CLIP)==CLIP_SHA
 options=GAME/'options.txt';original=options.read_bytes();option_sha=hashlib.sha256(original).hexdigest();assert option_sha=='0501a9890883772eb585797421c8a6cc848a5720c52ad21c06cfd1a44552ca88';(OUT/'options.before.txt').write_bytes(original)
 log=(OUT/'process.log').open('wb');error=(OUT/'process.error.log').open('wb');env=dict(os.environ);env.update(spec.get('environment',{}));before=time.monotonic();process=None;attached=False;timed_out=False
 try:
  process=subprocess.Popen([spec['command'][0],'@'+str(OUT/'launch.args')],cwd=spec['workingDirectory'],env=env,stdout=log,stderr=error,creationflags=0x08000000)
  write('RUNNING.json',dict(pid=process.pid,immutable_jar_sha256=JAR_SHA,clip_sha256=CLIP_SHA,world=spec['world'],options_original_sha256=option_sha,started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())));print('Combined C7 native PID',process.pid,flush=True)
  logged_at=None;last_status=0
  while process.poll() is None and time.monotonic()-before<600:
   hide(process.pid);text=(OUT/'process.log').read_text('utf8',errors='replace')
   if logged_at is None and 'logged in with entity id' in text:logged_at=time.monotonic()
   if not attached and logged_at is not None and time.monotonic()-logged_at>=2:
    result=subprocess.run([str(JDK/'java.exe'),'-cp',str(TOOLS/'tool_classes'),'OrdinaryMotionR52Attach',str(process.pid),str(TOOLS/'ordinary_motion_agent.jar')],capture_output=True,text=True);(OUT/'attach.log').write_text(result.stdout+result.stderr,'utf8');assert result.returncode==0,result.stderr;attached=True;print('Attached prechecked tool: raw first-battle capture precedes ordinary input replay.',flush=True)
   elapsed=time.monotonic()-before
   if elapsed-last_status>=25:
    last_status=elapsed;phase='ordinary actual input' if (OUT/'ordinary/FIRST_BATTLE_COMPLETED_BEFORE_ORDINARY.json').exists() else 'first-battle actual capture' if attached else 'boot';print('Native C7',round(elapsed,1),'seconds;',phase,flush=True)
   if (OUT/'ordinary/FAILURE.json').exists():print('Explicit QA failure:',(OUT/'ordinary/FAILURE.json').read_text(),flush=True)
   time.sleep(.5)
  timed_out=process.poll() is None
  if timed_out:
   write('commands.json',dict(seq=1000,commands=[],quit=True))
   try:process.wait(timeout=30)
   except subprocess.TimeoutExpired:pass
 finally:
  log.close();error.close();temporary=options.with_suffix('.r52-options-restore.tmp');temporary.write_bytes(original);os.replace(temporary,options);write('OPTIONS_RESTORED.json',dict(before_sha256=option_sha,after_sha256=digest(options),passed=digest(options)==option_sha));print('Exact original options restored.',flush=True)
 if process is None:return
 complete=(OUT/'ordinary/CAPTURE_COMPLETE.json').is_file();first_complete=(OUT/'ordinary/FIRST_BATTLE_COMPLETED_BEFORE_ORDINARY.json').is_file();result=dict(pid=process.pid,elapsed_seconds=time.monotonic()-before,exit_code=process.poll(),natural_exit=not timed_out and process.poll()==0,attached=attached,timed_out=timed_out,first_battle_completed_before_ordinary=first_complete,ordinary_complete=complete,immutable_jar_sha256=JAR_SHA,review_clip_sha256=CLIP_SHA,native_visual_acceptance=False)
 write('RUN_RESULT.json',result);print(json.dumps(result,indent=2),flush=True);assert result['natural_exit'] and attached and complete and first_complete
 assert json.loads((OUT/'ordinary/CAPTURE_COMPLETE.json').read_text('utf8'))['native_frames']>0
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--run',action='store_true');args=ap.parse_args()
 if args.prepare:prepare()
 if args.run:run()
