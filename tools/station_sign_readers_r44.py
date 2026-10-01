"""Read real board lettering from a standing eye through measured native shapes.

The panel anchor is not the complete panel. Sample the actual lettering span,
including its top and lower lines, rather than accepting a centre ray alone.
This is a conservative geometry check; text legibility still needs native art.
"""
import math

NORMAL = {'north': (0, -1), 'south': (0, 1), 'west': (-1, 0), 'east': (1, 0)}


def reader_visibility(state_at, shape_for, anchor, face, reader, *, direction, compact=False, route_map=False):
    nx, nz = NORMAL[face]
    eye = (reader[0] + .5, reader[1] + 1.62, reader[2] + .5)
    # StationDepartureBoardRenderer: route header Y1.78; last footer Y.47.
    heights = (.30, .52, .78) if compact else (.54, 1.10, 1.70) if route_map else (.73, 1.19, 1.70) if direction else (.54, .80, 1.06)
    plane = -.27 if compact else .205
    half_width = .34 if compact else 1.18
    failures = []
    for across in (-half_width, 0., half_width):
        for height in heights:
            target = (anchor[0] + .5 + nx*plane + nz*across,
                      anchor[1] + height,
                      anchor[2] + .5 + nz*plane - nx*across)
            count = max(2, math.ceil(math.dist(eye, target) * 20))
            for i in range(count + 1):
                point = tuple(eye[j] + (target[j] - eye[j])*i/count for j in range(3))
                cell = tuple(map(math.floor, point))
                if cell == tuple(anchor):
                    continue
                sources=[cell]
                # A neighbouring three-metre board may project into this air
                # voxel. Query its real anchor instead of treating the voxel
                # containing the ray point as the only possible shape owner.
                for dx,dz in ((-1,0),(0,0),(1,0),(0,-1),(0,1)):
                    for dy in (0,-1):
                        source=(cell[0]+dx,cell[1]+dy,cell[2]+dz)
                        value=state_at(source)
                        if source!=cell and value and value.startswith('projectseele:station_departure_board['):
                            sources.append(source)
                blocked=None
                for source in sources:
                    if source==tuple(anchor):continue
                    state=state_at(source);boxes=shape_for(state)
                    if boxes is None or any(all(source[j]+b[j]+.001 < point[j] < source[j]+b[j+3]-.001
                                                for j in range(3)) for b in boxes):
                        blocked={'target':target,'blocked_at':cell,'shape_owner':source,'state':state};break
                if blocked:
                    failures.append(blocked);break
    return {'clear': not failures, 'rays': 9, 'failures': failures}
