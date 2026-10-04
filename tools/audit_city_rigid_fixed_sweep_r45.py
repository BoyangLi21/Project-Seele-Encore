"""Read-only rigid vertical sweep against persisted fixed dome anchors.

Reports known solid cube intersections separately from shapes requiring native
inspection. Never removes anchors, changes cargo or proposes a guessed shaft.
"""
from pathlib import Path
import json
import hashlib
import nbtlib
from measure_city_placements_r45 import unpack_pos

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'artifacts/rebuild_r45/city_motion/create_probe_v2/preflight.json'
OUT=ROOT/'artifacts/rebuild_r45/city_motion/rigid_fixed_anchor_sweep.json'
KNOWN_FULL={
    'minecraft:iron_block','minecraft:smooth_stone','minecraft:stone_bricks',
    'minecraft:polished_deepslate','minecraft:gray_concrete',
    'minecraft:light_gray_concrete','minecraft:white_concrete',
    'minecraft:black_concrete','minecraft:light_blue_concrete',
    'minecraft:cyan_concrete','minecraft:green_concrete',
    'minecraft:light_gray_terracotta','minecraft:gray_terracotta',
    'minecraft:sea_lantern','minecraft:glass',
}


def main():
    preflight=json.loads(INPUT.read_text('utf8'));records=[]
    for row in preflight['records']:
        path=Path(row['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
        building=nbtlib.load(path)['data']['Buildings'][0]
        cx,cy,cz=row['center'];delta=-61-row['height']
        corner_cells={}
        for cell in building['Cargo']:
            x,y,z=unpack_pos(int(cell['Pos']))
            corner_cells.setdefault((x,z),[]).append((y,cell))
        intersections=[]
        for absolute in building['NegativeDomeAnchorMask']:
            ax,ay,az=unpack_pos(int(absolute))
            for local_y,cell in corner_cells.get((ax-cx,az-cz),[]):
                translation=ay-cy-local_y
                if delta<=translation<=0:
                    name=str(cell['State']['Name'])
                    if name=='minecraft:air':continue
                    intersections.append(dict(anchor=[ax,ay,az],cargo_local=[ax-cx,local_y,az-cz],
                        cargo_state=cell['State'].unpack(),at_delta_y=translation,
                        known_full_cube=name in KNOWN_FULL))
        records.append(dict(index=row['index'],archive_sha256=row['sha256'],height=row['height'],
            source_base_y=80,target_base_y=19-row['height'],target_delta_y=delta,
            fixed_anchor_count=len(building['NegativeDomeAnchorMask']),
            intersecting_cargo_anchor_pairs=len(intersections),
            known_full_cube_pairs=sum(x['known_full_cube'] for x in intersections),
            first_failure=min(intersections,key=lambda x:abs(x['at_delta_y'])) if intersections else None,
            intersections=intersections))
    report=dict(schema='projectseele.city-rigid-fixed-anchor-sweep-r45.v1',world_id=preflight['world_id'],
        world_written=False,cargo_written=False,anchor_written=False,native_shapes=False,
        denominator_towers=len(records),towers_with_known_solid_collision=sum(r['known_full_cube_pairs']>0 for r in records),
        towers_with_any_nonair_intersection=sum(r['intersecting_cargo_anchor_pairs']>0 for r in records),
        known_full_cube_pairs=sum(r['known_full_cube_pairs'] for r in records),
        nonair_intersection_pairs=sum(r['intersecting_cargo_anchor_pairs'] for r in records),
        conclusion='Current persisted dome corner anchors lie inside true rigid vertical cargo swept volume. Preserve the anchors/cargo; Root must resolve the measured mechanical path before production.',records=records)
    OUT.write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='records'},indent=2))


if __name__=='__main__':main()
