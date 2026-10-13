"""All existing ordinary reflection targets plus native shapes and actual support guards."""
from pathlib import Path
import argparse,hashlib,json,os,runpy
from build_immutable_r52_candidate import frozen_build_class_pins
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser(description=__doc__)
for flag in ('actual-candidate','jar','build-receipt','launch','out'):ap.add_argument('--'+flag,type=Path)
ap.add_argument('--jar-sha256');a=ap.parse_args()
selected={'R52_PREFLIGHT_CANDIDATE':a.actual_candidate,'R52_PREFLIGHT_JAR':a.jar,'R52_PREFLIGHT_BUILD_RECEIPT':a.build_receipt,'R52_PREFLIGHT_LAUNCH':a.launch,'R52_PREFLIGHT_OUT':a.out,'R52_PREFLIGHT_SHA256':a.jar_sha256}
for key,value in selected.items():
 if value is not None:os.environ[key]=str(value.resolve()) if isinstance(value,Path) else value
required=('R52_PREFLIGHT_CANDIDATE','R52_PREFLIGHT_JAR','R52_PREFLIGHT_BUILD_RECEIPT','R52_PREFLIGHT_LAUNCH','R52_PREFLIGHT_OUT','R52_PREFLIGHT_SHA256')
assert all(os.environ.get(key) for key in required),'Explicit actual candidate/JAR/SHA/build/launch/output required'
os.environ.setdefault('R52_PREFLIGHT_HANDLING_ONLY','true')
candidate=Path(os.environ['R52_PREFLIGHT_CANDIDATE']).resolve();jar=Path(os.environ['R52_PREFLIGHT_JAR']).resolve();build=Path(os.environ['R52_PREFLIGHT_BUILD_RECEIPT']).resolve();launch=Path(os.environ['R52_PREFLIGHT_LAUNCH']).resolve();output=Path(os.environ['R52_PREFLIGHT_OUT']).resolve()
assert candidate.is_relative_to(ROOT/'artifacts') and jar==candidate/'projectseele-0.1.0-all.jar' and build==candidate/'BUILD_RECEIPT.json' and output.is_relative_to(ROOT/'artifacts') and launch.parent==output
jar_sha=hashlib.sha256(jar.read_bytes()).hexdigest();assert jar_sha==os.environ['R52_PREFLIGHT_SHA256']
planned=json.loads(launch.read_text('utf-8'));assert Path(planned['immutable_jar']['path']).resolve()==jar and planned['immutable_jar']['sha256']==jar_sha
frozen_build_class_pins(build,jar)
os.environ.setdefault('R52_PREFLIGHT_OUT',str(ROOT/'.codex/r52_native_collision_export'))
n=runpy.run_path(str(ROOT/'.codex/r52_ordinary_classfile_preflight.py'))
method,field=n['method'],n['field']
method('com.google.gson.Gson','fromJson','Ljava/lang/String;Ljava/lang/Class;','Ljava/lang/Object;')
method('com.projectseele.visual.RegionalSpatialAuditDriver','parse','Ljava/lang/String;','Lnet/minecraft/world/level/block/state/BlockState;',True)
method('net.minecraft.world.level.EmptyBlockGetter','values','','[Lnet/minecraft/world/level/EmptyBlockGetter;')
method('net.minecraft.core.BlockPos','<init>','III','V')
method('net.minecraft.world.phys.shapes.CollisionContext','of|m_82750_','Lnet/minecraft/world/entity/Entity;','Lnet/minecraft/world/phys/shapes/CollisionContext;')
method('net.minecraft.world.level.block.state.BlockState','getCollisionShape|m_60742_','Lnet/minecraft/world/level/BlockGetter;Lnet/minecraft/core/BlockPos;Lnet/minecraft/world/phys/shapes/CollisionContext;','Lnet/minecraft/world/phys/shapes/VoxelShape;')
method('net.minecraft.world.phys.shapes.VoxelShape','toAabbs|m_83299_','','Ljava/util/List;')
for names in ['minX|f_82288_','minY|f_82289_','minZ|f_82290_','maxX|f_82291_','maxY|f_82292_','maxZ|f_82293_']:field('net.minecraft.world.phys.AABB',names,'D')
method('net.minecraft.world.entity.Entity','onGround|m_20096_','','Z')
method('com.projectseele.entity.EvaUnit01Entity','isVisuallyAirborneForRender','','Z')
for names in ['xOld|f_19790_','yOld|f_19791_','zOld|f_19792_']:field('net.minecraft.world.entity.Entity',names,'D')
field('com.projectseele.visual.FirstBattleR10Review','finished','Z')
field('com.projectseele.visual.FirstBattleR10Review','heroId','I')
method('net.minecraft.world.entity.Entity','getId|m_19879_','','I')
method('com.projectseele.entity.EvaUnit01Entity','isFirstBattleActive','','Z')
method('com.projectseele.entity.EvaUnit01Entity','firstBattleSignals','','Lcom/projectseele/entity/FirstBattleSignals$SignalSet;')
method('com.projectseele.entity.FirstBattleSignals','clientFrameTime','','J')
method('com.projectseele.entity.FirstBattleSignals$SignalSet','age','Lnet/minecraft/world/entity/Entity;','I')
method('com.projectseele.entity.FirstBattleSignals$SignalSet','time','Lnet/minecraft/world/entity/Entity;F','F')
method('com.projectseele.client.EvaCommandFeedClient','isOpticalRenderPass','','Z')
method('com.projectseele.entity.EvaDorsalMechanism','eyesEnabled','Lcom/projectseele/entity/EvaUnit01Entity;','Z')
method('com.projectseele.entity.EvaDorsalMechanism','eyeSurface','Lcom/projectseele/entity/EvaUnit01Entity;','I')
method('com.projectseele.client.visual.FirstBattleR10Client','tick','Lnet/minecraftforge/event/TickEvent$ClientTickEvent;','V')
if os.environ.get('R52_PREFLIGHT_HANDLING_ONLY')=='true':
 method('com.projectseele.entity.EvaUnit01Entity','ordinaryStandingSupportLockedR52','','Z')
 method('com.projectseele.entity.EvaGameplayMotionR32','airAge','Lcom/projectseele/entity/EvaUnit01Entity;F','F')
 field('com.projectseele.entity.EvaOrdinaryStandingSupportR52','MEMORY','Lcom/projectseele/util/WeakIdentityMap;',True)
 method('com.projectseele.util.WeakIdentityMap','get','Ljava/lang/Object;','Ljava/lang/Object;')
 for name,desc in [('changed','D'),('last','D'),('from','F'),('target','F'),('action','Z'),('actionFrom','F'),('correction','Lcom/projectseele/entity/EvaOrdinaryStandingSupportR52$Correction;')]:
  field('com.projectseele.entity.EvaOrdinaryStandingSupportR52$MotionMemory',name,desc,True)
 method('com.projectseele.client.render.EvaPoseTransition','retainNormalWeaponHistoryR52','Lcom/projectseele/entity/EvaUnit01Entity;','Z',True)
 method('com.projectseele.client.render.EvaPoseTransition','sharedExitDurationR52','ZZZ','D',True)
 method('com.projectseele.client.render.EvaPoseTransition','continuesWeaponExitR52','ZDDZZ','Z',True)
 field('com.projectseele.client.render.EvaPoseTransition','STATES','Ljava/util/Map;',True)
 for name,desc in [('time','D'),('start','D'),('duration','D'),('liveAction','Z'),('weapon','I'),('weaponGuardExit','Z'),('entryCorrection','Z'),('entryStart','F'),('entryEnd','F'),('actionPhase','F'),('recordedFrame','J')]:
  field('com.projectseele.client.render.EvaPoseTransition$State',name,desc,True)
