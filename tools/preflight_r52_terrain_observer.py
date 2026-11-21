"""Verify the standalone observer against installed local bytecode; no game launch."""
from pathlib import Path
import hashlib,json,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
JAVAP=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin/javap.exe')
JDK=JAVAP.parent
MODS=Path('D:/eva/artifacts/r51_nonmap_release/native_r51/game/mods')
EMBED=MODS/'embeddium-0.3.31+mc1.20.1.jar'
CLIENT=Path('C:/Users/liboy/AppData/Roaming/.minecraft/libraries/net/minecraft/client/1.20.1-20230612.114412/client-1.20.1-20230612.114412-srg.jar')
TOOLS=ROOT/'.codex/r52_final_art_capture'
OUTPUT=TOOLS/'OBSERVER_COMPILE_RECEIPT.json'
CACHE=TOOLS/'installed_api'
JAVA_SOURCES=('R52TerrainReadyReadOnlyAgent','R52TerrainReadyReadOnlyAttach','R52TerrainReadinessDecision','R52TerrainReadinessDecisionEvidence','R52PhotoRoomLightAgent','R52FinalPhotoEvidence')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def code(jar,name):
    out=subprocess.check_output([str(JAVAP),'-J-Xmx128m','-p','-c','-constants','-cp',str(jar),name],text=True,encoding='utf8',errors='replace')
    (CACHE/(name.rsplit('.',1)[-1]+'.javap.txt')).write_text(out,'utf8');return out
