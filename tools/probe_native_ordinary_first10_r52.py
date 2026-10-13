"""Read-only first native 10-second facts and actual frames; no visual pass inference."""
from pathlib import Path
import argparse, json
import numpy as np
from PIL import Image, ImageDraw

def rows(path):
    result = []
    if path.exists():
        for line in path.read_text('utf8', errors='replace').splitlines():
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # Concurrent writer may have only written part of its final line.
    return result

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', type=Path, required=True)
args = parser.parse_args()
run = args.run.resolve()
poses = [r for r in rows(run / 'poses.jsonl') if r['variant'] == 0 and r['age'] <= 200]
frames = [r for r in rows(run / 'frames.jsonl') if r['variant'] == 0 and r['age'] <= 200 and (run / 'frames' / r['file']).exists()]
inputs = [r for r in rows(run / 'inputs.jsonl') if r.get('variant') == 0 and r.get('age', -1) <= 200]
facts = dict(native_visual_acceptance=False, examined_variant=0, pose_rows=len(poses), actual_framebuffer_frames=len(frames),
             greatest_age=max((r['age'] for r in poses), default=None), failure_file=(run / 'FAILURE.json').exists())
for name, start, end in [('walk', 35, 74), ('run', 80, 119), ('stop', 160, 180)]:
    selected = [r for r in poses if start <= r['age'] <= end]
    points = np.asarray([r['position'] for r in selected])
    facts[name] = dict(rows=len(selected), actual_keys=sorted({r['key'] for r in selected}),
        server_forward_input_range=[min(r.get('pilot_server_forward_input', 0) for r in selected), max(r.get('pilot_server_forward_input', 0) for r in selected)] if selected else None,
        displacement_blocks=float(np.linalg.norm(points[-1]-points[0])) if len(points) > 1 else None,
        actual_move_blend_range=[min(r.get('rifleMoveBlend', 0) for r in selected), max(r.get('rifleMoveBlend', 0) for r in selected)] if selected else None,
        actual_run_blend_range=[min(r.get('rifleRunBlend', 0) for r in selected), max(r.get('rifleRunBlend', 0) for r in selected)] if selected else None,
        actual_gait_phase_range=[min(r.get('rifleGaitPhase', 0) for r in selected), max(r.get('rifleGaitPhase', 0) for r in selected)] if selected else None)
    for bone in ('leg_l', 'shin_l', 'leg_r', 'shin_r'):
        matrices = np.asarray([r['final_rendered_model_bones'][bone] for r in selected if bone in r['final_rendered_model_bones']])
        facts[name][bone + '_maximum_matrix_component_change'] = float(np.abs(matrices-matrices[0]).max()) if len(matrices) else None
facts['actual_vanilla_movement_packets'] = sum(r.get('kind') == 'actual_vanilla_player_input_packet' and r.get('forward') == 1 for r in inputs)
facts['limits'] = 'Only actual packet/server/pose/frame facts. Displacement alone cannot establish gait quality; inspect native image sequence before proceeding.'
(run / 'FIRST10_FACTS.json').write_text(json.dumps(facts, indent=2), 'utf8')
if frames:
    choices = []
    for target in (0, 36, 48, 62, 81, 94, 108, 130, 160, 178):
        candidate = min(frames, key=lambda r: abs(r['age']-target))
        if candidate not in choices:
            choices.append(candidate)
    sheet = Image.new('RGB', (1280, ((len(choices)+3)//4)*208), '#171923')
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(choices):
        with Image.open(run / 'frames' / row['file']) as picture:
            tile = picture.convert('RGB'); tile.thumbnail((320, 180))
        x, y = index%4*320, index//4*208
        sheet.paste(tile, (x, y))
        draw.text((x+4, y+182), f"actual age {row['age']} {row['key']}", fill='white')
        draw.text((x+4, y+195), f"forward={row.get('pilot_server_forward_input')} run={row.get('rifleRunBlend')}", fill='white')
    sheet.save(run / 'FIRST10_ACTUAL_FRAMES.jpg', quality=93)
    (run / 'FIRST10_ACTUAL_FRAMES.json').write_text(json.dumps(choices, indent=2), 'utf8')
print(json.dumps(facts, indent=2))
