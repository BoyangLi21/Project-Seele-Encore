"""Remove only the measured retired-shaft plug below the current TV roof."""
from pathlib import Path
import argparse
import regional_voxels as vox


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument('world', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    vox.WORLD, vox.OUT, vox.DIM = args.world, args.output, 'projectseele:geofront'
    p = vox.Painter(vertical_bounds=(-1344,320))
    p.exact((126,-36,269,134,-35,277), 'projectseele:geofront_skyweave',
            'minecraft:air', 'retired_public_lift_wrong_roof_datum')
    p.exact((126,-34,269,134,24,277), 'minecraft:stone',
            'minecraft:air', 'retired_public_lift_wrong_roof_datum')
    p.meta.update(measured_old={'minecraft:stone':4779,'projectseele:geofront_skyweave':162},
        authority='Public surface lift retired by user; current TvWorldPreviewTerrain roof=24',
        preserves='Roof cover begins at 25; public lift now terminates at GeoFront lakeside')
    p.apply('correct_retired_roof_datum')


if __name__ == '__main__':
    main()