field('net.minecraft.world.entity.Entity','tickCount|f_19797_','I')
method('software.bernie.geckolib.cache.object.BakedGeoModel','topLevelBones','','Ljava/util/List;')
method('software.bernie.geckolib.cache.object.GeoBone','getName','','Ljava/lang/String;')
method('software.bernie.geckolib.cache.object.GeoBone','getChildBones','','Ljava/util/List;')
for name,desc in [('lastPoseClock','D'),('groundTime','D'),('groundY','D'),('leftGround','D'),('rightGround','D'),('groundFloor','Z')]:
 field('com.projectseele.entity.EvaOrdinaryStandingSupportR52$MotionMemory',name,desc,True)
method('com.projectseele.entity.EvaOrdinaryStandingSupportR52$MotionMemory','sampleClockR52','D','D')
report=n['report'];report['classes']={name:{'source':c['source'],'super':c['super']} for name,c in n['cache'].items()};report['failed']=[c for c in n['checks'] if not c['passed']]
report['actual_build_selection']={'candidate':str(candidate),'jar':str(jar),'sha256':jar_sha,'build_receipt':str(build),'build_receipt_sha256':hashlib.sha256(build.read_bytes()).hexdigest(),'scenario':'C10_UNIT1_HANDLING210'}
(n['OUT']/'EXTENDED_CLASSFILE_REFLECTION_PREFLIGHT.json').write_text(json.dumps(report,indent=2),'utf8')
print(json.dumps(dict(checks=len(n['checks']),classes=len(n['cache']),failed=report['failed']),indent=2))
assert not report['failed']
