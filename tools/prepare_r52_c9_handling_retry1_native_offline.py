"""Pure offline preflight of C9 retry1 Unit1 handling210; first attempt evidence retained."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,zipfile
from prepare_r52_c8_native_offline import ROOT,JDK,ASM,GAME,RUNTIME,BODY_SHA,CLIP_SHA,PREVIOUS,sha,read,write,quote,unique_properties,checked_run
from release_r45_contract import class_protocol
FUTURE=ROOT/'artifacts/r52_native_handling_candidate9_retry1'
C9=ROOT/'artifacts/r52_unified_candidate9/projectseele-0.1.0-all.jar'

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--jar',required=True,type=Path);ap.add_argument('--jar-sha256',required=True);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args()
 jar,out=a.jar.resolve(),a.out.resolve();assert jar==C9.resolve() and sha(jar)==a.jar_sha256 and len(a.jar_sha256)==64
 assert out.is_relative_to(ROOT/'artifacts') and out!=FUTURE and not out.exists() and not FUTURE.exists(),'Fresh CREATE_NEW preflight and capture directories required'
 selection=read(ROOT/'artifacts/r52_runtime_candidate/MOTION_RUNTIME_SELECTION_RECEIPT.json');contract=read(RUNTIME/'combat_bundle_r44.json');assert set(contract['files'])==set(selection['files']) and len(contract['files'])==28
 for name,digest in contract['files'].items():assert sha(RUNTIME/name)==digest,name
 assert contract['files']['eva_body_r44.json']==BODY_SHA and contract['files']['first_battle_r44.json']==CLIP_SHA
 with zipfile.ZipFile(jar) as z:
  assert len(z.namelist())==len(set(z.namelist())) and class_protocol(z.read('com/projectseele/network/SeeleNetwork.class'))=='69'
  for name,row in selection['required_jar_assets'].items():assert hashlib.sha256(z.read(name)).hexdigest()==row['selected_sha256'],name
  transition=z.read('com/projectseele/client/render/EvaPoseTransition.class');support=z.read('com/projectseele/entity/EvaOrdinaryStandingSupportR52$MotionMemory.class')
  for token in (b'rebaseClockR52',b'prepareTransitionR52',b'applyFinalWeaponGuardR52',b'deferWeaponGuardFinal'):assert token in transition,'C9 guard fix absent: '+str(token)
  for token in (b'retainsGroundContactR52',b'retainsGroundFloorR52',b'groundTime',b'groundFloor'):assert token in support,'C9 bounded support fix absent: '+str(token)
 previous=read(PREVIOUS);world=GAME.resolve()/'saves/SEELE_FIRST_BATTLE_REVIEW_R10';assert Path(previous['world']).resolve()==world and (world/'level.dat').is_file() and not(world/'r10_resume_expected.json').exists()
 command=[v for v in previous['command'] if not v.startswith('-Dprojectseele.') and v!='-XX:+EnableDynamicAgentLoading']
 properties=dict(regionalBuild='ordinary-motion-r52',firstBattleBerserkReviewR52='false',firstBattleThenOrdinaryR52='false',firstBattleThenHandlingR52='false',ordinaryHandlingOnlyR52='true',firstBattleMovieOnly='false',firstBattleRuntimeWitnessR52='false',firstBattleFollowupOrdinaryReviewR52='false',firstBattleControlRecoveryCaptureR52='false',firstBattleNoFrameCaptureR52='true',ordinaryMotionWorldR52=str(world),ordinaryMotionOutputR52=str(FUTURE/'ordinary'),r47NativeCommandInbox=str(FUTURE/'commands.json'),combatBundleDirectory=str(RUNTIME))
 command[1:1]=['-XX:+EnableDynamicAgentLoading',*['-Dprojectseele.'+k+'='+v for k,v in properties.items()]];actual_properties=unique_properties(command)
 assert Path(command[command.index('--gameDir')+1]).resolve()==GAME.resolve() and command[command.index('--quickPlaySingleplayer')+1]==world.name
 assert all('candidate8' not in v for v in command)
 for key in ('ordinaryMotionOutputR52','r47NativeCommandInbox'):assert Path(properties[key]).is_relative_to(FUTURE) and not Path(properties[key]).exists()
 out.mkdir(parents=True);planned=dict(command=command,environment=previous.get('environment',{}),workingDirectory=str(GAME.resolve()),world=str(world),immutable_jar=dict(path=str(jar),sha256=a.jar_sha256),staged_jar=dict(path=str(GAME.resolve()/'mods/projectseele-0.1.0-all.jar'),sha256=a.jar_sha256),bundle_directory=str(RUNTIME),runtime_fingerprints=contract['files'],candidate_sha256=CLIP_SHA,properties=properties,native_output=str(FUTURE),ready_to_launch=False,staging_pending=True,offline_only=True,baseline_only=False)
 write(out/'PLANNED_LAUNCH.json',planned);(out/'PLANNED_LAUNCH.args').write_text('\n'.join(quote(v) for v in command[1:])+'\n','utf8')
 classes=out/'tool_classes';classes.mkdir();sources=[ROOT/'tools/java'/n for n in ('OrdinaryMotionR52Agent.java','OrdinaryMotionR52Attach.java','VerifyC9HandlingToolModesR52.java')];cp=';'.join(map(str,ASM));checked_run([str(JDK/'javac.exe'),'-J-Xmx256m','-cp',cp,'-d',str(classes),*map(str,sources)],out/'compile.log')
 agent=out/'ordinary_motion_agent.jar'
 with zipfile.ZipFile(agent,'x',zipfile.ZIP_DEFLATED) as z:
  z.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\nAgent-Class: OrdinaryMotionR52Agent\nCan-Retransform-Classes: true\n\n')
  for p in classes.glob('OrdinaryMotionR52Agent*.class'):z.write(p,p.name)
 env=dict(os.environ);env.update(R52_PREFLIGHT_OUT=str(out),R52_PREFLIGHT_JAR=str(jar),R52_PREFLIGHT_SHA256=a.jar_sha256,R52_PREFLIGHT_LAUNCH=str(out/'PLANNED_LAUNCH.json'),R52_PREFLIGHT_HANDLING_ONLY='true')
 checked_run([sys.executable,str(ROOT/'.codex/r52_ordinary_extended_preflight.py')],out/'reflection.log',env);reflection=read(out/'EXTENDED_CLASSFILE_REFLECTION_PREFLIGHT.json');assert not reflection['failed'] and len(reflection['checks'])>=181
 client=reflection['classes']['net.minecraft.client.Minecraft']['source'];transformed=checked_run([str(JDK/'java.exe'),'-cp',str(classes)+';'+cp,'VerifyC9HandlingToolModesR52',str(jar),client,str(out/'verified_transforms')],out/'transform.log')
 frozen=read(ROOT/'.codex/r52_c8_handoff_fix/SOURCE_COMPILE_RECEIPT.json')['sources'];motion_sources={n:d for n,d in frozen.items() if n.startswith('src')}
 for n,d in motion_sources.items():assert sha(ROOT/n)==d,'Reviewed source unfrozen: '+n
 receipt=dict(schema='projectseele.r52.c9-handling-offline-preflight.v1',C9_qualified=True,baseline_only=False,immutable_jar=planned['immutable_jar'],source_root=str(ROOT),expected_native_output=str(FUTURE),runtime_contract_sha256=sha(RUNTIME/'combat_bundle_r44.json'),selected_clip_sha256=CLIP_SHA,preserved_body_sha256=BODY_SHA,protocol=69,four_uv_members=4,unique_jvm_properties=len(actual_properties),property_keys_unique=True,planned_outputs_entirely_new=True,reflection_checks=len(reflection['checks']),reflection_failed=reflection['failed'],attach_modes_and_transformed_stacks=transformed,tool_agent_sha256=sha(agent),tool_sources={str(p.relative_to(ROOT)):sha(p) for p in sources},reviewed_motion_sources=motion_sources,sequence=dict(final_C12_movies=0,repeated_ordinary_movie=0,ordinary_variants=[1],ordinary_ticks=210,handling_exit_each_render_pose_ticks=[150,185],actual_transition_history_readback=True,actual_support_memory_and_final_foot_matrices=True),planned_launch_sha256=sha(out/'PLANNED_LAUNCH.json'),planned_args_sha256=sha(out/'PLANNED_LAUNCH.args'),world_written=False,game_written=False,game_started=False,attach_executed=False,native_acceptance=False,user_artistic_acceptance=False,pending=['Root-controlled staging/run and actual handling boundary readback'])
 write(out/'OFFLINE_PREFLIGHT_RECEIPT.json',receipt);print(json.dumps(dict(passed=True,C9_qualified=True,reflection_checks=receipt['reflection_checks'],native_output=str(FUTURE),game_started=False,receipt=str(out/'OFFLINE_PREFLIGHT_RECEIPT.json'))))
if __name__=='__main__':main()
