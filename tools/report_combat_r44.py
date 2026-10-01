"""Write the combat ownership/coverage receipt, including exact protected files."""
from pathlib import Path
import hashlib,json,re,subprocess

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44/combat';JAVA=ROOT/'src/main/java/com/projectseele'
FILES=[
 'entity/EvaUnit01Entity.java','entity/EvaBodyPose.java','entity/EvaGameplayMotionR32.java','entity/EvaCombatSupportR33.java','entity/EvaHandsR41.java',
 'entity/CombatMotionResourcesR44.java','entity/FirstBattleClip.java','entity/SachielGameplayMotionR32.java','entity/EvaPrototypeEntity.java','entity/EvaCombatR31.java',
 'entity/ShamshelEntity.java','entity/RamielEntity.java','entity/ZeruelEntity.java',
 'client/render/EvaPoseGraph.java','client/render/EvaHandPoseR28.java','client/render/EvaCombatPoseR31.java','client/render/EvaMotionEngineV2.java',
 'client/render/EvaLocomotionRig.java','client/render/EvaFootPlacement.java',
 'physics/CombatEntityQueryR44.java','physics/CombatBodyContacts.java','physics/CombatBodyProfiles.java','fx/StrategicExplosionDirector.java','item/PositronRifleItem.java',
 'mixin/GiantExplosionQueryMixinR44.java','network/SeeleNetwork.java','network/CombatBundleGateR44.java','network/ClientboundCombatContractR44.java',
 'network/ServerboundCombatContractR44.java','client/CombatContractClientR44.java',
 'visual/CombatQueryNativeR44.java','client/render/EvaFootWitnessR44.java','client/render/LocalTriangleMeshLayer.java',
]
TOOLS=['audit_combat_pipeline_r44.py','author_combat_bundle_r44.py','validate_combat_bundle_r44.py','finalize_combat_bundle_r44.py',
       'audit_cadence_r44.py','warp_locomotion_r44.py','check_locomotion_warp_r44.py','check_combat_hull_queries_r44.py','report_combat_r44.py',
       'review_combat_query_r44.py','analyze_runtime_feet_r44.py','trace_runtime_support_r44.py','author_low_combat_r44.py',
       'prepare_tv_exchange_r44.py','build_tv_exchange_r44.py','author_video_counter_r44.py','audit_tv_exchange_r44.py','render_tv_exchange_r44.py',
       'fetch_video_mocap_source_r44.py','import_video_boxing_r44.py','analyze_video_boxing_r44.py','import_blender_video_boxing_r44.py',
       'calibrate_angel_sole_binding_r44.py','inspect_exchange_surface_r44.py']


def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()


def main():
    baseline=json.loads((ROOT/'artifacts/rebuild_r44/baseline.json').read_text('utf8'));protected=[];files=[];coverage=[]
    for relative,expected in baseline['original_user_files'].items():
        actual=sha(ROOT/relative);protected.append(dict(file=relative,expected=expected,actual=actual,match=actual==expected))
    for relative in FILES:
        source=JAVA/relative
        if not source.is_file():continue
        snapshot=ART/'source_before'/relative
        if not snapshot.exists():
            previous=subprocess.run(['git','show','HEAD:src/main/java/com/projectseele/'+relative],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            if previous.returncode==0:snapshot.parent.mkdir(parents=True,exist_ok=True);snapshot.write_bytes(previous.stdout)
        files.append(dict(file=str(source.relative_to(ROOT)),before_sha256=sha(snapshot) if snapshot.exists() else None,after_sha256=sha(source),
                          shared_note='EvaPoseGraph retains root RuntimeR44ClientProbe.capture and cadence fallback; root owns mixin registration' if 'PoseGraph' in relative else None))
        for number,line in enumerate(source.read_text('utf8').splitlines(),1):
            if 'CombatEntityQueryR44.' in line:coverage.append(dict(file=relative,line=number,entry=line.strip(),status='SOURCE_IMPLEMENTED; native behavior not inferred'))
    manifests=[]
    for directory in [ART/'motion',ART/'locomotion_warp/motion',ART/'low_attack_bundle/motion',ART/'low_attack_v2/motion']:
        file=directory/'combat_bundle_r44.json'
        if file.exists():
            manifest=json.loads(file.read_text('utf8'));validation=directory.parent/'candidate_validation.json'
            manifests.append(dict(directory=str(directory.resolve()),bundle=manifest['bundle_id'],
                        validation=json.loads(validation.read_text('utf8')).get('functional_offline_pass') if validation.is_file() else None,
                        status='FAILED_ISOLATED: do not install or test as a passing candidate' if 'low_attack' in directory.as_posix() else 'VISUAL_FAIL: diagnostic only; user rejected all current 3D clips',
                        files={name:dict(expected=digest,actual=sha(directory/name),match=sha(directory/name)==digest) for name,digest in manifest['files'].items()}))
    mixins=json.loads((ROOT/'src/main/resources/projectseele.mixins.json').read_text('utf8'))
    result=dict(ownership='Combat source and isolated candidates only; no world edits, packaging, commit or Minecraft/Gradle launches by this agent',
                source=files,tools={name:sha(ROOT/'tools'/name) for name in TOOLS},documentation=['docs/COMBAT_RECONSTRUCTION_R44.md','docs/TV_EXCHANGE_DIRECTION_R44.md'],
                query_call_sites=coverage,query_call_site_count=len(coverage),vanilla_explosion_mixin_registered='GiantExplosionQueryMixinR44' in mixins['mixins'],
                protected_files=protected,all_protected_files_match=all(r['match'] for r in protected),bundles=manifests,
                numerical_balance=dict(fist=20,heavy_fist=35,knife=60,heavy_knife=80,kick=50,shamshel_whip=30,zeruel_paper_arm=72,zeruel_eye=125,
                                       note='Damage/health/cooldown constants unchanged; geometric contact and attenuation distance are revised and require native comparison'),
                native_api=dict(result='artifacts/rebuild_r44/combat/native_query_qa/20260930_153833/result.json',passed=66,total=66,
                                scope='Original 40 spatial + 17 production method + 9 embedded server-handler denominator; input/GPU/artistic quality not inferred'),
                tv_exchange=dict(blocking_v1='VISUAL_FAIL after actual parent review',counter_v2='GEOMETRY_FAIL: actual shin/foot-blended sole -1.8853m; original negative retained',
                    counter_v3='UNREVIEWED: actual whole-mesh minimum -0.00205m after candidate-only plantar ownership correction; no native/art acceptance',
                    video_source='Actual SMPLOlympics Boxing source: 8 takes, 24 joints, 30fps; Blender/FBX/BVH import-export-FBX-reimport complete; no fingers/measured COM/contact impulses',
                    runtime_installed=False,source_mesh_overwritten=False),
                unverified=['New paired exchange artistic acceptance and runtime adapter','Position/phase tuple and release clock revision: pending next native epoch','Low-stance full source/phase/contact: two isolated failed candidates',
                            'Walk-run mixture, slopes/obstacles, turning, jumps and landing','Berserk eyes, paired finisher and reload/remote resumption',
                            'Every Angel new visible attack and response language','Native explosion Mixin + null-source scope','Two clients and performance','User visual acceptance'])
    (ART/'affected_files.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(source_files=len(files),query_call_sites=len(coverage),protected_match=result['all_protected_files_match'],
                          mixin_registered=result['vanilla_explosion_mixin_registered'],bundles=[m['bundle'] for m in manifests]),ensure_ascii=False))


if __name__=='__main__':main()
