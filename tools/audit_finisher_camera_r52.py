"""Audit every authored camera frame against exact selected posed skin vertices."""
from pathlib import Path
import argparse
import hashlib
import json
import time
import numpy as np
from r52_motion_core import selected, MIRROR, UNIT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('body', 'assets', 'angel-rig', 'clip', 'source-clip', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--hull-cache', type=Path)
    parser.add_argument('--hull-source-clip', type=Path)
    parser.add_argument('--allow-actor-changes', action='store_true')
    parser.add_argument('--renderer-welds', action='store_true')
    parser.add_argument('--start',type=int,default=0)
    parser.add_argument('--end',type=int)
    args = parser.parse_args()
    clip = json.loads(args.clip.read_text('utf8'))
    source = json.loads(args.source_clip.read_text('utf8'))
    equal_actors=all(clip[role] == source[role] for role in ('eva', 'angel'))
    if not args.allow_actor_changes:assert equal_actors
    cached = None
    if args.hull_cache:
        assert not args.renderer_welds, 'Renderer weld audit requires fresh geometry, not an older rigid cache'
        cache_source = json.loads(args.hull_source_clip.read_text('utf8'))
        assert all(source[role] == cache_source[role] for role in ('eva', 'angel'))
        cache = np.load(args.hull_cache)
        assert str(cache['source_sha256']) == digest(args.hull_source_clip)
        cached = [cache['vertices'][a:b] for a, b in zip(cache['offsets'][:-1], cache['offsets'][1:])]
    if cached is None or args.allow_actor_changes:
        _, hero, angel = selected(args.body, args.assets, args.angel_rig)
        if args.renderer_welds:
            import sys
            sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.codex'))
            from r52_runtime_weld_model import install
            runtime_welds=install(hero)
        chosen = [name for name in hero.parts if name in hero.names and name not in
                  ('dorsal_liner', 'r37_red_upper', 'r37_red_lower', 'r37_lining')]
    rows, failures = [], []
    reused=fresh=0
    start = time.monotonic()
    end=args.end if args.end is not None else len(clip['eva']['frames'])-1
    for frame in range(args.start,end+1):
        same_frame=cached is not None and all(clip[role]['frames'][frame]==cache_source[role]['frames'][frame] and clip[role]['root_blocks'][frame]==cache_source[role]['root_blocks'][frame] for role in ('eva','angel'))
        # Native immutable C6 hides Sachiel at 18.65s. The old cache omitted
        # it at 18.6s, so regenerate those three still-visible samples.
        if same_frame and not (18.6<=frame/clip['fps']<18.65):
            vertices = cached[frame]
            reused+=1
        else:
            fresh+=1
            points = []
            for role, rig, parts in [('eva', hero, chosen), ('angel', angel, None)]:
                if role == 'angel' and frame / clip['fps'] >= 18.65:
                    continue
                pose = rig.decode(clip[role]['frames'][frame], clip[role]['bones'])
                surface = pose.surface(parts) * (MIRROR if role == 'eva' else 1) * UNIT
                points.append(surface + np.asarray(clip[role]['root_blocks'][frame]))
            vertices = np.concatenate(points)
        position = np.asarray(clip['camera']['position'][frame])
        target = np.asarray(clip['camera']['target'][frame])
        forward = target - position
        forward /= np.linalg.norm(forward)
        right = np.cross(forward, [0, 1, 0])
        right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        relative = vertices - position
        depth = relative @ forward
        tangent = np.tan(np.radians(clip['camera']['fov'][frame]) / 2)
        horizontal = np.max(np.abs((relative @ right) / depth / tangent / (16 / 9)))
        vertical = np.max(np.abs((relative @ up) / depth / tangent))
        distance = np.max(np.linalg.norm(relative, axis=1))
        row = dict(frame=frame, seconds=frame / clip['fps'],
                   max_skin_distance=float(distance), horizontal_ndc=float(horizontal),
                   vertical_ndc=float(vertical), minimum_forward_depth=float(depth.min()))
        rows.append(row)
        if depth.min() <= 1 or distance >= 95 or horizontal > .88 or vertical > .78:
            failures.append(row)
        if frame % 300 == 0:
            print('audited exact camera frame', frame, flush=True)
    report = dict(clip_sha256=digest(args.clip), source_clip_sha256=digest(args.source_clip),
                  body_sha256=digest(args.body), all_actor_bones_root_and_curves_equal=equal_actors,
                  source_equal_full_skin_frames_reused=reused,fresh_actual_full_skin_frames=fresh,sachiel_visibility_cutoff_seconds=18.65,
                  frames=[args.start,end],frame_count=len(rows), fps=clip['fps'], sample_step_frames=1,
                  max_skin_distance=max(row['max_skin_distance'] for row in rows),
                  horizontal_ndc_max=max(row['horizontal_ndc'] for row in rows),
                  vertical_ndc_max=max(row['vertical_ndc'] for row in rows),
                  safe_horizontal_ndc=.88, safe_vertical_ndc=.78, distance_limit=95,
                  failures=failures, passed=not failures, elapsed_seconds=time.monotonic()-start,
                  exact_hull_cache=str(args.hull_cache) if cached is not None else None,
                  scope='All authored 60fps frames, exact selected visible skin; no native camera collision, entry/return blending, or continuous visual acceptance inferred',
                  native_verified=False, user_accepted=False)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    report['renderer_fallback_welds']=runtime_welds if args.renderer_welds else None
    args.out.write_text(json.dumps(report, indent=2), 'utf8')
    print(json.dumps({key: value for key, value in report.items() if key != 'failures'}, indent=2))


if __name__ == '__main__':
    main()
