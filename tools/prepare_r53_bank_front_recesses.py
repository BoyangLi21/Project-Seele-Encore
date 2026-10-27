"""Recess declared horizontal bank beams for the intact original deck.

This prepares exact forward/inverse cells only. It neither writes a world nor
changes the original rail, door, route, actor or task. No digest report is made.
"""
import argparse
import json
from pathlib import Path

import numpy as np


def clip(polygon, axis, plane, above):
    if not polygon:
        return []
    result = []
    previous = polygon[-1]
    old = (previous[axis] - plane) * (1 if above else -1)
    for current in polygon:
        value = (current[axis] - plane) * (1 if above else -1)
        if (old >= 0) != (value >= 0):
            result.append(previous + (current - previous) * old / (old - value))
        if value >= 0:
            result.append(current)
        previous, old = current, value
    return result


def deck_sections(carrier):
    deck = np.asarray(carrier['parts']['deck']).reshape(-1, 3, 8)[:, :, :3].copy()
    # The declared bank-to-bank motion is translation along Z at Y=-1030,
    # yaw180. Every local Z of this source crosses each front during that leg.
    deck[:, :, 0] *= -1
    deck[:, :, 0] += .5
    deck[:, :, 1] -= 1030
    sections = {}
    for y in (-1035, -1034):
        columns = []
        for x in range(-15, 16):
            for face in deck:
                polygon = list(face)
                for axis, plane, above in ((0, x, True), (0, x + 1, False),
                                           (1, y, True), (1, y + 1, False)):
                    polygon = clip(polygon, axis, plane, above)
                if polygon:
                    columns.append(x)
                    break
        sections[y] = columns
    assert sections[-1035] == [-11, -10, -9, -8, 8, 9, 10, 11, 12]
    assert sections[-1034] == list(range(-12, 14))
    return sections


def prepare(world, carrier, measured, plan, output, complete=False):
    assert plan['world_written'] and plan['full_component_exact_readback']
    assert plan['source'] == 'frozen original bank geometry'
    assert plan['bank_centres_z'] == [124.5, 76.5, 28.5]
    assert plan['foot_y'] == -646 and plan['centre_spacing'] == 48
    assert plan['chamber_depth'] == 37 and plan['connector_length'] == 11
    sections = deck_sections(carrier)
    rows = []
    allowed = {'projectseele:nerv_machine_edge', 'projectseele:nerv_structural_panel'}
    if complete:
        assert len(measured)==3 and {m['unit'] for m in measured}=={0,1,2}
    else:
        assert {(m['unit'], m['bank']) for m in measured} == {(u, b) for u in range(3) for b in (2, 3)}
    for interface in measured:
        unit, bank = interface['unit'], interface.get('bank', 0)
        centre, front = 72 - 42 * unit, 188 - 48 * bank
        cells = {tuple(row[:3]): row[3] for row in interface['cells']}
        # Original routes plus their full unchanged deck footprint occupy this
        # declared bank/connector band. The incline refit already covers Z>=109.
        zs = range(13,109) if complete else (front,front+1)
        changed = set()
        for y, columns in sections.items():
            for x in columns:
                for z in zs:
                    at = centre + x, y, z
                    before = cells[at]
                    if before == 'minecraft:air':
                        continue
                    assert before in allowed, ('Preserve unknown material', at, before)
                    changed.add(at)
                    rows.append(dict(pos=list(at), before=before, after='minecraft:air',
                                     before_nbt=None, after_nbt=None,
                                     purpose=f'unit{unit}/horizontal_bank_beam_deck_recess'))
        # The continuous original lower beam carries the side frames. The
        # central running-rail seats remain at -1035; only its outer grooves
        # reach the next layer. No personnel surface at -1030 is edited.
        for x, y, z in changed:
            bottom = y - 1
            while (x, bottom, z) in changed:
                bottom -= 1
            assert bottom >= -1036 and cells[x, bottom, z] in allowed
        assert all((centre + x, -1035, z) not in changed
                   for x in range(-7, 8) for z in zs)
    assert rows and len({tuple(r['pos']) for r in rows}) == len(rows)
    output.mkdir(parents=True, exist_ok=False)
    def write(name, value):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf8')
    rows.sort(key=lambda r: r['pos'])
    write('forwardPatch.json', rows)
    write('inversePatch.json', [dict(r, before=r['after'], after=r['before']) for r in rows])
    write('positiveEditMask.json', [r['pos'] for r in rows])
    write('installation_manifest.json', dict(world=str(world.resolve()), static_cells=len(rows),
          world_written=False, world_tables=[], metadata_preconditions=[],
          class_prefixes=[], resources=[], progress_changes=[],
          equipment_scope='Original three-channel horizontal bank/connector equipment band; retained 48m bank pitch',
          retained=['Original lower continuous beam at Y<=-1036',
                    'Original central running rail seats at Y=-1035 and relative X=-7..7',
                    'Original side columns, personnel floor, gates, rail meshes and native sockets'],
          sections={str(y): xs for y, xs in sections.items()}, changed_z=sorted({r['pos'][2] for r in rows}), complete_horizontal_band=complete))
    print(json.dumps(dict(candidate=str(output.resolve()), cells=len(rows), world_written=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('world', 'carrier', 'measured', 'bank-plan', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--complete-horizontal-band', action='store_true')
    args = parser.parse_args()
    read = lambda path: json.loads(path.read_text('utf8'))
    prepare(args.world, read(args.carrier), read(args.measured), read(args.bank_plan), args.output, args.complete_horizontal_band)
