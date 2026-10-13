"""Fit finite cinematic shots to exact per-frame skin convex hulls; preserve actors."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from scipy.spatial import ConvexHull
from scipy.signal import savgol_filter
from r52_motion_core import selected, MIRROR, UNIT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hulls(args, clip, source_sha):
    if args.cache.is_file():
        cache = np.load(args.cache)
        assert str(cache['source_sha256']) == source_sha
        return [cache['vertices'][a:b] for a, b in zip(cache['offsets'][:-1], cache['offsets'][1:])]
    _, hero, angel = selected(args.body, args.assets, args.angel_rig)
    chosen = [name for name in hero.parts if name in hero.names and name not in
              ('dorsal_liner', 'r37_red_upper', 'r37_red_lower', 'r37_lining')]
    reused=None;reused_clip=None;reused_frames=[]
    if args.reuse_cache:
        assert args.reuse_clip is not None
        old=np.load(args.reuse_cache);reused_clip=json.loads(args.reuse_clip.read_bytes())
        assert str(old['source_sha256'])==digest(args.reuse_clip)
        assert reused_clip['fps']==clip['fps']
        assert all(reused_clip[role]['bones']==clip[role]['bones'] for role in ('eva','angel'))
        reused=[old['vertices'][a:b] for a,b in zip(old['offsets'][:-1],old['offsets'][1:])]
        assert len(reused)==len(clip['eva']['frames'])
    result = []
    for frame in range(len(clip['eva']['frames'])):
        if reused is not None and all(reused_clip[role]['frames'][frame]==clip[role]['frames'][frame]
                and reused_clip[role]['root_blocks'][frame]==clip[role]['root_blocks'][frame] for role in ('eva','angel')):
            result.append(reused[frame]);reused_frames.append(frame);continue
        surfaces = []
        for role, rig, parts in [('eva', hero, chosen), ('angel', angel, None)]:
            if role == 'angel' and frame / clip['fps'] >= 18.6:
                continue
            pose = rig.decode(clip[role]['frames'][frame], clip[role]['bones'])
            surfaces.append(pose.surface(parts) * (MIRROR if role == 'eva' else 1) * UNIT
                            + np.asarray(clip[role]['root_blocks'][frame]))
        points = np.concatenate(surfaces)
        result.append(points[ConvexHull(points).vertices])
        if frame % 300 == 0:
            print('cached exact skin hull', frame, flush=True)
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    assert digest(args.clip)==source_sha, 'Candidate changed while its exact hulls were being generated'
    np.savez_compressed(args.cache, source_sha256=source_sha,
                        offsets=np.r_[0, np.cumsum([len(points) for points in result])],
                        vertices=np.concatenate(result))
    if reused is not None:
        (args.cache.parent/'HULL_REUSE_RECEIPT.json').write_text(json.dumps(dict(source_sha256=source_sha,
                reused_clip_sha256=digest(args.reuse_clip),reused_cache_sha256=digest(args.reuse_cache),
                unchanged_pose_and_root_frames=reused_frames,recomputed_frames=len(result)-len(reused_frames),
                body_sha256=digest(args.body),scope='Reuse only this run\'s selected-input exact cache after per-frame pose/root equality; geometry inputs are the same read-only selected files.',
                native_verified=False,user_accepted=False),indent=2),'utf8')
    return result


def constraints(points, target, yaw, pitch, distance_limit=92):
    yaw, pitch = np.radians([yaw, pitch])
    offset = np.array([np.sin(yaw)*np.cos(pitch), np.sin(pitch), np.cos(yaw)*np.cos(pitch)])
    forward = -offset
    right = np.cross(forward, [0, 1, 0]); right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    relative = points - target
    depth = relative @ forward
    tangent = np.tan(np.radians(80) / 2)
    required = max(np.max(abs(relative @ right)/(tangent*.86*16/9) - depth),
                   np.max(abs(relative @ up)/(tangent*.76) - depth),
                   2 - depth.min())
    dot = relative @ offset
    perpendicular = np.sum(relative*relative, axis=1) - dot*dot
    if perpendicular.max() >= distance_limit*distance_limit:
        return None
    maximum = np.min(dot + np.sqrt(distance_limit*distance_limit - perpendicular))
    return required, maximum, offset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('body', 'assets', 'angel-rig', 'clip', 'cache', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--cache-only', action='store_true')
    parser.add_argument('--reuse-cache',type=Path)
    parser.add_argument('--reuse-clip',type=Path)
    parser.add_argument('--preferred-shots',type=Path)
    args = parser.parse_args()
    raw=args.clip.read_bytes();source_sha=hashlib.sha256(raw).hexdigest();clip=json.loads(raw)
    frames = hulls(args, clip, source_sha)
    if args.cache_only:
        print('Exact hull cache complete', len(frames), flush=True)
        return
    centres = np.asarray([(points.min(0)+points.max(0))/2 for points in frames])
    centres = savgol_filter(centres, 31, 3, axis=0)
    # Feasibility of a finite shot is measured over every frame. Both direction
    # and cut location are authored before the native review, never inferred
    # from sparse camera samples.
    intervals = [(0, 264), (264, 360), (360, 726), (726, 804), (804, 1116), (1116, len(frames))]
    orientations = [(yaw, pitch) for yaw in range(-100, 101, 5) for pitch in (0, 5, 10, 15, 20, 25, 30)]
    choices = []
    preferred=json.loads(args.preferred_shots.read_bytes())['shots'] if args.preferred_shots else []
    for start, end in intervals:
        scored = []
        prior=next((shot for shot in preferred if shot['start']==start and shot['end']==end-1),None)
        options=[(prior['yaw'],prior['pitch'])]+orientations if prior else orientations
        for yaw, pitch in options:
            good, margin, targets, distances = 0, float('inf'), [], []
            for index in range(start, end):
                candidates = []
                for shift in (-12, -8, -4, 0, 4, 8, 12):
                    target = centres[index] + [0, shift, 0]
                    limits = constraints(frames[index], target, yaw, pitch)
                    if limits is None:
                        continue
                    required, maximum, offset = limits
                    candidates.append((maximum-required, -abs(shift), target, (required+maximum)/2))
                best = max(candidates, key=lambda value: value[:2]) if candidates else None
                if best is not None and best[0] >= 0:
                    good += 1; margin = min(margin, best[0]); targets.append(best[2]); distances.append(best[3])
                else:
                    targets.append(centres[index]); distances.append(0)
                    break
            scored.append((good, margin, yaw, pitch, np.asarray(targets), np.asarray(distances)))
            if prior and (yaw,pitch)==(prior['yaw'],prior['pitch']) and good==end-start:
                break
        best = max(scored, key=lambda value: (value[0], value[1]))
        summary = dict(start=start, end=end-1, fitting_frames=best[0], total_frames=end-start,
                       minimum_margin=best[1], yaw=best[2], pitch=best[3])
        choices.append(summary)
        print(summary, flush=True)
        if best[0] != end-start:
            continue
        # The target and distance are gently filtered only inside each finite
        # shot; an exact second pass clamps distance to the geometric interval.
        targets = savgol_filter(best[4], min(21, (end-start)//2*2-1), 3, axis=0)
        distances = savgol_filter(best[5], min(21, (end-start)//2*2-1), 3)
        for index in range(start, end):
            target = targets[index-start]
            limits = constraints(frames[index], target, best[2], best[3], 93)
            assert limits is not None and limits[0] <= limits[1], ('Filtered shot target is infeasible', index)
            distance = np.clip(distances[index-start], limits[0], limits[1])
            clip['camera']['position'][index] = (target + limits[2]*distance).tolist()
            clip['camera']['target'][index] = target.tolist()
            clip['camera']['fov'][index] = 80
    assert digest(args.clip)==source_sha, 'Candidate changed while its exact camera was being fitted'
    report = dict(source_clip_sha256=source_sha, shots=choices,
                  all_shots_fit=all(shot['fitting_frames']==shot['total_frames'] for shot in choices),
                  native_verified=False, user_accepted=False)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'SHOT_FIT_REPORT.json').write_text(json.dumps(report, indent=2), 'utf8')
    if report['all_shots_fit']:
        clip['camera']['cuts'] = [start for start, end in intervals if start]
        clip['r52_finisher_rebuild']['camera_revision'] = 'r52-full-skin-every-frame-finite-shots'
        (args.out / 'first_battle_r52_camera4.json').write_text(json.dumps(clip, separators=(',', ':')), 'utf8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
