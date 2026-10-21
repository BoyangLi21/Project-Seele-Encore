"""Guard the observed west-facing twelve-step stair, keeping its three lanes."""
import argparse
import gzip
import json
import math
from pathlib import Path
from query_blocks import read_box, iter_block_entities
from repair_r53_long_stair_guard import install, rail_gaps
from repair_r53_reported_landings import DIM
from prepare_school_hakone_native_r45 import ActualGeometry


def plan(frozen, output):
    lo, hi = (14, -436, 304), (30, -419, 310)
    cells = read_box(frozen, DIM, lo, hi)
    tags = dict(iter_block_entities(frozen, DIM, lo, hi))
    tread = 'minecraft:quartz_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]'
    rows, gaps = [], []
    for z in (306, 308):
        run = []
        for step in range(12):
            x, y = 27-step, -434+step
            assert all(cells[x, y, lane] == tread for lane in (306, 307, 308))
            pos = (x, y+1, z)
            assert cells[pos] == 'minecraft:air' and pos not in tags, (pos, cells[pos])
            new = f'projectseele:personnel_stair_guard_r53[facing=west,left={str(z==308).lower()}]'
            rows.append(dict(pos=pos, before=cells[pos], after=new,
                             before_nbt=None, after_nbt=None,
                             reason='observed_unguarded_upper_white_stair_edge'))
            run.append((pos, new))
        gaps.extend(rail_gaps(run))
    assert len(rows) == 24 and not gaps
    proposed = dict(cells)
    proposed.update((tuple(row['pos']),row['after']) for row in rows)
    class View:
        world = frozen
        def get(self,x,y,z):
            return proposed.get((math.floor(x),math.floor(y),math.floor(z)))
        def block(self,pos):
            return self.get(*pos)
    geometry = ActualGeometry(View())
    samples = []
    for step in range(12):
        for offset in (.36,.5,1.5,2.5,2.64):
            point = (27-step+.3,-433+step,306+offset)
            status = geometry.clear(point)
            assert status == 'CLEAR', (point,status,geometry.unknown)
            samples.append(dict(point=point,status=status))
    output.mkdir(parents=True, exist_ok=False)
    (output/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(), mtime=0))
    (output/'FULL_WIDTH_CLEARANCE.json').write_text(json.dumps(samples,indent=2),'utf8')
    (output/'PLAN.json').write_text(json.dumps(dict(
        frozen=str(frozen), changed_cells=len(rows), before_missing_guards=len(rows),
        proposed_rail_gaps=gaps, tread_width=3, edge_strip_width=.055,
        source='Observed existing stair X16..27, Y-434..-423, Z306..308; map_4.png',
        bounds=[lo,hi], world_written=False), indent=2), 'utf8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--frozen', type=Path)
    parser.add_argument('--world', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    install(args.world,args.output) if args.apply else plan(args.frozen,args.output)