def main():
    CACHE.mkdir(parents=True,exist_ok=True);checks=[]
    def check(name,okay):
        checks.append(dict(check=name,pass_=bool(okay)))
        if not okay:raise AssertionError(name)
    source={
        'mc':code(CLIENT,'net.minecraft.client.Minecraft'),
        'renderer':code(CLIENT,'net.minecraft.client.renderer.LevelRenderer'),
        'camera':code(CLIENT,'net.minecraft.client.Camera'),
        'cache':code(CLIENT,'net.minecraft.client.multiplayer.ClientChunkCache'),
        'client_level':code(CLIENT,'net.minecraft.client.multiplayer.ClientLevel'),
        'server':code(CLIENT,'net.minecraft.server.MinecraftServer'),
        'light':code(CLIENT,'net.minecraft.world.level.lighting.LevelLightEngine'),
        'screenshot':code(CLIENT,'net.minecraft.client.Screenshot'),
        'image':code(CLIENT,'com.mojang.blaze3d.platform.NativeImage'),
        'nbt':code(CLIENT,'net.minecraft.nbt.CompoundTag'),
        'game_mode':code(CLIENT,'net.minecraft.server.level.ServerPlayerGameMode'),
        'entity':code(CLIENT,'net.minecraft.world.entity.Entity'),
        'world':code(EMBED,'me.jellysquid.mods.sodium.client.render.SodiumWorldRenderer'),
        'manager':code(EMBED,'me.jellysquid.mods.sodium.client.render.chunk.RenderSectionManager'),
        'builder':code(EMBED,'me.jellysquid.mods.sodium.client.render.chunk.compile.executor.ChunkBuilder'),
        'tracker':code(EMBED,'me.jellysquid.mods.sodium.client.render.chunk.map.ChunkTracker'),
        'tracker_holder':code(EMBED,'me.jellysquid.mods.sodium.client.render.chunk.map.ChunkTrackerHolder'),
        'mixin':code(EMBED,'me.jellysquid.mods.sodium.mixin.core.render.world.WorldRendererMixin'),
    }
    for key,tokens in {
        'mc':['m_91087_()','m_91092_()','m_91104_()','m_91302_()','m_260875_()','m_91288_()','m_91385_()','f_91060_','f_91063_','f_91073_','f_91074_','f_91066_','f_91080_','f_90980_'],
        'renderer':['f_172938_','f_109442_','m_202430_(','m_109820_()','m_109821_()'],
        'camera':['m_90583_()','m_90589_()','m_90590_()'],
        'cache':['m_7827_()'],
        'client_level':['m_104735_()'],
        'server':['m_129843_(','m_129921_()','m_129903_()'],
        'light':['m_75808_()'],
        'screenshot':['m_92279_(com.mojang.blaze3d.pipeline.RenderTarget)'],
        'image':['m_85066_(java.nio.file.Path)','m_84982_()','m_85084_()'],
        'nbt':['m_128441_(java.lang.String)','m_128461_(java.lang.String)','m_128451_(java.lang.String)','m_128457_(java.lang.String)','m_128454_(java.lang.String)','m_128471_(java.lang.String)'],
        'game_mode':['m_7179_(net.minecraft.server.level.ServerPlayer, net.minecraft.world.level.Level, net.minecraft.world.item.ItemStack, net.minecraft.world.InteractionHand, net.minecraft.world.phys.BlockHitResult)'],
        'entity':['m_20182_()','m_146892_()','m_5833_()'],
        'world':['instance()','renderSectionManager','getDebugStrings()','isSectionReady('],
        'manager':['buildResults','asyncSubmittedTasks','rebuildLists','getBuilder()','isSectionVisible('],
        'builder':['getScheduledJobCount()','getBusyThreadCount()'],
        'tracker':['getReadyChunks()','private void updateMerged('],
        'tracker_holder':['get(net.minecraft.client.multiplayer.ClientLevel)'],
        'mixin':['private int frame;','Field frame:I','setupTerrain:'],
    }.items():
        for token in tokens:check('Installed bytecode '+key+': '+token,token in source[key])
    tracker=source['tracker'].split('private void updateMerged(',1)[1].split('public it.unimi.dsi.fastutil.longs.LongCollection getReadyChunks()',1)[0]
    check('Tracker readiness intersects 3x3 block/light flags',tracker.count('iconst_m1')==2 and 'iand' in tracker and 'iconst_3' in tracker)
    complete=source['world'].split('public boolean isTerrainRenderComplete();',1)[1].split('public void setupTerrain(',1)[0]
    check('Terrain-complete shortcut only checks builder queue, so observer checks remaining queues separately','isBuildQueueEmpty' in complete and 'upload' not in complete)
    check('Observer never contains mutation or native query APIs',not any(t in (ROOT/'tools/java/R52TerrainReadyReadOnlyAgent.java').read_text('utf8') for t in ['scheduleTerrainUpdate(','scheduleRebuild(','allChanged(','getChunk(','setBlock(','smartCull=','pauseOnLostFocus=']))
    # Compile only standalone diagnostic tools; no project build or game start.
    classes=TOOLS/'observer_classes';classes.mkdir(parents=True,exist_ok=True)
    subprocess.run([str(JDK/'javac.exe'),'-J-Xmx256m','-encoding','UTF-8','-d',str(classes),*[str(ROOT/'tools/java'/(n+'.java'))for n in JAVA_SOURCES]],cwd=ROOT,check=True)
    evidence=[]
    for name in ('R52TerrainReadinessDecisionEvidence','R52FinalPhotoEvidence'):
        evidence.append(subprocess.check_output([str(JDK/'java.exe'),'-Xmx128m','-cp',str(classes),name],cwd=ROOT,text=True,encoding='utf8').strip())
    for agent,contents,jar in [('R52TerrainReadyReadOnlyAgent',('R52TerrainReadyReadOnlyAgent','R52TerrainReadinessDecision'),'r52_terrain_ready_readonly_agent.jar'),('R52PhotoRoomLightAgent',('R52PhotoRoomLightAgent',),'r52_photo_room_light_agent.jar')]:
        with zipfile.ZipFile(TOOLS/jar,'w',compression=zipfile.ZIP_DEFLATED)as archive:
            archive.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\r\nAgent-Class: '+agent+'\r\nCan-Redefine-Classes: false\r\nCan-Retransform-Classes: false\r\n\r\n')
            for name in contents:archive.write(classes/(name+'.class'),name+'.class')
    files=[ROOT/'tools/java'/(n+'.java')for n in JAVA_SOURCES]+[classes/(n+'.class')for n in JAVA_SOURCES]+[TOOLS/'r52_terrain_ready_readonly_agent.jar',TOOLS/'r52_photo_room_light_agent.jar']+[ROOT/'tools'/n for n in ('review_r52_native_civil_views.py','prepare_r52_final_art_views.py','prepare_r52_terrain_observer_plan.py','build_immutable_r52_candidate.py','preflight_r52_terrain_observer.py')]
    report=dict(compile_passed=True,java_heap_cap_mb=256,world_opened=False,game_started=False,native_observed=False,native_acceptance=False,checks=checks,installed_bytecode={str(p):sha(p) for p in [EMBED,CLIENT]},files={p.relative_to(ROOT).as_posix():sha(p)for p in files},isolated_evidence=evidence,native_result_pending='Root must synchronize final Jar/resources and the one used QA, then explicitly run the final camera plan. No native READY/photo/visual acceptance exists yet.')
    OUTPUT.write_text(json.dumps(report,indent=2)+'\n','utf8');print(json.dumps(dict(checks=len(checks),report=str(OUTPUT),native_observed=False,evidence=evidence)))
if __name__=='__main__':main()
