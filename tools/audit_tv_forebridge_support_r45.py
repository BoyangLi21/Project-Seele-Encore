"""Check full player footprints across the proposed closed mechanical deck.

This is candidate-space geometry, not live walking or an occupancy contract.
Opening under people remains prohibited; actual guards/routes are separate.
"""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
from audit_tv_personnel_whole_standing_r44 import uncovered,intersects


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--asset',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();assert not a.out.exists()
    d=json.loads(a.asset.read_text('utf8'));records=[];failures=[]
    for v in range(3):
        boxes=[];owners=[];support=[];slots=[]
        for c in d['components']:
            if c.get('variant',v)!=v or c['part'].startswith('thin_side_rails'):continue
            source=d['collision_parts'].get(c['part'],[])
            boxes.extend(source);owners.extend([c['part']]*len(source))
            for b in d['personnel_forebridge_r45']['standing_surface_boxes'].get(c['part'],[]):
                assert b in source,'Support must be a real authored collision solid'
                support.append(b)
            slots.extend(d['personnel_forebridge_r45']['roof_running_slots'].get(c['part'],[]))
        boxes=np.asarray(boxes)
        support=np.asarray(support);slots=np.asarray(slots)
        assert np.max(slots[:,1,2]-slots[:,0,2])<=.054001
        for lane in (-.5,0.,.5):
            right=12.0
            points=[[-12.+lane,-15.5],[-12.+lane,-18.45+lane],
                    [right+lane,-18.45+lane],[right+lane,-15.5]]
            if v==2:
                # EVA02's retained lift leaves a narrower green work face.
                # Its actual portal is reached via the fixed front landing;
                # do not aim an invented route through the lift lane.
                points=[[-12.+lane,-15.5],[-12.+lane,-18.45+lane],
                        [11.50,-18.45+lane],[11.50,-16.89],
                        [9.70+lane*.25,-16.89],[9.70+lane*.25,-15.50]]
            last_y=None
            for segment,(first,last) in enumerate(zip(points,points[1:])):
                count=int(np.ceil(np.linalg.norm(np.array(last)-first)/.05))+1
                for step in range(count):
                    x,z=np.array(first)+(np.array(last)-first)*step/(count-1)
                    close=(support[:,1,0]>x-.3)&(support[:,0,0]<x+.3)&(support[:,1,2]>z-.3)&(support[:,0,2]<z+.3)
                    floor=support[close&(support[:,1,1]>=48.9)&(support[:,1,1]<50.9)]
                    if not len(floor):
                        failures.append({'variant':v,'lane':lane,'xz':[x,z],'reason':'NO_FLOOR'});continue
                    y=float(floor[:,1,1].max())
                    body=np.array([[x-.3,y,z-.3],[x+.3,y+1.8,z+.3]])
                    hits=np.flatnonzero(intersects(boxes,body))
                    missing=uncovered(np.array([[x-.3,z-.3],[x+.3,z+.3]]),floor[floor[:,1,1]>=y-.6])
                    under=slots[(slots[:,1,1]>=y-.6)&(slots[:,1,1]<=y+.001)]
                    unexplained=uncovered(np.array([[x-.3,z-.3],[x+.3,z+.3]]),np.concatenate((floor[floor[:,1,1]>=y-.6],under)))
                    delta=0 if last_y is None else y-last_y
                    row={'variant':v,'lane':lane,'segment':segment,'position':[x,y,z],
                         'uncovered_footprint_m2':missing,'step_delta_m':delta,
                         'unexplained_support_gap_m2':unexplained,
                         'visible_running_slots_max_width_m':.054,
                         'head_body_collisions':sorted({owners[int(i)]for i in hits})}
                    records.append(row)
                    if unexplained>1e-7 or missing>.36*.30 or len(hits) or abs(delta)>.60:failures.append(row)
                    last_y=y
    a.out.mkdir(parents=True)
    result={'asset_sha256':hashlib.sha256(a.asset.read_bytes()).hexdigest(),'samples':len(records),
            'failures':failures,'records':records,'native_passed':False,'world_write':False,
            'remaining':['World approach and exact installed grating/doors','Edge protection',
             'Complete operator occupancy and safe egress through prepare','Actual entry, return, reload, visual review']}
    (a.out/'audit.json').write_text(json.dumps(result,separators=(',',':')),'utf8')
    print(json.dumps({'samples':len(records),'failures':len(failures),'first':failures[:2]}))


if __name__=='__main__':main()
