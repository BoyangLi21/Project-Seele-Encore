"""Read exact block states out of a saved world box.

Measurement helper for coordinate-specific repairs on a frozen save: no
world writing, no semantic guessing, just "what block is actually at these
coordinates".  Prints full states (name plus properties) so a repair can be
authored against the real palette instead of an assumed one.

Usage:
    python tools/query_blocks.py <world> --dim projectseele:geofront \
        --box x0 y0 z0 x1 y1 z1 [--mode list|census|slice]

Modes:
    list    every non-air cell in the box (default; capped)
    census  counts per block state
    slice   per-y ASCII plan of the box using single-character legend
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from inspect_map_assets import (  # noqa: E402
    decode_modern_section,
    iter_chunks,
    palette_state,
)

AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}

def chunk_statuses(world: Path, dimension: str, selected):
    """Metadata preflight without decoding voxel palettes or altering chunks."""
    wanted=set(map(tuple,selected))
    if not wanted:return {}
    bounds=(min(x for x,z in wanted),max(x for x,z in wanted),min(z for x,z in wanted),max(z for x,z in wanted))
    result={p:'missing' for p in wanted}
    for cx,cz,chunk in iter_chunks(dimension_dir(world,dimension),bounds,wanted):
        result[cx,cz]=str(chunk.get('Status','')).removeprefix('minecraft:')
    return result

def iter_matching_sections(world: Path, dimension: str, prefixes, stats=None):
    """Full-save palette prefilter; decode only sections containing requested blocks."""
    import numpy as np
    prefixes=tuple(prefixes);stats={} if stats is None else stats
    stats.update(chunks_read=0,full_chunks=0,unfinished_chunks=0,matching_sections=0,complete=False)
    for cx,cz,chunk in iter_chunks(dimension_dir(world,dimension),(-1875000,1875000,-1875000,1875000)):
        stats['chunks_read']+=1
        if str(chunk.get('Status','')).removeprefix('minecraft:')!='full':stats['unfinished_chunks']+=1;continue
        stats['full_chunks']+=1
        for section in chunk.get('sections',[]):
            candidates=section.get('block_states',{}).get('palette',[])
            if not any(str(entry.get('Name','')).startswith(prefixes) for entry in candidates):continue
            palette,indices=decode_modern_section(section)
            if not palette:continue
            stats['matching_sections']+=1
            yield cx,cz,int(section.get('Y',0)),tuple(palette_state(entry) for entry in palette),np.asarray(indices,dtype=np.int32)
    stats['complete']=True


def iter_selected_sections(world: Path, dimension: str,
                           selected: dict[tuple[int, int], set[int]], *, skip_unfinished: bool = False):
    """Read exact requested sections as palette/index arrays for large measured patches.

    Coordinates are chunk X/Z and section Y. Decoding remains centralized here;
    callers receive the same complete state strings as read_box, without a
    Python dictionary entry for every air voxel. Only FULL chunks are accepted.
    """
    import numpy as np
    if not selected:
        return
    bounds=(min(x for x,z in selected),max(x for x,z in selected),
            min(z for x,z in selected),max(z for x,z in selected))
    for cx,cz,chunk in iter_chunks(dimension_dir(world,dimension),bounds,selected):
        wanted=selected.get((cx,cz))
        if not wanted:continue
        if str(chunk.get('Status','')).removeprefix('minecraft:')!='full':
            if skip_unfinished:continue
            raise RuntimeError(f'Unfinished chunk {(cx,cz)}')
        for section in chunk.get('sections',[]):
            sy=int(section.get('Y',0))
            if sy not in wanted:continue
            palette,indices=decode_modern_section(section)
            if not palette:continue
            yield cx,cz,sy,tuple(palette_state(entry) for entry in palette),np.asarray(indices,dtype=np.int32)


def dimension_dir(world: Path, dimension: str) -> Path:
    if dimension in ("minecraft:overworld", "overworld"):
        return world
    namespace, path = dimension.split(":", 1)
    if namespace == "minecraft":
        return world / "DIM-1" if path == "the_nether" else world / "DIM1"
    return world / "dimensions" / namespace / path


def read_box(world: Path, dimension: str,
             lo: tuple[int, int, int], hi: tuple[int, int, int],
             namespace: str | None = None,
             ) -> dict[tuple[int, int, int], str]:
    return dict(iter_box_cells(world, dimension, lo, hi, namespace))


def iter_box_cells(world: Path, dimension: str,
                   lo: tuple[int, int, int], hi: tuple[int, int, int],
                   namespace: str | None = None, *,
                   step: tuple[int, int, int] = (1, 1, 1),
                   include_air: bool = True, full_chunks_only: bool = False):
    """Yield measured cells; optional strides sample from lo, never interpolate."""
    if any(value < 1 for value in step):
        raise ValueError("Sampling steps must be positive")
    root = dimension_dir(world, dimension)
    bounds = (lo[0] >> 4, hi[0] >> 4, lo[2] >> 4, hi[2] >> 4)
    for chunk_x, chunk_z, chunk in iter_chunks(root, bounds):
        if full_chunks_only and str(chunk.get('Status', '')).removeprefix('minecraft:') != 'full':
            continue
        base_x, base_z = chunk_x * 16, chunk_z * 16
        for section in chunk.get("sections", []):
            section_y = int(section.get("Y", 0))
            base_y = section_y * 16
            if base_y > hi[1] or base_y + 15 < lo[1]:
                continue
            palette, indices = decode_modern_section(section)
            if not palette:
                continue
            names = [palette_state(entry) for entry in palette]
            accepted = None if namespace is None else {
                index for index, state in enumerate(names)
                if state.startswith(namespace + ":")
            }
            if accepted is not None and not accepted:
                continue
            if not include_air and all(name in AIR for name in names):
                continue
            starts = tuple(max(a, b) + (a - max(a, b)) % stride
                           for a, b, stride in zip(lo, (base_x, base_y, base_z), step))
            for y in range(starts[1], min(hi[1], base_y + 15) + 1, step[1]):
                for z in range(starts[2], min(hi[2], base_z + 15) + 1, step[2]):
                    for x in range(starts[0], min(hi[0], base_x + 15) + 1, step[0]):
                        offset = ((y - base_y) << 8) | ((z - base_z) << 4) | (x - base_x)
                        index = indices[offset]
                        if accepted is not None and index not in accepted:
                            continue
                        state = names[index]
                        if include_air or state not in AIR:
                            yield (x, y, z), state


def iter_block_entities(world: Path, dimension: str,
                        lo: tuple[int, int, int], hi: tuple[int, int, int], *, selected_chunks=None):
    """Yield exact block-entity NBT entries inside a loaded world box."""
    root = dimension_dir(world, dimension)
    bounds = (lo[0] >> 4, hi[0] >> 4, lo[2] >> 4, hi[2] >> 4)
    for _chunk_x, _chunk_z, chunk in iter_chunks(root, bounds, selected_chunks):
        for entry in chunk.get("block_entities", []):
            if not all(key in entry for key in ("x", "y", "z")):
                continue
            x, y, z = int(entry["x"]), int(entry["y"]), int(entry["z"])
            if (lo[0] <= x <= hi[0] and lo[1] <= y <= hi[1]
                    and lo[2] <= z <= hi[2]):
                yield (x, y, z), entry


def iter_selected_biome_sections(world: Path, dimension: str, selected):
    """Yield exact FULL-chunk biome section NBT; quart codecs stay native.

    The R44 native registry/PalettedContainer encoder supplies intended quart
    changes. This read entry point deliberately does not decode biome packing.
    """
    if not selected:
        return
    bounds = (min(x for x, z in selected), max(x for x, z in selected),
              min(z for x, z in selected), max(z for x, z in selected))
    for cx, cz, chunk in iter_chunks(dimension_dir(world, dimension), bounds, selected):
        if str(chunk.get('Status', '')).removeprefix('minecraft:') != 'full':
            raise RuntimeError(f'Unfinished biome chunk {(cx, cz)}')
        for section in chunk.get('sections', []):
            sy = int(section.get('Y', 0))
            if sy in selected[cx, cz] and 'biomes' in section:
                yield cx, cz, sy, section['biomes'].copy()


def short(state: str) -> str:
    return state.split("[", 1)[0].replace("minecraft:", "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("world", type=Path)
    parser.add_argument("--dim", default="projectseele:geofront")
    parser.add_argument("--box", type=int, nargs=6, required=True,
                        metavar=("X0", "Y0", "Z0", "X1", "Y1", "Z1"))
    parser.add_argument("--mode", default="list",
                        choices=("list", "census", "slice"))
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument("--air", action="store_true",
                        help="include air cells in list mode")
    parser.add_argument("--namespace",
                        help="only report states in this namespace (for example: create)")
    args = parser.parse_args()

    x0, y0, z0, x1, y1, z1 = args.box
    lo = (min(x0, x1), min(y0, y1), min(z0, z1))
    hi = (max(x0, x1), max(y0, y1), max(z0, z1))
    cells = read_box(args.world, args.dim, lo, hi, args.namespace)

    if args.mode == "census":
        counter = Counter(cells.values())
        total = (hi[0] - lo[0] + 1) * (hi[1] - lo[1] + 1) * (hi[2] - lo[2] + 1)
        missing = total - len(cells)
        if missing:
            print(f"  (unloaded/absent cells: {missing})")
        for state, count in counter.most_common():
            print(f"{count:8d}  {state}")
        return

    if args.mode == "slice":
        legend: dict[str, str] = {}
        alphabet = "#=+*oxXO%&$@ABCDEFGHJKLMNPQRSTUVWYZ"
        for y in range(lo[1], hi[1] + 1):
            print(f"--- y={y}  (x {lo[0]}..{hi[0]} left->right, "
                  f"z {lo[2]}..{hi[2]} top->bottom) ---")
            for z in range(lo[2], hi[2] + 1):
                row = []
                for x in range(lo[0], hi[0] + 1):
                    state = cells.get((x, y, z))
                    if state is None:
                        row.append("?")
                    elif state in AIR:
                        row.append(".")
                    else:
                        key = short(state)
                        if key not in legend:
                            legend[key] = alphabet[
                                len(legend) % len(alphabet)]
                        row.append(legend[key])
                print(f"  z={z:5d} " + "".join(row))
        print("legend: " + ", ".join(
            f"{char}={name}" for name, char in sorted(
                legend.items(), key=lambda item: item[1])))
        return

    shown = 0
    for position in sorted(cells, key=lambda p: (p[1], p[2], p[0])):
        state = cells[position]
        if not args.air and state in AIR:
            continue
        print(f"  {position[0]:5d} {position[1]:5d} {position[2]:5d}  {state}")
        shown += 1
        if shown >= args.limit:
            print(f"  ... capped at {args.limit}")
            break
    if shown == 0:
        print("  (no matching cells)")


if __name__ == "__main__":
    main()
