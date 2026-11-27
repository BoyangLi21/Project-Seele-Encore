"""Prepare the two registered tower extensions from the installed R66 cargo and private 100-owner skyline.

The explicit shaft columns were surveyed in the installed world. The stage writer verifies every
stone and dirt block against the new target world's actual preimage before changing either endpoint.
"""
import argparse
import gzip
import json
from pathlib import Path
import struct

import nbtlib
from city_body_sync import topology
from mca import World
from private_cleanup import DATA, control, state, unpack
from tokyo3_r66_design import AIR, FINS, GLASS, STONE, model
from tokyo3_r66_plan import mesh

CROWNS = {37: (104, 130), 43: (120, 153)}


def crowned(owner, height, original):
    # Keep the original occupied base, glazing rhythms and all block entities. The crown
    # steps in over its final seven storeys and has a screened, two-block rooftop plant.
    body = model(owner, height, 10, original)
    for x in range(-6, 7):
        for z in range(-6, 7):
            if abs(x) + abs(z) > 9:
                continue
            body[x, height + 1, z] = STONE
            if abs(x) == 6 or abs(z) == 6 or abs(x) + abs(z) == 9:
                body[x, height + 2, z] = FINS if (x + z) % 4 else GLASS
    return body


def generate(world, shell, out):
    out.mkdir(parents=True, exist_ok=True)
    ts = topology(world)
    geometry = World(world / DATA.parent / 'region')
    ledger = control(world)
    assert ledger['phase'] == 'IDLE'
    stats, proofs = {}, {}
    clearance = []
    with gzip.open(shell, 'rb') as source, (out / 'city_shells_r66.bin.gz').open('wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as far:
        header = source.read(6)
        assert struct.unpack('>IH', header) == (0x54333636, 100)
        far.write(header)
        for i, t in ts.items():
            frame = source.read(16)
            n, = struct.unpack('>I', source.read(4))
            encoded = source.read(n * struct.calcsize('>BhhhBBBBBB'))
            assert len(encoded) == n * 13
            assert struct.unpack('>8h', frame) == (*t['centre'], t['ret'], *t['fp'])
            stats[i] = dict(height=t['H'], centre=t['centre'], base=t['ret'], fp=t['fp'], changes=0, quads=n)
            if i not in CROWNS:
                far.write(frame + struct.pack('>I', n) + encoded)
                continue
            old, new = CROWNS[i]
            cx, cy, cz = t['centre']
            assert (cx, cy, cz) == (70 if i == 37 else 110, 80, 100)
            assert t['H'] == old and tuple(t['fp']) == (-10, 10, -10, 10)
            for j, peer in ts.items():
                if i == j:
                    continue
                px, _, pz = peer['centre']
                a, b, c, d = peer['fp']
                assert cx + 10 < px + a or cx - 10 > px + b or cz + 10 < pz + c or cz - 10 > pz + d
            recipe = nbtlib.load(world / DATA / 'city_rigid_generation_r45' / 'cargo' / f'{i}.dat')['data']['Buildings'][0]
            original = {unpack(row['Pos']): state(row['State']) for row in recipe['Cargo']}
            after = crowned(i, new, original)
            for row in recipe['Cargo']:
                if 'NBT' in row:
                    assert after[unpack(row['Pos'])] == state(row['State'])
            # Compare the complete owned swept volume. The only pre-existing obstructions
            # permitted are its own parked cargo, hatch at street grade and the stone/soil plug.
            base = cy if ledger['depth'] == 0 else t['ret']
            checked = 0
            for x in range(cx - 10, cx + 11):
                for z in range(cz - 10, cz + 11):
                    for y in range(t['ret'], cy + new + 4):
                        expected = original.get((x-cx, y-base, z-cz), AIR)
                        block = geometry.get(x, y, z)
                        if block is None:
                            raise ValueError(f'missing chunk at {x},{y},{z}')
                        if 42 <= y < 80:
                            expected = 'minecraft:dirt' if y in (77, 78) else 'minecraft:stone'
                            if geometry.block_entity(x, y, z) is not None:
                                raise ValueError(f'foreign shaft block entity at {x},{y},{z}')
                            clearance.append((x, y, z, expected, AIR))
                        if y == 80 and ledger['depth'] != 0:
                            continue  # the live journal validates the 441 registered hatch cells
                        if block != expected:
                            raise ValueError(f'unowned sweep obstruction {i} at {x},{y},{z}: {block}, expected {expected}')
                        checked += 1
            delta = [(p, original.get(p, AIR), after.get(p, AIR)) for p in sorted(original.keys() | after.keys()) if original.get(p) != after.get(p)]
            with gzip.open(out / f'{i}.tsv.gz', 'wt', encoding='utf8') as f:
                for (x, y, z), before, final in delta:
                    f.write(f'{x}\t{y}\t{z}\t{before}\t{final}\n')
            stats[i].update(changes=len(delta), quads=mesh(i, t, after, far))
            proofs[i] = dict(raised_top=cy + max(p[1] for p in after), lowered_top=t['ret'] + max(p[1] for p in after),
                             height_before=old, height_after=new, raised_base=cy, lower_base=t['ret'], travel=cy-t['ret'],
                             cargo_cells=len(after), delta_cells=len(delta), swept_positions=checked, other_footprint_intersections=0)
        assert not source.read(1)
    with gzip.open(out / 'streetscape.tsv.gz', 'wt', encoding='utf8') as f:
        for x, y, z, before, after in clearance:
            f.write(f'{x}\t{y}\t{z}\t{before}\t{after}\n')
    (out / 'owners.json').write_text(json.dumps(stats, indent=1), 'utf8')
    (out / 'crown-heights.tsv').write_text('37\t104\t130\n43\t120\t153\n', 'ascii')
    (out / 'sweep.json').write_text(json.dumps(proofs, indent=2), 'utf8')
    print(json.dumps(proofs))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('world', type=Path)
    parser.add_argument('installed_shell', type=Path)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    generate(args.world, args.installed_shell, args.out)
