"""Measured pyramid ownership, independent of later excavation or world writes.

The public surface lift is a separate component even where it intersects the
lower pyramid. Its upper column must stay at its original absolute position.
"""
from pathlib import Path
import hashlib, json
import numpy as np
from r52_spatial_plan import BASE, PYRAMID


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    survey = BASE/'survey'
    source = survey/'headquarters_and_original_station.npz'
    data = np.load(source)
    states, origin, palette = data['states'], data['origin'], data['palette']
    yy, zz, xx = np.ogrid[:states.shape[0], :states.shape[1], :states.shape[2]]
    y, z, x = yy+origin[1], zz+origin[2], xx+origin[0]
    radius = np.minimum(120, np.ceil((-292-y)*120/174))
    owned = np.broadcast_to((y >= -470) & (y <= -292) &
                             (np.maximum(abs(x-30), abs(z-327)) <= radius+1), states.shape).copy()
    public_lift = np.broadcast_to((x >= 126) & (x <= 134) & (z >= 269) & (z <= 277), states.shape)
    owned &= ~public_lift
    # Original beacon is a complete fixture above the shell tip, not a remnant.
    owned |= np.broadcast_to((x == 30) & (z == 327) & (y == -291), states.shape)
    window_ids = [i for i, s in enumerate(palette) if s.startswith('projectseele:one_way_glass[') and 'pyramid=true' in s]
    window_mask = np.isin(states, window_ids)
    assert np.count_nonzero(window_mask) == 2344
    assert np.all(owned[window_mask]), 'Original glazing left outside component'
    devices = json.loads((survey/'headquarters_and_original_station_devices.json').read_text('utf8'))

    def owns(point):
        px, py, pz = map(int, np.floor(point))
        ix, iy, iz = px-origin[0], py-origin[1], pz-origin[2]
        return 0 <= iy < states.shape[0] and 0 <= iz < states.shape[1] and 0 <= ix < states.shape[2] and bool(owned[iy, iz, ix])

    moving_devices = [dict(row, destination=PYRAMID.block(row['pos'])) for row in devices if owns(row['pos'])]
    artwork = [r for r in moving_devices if r['id'] == 'projectseele:wall_artwork']
    assert len(artwork) == 4
    assert any(r['id'] == 'minecraft:beacon' for r in moving_devices)
    all_actors = json.loads((survey/'ORIGINAL_ALL_ACTORS.json').read_text('utf8'))
    actors = [dict(row, destination=PYRAMID.point(row['pos'])) for row in all_actors['actors'] if owns(row['pos'])]
    out = BASE/'pyramid_component'
    out.mkdir(exist_ok=True)
    np.savez_compressed(out/'owner_mask.npz', origin=origin, owned=owned)
    (out/'devices_and_actors.json').write_text(json.dumps(dict(devices=moving_devices, actors=actors), ensure_ascii=False), 'utf8')
    report = dict(status='measured source component; NOT applied', source=str(source), source_sha256=digest(source),
                  source_cells=int(owned.sum()), source_nonair_cells=int(np.count_nonzero(owned & ~np.isin(states,
                    [i for i,s in enumerate(palette) if s in {'minecraft:air','minecraft:cave_air','minecraft:void_air'}]))),
                  protected_public_lift_cells=int(np.count_nonzero(public_lift)),
                  original_glazing=2344, preserved_artwork=artwork, devices=len(moving_devices), actors=len(actors),
                  shift_y=-93, actors_keep_uuid=True, world_written=False,
                  next_required=['resolve cross-component elevator/controller references',
                                 'move complete old Terminal component before pyramid destination occupation',
                                 'apply paired source removal/target insertion with typed NBT and actor identities',
                                 'build only explicit floor-loop and entrance connections',
                                 'native elevator/entrance/artwork and whole exterior review'])
    (out/'COMPONENT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2), 'utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'preserved_artwork','next_required'}},ensure_ascii=False))


if __name__ == '__main__':
    main()
