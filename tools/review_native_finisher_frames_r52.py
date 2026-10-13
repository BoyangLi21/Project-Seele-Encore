"""Assemble native timestamped frames and bounded receipts without interpolation."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
from PIL import Image, ImageDraw


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    manifest = json.loads((run / 'frames/frames.json').read_text('utf8'))
    frames = manifest['frames']
    assert manifest['capture_mode'] == 'full_frame_sequence'
    assert not manifest['write_failure']
    for frame in frames:
        assert (run / 'frames' / frame['file']).is_file()
    products, summaries = [], []
    for sequence in (0, 1):
        actual = [frame for frame in frames if frame.get('review_sequence_r52', 0) == sequence and frame.get('active')]
        assert actual, 'Missing full native scene ' + str(sequence)
        text = []
        intervals = []
        for index, frame in enumerate(actual):
            file = (run / 'frames' / frame['file']).as_posix().replace("'", "'\\''")
            text.append("file '" + file + "'")
            if index + 1 < len(actual):
                duration = actual[index + 1]['seconds'] - frame['seconds']
                assert duration > 0
                intervals.append(duration)
                text.append('duration ' + str(duration))
        concat = run / ('sequence_' + str(sequence) + '.ffconcat')
        concat.write_text('\n'.join(text) + '\n', 'utf8')
        movie = run / ('native_' + ('berserk' if sequence == 0 else 'ordinary') + '_continuous.mp4')
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat),
                        '-vsync', 'vfr', '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '19',
                        '-pix_fmt', 'yuv420p', str(movie)], check=True)
        products.append(dict(path=str(movie), sha256=digest(movie), bytes=movie.stat().st_size))
        summaries.append(dict(sequence=sequence, actual_native_frames=len(actual),
                              first_scene_seconds=actual[0]['scene_seconds'], last_scene_seconds=actual[-1]['scene_seconds'],
                              max_actual_capture_gap_seconds=max(intervals), fps_samples_min=min(frame['fps'] for frame in actual),
                              fps_samples_max=max(frame['fps'] for frame in actual)))
        ticks = [50, 100, 158, 167, 184, 230, 260, 279, 310, 325, 345, 360, 373, 416, 432, 440]
        sheet = Image.new('RGB', (1600, 1000), (18, 22, 27))
        selected = []
        for index, tick in enumerate(ticks):
            frame = min(actual, key=lambda row: abs(row['synced_age_ticks']-tick))
            file = run / 'frames' / frame['file']
            with Image.open(file) as image:
                tile = image.convert('RGB'); tile.thumbnail((400, 225))
            left, top = index % 4 * 400, index // 4 * 250
            sheet.paste(tile, (left, top))
            ImageDraw.Draw(sheet).text((left+8, top+229), 'native age ' + str(frame['synced_age_ticks']), fill='white')
            selected.append(dict(scheduled_review_tick=tick, actual=frame, file=str(file), sha256=digest(file)))
        sheet_file = run / ('NATIVE_SEQUENCE_' + str(sequence) + '.jpg')
        sheet.save(sheet_file, quality=92)
        (run / ('SELECTED_SEQUENCE_' + str(sequence) + '.json')).write_text(json.dumps(selected, indent=2), 'utf8')
    contact_file = run / 'contact_shade.jsonl'
    control = [frame for frame in frames if frame.get('control_recovery_window_r52') and not frame.get('active')]
    control_summary = dict(captured=False, actual_native_frames=0, actual_w_frames=0)
    if control:
        text = []
        for index, frame in enumerate(control):
            file = (run / 'frames' / frame['file']).as_posix().replace("'", "'\\''")
            text.append("file '" + file + "'")
            if index + 1 < len(control):
                duration = control[index + 1]['seconds'] - frame['seconds']
                assert duration > 0
                text.append('duration ' + str(duration))
        concat = run / 'control_recovery.ffconcat'
        concat.write_text('\n'.join(text) + '\n', 'utf8')
        movie = run / 'native_control_recovery_continuous.mp4'
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat),
                        '-vsync', 'vfr', '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '19',
                        '-pix_fmt', 'yuv420p', str(movie)], check=True)
        products.append(dict(path=str(movie), sha256=digest(movie), bytes=movie.stat().st_size))
        control_summary = dict(captured=True, actual_native_frames=len(control),
                               actual_w_frames=sum(frame.get('actual_w_key_down_r52', False) for frame in control),
                               first_position=control[0]['entity_position_r52'], last_position=control[-1]['entity_position_r52'],
                               max_actual_capture_gap_seconds=max((b['seconds']-a['seconds'] for a,b in zip(control,control[1:])), default=0))
    receipts = [json.loads(line) for line in contact_file.read_text('utf8').splitlines() if line]
    contacts = []
    for row in receipts:
        draws = row['actual_draws']
        contacts.append(dict(age=row['age'], submitted_quads=row['submitted_quads'], actual_draw_count=len(draws),
                             actual_shader_classes=list({draw['shader_class'] for draw in draws}),
                             color_write_masks=[draw['color_write'] for draw in draws],
                             depth_write=[draw['depth_write'] for draw in draws],
                             framebuffer=[draw['draw_framebuffer'] for draw in draws]))
    report = dict(capture_mode=manifest['capture_mode'], native_frames=len(frames), dropped_frames=manifest['dropped'],
                  movies=products, sequences=summaries, control_recovery=control_summary, contact_actual_draws=contacts,
                  timestamped_native_only=True, interpolated_frames=0,
                  full_motion_visual_acceptance='Requires visual review of the actual movies and images',
                  native_visual_acceptance=False, user_accepted=False)
    (run / 'NATIVE_CONTINUOUS_CAPTURE_RECEIPT.json').write_text(json.dumps(report, indent=2), 'utf8')
    print(json.dumps({key: value for key, value in report.items() if key != 'contact_actual_draws'}, indent=2))


if __name__ == '__main__':
    main()
