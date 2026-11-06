"""Read an existing native capture; never launch, load, or edit a Minecraft save."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('D:/eva/artifacts/r52_fresh_from_r51_20261009')
RUN = BASE / 'native_r52_validation/civil_views_candidate8'
OUT = BASE / 'runtime_directory/candidate/CIVIL_C8_CAPTURE_READINESS_DIAGNOSIS.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows = [json.loads(line) for line in (RUN/'commands.json.ack.jsonl').read_text('utf8').splitlines() if line.strip()]
    log = (RUN/'process.log').read_text('utf8', errors='replace').splitlines()
    delays = [line for line in log if "Can't keep up!" in line]
    options = dict(line.split(':', 1) for line in (RUN/'options.before.txt').read_text('utf8').splitlines() if ':' in line)
    views = json.loads((RUN/'PLAN.json').read_text('utf8'))['views']
    captures = []
    for index, (name, position, target) in enumerate(views):
        tp_seq = 3 + 2*index
        submitted = next(row for row in rows if row['seq'] == tp_seq and row['event'] == 'submitted')
        captured = next(row for row in rows if row['seq'] == tp_seq+1 and row['event'] == 'screenshot_saved')
        captures.append(dict(name=name, position=position, target=target,
                             submitted_client_tick=submitted['client_tick'], captured_client_tick=captured['client_tick'],
                             client_tick_delta=captured['client_tick']-submitted['client_tick'],
                             png_sha256=sha(RUN/(name+'.png')), section_readiness_recorded=False))
    report = dict(
        scope='Read-only diagnosis of the already completed C8 civil capture, not native acceptance',
        source_root=str(ROOT), world_opened=False, world_written=False, game_started=False,
        jar_sha256=json.loads((RUN/'PLAN.json').read_text('utf8'))['jar_sha256'],
        evidence={name:sha(RUN/name) for name in ['process.log','commands.json.ack.jsonl','PLAN.json','RESULT.json']},
        run_result=json.loads((RUN/'RESULT.json').read_text('utf8')),
        options={name:options[name] for name in ['renderDistance','simulationDistance','pauseOnLostFocus','maxFps','enableVsync']},
        captures=captures,
        server_delay_warnings=delays,
        highest_room_error_count=sum('Highest-room chamber held' in line for line in log),
        fatal_or_load_failure_lines=[line for line in log if re.search(r'Failed to load|Error rendering|OutOfMemory|thread/FATAL', line)],
        conclusion='Incomplete arrival/lighting/mesh preparation is supported by severe server delay and absent readiness gates; this capture cannot establish whether a residual Embeddium/Oculus culling defect exists.',
        reasons=[
            'TP acknowledgment is client sendCommand submission; it does not acknowledge server TP processing or chunk/light arrival.',
            'The runner waits eight wall-clock seconds, then the inbox captures after twenty client ticks without checking camera, chunk, light, mesh, or renderer queues.',
            'Client tick delta also does not establish render-frame count or integrated-server progress. The east view has only thirty-five ticks from TP submission to capture.',
            'A hidden window with pauseOnLostFocus=true can stall the integrated server; actual pause/window state was not recorded, so continuous pause is not claimed.',
            'Static full block availability, which Root verified separately, does not prove that client section meshes were delivered and uploaded.',
            'LargeStructureRenderMixin only changes the origin-section prerequisite for listed large entities; its smartCull override is restricted to r43-facility-photos and was not active in this civil run.',
        ],
        next_capture_readiness={
            'camera': 'Observe actual dimension, camera entity, eye position and yaw/pitch at the target; do not start settling time from command submission.',
            'unpaused': 'Record mc.isPaused(), mc.isWindowActive(), pauseOnLostFocus, screen name and progressing client/server clocks. Temporarily disable pause-on-focus-loss only for the explicit capture and restore it afterward.',
            'chunks_and_light': 'For each required visible landmark section, require ClientChunkCache.hasChunk. With the installed Embeddium, ChunkTrackerHolder.get(level).getReadyChunks contains the column only after block+light flags for its complete 3x3 neighborhood.',
            'sections': 'Require LevelRenderer.isChunkCompiled(anchor), backed by Embeddium isSectionReady -> RenderSectionManager.isSectionBuilt, for the actual visible building/shore/ridge sections. A single target point is insufficient for a tall facade.',
            'queues': 'Record SodiumWorldRenderer.getDebugStrings: Chunk Builder scheduled/busy; Chunk Queues U and P0/P1/P2. Capture after required sections are built and queues are empty across consecutive render frames. isTerrainRenderComplete alone only checks builder queue emptiness, not pending rebuild or upload results.',
            'light_work': 'Record level.getChunkSource().getLightEngine().hasLightWork; use regional block/light readiness as the primary gate because unrelated global light work can continue.',
            'render_progress': 'Record render-frame count, FPS, countRenderedChunks/getChunkStatistics, smartCull and camera coordinates from the same capture callback; require consecutive stable samples and at least 100 rendered frames after arrival.',
            'timeout': 'If required sections remain unavailable, write their loaded/light-ready/compiled flags and queue diagnostics and mark the view inconclusive; do not treat its screenshot as a failed building or reshape the map.',
            'culling_discrimination': 'Only after a settled baseline remains wrong, make a separate explicit diagnostic at the same camera with terrain rebuild and then smartCull disabled. Preserve the normal baseline and restore options. Geometry becoming visible only with culling disabled would justify a culling investigation; current screenshots contain no such comparison.',
        },
        local_primary_api_evidence={
            'embeddium_jar':'D:/eva/artifacts/r51_nonmap_release/native_r51/game/mods/embeddium-0.3.31+mc1.20.1.jar',
            'oculus_jar':'D:/eva/artifacts/r51_nonmap_release/native_r51/game/mods/oculus-mc1.20.1-1.8.0.jar',
            'existing_gate':'src/main/java/com/projectseele/client/visual/RegionalStationPhoto.java:242',
            'timer_capture':'src/main/java/com/projectseele/client/visual/NativeCommandInboxR47.java:41',
            'terrain_scope':'src/main/java/com/projectseele/mixin/client/LargeStructureRenderMixin.java:25',
            'api_verified':'Local javap of installed jars: SodiumWorldRenderer, RenderSectionManager, ChunkBuilder, ChunkTracker/ChunkTrackerHolder/ChunkStatus; mapped LevelLightEngine.hasLightWork.',
        },
        qa_next_jar='C9 or later matching Root highest-chamber rebind; do not reopen the used QA with C8',
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', 'utf8')
    print(json.dumps(dict(report=str(OUT), captures=len(captures), error_count=report['highest_room_error_count'],
                         server_delay_warnings=len(delays), native_acceptance=False)))


if __name__ == '__main__':
    main()
