"""Original fine grating/stringer models matching the declared native deck.

Private assets only. Native registered64 collision/outline unions must be
exported and compared before a world candidate may become applicable.
"""
from pathlib import Path
import argparse, hashlib, json
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/rebuild_r44/hangar_machinery'


def authored(profile, level):
    base = level / 4
    if profile == 'flat': slices = [(0, 1, base + .25)]
    elif profile == 'ramp': slices = [(i / 4, (i + 1) / 4, base + (i + 1) / 16) for i in range(4)]
    elif profile == 'stair': slices = [(i / 3, (i + 1) / 3, base + (i + 1) / 4) for i in range(3)]
    else: slices = [(0, .5, base), (.5, .75, base + .5), (.75, 1, base + .75)]
    boxes = []
    for z0, z1, top in slices:
        bottom = top - .16 if profile == 'flat' else base - .16
        boxes += [[0, bottom, z0, .055, top, z1], [.945, bottom, z0, 1, top, z1]]
        boxes += [[x - .0175, top - .09, z0, x + .0175, top, z1] for x in (.1875, .34375, .5, .65625, .8125)]
        boxes += [[.055, top - .035, z0, .945, top, z0 + .032], [.055, top - .035, z1 - .032, .945, top, z1]]
    return boxes


def rotated(b, facing):
    x0, y0, z0, x1, y1, z1 = b
    if facing == 'south': return b
    if facing == 'north': return [1 - x1, y0, 1 - z1, 1 - x0, y1, 1 - z0]
    if facing == 'east': return [z0, y0, 1 - x1, z1, y1, 1 - x0]
    return [1 - z1, y0, x0, 1 - z0, y1, x1]


def main(out):
    out = Path(out).resolve()
    if out.parent != BASE.resolve() or out.exists(): raise ValueError('Fresh private revision required')
    assets = out / 'assets/projectseele'
    for name in ('models/block', 'models/item', 'blockstates', 'textures/block'): (assets / name).mkdir(parents=True)
    variants, states = {}, {}
    for profile in ('flat', 'ramp', 'stair', 'transfer'):
        for level in range(4):
            name = f'tv_personnel_deck_r44_{profile}_{level}'; boxes = authored(profile, level)
            elements = []
            for box in boxes:
                elements.append({'from': [v * 16 for v in box[:3]], 'to': [v * 16 for v in box[3:]],
                                 'faces': {face: {'texture': '#metal', 'uv': [0, 0, 16, 16]} for face in ('down', 'up', 'north', 'south', 'east', 'west')}})
            (assets / 'models/block' / (name + '.json')).write_text(json.dumps({'ambientocclusion': False, 'textures': {'metal': 'projectseele:block/tv_personnel_grating_r44', 'particle': 'projectseele:block/tv_personnel_grating_r44'}, 'elements': elements}, separators=(',', ':')), 'utf8')
            for facing, angle in [('south', 0), ('north', 180), ('east', 270), ('west', 90)]:
                key = f'facing={facing},level={level},profile={profile}'
                variants[key] = {'model': 'projectseele:block/' + name, 'y': angle}
                states['projectseele:tv_personnel_deck_r44[' + key + ']'] = [rotated(q, facing) for q in boxes]
    (assets / 'blockstates/tv_personnel_deck_r44.json').write_text(json.dumps({'variants': variants}, separators=(',', ':')), 'utf8')
    (assets / 'models/item/tv_personnel_deck_r44.json').write_text(json.dumps({'parent': 'projectseele:block/tv_personnel_deck_r44_flat_3'}), 'utf8')
    image = Image.new('RGB', (128, 128), '#505d59'); draw = ImageDraw.Draw(image)
    for y in range(0, 128, 8):
        for x in range(0, 128, 8):
            draw.line((x + 1, y + 5, x + 5, y + 1), fill='#788580', width=1)
            draw.line((x + 2, y + 6, x + 6, y + 2), fill='#3b4744', width=1)
    image.save(assets / 'textures/block/tv_personnel_grating_r44.png')
    report = {'native_expected_authored_unions': states, 'source_java_sha256': hashlib.sha256((ROOT / 'src/main/java/com/projectseele/world/TvPersonnelDeckR44.java').read_bytes()).hexdigest(),
              'actual_native_export_verified': False, 'world_apply_allowed': False,
              'appearance': 'Real open steel grating bearing bars, crossbars and thin stepped side stringers. Collision is the same visible member union, not a hidden full plate or cube.',
              'ownership': 'Permanent authored world deck; support does not depend on loaded gantry entities.',
              'world_write_performed': False, 'native_passed': False}
    (out / 'asset_contract.json').write_text(json.dumps(report, indent=2), 'utf8')
    print(json.dumps({'states': len(states), 'models': 16, 'private_assets': str(assets), 'registration_pending': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); main(args.out)
