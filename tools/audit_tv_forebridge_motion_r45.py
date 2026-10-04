"""Bounded candidate geometry audit; no world/occupancy/art acceptance."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
from audit_tv_cage_space_r44 import motion


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--asset',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();assert not a.out.exists()
    d=json.loads(a.asset.read_text('utf8'));failures=[];checks=0;contacts=[]
    for variant in range(3):
        cs=[c for c in d['components'] if c.get('variant',variant)==variant]
        movers=[c for c in cs if c['part'].startswith('front_stage_')]
        others=[c for c in cs if c['part'].startswith(('front_stage_','front_receiver_','platform_'))]
        for c in movers:
            first=np.array(d['collision_parts'][c['part']])
            for other in others:
                if other['part']==c['part']:continue
                if other in movers and other['part']<c['part']:continue
                second=np.array(d['collision_parts'][other['part']])
                raw=[]
                for phase in np.linspace(0,1,121):
                    x=first+motion(c,float(phase));y=second+motion(other,float(phase))
                    gap=np.minimum(x[:,None,1],y[None,:,1])-np.maximum(x[:,None,0],y[None,:,0])
                    hit=np.argwhere(np.all(gap>1e-6,axis=2));checks+=1
                    if len(hit):raw.append({'phase':float(phase),'pairs':hit.tolist(),
                                           'max_overlap_m':float(np.min(gap[hit[:,0],hit[:,1]],axis=1).max())})
                if raw:failures.append({'variant':variant,'parts':[c['part'],other['part']],'samples':raw})
        for side in ('l','r'):
            name='front_stage_0_'+side
            boxes=np.array(d['collision_parts'][name])
            centre_roof=boxes[np.argmax(boxes[:,1,1])]
            contacts.append({'variant':variant,'part':name,'centre_roof':centre_roof.tolist()})
    result={'asset_sha256':hashlib.sha256(a.asset.read_bytes()).hexdigest(),
            'phase_pair_checks':checks,'intersecting_part_pairs':len(failures),'findings':failures,
            'centre_roofs':contacts,'limit':'121 simultaneous poses, authored collision solids only; continuous clearance, skin, world, routes and guards remain unverified',
            'native_passed':False,'art_passed':False,'world_write':False}
    a.out.mkdir(parents=True);(a.out/'audit.json').write_text(json.dumps(result,indent=2),'utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('findings','centre_roofs')}))


if __name__=='__main__':main()
