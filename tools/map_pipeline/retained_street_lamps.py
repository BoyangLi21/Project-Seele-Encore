"""Reseat complete captured lamps along the composed, walkable road shoulder."""
import numpy as np
from scipy.ndimage import distance_transform_edt
from query_blocks import AIR
from plan_ashi_landscape_r54 import SOIL, PLANTS


def reseat(editor, network, spec, details, protected):
    x, z, X, Z = map(int, network['bounds'])
    distance = distance_transform_edt(~network['walk'])
    choices = np.argwhere((distance >= 3) & (distance <= 7) & ~network['plots'] & ~network['wet'])
    empty = AIR | PLANTS | {'minecraft:light'}
    moved = []
    for payload in spec.get('retained_road_lamp_payloads', []):
        ox, oy, oz = payload['base']
        offsets = [(np.asarray(row['pos']) - [ox, oy, oz], row['state']) for row in payload['members']]
        # Each member must still agree with the current captured baseline.
        for row in payload['members']:
            if editor.state(*row['pos'], original=True) != row['state']:
                raise ValueError(('Changed captured road lamp', row['pos']))
        costs = (choices[:, 1] + x - ox) ** 2 + (choices[:, 0] + z - oz) ** 2
        for k in np.argsort(costs):
            j, i = map(int, choices[k]); px, pz = i + x, j + z
            if costs[k] > 180 ** 2:
                raise ValueError(('No local shoulder for complete lamp', payload['base']))
            if any(np.hypot(px-q[0], pz-q[2]) < 24 for q in details['lights']):
                continue
            h = int(network['ground'][j, i])
            cells = [(tuple(map(int, offset + [px, h, pz])), state) for offset, state in offsets]
            footing = [(px, y, pz) for y in range(h-2, h+1)]
            if any(protected(p) or editor.state(*p).split('[')[0] not in SOIL for p in footing+[(px,h-3,pz)]):
                continue
            if any(not(x <= p[0] <= X and z <= p[2] <= Z) or protected(p)
                   or editor.state(*p).split('[')[0] not in empty for p, _ in cells):
                continue
            if any(network['walk'][p[2]-z, p[0]-x] for p, _ in cells):
                continue
            for p in footing:
                editor.put(*p, 'minecraft:polished_andesite')
            for p, state in cells:
                editor.put(*p, state)
            row = dict(before=payload['base'], after=[px,h,pz],
                       members=[dict(pos=list(p), state=s) for p,s in cells], footing=[list(p) for p in footing])
            moved.append(row); details['lights'].append([px,h+1,pz])
            break
        else:
            raise ValueError(('No available shoulder for complete lamp', payload['base']))
    details['retained_lamps'] = moved


def verify(editor, details):
    errors = []
    for row in details.get('retained_lamps', []):
        for member in row['members']:
            if editor.state(*member['pos']) != member['state']:
                errors.append(['retained lamp member', member['pos']])
        for pos in row['footing']:
            if editor.state(*pos) != 'minecraft:polished_andesite':
                errors.append(['retained lamp footing', pos])
        px, h, pz = row['after']
        if editor.state(px,h-3,pz).split('[')[0] not in SOIL:
            errors.append(['retained lamp ground bearing', row['after']])
    return errors
