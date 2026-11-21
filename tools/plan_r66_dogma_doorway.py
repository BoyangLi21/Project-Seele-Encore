"""The EVA doorway in the hangar hall's east wall that leads to the Central Dogma main shaft (ROADMAP 5.2a).

The hall lies wholly inside the 32-block launch route reservations, so the writer refuses any cell there. The doorway
is the one approved exception (project review, 2026-11-22): write_deep_cells --dogma-hall-doorway admits a row inside
the reservation only when it lies in DOOR and opens it (block to air), and never on a mechanical cell (rail anchor,
door layer, receiver seat). The EVA lanes run at x -11.5, 30.5 and 72.5 (each 17 wide, so x <= 81): the doorway at
x 94-95 is 13 blocks east of the nearest.
"""
DOOR = dict(x=(94, 95), y=(-1051, -989), z=(230, 254))     # 2 thick, 63 tall, 25 wide


def in_doorway(x, y, z):
    return DOOR['x'][0] <= x <= DOOR['x'][1] and DOOR['y'][0] <= y <= DOOR['y'][1] and DOOR['z'][0] <= z <= DOOR['z'][1]
