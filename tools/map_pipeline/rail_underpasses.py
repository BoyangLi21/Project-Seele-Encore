"""Finite ground-road exceptions below a retained elevated railway.

Only original air/soil and the declared former road surface are editable.
Bridge members, foundations, native devices and the track envelope stay owned.
"""
import numpy as np
from hakone_earthworks import road_blocks
from plan_ashi_landscape_r54 import SOIL, PLANTS
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT


def editable_underpass_column(editor, x, z, low, high, boxes, old_walk, old_grade):
    mask = np.zeros(high - low + 1, bool)
    for a, b, c, A, B, C in boxes:
        if not (a <= x <= A and c <= z <= C):
            continue
        # The legacy retained train guard extends thirty blocks below rail
        # and seven above. An exception must end below the real deck guard.
        if B > high - 11:
            raise ValueError(('Underpass enters railway deck or clearance', x, z, B, high))
        floor, slab = road_blocks(old_grade)
        for y in range(max(low, b), min(high, B) + 1):
            state = editor.state(x, y, z, original=True)
            bare = state.split('[')[0]
            old_surface = old_walk and y == int(floor) and bare in PAVEMENT and ('type=bottom' in state) == bool(slab)
            if bare in AIR | SOIL | PLANTS | {'minecraft:light'} or old_surface:
                mask[y - low] = True
    return mask
