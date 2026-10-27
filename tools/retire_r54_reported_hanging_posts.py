"""Remove the two hanging armor strips identified by the owner on 2026-10-27."""
import argparse
import json
from pathlib import Path
import regional_voxels as vox
from query_blocks import read_box, iter_block_entities
from finish_r53_launch_armor import protected_cells


def run(world, output, apply):
    dimension = "projectseele:geofront"
    protected = protected_cells(world)
    rows = []
    for z in (60, 108):
        lo, hi = (40, -979, z), (40, -958, z)
        tags = dict(iter_block_entities(world, dimension, lo, hi))
        for point, state in read_box(world, dimension, lo, hi).items():
            if state == "minecraft:air":
                continue
            if not state.startswith("projectseele:nerv_launch_armor[") or point in protected or point in tags:
                raise ValueError(("Unexpected member at owner-reported strip", point, state))
            rows.append(dict(pos=point, old=state, new="minecraft:air"))
    output.mkdir(parents=True, exist_ok=False)
    (output / "delta.json").write_text(json.dumps(rows, indent=2), encoding="utf8")
    if apply and rows:
        vox.WORLD, vox.DIM, vox.OUT = world, dimension, output
        painter = vox.Painter(vertical_bounds=(-1440, 320))
        for row in rows:
            painter.exact((*row["pos"], *row["pos"]), row["old"], row["new"], "owner_reported_hanging_strip")
        painter.apply("remove_hanging_strips")
    print(dict(changed=len(rows), applied=apply, header_and_barrier_wall_retained=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("world", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    run(args.world, args.output, args.apply)
