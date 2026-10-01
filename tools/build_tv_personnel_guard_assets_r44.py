"""Private visible fifty-millimetre guard members; exact native union required."""
from pathlib import Path
import argparse, hashlib, json
from build_tv_personnel_deck_assets_r44 import rotated

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/rebuild_r44/hangar_machinery'


def members(drop):
    b = -drop / 4
    return [[0, b - .25, 0, .055, b + 1.375, .055], [.945, b - .25, 0, 1, b + 1.375, .055],
            [0, b + .64, .0025, 1, b + .69, .0525], [0, b + 1.325, .0025, 1, b + 1.375, .0525]]


def main(out):
    out = Path(out).resolve()
    if out.parent != BASE.resolve() or out.exists(): raise ValueError('Fresh private revision required')
    assets = out / 'assets/projectseele'; (assets / 'models/block').mkdir(parents=True); (assets / 'blockstates').mkdir()
    multipart = []; expected = {}
    for drop in range(4):
        name = f'tv_personnel_guard_r44_{drop}'
        elements = [{'from': [x * 16 for x in q[:3]], 'to': [x * 16 for x in q[3:]],
                     'faces': {f: {'texture': '#metal', 'uv': [0, 0, 16, 16]} for f in ('down', 'up', 'north', 'south', 'east', 'west')}} for q in members(drop)]
        (assets / 'models/block' / (name + '.json')).write_text(json.dumps({'ambientocclusion': False, 'textures': {'metal': 'projectseele:block/tv_personnel_grating_r44', 'particle': 'projectseele:block/tv_personnel_grating_r44'}, 'elements': elements}, separators=(',', ':')), 'utf8')
        for side, angle in [('north', 0), ('east', 90), ('south', 180), ('west', 270)]:
            multipart.append({'when': {'drop': str(drop), side: 'true'}, 'apply': {'model': 'projectseele:block/' + name, 'y': angle}})
    for mask in range(16):
        for drop in range(4):
            boxes = []
            for i, side in enumerate(('north', 'east', 'south', 'west')):
                if mask & (1 << i):
                    # The deck rotation helper's base is south; this guard's
                    # authored base is north, so rotate by the opposite face.
                    face = {'north': 'south', 'east': 'west', 'south': 'north', 'west': 'east'}[side]
                    boxes += [rotated(q, face) for q in members(drop)]
            props = {'drop': str(drop), **{s: str(bool(mask & (1 << i))).lower() for i, s in enumerate(('north', 'east', 'south', 'west'))}}
            key = 'projectseele:tv_personnel_guard_r44[' + ','.join(k + '=' + props[k] for k in sorted(props)) + ']'; expected[key] = boxes
    (assets / 'blockstates/tv_personnel_guard_r44.json').write_text(json.dumps({'multipart': multipart}, separators=(',', ':')), 'utf8')
    (out / 'asset_contract.json').write_text(json.dumps({'native_expected_authored_unions': expected,
        'source_java_sha256': hashlib.sha256((ROOT / 'src/main/java/com/projectseele/world/TvPersonnelGuardR44.java').read_bytes()).hexdigest(),
        'native_verified': False, 'world_apply_allowed': False, 'clear_width_policy': 'Guard planes mounted in the neighbouring bearing lip, outside the two metre deck; exact corners/entrance still checked.'}, indent=2), 'utf8')
    print(json.dumps({'models': 4, 'states': 64, 'private_assets': str(assets)}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--out', required=True, type=Path); args = p.parse_args(); main(args.out)
