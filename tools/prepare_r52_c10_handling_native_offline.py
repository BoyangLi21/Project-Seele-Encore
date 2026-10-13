"""Offline handling210 scenario against an explicitly selected immutable build."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,zipfile
from prepare_r52_c8_native_offline import ROOT,JDK,ASM,GAME,RUNTIME,BODY_SHA,CLIP_SHA,PREVIOUS,sha,read,write,quote,unique_properties,checked_run
from release_r45_contract import class_protocol
from build_immutable_r52_candidate import frozen_build_class_pins
FUTURE=ROOT/'artifacts/r52_native_handling_candidate10'
DEFAULT_NATIVE_OUTPUT=FUTURE
C10=ROOT/'artifacts/r52_unified_candidate10/projectseele-0.1.0-all.jar'
DEFAULT_CANDIDATE=C10.parent
TOOL_NAMES=('C10HandlingR52Agent.java','C10HandlingR52Attach.java','VerifyC10HandlingToolModesR52.java')

def compile_tools(out):
 classes=out/'tool_classes';classes.mkdir();sources=[ROOT/'tools/java'/n for n in TOOL_NAMES];cp=';'.join(map(str,ASM))
 for dependency in ASM:assert dependency.is_file()
 checked_run([str(JDK/'javac.exe'),'-J-Xmx256m','-encoding','UTF-8','-cp',cp,'-d',str(classes),*map(str,sources)],out/'compile.log')
 agent=out/'ordinary_motion_agent.jar'
 with zipfile.ZipFile(agent,'x',zipfile.ZIP_DEFLATED) as z:
  z.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\nAgent-Class: C10HandlingR52Agent\nCan-Retransform-Classes: true\n\n')
  for p in classes.glob('C10HandlingR52Agent*.class'):z.write(p,p.name)
 return classes,sources,cp,agent

def frozen_motion():
 motion=read(ROOT/'.codex/r52_motion_final_freeze/FINAL_MOTION_SOURCE_HANDOFF.json')['freeze_ready_sources']
 assert len(motion)==3
 for n,h in motion.items():assert sha(ROOT/n)==h,'Reviewed ordinary source changed: '+n
 return motion

def orchestration_sources():
 return {str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),ROOT/'tools/run_r52_c10_handling_native.py',ROOT/'tools/preflight_r52_c10_handling_reflection.py')}

def prepare_tools_only(out,build_path):
 assert out.is_relative_to(ROOT/'artifacts') and not out.is_relative_to(FUTURE) and not FUTURE.is_relative_to(out) and not out.is_relative_to(C10.parent) and not out.exists() and not FUTURE.exists(),'Fresh separate preparation/native/build namespaces required'
 motion=frozen_motion();out.mkdir(parents=True);classes,sources,cp,agent=compile_tools(out)
 # Mode guards can be checked without substituting any old project JAR.
 source=out/'C10AttachModeCheck.java';source.write_text('''import java.util.*;
public class C10AttachModeCheck {
 public static void main(String[] args){Properties p=new Properties();p.setProperty("projectseele.regionalBuild","ordinary-motion-r52");p.setProperty("projectseele.ordinaryHandlingC10R52","true");p.setProperty("projectseele.ordinaryHandlingOnlyR52","true");C10HandlingR52Attach.verifyTarget(p);int checks=1;
 for(String key:List.of("projectseele.ordinaryHandlingC10R52","projectseele.ordinaryHandlingOnlyR52","projectseele.firstBattleThenOrdinaryR52","projectseele.firstBattleThenHandlingR52")){Properties q=new Properties();q.putAll(p);q.setProperty(key,key.contains("firstBattle")?"true":"false");boolean rejected=false;try{C10HandlingR52Attach.verifyTarget(q);}catch(IllegalStateException expected){rejected=true;}if(!rejected)throw new AssertionError(key);checks++;}System.out.println("PASS explicit standalone C10 attach-mode guard "+checks+" checks; no target JVM/JAR/native run");}
}''','utf8')
 checked_run([str(JDK/'javac.exe'),'-J-Xmx128m','-cp',str(classes),'-d',str(classes),str(source)],out/'mode_compile.log')
 mode=checked_run([str(JDK/'java.exe'),'-Xmx128m','-cp',str(classes),'C10AttachModeCheck'],out/'mode_check.log')
 write(out/'TOOL_PREPARATION_RECEIPT.json',dict(schema='projectseele.r52.handling210-tools-preparation.v2',scenario='C10_UNIT1_HANDLING210',candidate_qualified=False,actual_candidate=str(C10.parent),expected_native_output=str(FUTURE),final_build_pending=True,actual_candidate_jar=None,actual_candidate_sha256=None,required_candidate_jar=str(C10),required_build_receipt=str(build_path),required_protocol=70,tool_sources={str(p.relative_to(ROOT)):sha(p)for p in sources},orchestration_sources=orchestration_sources(),tool_agent_sha256=sha(agent),compiled_class_sha256={p.name:sha(p)for p in classes.glob('*.class')},reviewed_motion_sources=motion,mode_check=mode,ASM={str(p):sha(p)for p in ASM},final_reflection_executed=False,final_transform_executed=False,world_written=False,game_written=False,game_started=False,attach_executed=False,native_acceptance=False,reason='Only scenario tools/mode checks were prepared. The selected actual Jar/BUILD_RECEIPT must pass a fresh separate offline preflight; no previous build or native result is substituted.'))
 print(json.dumps(dict(tools_prepared=True,candidate_qualified=False,actual_candidate=str(C10.parent),final_build_pending=True,game_started=False,receipt=str(out/'TOOL_PREPARATION_RECEIPT.json'))))

def main():
 global C10,FUTURE
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--actual-candidate',type=Path,default=DEFAULT_CANDIDATE);ap.add_argument('--native-output',type=Path);ap.add_argument('--jar',type=Path);ap.add_argument('--jar-sha256');ap.add_argument('--build-receipt',type=Path);ap.add_argument('--out',required=True,type=Path);ap.add_argument('--prepare-tools-only',action='store_true');a=ap.parse_args()
 candidate=a.actual_candidate.resolve();assert candidate.is_relative_to(ROOT/'artifacts') and candidate!=ROOT/'artifacts'
 if candidate!=DEFAULT_CANDIDATE.resolve():assert a.native_output is not None and a.build_receipt is not None and a.native_output.resolve()!=DEFAULT_NATIVE_OUTPUT.resolve(),'Explicit new candidate build/new capture paths required'
 C10=candidate/'projectseele-0.1.0-all.jar';FUTURE=(a.native_output or FUTURE).resolve();assert FUTURE.is_relative_to(ROOT/'artifacts') and FUTURE!=candidate and FUTURE!=ROOT/'artifacts'
 build_path=(a.build_receipt or candidate/'BUILD_RECEIPT.json').resolve();assert build_path==candidate/'BUILD_RECEIPT.json'
 if a.prepare_tools_only:
  assert a.jar is None and a.jar_sha256 is None,'Tools preparation never consumes a project Jar'
  prepare_tools_only(a.out.resolve(),build_path);return
 assert a.jar is not None and a.jar_sha256 is not None and a.build_receipt is not None,'Final actual C10 Jar/SHA/BUILD_RECEIPT required'
 jar,out=a.jar.resolve(),a.out.resolve();assert jar==C10.resolve() and sha(jar)==a.jar_sha256 and len(a.jar_sha256)==64
 assert a.build_receipt.resolve()==build_path;class_pins=frozen_build_class_pins(build_path,jar)
 assert out.is_relative_to(ROOT/'artifacts') and not out.is_relative_to(FUTURE) and not FUTURE.is_relative_to(out) and not out.is_relative_to(candidate) and not out.exists() and not FUTURE.exists(),'Fresh separate CREATE_NEW preflight/capture/build directories required'
 selection=read(ROOT/'artifacts/r52_runtime_candidate/MOTION_RUNTIME_SELECTION_RECEIPT.json');contract=read(RUNTIME/'combat_bundle_r44.json');assert set(contract['files'])==set(selection['files']) and len(contract['files'])==28
 for name,digest in contract['files'].items():assert sha(RUNTIME/name)==digest,name
 assert contract['files']['eva_body_r44.json']==BODY_SHA and contract['files']['first_battle_r44.json']==CLIP_SHA
 with zipfile.ZipFile(jar) as z:
  assert len(z.namelist())==len(set(z.namelist())) and class_protocol(z.read('com/projectseele/network/SeeleNetwork.class'))=='70'
  for name,row in selection['required_jar_assets'].items():assert hashlib.sha256(z.read(name)).hexdigest()==row['selected_sha256'],name
  transition=z.read('com/projectseele/client/render/EvaPoseTransition.class');support=z.read('com/projectseele/entity/EvaOrdinaryStandingSupportR52$MotionMemory.class')
  for token in (b'rebaseClockR52',b'prepareTransitionR52',b'applyFinalWeaponGuardR52',b'deferWeaponGuardFinal'):assert token in transition,'C10 guard fix absent: '+str(token)
  for token in (b'retainsGroundContactR52',b'retainsGroundFloorR52',b'groundTime',b'groundFloor',b'lastPoseClock',b'sampleClockR52'):assert token in support,'C10 bounded support fix absent: '+str(token)
 previous=read(PREVIOUS);world=GAME.resolve()/'saves/SEELE_FIRST_BATTLE_REVIEW_R10';assert Path(previous['world']).resolve()==world and (world/'level.dat').is_file() and not(world/'r10_resume_expected.json').exists()
 command=[v for v in previous['command'] if not v.startswith('-Dprojectseele.') and v!='-XX:+EnableDynamicAgentLoading']
 properties=dict(regionalBuild='ordinary-motion-r52',firstBattleBerserkReviewR52='false',firstBattleThenOrdinaryR52='false',firstBattleThenHandlingR52='false',ordinaryHandlingOnlyR52='true',ordinaryHandlingC10R52='true',firstBattleMovieOnly='false',firstBattleRuntimeWitnessR52='false',firstBattleFollowupOrdinaryReviewR52='false',firstBattleControlRecoveryCaptureR52='false',firstBattleNoFrameCaptureR52='true',ordinaryMotionWorldR52=str(world),ordinaryMotionOutputR52=str(FUTURE/'ordinary'),r47NativeCommandInbox=str(FUTURE/'commands.json'),combatBundleDirectory=str(RUNTIME))
 command[1:1]=['-XX:+EnableDynamicAgentLoading',*['-Dprojectseele.'+k+'='+v for k,v in properties.items()]];actual_properties=unique_properties(command)
 assert Path(command[command.index('--gameDir')+1]).resolve()==GAME.resolve() and command[command.index('--quickPlaySingleplayer')+1]==world.name
 assert all('candidate8' not in v for v in command)
 for key in ('ordinaryMotionOutputR52','r47NativeCommandInbox'):assert Path(properties[key]).is_relative_to(FUTURE) and not Path(properties[key]).exists()
 out.mkdir(parents=True);planned=dict(actual_candidate=str(candidate),scenario='C10_UNIT1_HANDLING210',command=command,environment=previous.get('environment',{}),workingDirectory=str(GAME.resolve()),world=str(world),immutable_jar=dict(path=str(jar),sha256=a.jar_sha256),staged_jar=dict(path=str(GAME.resolve()/'mods/projectseele-0.1.0-all.jar'),sha256=a.jar_sha256),bundle_directory=str(RUNTIME),runtime_fingerprints=contract['files'],candidate_sha256=a.jar_sha256,selected_clip_sha256=CLIP_SHA,properties=properties,native_output=str(FUTURE),ready_to_launch=False,staging_pending=True,offline_only=True,baseline_only=False)
 write(out/'PLANNED_LAUNCH.json',planned);(out/'PLANNED_LAUNCH.args').write_text('\n'.join(quote(v) for v in command[1:])+'\n','utf8')
 classes,sources,cp,agent=compile_tools(out)
 env=dict(os.environ);env.update(R52_PREFLIGHT_OUT=str(out),R52_PREFLIGHT_JAR=str(jar),R52_PREFLIGHT_SHA256=a.jar_sha256,R52_PREFLIGHT_LAUNCH=str(out/'PLANNED_LAUNCH.json'),R52_PREFLIGHT_HANDLING_ONLY='true',R52_PREFLIGHT_CANDIDATE=str(candidate),R52_PREFLIGHT_BUILD_RECEIPT=str(build_path))
 checked_run([sys.executable,str(ROOT/'tools/preflight_r52_c10_handling_reflection.py')],out/'reflection.log',env);reflection=read(out/'EXTENDED_CLASSFILE_REFLECTION_PREFLIGHT.json');assert not reflection['failed'] and len(reflection['checks'])>=181
 client=reflection['classes']['net.minecraft.client.Minecraft']['source'];transformed=checked_run([str(JDK/'java.exe'),'-Xmx256m','-cp',str(classes)+';'+cp,'VerifyC10HandlingToolModesR52',str(jar),client,str(out/'verified_transforms')],out/'transform.log')
 motion_sources=frozen_motion()
 build=read(jar.parent/'BUILD_RECEIPT.json');snapshot=read(jar.parent/'SOURCE_BEFORE.json')
 assert build['build_exit']==0 and not build['changed_during_build'] and build['sha256']==a.jar_sha256 and Path(build['jar']).resolve()==jar
 for n,d in motion_sources.items():
  assert sha(ROOT/n)==d,'Reviewed source unfrozen: '+n
  assert snapshot[n.replace('\\','/')]==d,'C10 build does not contain reviewed source: '+n
 receipt=dict(schema='projectseele.r52.c10-handling-offline-preflight.v1',C10_qualified=True,baseline_only=False,immutable_jar=planned['immutable_jar'],source_root=str(ROOT),expected_native_output=str(FUTURE),runtime_contract_sha256=sha(RUNTIME/'combat_bundle_r44.json'),selected_clip_sha256=CLIP_SHA,preserved_body_sha256=BODY_SHA,protocol=70,build_receipt=str(build_path),build_receipt_sha256=sha(build_path),SOURCE_BEFORE_sha256=sha(jar.parent/'SOURCE_BEFORE.json'),required_delivery_classes=class_pins,required_source_assets=build['required_source_assets'],four_uv_members=4,unique_jvm_properties=len(actual_properties),property_keys_unique=True,planned_outputs_entirely_new=True,reflection_checks=len(reflection['checks']),reflection_failed=reflection['failed'],attach_modes_and_transformed_stacks=transformed,tool_agent_sha256=sha(agent),tool_sources={str(p.relative_to(ROOT)):sha(p) for p in sources},reviewed_motion_sources=motion_sources,sequence=dict(final_C12_movies=0,repeated_ordinary_movie=0,ordinary_variants=[1],ordinary_ticks=210,handling_exit_each_render_pose_tick_ranges=[[78,105],[150,195]],actual_entity_tick_clock=True,actual_bounded_ground_memory=True,production_body_resampled_by_tool=False,actual_transition_history_readback=True,actual_support_memory_and_final_foot_matrices=True),planned_launch_sha256=sha(out/'PLANNED_LAUNCH.json'),planned_args_sha256=sha(out/'PLANNED_LAUNCH.args'),world_written=False,game_written=False,game_started=False,attach_executed=False,native_acceptance=False,user_artistic_acceptance=False,pending=['Root-controlled staging/run and actual handling boundary readback'])
 receipt.update(schema='projectseele.r52.handling210-offline-preflight.v2',candidate_qualified=True,actual_candidate=str(candidate),scenario='C10_UNIT1_HANDLING210',orchestration_sources=orchestration_sources());receipt.pop('C10_qualified')
 write(out/'OFFLINE_PREFLIGHT_RECEIPT.json',receipt);print(json.dumps(dict(passed=True,candidate_qualified=True,actual_candidate=str(candidate),reflection_checks=receipt['reflection_checks'],native_output=str(FUTURE),game_started=False,receipt=str(out/'OFFLINE_PREFLIGHT_RECEIPT.json'))))
if __name__=='__main__':main()
