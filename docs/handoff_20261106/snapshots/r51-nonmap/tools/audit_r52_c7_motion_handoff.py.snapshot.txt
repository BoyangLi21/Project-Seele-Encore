"""Read existing C7 pose evidence and older low-overhead JFR receipts; no replay."""
from pathlib import Path
import hashlib, json, math

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'artifacts/r52_native_ordinary_candidate7_retry1'
OUT = ROOT / '.codex/r52_motion_delivery_audit'

def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f, 'sha256').hexdigest()
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def basis(m):
    return [[m[i+j*4]/math.sqrt(sum(m[k+j*4]**2 for k in range(3))) for i in range(3)] for j in range(3)]
def local_basis(row, bone, parent):
    c = basis(row['final_rendered_model_bones'][bone])
    p = basis(row['final_rendered_model_bones'][parent])
    return [[dot(p[i], c[j]) for i in range(3)] for j in range(3)]
def angle(a,b):return math.degrees(math.acos(max(-1, min(1, (sum(dot(x,y) for x,y in zip(a,b))-1)/2))))

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(x) for x in (RUN / 'poses.jsonl').read_text('utf8').splitlines()]
    body = read(ROOT / 'artifacts/r52_runtime_candidate/projectseele-local-maps/eva_body_r44.json')
    parents = {int(r):{b['name']:b.get('parent') for b in rig} for r,rig in body['rigs'].items()}
    boundaries = []
    for variant in (0,1,2):
        actor_rows = [r for r in rows if r['variant'] == variant]
        for a,b in zip(actor_rows, actor_rows[1:]):
            if a['getWeapon'] == b['getWeapon']:continue
            angles = {}
            for bone in ('arm_l','arm_r','forearm_l','forearm_r','wrist_l','wrist_r','hand_l','hand_r'):
                parent = parents[variant].get(bone)
                if not parent or bone not in a['final_rendered_model_bones'] or parent not in a['final_rendered_model_bones']:continue
                angles[bone] = angle(local_basis(a,bone,parent), local_basis(b,bone,parent))
            boundaries.append(dict(variant=variant, before_age=a['age'], after_age=b['age'],
                before_weapon=a['getWeapon'], after_weapon=b['getWeapon'], before_handling=a['handling_active'],
                after_handling=b['handling_active'], before_handling_phase=a['handling_phase'], after_handling_phase=b['handling_phase'],
                server_tick_gap=b['server_tick']-a['server_tick'], local_bone_angle_delta_degrees=angles,
                before_and_after_same_uuid=a['uuid']==b['uuid']))
    profile = read(ROOT / 'artifacts/r52_native_finisher_profile_retry1/PERFORMANCE_FIX_RECEIPT_R52.json')
    comparison = read(ROOT / 'artifacts/r52_native_finisher_profile_postfix1/PERFORMANCE_COMPARISON_R52.json')
    source_names = ('entity/EvaPoseSignalClock.java','entity/FirstBattleClock.java','entity/FirstBattleSignals.java',
        'entity/FirstBattleClip.java','entity/EvaUnit01Entity.java','entity/EvaBodyPose.java','entity/EvaGameplayMotionR32.java',
        'entity/EvaWeaponHandlingR45.java','entity/EvaSwordActionsR45.java','entity/EvaOrdinaryStandingSupportR52.java',
        'entity/EvaShutdownR30.java','client/render/EvaMechanicalResetR30.java','client/render/EvaPoseTransition.java',
        'client/render/EvaMotionEngineV2.java','client/render/PosedMeshCacheR52.java','client/render/RigidCapsuleGpu.java')
    report = dict(schema='projectseele.r52.existing-native-handoff-audit.v1', native_pose_rows=len(rows),
        C7_pose_sha256=sha(RUN / 'poses.jsonl'), captured_weapon_boundaries=boundaries,
        boundary_limits='Adjacent actual C7 final bone rotation bases normalized and compared in parent space; sampled gaps are reported, not reconstructed. No per-frame image or exact unsampled handoff is invented.',
        clock_audit=dict(ordinary='Nano render clock via EvaPoseSignalClock.sample; action-source bulk packet identity keeps restart endpoints separate',
            firstbattle='Shared FirstBattleClock uses bounded two-tick extrapolation and cue ceilings; renderOffset cancels entity interpolated origin',
            adjacent_clip_frames='EvaBodyPose.clip / FirstBattleClip.pose keep f-a slerp/lerp after integer array indices',
            ordinary_path='previewMode zero uses applyGameplay; old preview-only >48 STATES.clear is outside normal gameplay',
            world_position='ordinary uses double partial + xOld/current; logistics lerpTo sets two steps; integral origin clock subtraction precedes float fractions'),
        exit_audit=dict(firstbattle_berserk='completeFirstBattle captures finalEvaPose before clearing clip; restAfterFirstBattle freezes it and confirms authority',
            ordinary='complete-owner bypass clears transition history; regular action change rebases Track from last presented pose',
            weapon='Controllers still reset for normal weapon changes; shared ordinary final history now survives, with a finite 0.20s upper guard exit. Full mechanical resets remain absolute. Actual C7 weapon boundaries recorded above; new native C8 result remains pending',
            sword='Sword state .273 phase may remain after inactive; inactive flags and clip ownership must qualify idle statistics'),
        performance=dict(low_overhead_profile_jar_is_older_than_C7=True,
            profile_source_jfr_sha256=profile['profile_source_jfr_sha256'],
            render_upload_inclusive_percent=profile['upload_vertex_build_percent_of_render_execution_samples'],
            render_skin_inclusive_percent=profile['eva_skin_percent'], server_tick_ms=profile['server_tick_ms'],
            cpu_cache_fixes_present='Per-source LCA dependencies and bounded pass VBOs remain in audited source',
            postfix_focused_middle_scene_median_fps=comparison['fps_comparison']['postfix']['phases'][1]['median_fps'],
            postfix_no_jfr=True, C7_capture_fps_is_not_uncaptured_benchmark=True,
            remaining_unprofiled_costs=['PosedMeshCache.prepare re-collects hierarchy per part for each new evaluation',
                'Standing support transforms 4 shoe hulls per eligible pose (196/204/192 points for Units 0/1/2) and performs two real floor rays',
                'Standing Correction constructor and finish both copy all pose channels; old first copy is replaced before use'],
            blind_tickrate_change_needed=False, production_optimization_attempted=False),
        source_sha256={n:sha(ROOT / 'src/main/java/com/projectseele' / n) for n in source_names},
        weapon_guard_source_replay_receipt=str(ROOT / '.codex/r52_weapon_guard_handoff/SOURCE_COMPILE_RECEIPT.json'),
        weapon_guard_source_replay_native_verified=False,
        pending=['C8 final C12 native source/submission parity and core-contact view',
                 'C8 Unit1 handling shoe support eligibility in actual game',
                 'Raw begin age1 eye pixels (C7 head offscreen)',
                 'Direct arbitrary normal weapon guard switch continuity is not fully represented by C7 handling sample'],
        source_modified=False, game_started=False, world_written=False, native_acceptance=False, user_accepted=False)
    (OUT / 'EXISTING_NATIVE_AND_SOURCE_AUDIT.json').write_text(json.dumps(report, indent=2) + '\n', 'utf8')
    print(json.dumps(dict(native_rows=len(rows), boundaries=boundaries, production_source_modified=False, game_started=False)))

if __name__ == '__main__':main()
