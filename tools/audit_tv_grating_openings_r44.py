"""Exact empty aperture rectangles in all64 actual native grating projections."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np

def audit(state,raw):
    boxes=np.array(raw).reshape(-1,2,3);rect=boxes[:,:,[0,2]]
    xs=np.unique(np.r_[0.,1.,rect[:,:,0].ravel()]);zs=np.unique(np.r_[0.,1.,rect[:,:,1].ravel()])
    xs=xs[(xs>=0)&(xs<=1)];zs=zs[(zs>=0)&(zs<=1)]
    holes=[]
    for i in range(len(xs)-1):
        for j in range(i+1,len(xs)):
            for k in range(len(zs)-1):
                for m in range(k+1,len(zs)):
                    low=np.array([xs[i],zs[k]]);high=np.array([xs[j],zs[m]])
                    if not np.any(np.all((rect[:,1]>low+1e-8)&(rect[:,0]<high-1e-8),axis=1)):
                        holes.append((float(min(high-low)),float(max(high-low)),low.tolist(),high.tolist()))
    largest=max(holes,default=(0.,0.,[],[]))
    return {'state':state,'actual_members':len(boxes),'maximum_aperture_minimum_axis_m':largest[0],
            'corresponding_long_axis_m':largest[1],'aperture_xz':[largest[2],largest[3]],
            'whole0_6m_axis_aligned_footprint_fits_aperture':largest[0]>=.6-1e-8}

def main(native,out):
    native,out=Path(native),Path(out)
    if out.exists():raise ValueError('Fresh epoch required')
    d=json.loads(native.read_text('utf8'));rows=[audit(s,b) for s,b in d.items() if s.startswith('projectseele:tv_personnel_deck_r44[')]
    if len(rows)!=64:raise ValueError(('Incomplete native64',len(rows)))
    out.mkdir(parents=True)
    r={'native_shapes_sha256':hashlib.sha256(native.read_bytes()).hexdigest(),'states':rows,
       'max_slot_narrow_axis_m':max(q['maximum_aperture_minimum_axis_m'] for q in rows),
       'whole_footprint_fallthrough_possible':any(q['whole0_6m_axis_aligned_footprint_fits_aperture'] for q in rows),
       'proof':'Exhaustive maximum axis-aligned empty rectangles partitioned at every native member boundary, using the actual64 collision projections. World-aligned Minecraft body width0.6m cannot fit through an opening whose smaller axis is below0.6m. No collision slab is invented.',
       'limitations':['Vertical contact transitions/step-up and neighbour datum require native walking and stationary landing tests; not a biomechanical shoe simulation.'],
       'native_landing_passed':False,'world_write':False}
    (out/'contract.json').write_text(json.dumps(r,indent=2),'utf8');print(json.dumps({k:v for k,v in r.items() if k!='states'}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.native,a.out)
