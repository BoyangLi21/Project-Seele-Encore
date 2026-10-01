"""Read-only resource/pose audit; never prints a minified motion document."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts/rebuild_r44/combat'
OWNED = [
    'entity/EvaUnit01Entity.java', 'entity/EvaBodyPose.java',
    'entity/EvaGameplayMotionR32.java', 'entity/EvaCombatSupportR33.java',
    'entity/EvaHandsR41.java', 'entity/SachielGameplayMotionR32.java',
    'client/render/EvaCombatPoseR31.java', 'client/render/EvaHandPoseR28.java',
    'client/render/EvaPoseGraph.java', 'entity/FirstBattleClip.java',
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(path):
    data = json.loads(path.read_text('utf8'))
    motion = data.get('motion', data)
    names = motion.get('bones', [])
    clips = []
    for name, clip in motion.get('clips', {}).items():
        frames = clip.get('frames', [])
        if not frames:
            continue
        q = np.asarray([f['rotation_wxyz'] for f in frames], float)
        norms = np.linalg.norm(q, axis=2)
        q /= np.maximum(norms[..., None], 1e-12)
        angles = np.degrees(2*np.arccos(np.clip(np.abs((q[:-1]*q[1:]).sum(2)), 0, 1)))
        selected = [i for i, n in enumerate(names) if n.startswith(('leg_', 'shin_', 'arm_', 'forearm_', 'hand_', 'finger_'))]
        worst = None
        if selected and len(angles):
            at = np.unravel_index(np.argmax(angles[:, selected]), angles[:, selected].shape)
            worst = dict(frame=int(at[0]), bone=names[selected[at[1]]], degrees=float(angles[at[0], selected[at[1]]]))
        clips.append(dict(name=name, frames=len(frames), channels=len(names),
                          duration=clip.get('duration_seconds'), contact=clip.get('contact_phase'),
                          finite=bool(np.isfinite(q).all() and np.isfinite(norms).all()),
                          minimum_quaternion_norm=float(norms.min()), worst_step=worst))
    return dict(path=str(path.resolve()), sha256=sha(path), bytes=path.stat().st_size,
                schema=data.get('schema'), rig=data.get('rig_key'), channels=len(names),
                channel_names=names, clips=clips)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot-source', action='store_true')
    parser.add_argument('--candidate', type=Path)
    args = parser.parse_args()
    ART.mkdir(parents=True, exist_ok=True)
    baseline = json.loads((ROOT/'artifacts/rebuild_r44/baseline.json').read_text('utf8'))
    instance = Path(baseline['instance'])
    local = instance/'projectseele-local-maps'
    paths = [local/'eva_body_r43.json', local/'eva_gameplay_r43_1.json']
    paths += [local/f'eva_gameplay_r42_{key}.json' for key in range(5)]
    paths += [local/'first_battle_r43.json', local/'sachiel_gameplay_r32.json']
    legacy = ROOT/'src/main/resources/assets/projectseele/motion'
    paths += [legacy/'eva_knife_attacks_phase_m_v1.json', legacy/'eva_kick_side_left_v1.json']
    if args.candidate:
        paths += sorted(args.candidate.glob('eva_gameplay_r44_*.json'))
    records = [inspect(p) for p in paths if p.is_file() and not p.name.startswith('first_battle')]
    identity = []
    for path in paths:
        if not path.is_file():
            identity.append(dict(name=path.name, exists=False, path=str(path)))
            continue
        source = ROOT/'run/projectseele-local-maps'/path.name
        identity.append(dict(name=path.name, path=str(path.resolve()), sha256=sha(path),
                             source_path=str(source), source_sha256=sha(source) if source.is_file() else None,
                             same_as_development=source.is_file() and sha(source)==sha(path)))
    body = json.loads((local/'eva_body_r43.json').read_text('utf8'))
    legacy_channels = {record['path'].split('\\')[-1]: set(record['channel_names'])
                       for record in records if 'phase_m' in record['path'] or 'kick_side' in record['path']}
    missing = []
    for key, rig in body['rigs'].items():
        required = {b['name'] for b in rig}
        missing.append(dict(rig=int(key), bones=len(required),
                            omitted_by_legacy={name:sorted(required-channels) for name, channels in legacy_channels.items()}))
    report = dict(scope='Local SEELE43 resources, candidate files and source-channel audit only; no native playback or visual acceptance claimed',
                  identity=identity, rigs=missing, motion=records,
                  knife_timing=dict(rate=1.5, forward_before_ticks=round(44*20/60),
                                    forward_after_ticks=round(44*20/60/1.5),
                                    reverse_before_ticks=round(24*20/60), reverse_after_ticks=round(24*20/60/1.5)),
                  unverified=['Remote server fleet state and resource versions', 'Knife final rendered bones in a real client',
                              'Native contact, slope support, network synchronization, final artistic acceptance'])
    (ART/'resource_identity.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
    if args.snapshot_source:
        destination = ART/'source_before'
        for item in OWNED:
            source = ROOT/'src/main/java/com/projectseele'/item
            target = destination/item
            if source.is_file() and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        (destination/'hashes.json').write_text(json.dumps({item:sha(destination/item) for item in OWNED if (destination/item).exists()}, indent=2),'utf8')
    print(json.dumps(dict(resources=len(records), rigs=len(missing), identity_report=str(ART/'resource_identity.json'),
                          knife_timing=report['knife_timing']), ensure_ascii=False))


if __name__ == '__main__':
    main()
