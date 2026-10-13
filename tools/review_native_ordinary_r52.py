"""Export timestamped native sequences and facts; images/continuous motion still require visual review."""
from pathlib import Path
import argparse, hashlib, json, subprocess
from PIL import Image, ImageDraw


def read_rows(file):
    return [json.loads(line) for line in file.read_text('utf8').splitlines() if line]


def sheet(run, rows, name, count=24):
    if not rows:
        return None
    indexes = sorted(set(round(i * (len(rows)-1) / max(1, count-1)) for i in range(count)))
    selected = [rows[i] for i in indexes]
    result = Image.new('RGB', (1280, ((len(selected)+3)//4)*208), '#171923')
    draw = ImageDraw.Draw(result)
    manifest = []
    for index, row in enumerate(selected):
        file = run / 'frames' / row['file']
        with Image.open(file) as image:
            tile = image.convert('RGB')
            tile.thumbnail((320, 180))
        x, y = (index % 4)*320, (index//4)*208
        result.paste(tile, (x, y))
        draw.text((x+5, y+182), f"v{row['variant']} tick {row['age']} {row['key']}", fill='white')
        draw.text((x+5, y+195), f"phase {row['phase']:.3f} stance {row['stance']:.2f}", fill='white')
        manifest.append(dict(file=str(file), variant=row['variant'], age=row['age'], key=row['key'], phase=row['phase']))
    result.save(run / (name + '.jpg'), quality=93)
    (run / (name + '.json')).write_text(json.dumps(manifest, indent=2), 'utf8')
    return str(run / (name + '.jpg'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    poses, frames, inputs = [read_rows(run / (name + '.jsonl')) for name in ('poses', 'frames', 'inputs')]
    report = dict(native_only=True, interpolated_frames=0, pose_rows=len(poses), input_rows=len(inputs),
                  framebuffer_frames=len(frames), native_visual_acceptance=False, rigs=[], products=[])
    for variant in (0, 1, 2):
        p = [r for r in poses if r['variant'] == variant]
        f = [r for r in frames if r['variant'] == variant]
        commands = [r for r in inputs if r.get('variant') == variant and r['kind'] == 'actual_client_packet']
        segments = []
        for row in p:
            state = (row['key'], row['handling_active'], row['sword_active'])
            if not segments or tuple(segments[-1]['state']) != state:
                segments.append(dict(state=state, first_age=row['age'], last_age=row['age'], samples=0))
            segments[-1]['last_age'] = row['age']
            segments[-1]['samples'] += 1
        sole = {side: [r['actual_foot_witness'][side+'_sole_clearance'] for r in p
                      if side+'_sole_clearance' in r['actual_foot_witness']] for side in ('l', 'r')}
        fact = dict(variant=variant, pose_rows=len(p), native_frames=len(f),
                    first_age=p[0]['age'] if p else None, last_age=p[-1]['age'] if p else None,
                    powered_false_rows=sum(not r['isPoweredOn'] for r in p),
                    hand_joint_counts=sorted({r['finger_joint_count'] for r in p}), actual_packets=commands,
                    knife_types=sorted({r['knife_type'] for r in p}),
                    handling_active_rows=sum(r['handling_active'] for r in p),
                    sword_active_rows=sum(r['sword_active'] for r in p),
                    prone_rows=sum(r['stance'] > 2.99 for r in p),
                    submitted_sole_rows={side: len(values) for side, values in sole.items()},
                    sole_clearance_ranges={side: [min(values), max(values)] if values else None for side, values in sole.items()},
                    actual_state_segments=segments,
                    maximum_capture_gap_seconds=max(((b['capture_ns']-a['capture_ns'])/1e9 for a,b in zip(f,f[1:])), default=0))
        report['rigs'].append(fact)
        if not f:
            continue
        text = []
        for index, row in enumerate(f):
            text.append("file '" + str((run / 'frames' / row['file']).as_posix()).replace("'", "'\\''") + "'")
            if index+1 < len(f):
                text.append('duration ' + str((f[index+1]['capture_ns']-row['capture_ns'])/1e9))
        concat = run / f'rig{variant}_native.ffconcat'
        concat.write_text('\n'.join(text)+'\n', 'utf8')
        video = run / f'rig{variant}_native_continuous.mp4'
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat),
                        '-vsync', 'vfr', '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '19',
                        '-pix_fmt', 'yuv420p', str(video)], check=True)
        with video.open('rb') as stream:
            video_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
        report['products'].append(dict(video=str(video), sha256=video_hash, sheet=sheet(run, f, f'RIG{variant}_NATIVE_SEQUENCE')))
        sheet(run, [r for r in f if 25 <= r['age'] <= 155], f'RIG{variant}_LOCOMOTION_NATIVE', 32)
        sheet(run, [r for r in f if r['stance'] > 2.5], f'RIG{variant}_PRONE_NATIVE', 24)
    sheet(run, [r for r in frames if r['variant'] == 1 and 466 <= r['age'] <= 510], 'KNIFE_CANCEL_REINPUT_NATIVE', 36)
    sheet(run, [r for r in frames if r['variant'] == 1 and 245 <= r['age'] <= 310], 'KNIFE_DRAW_NATIVE', 28)
    sheet(run, [r for r in frames if r['variant'] == 1 and 725 <= r['age'] <= 780], 'KNIFE_STOW_NATIVE', 28)
    sheet(run, [r for r in frames if r['variant'] == 2 and 245 <= r['age'] <= 450], 'SWORD_ATTACK_NATIVE', 36)
    (run / 'NATIVE_FACTS.json').write_text(json.dumps(report, indent=2), 'utf8')
    print(json.dumps({k: report[k] for k in ('pose_rows', 'framebuffer_frames', 'products')}, indent=2))


if __name__ == '__main__':
    main()
