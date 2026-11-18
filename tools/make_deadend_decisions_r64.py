"""Per-end decisions for the R64 dead-end round from classify_deadends_r64 output and plan_dead_end_options.

  接通     connect: a route at MAX_GRADE or less, earthwork EARTH per block or less, no bridge, into a piece of
           TARGET_MIN declared cells or more (a smaller target only moves the dead end).
  拆除碎片 a piece of road joined to nothing, smaller than TARGET_MIN, that no good route joins: all of it goes.
  截回     a spur of SHORT blocks or less to the next junction: taken up back to the junction.
  待定     a longer spur with no good route: judged one by one (a longer link, a place at the end, or a cut).
  保留 / 不改  kept ends (rule keep) and stray specks / network-only height steps.
Ends inside a --skip box (handled by another plan) are left out. --override id=decision[:x,z] sets one end
(截回 with x,z stops the cut at that point instead of the junction).
usage: make_deadend_decisions_r64.py <r64.json> <options.json> <network.npz> <out.json> [--skip x0,z0,x1,z1] [--override ...]"""
import json
import math
import sys
from collections import Counter

import numpy as np
from scipy import ndimage

MAX_GRADE, EARTH, TARGET_MIN, SHORT = 0.07, 4.0, 2000, 60


def main():
    a = sys.argv[1:]
    skips, overrides = [], {}
    while '--skip' in a:
        k = a.index('--skip')
        skips.append(tuple(map(int, a[k + 1].split(','))))
        del a[k:k + 2]
    while '--override' in a:
        k = a.index('--override')
        i, v = a[k + 1].split('=', 1)
        overrides[int(i)] = v
        del a[k:k + 2]
    ends = json.load(open(a[0], encoding='utf8'))['ends']
    opts = {o['id']: o for o in json.load(open(a[1], encoding='utf8'))}
    net = np.load(a[2])
    ax, az = map(int, net['bounds'][:2])
    pieces, _ = ndimage.label(net['road'] | net['walk'], structure=np.ones((3, 3)))
    sizes = np.bincount(pieces.ravel())

    def piece_size(x, z):
        best = 0
        for dx in range(-3, 4):
            for dz in range(-3, 4):
                iz, ix = z + dz - az, x + dx - ax
                if 0 <= iz < pieces.shape[0] and 0 <= ix < pieces.shape[1] and pieces[iz, ix]:
                    best = max(best, int(sizes[pieces[iz, ix]]))
        return best

    out = []
    for e in ends:
        i, x, z = e['id'], e['x'], e['z']
        d = dict(id=i, x=x, z=z, feet=e['feet'], rule=e['rule'], rule_note=e['rule_note'], spur=e['spur'], piece=e['comp_cells'])
        if any(x0 <= x <= x1 and z0 <= z <= z1 for x0, z0, x1, z1 in skips):
            d.update(decision='另案', why='inside a box handled by its own plan')
            out.append(d)
            continue
        if e['rule'] == 'keep':
            d.update(decision='保留', why=e['rule_note'])
            out.append(d)
            continue
        if e['rule'] == 'speck':
            d.update(decision='不改', why=f"stray paving, {e['rule_note']}: not a road")
            out.append(d)
            continue
        o = opts.get(i, {})
        c = o.get('connect') or {}
        why = None
        if c and 'route' in c:
            grade = abs(c['to_feet'] - e['feet']) / max(c['length'], 1)
            target = piece_size(*c['to'])
            d['connect'] = dict(to=c['to'], length=c['length'], grade=round(grade, 3), earth=c['earthwork_per_block'], target_piece=target,
                                bridge=c['bridge'])
            if grade <= MAX_GRADE and c['earthwork_per_block'] <= EARTH and not c['bridge'] and target >= TARGET_MIN:
                d.update(decision='接通', why=f"route {c['length']:.0f} blocks, grade {grade * 100:.1f}%, into a piece of {target} cells")
            else:
                why = (f"route refused: grade {grade * 100:.1f}%" if grade > MAX_GRADE else
                       f"route refused: earthwork {c['earthwork_per_block']:.1f}/block" if c['earthwork_per_block'] > EARTH else
                       'route refused: needs a bridge' if c['bridge'] else f'route refused: target piece only {target} cells')
        elif c:
            why = f"no route: {c.get('infeasible', 'none')}"
        else:
            why = 'no road within reach'
        if 'decision' not in d:
            if e['to'] == 'isolated' and e['comp_cells'] < TARGET_MIN:
                d.update(decision='拆除碎片', why=f"isolated piece of {e['comp_cells']} cells; {why}")
            elif e['rule'] == 'height':
                d.update(decision='待定', why=f"{e['rule_note']}; {why}")
            elif e['spur'] <= SHORT:
                d.update(decision='截回', why=f"spur of {e['spur']} blocks back to the junction; {why}")
            else:
                d.update(decision='待定', why=f"spur of {e['spur']} blocks; {why}")
        if i in overrides:
            v = overrides[i]
            dec, _, at = v.partition(':')
            d.update(decision=dec, why=f'set by hand: {v}')
            if at:
                d['stop_xz'] = list(map(int, at.split(',')))
        out.append(d)
    json.dump(out, open(a[3], 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    print(json.dumps(dict(Counter(d['decision'] for d in out)), ensure_ascii=False))


if __name__ == '__main__':
    main()
