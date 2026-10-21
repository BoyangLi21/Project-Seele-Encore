"""Prepare the exact HQ ceiling-remnant delta and exclude enclosure-cap routing.

The original R20 perimeter walls and R52 station translation establish purpose.
Only the three visually reviewed isolated concrete fragments may be removed;
the complete original walls, stair flights and train envelopes stay intact.
"""
import argparse,gzip,hashlib,json
from pathlib import Path
from query_blocks import read_box,iter_block_entities

DIM='projectseele:geofront'

def plan(frozen,review,output):
    evidence=json.loads(review.read_text('utf8'))
    assert evidence['decision']=='remove_three_isolated_ceiling_fragments_keep_glass_walls'
    assert evidence['station']=='original_hq_station'
    cells=read_box(frozen,DIM,(-7,-561,473),(74,-548,539))
    tags=dict(iter_block_entities(frozen,DIM,(-7,-561,473),(74,-548,539)))
    positions={(x,-551,506) for start in (-5,11,43) for x in range(start,start+4)}
    assert positions=={tuple(p) for p in evidence['fragments']}
    for p in positions:
        assert cells[p]=='minecraft:gray_concrete' and p not in tags
        for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
            q=(p[0]+dx,p[1]+dy,p[2]+dz)
            assert q in positions or cells[q]=='minecraft:air',('Fragment no longer isolated',q,cells[q])
    nav=json.loads(gzip.decompress((frozen/'nerv_routes_r24.json.gz').read_bytes()))
    nodes=[]
    for i,(row,active) in enumerate(zip(nav['nodes'],nav['node_active'])):
        x,y,z=row[:3]
        if not active or not(39<=x<=53 and y==-556 and z in (475,505,507,537)):continue
        floor=cells[x,y-1,z]
        if floor.partition('[')[0].endswith('_stairs'):continue
        assert floor=='minecraft:light_gray_stained_glass'
        witnesses=[dict(pos=(x,y-d,z),state=cells[x,y-d,z]) for d in (1,2)]
        assert all(r['state']=='minecraft:light_gray_stained_glass' for r in witnesses)
        nodes.append(dict(node=i,position=(x,y,z),witnesses=witnesses))
    assert len(nodes)==60
    rows=[dict(pos=p,before=cells[p],after='minecraft:air',before_nbt=None,after_nbt=None,
               reason='visually_reviewed_isolated_HQ_ceiling_remnant') for p in sorted(positions)]
    inverse=[dict(r,before=r['after'],after=r['before']) for r in rows]
    output.mkdir(parents=True,exist_ok=False)
    for name,data in [('EXACT_DELTA.json.gz',rows),('INVERSE_DELTA.json.gz',inverse),
                      ('POSITIVE_EDIT_MASK.json.gz',[r['pos'] for r in rows])]:
        (output/name).write_bytes(gzip.compress(json.dumps(data).encode(),mtime=0))
    exclusions=dict(purpose='HQ station perimeter glass is enclosure, not pedestrian floor',
                    source='tools/build_transit_civil_r20.py:station/perimeter_wall',
                    frame='R52 original HQ translation Y-93; perimeter glass at platform Y+2..3',nodes=nodes)
    (output/'EXCLUDED_NODES.json').write_text(json.dumps(exclusions,indent=2),'utf8')
    (output/'PLAN.json').write_text(json.dumps(dict(frozen=str(frozen),review_sha256=hashlib.sha256(review.read_bytes()).hexdigest(),
        changed_cells=12,excluded_navigation_nodes=60,retained_stairs=True,retained_glass_walls=True,world_written=False),indent=2),'utf8')
    print('Prepared 12 exact ceiling cells and 60 declared wall-cap nodes; world unchanged')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--frozen',type=Path,required=True)
    p.add_argument('--review',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    plan(a.frozen,a.review,a.output)
