"""Immutable review: every moving primitive's continuous sweep vs new fixed mesh."""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
from audit_tv_cage_space_r44 import motion
from build_tv_shoulder_shells_r44 import box_vertices
from author_tv_shoulder_installation_r44 import prism_hits_triangle

CHANGED={'platform_r','platform_l','platform_2_r','fixed_support_2_r','staff_deck_bearings_l','staff_deck_bearings_r'}

def main(asset,out):
    asset,out=Path(asset),Path(out)
    if out.exists():raise ValueError('Fresh output required')
    d=json.loads(asset.read_text('utf8')); rows=[]; checks=[]
    for v in range(3):
        fixed=[c for c in d['components'] if c['part'] in CHANGED and c.get('variant',v)==v]
        for f in fixed:
            tri=np.array(d['parts'][f['part']]).reshape(-1,3,d.get('stride',6))[:,:,:3]
            lo,hi=tri.min(1),tri.max(1)
            for c in d['components']:
                if c['motion']=='fixed' or c.get('variant',v)!=v:continue
                local=np.array(d['collision_parts'][c['part']]); broad_pairs=0
                for first,last in zip(np.linspace(0,1,121)[:-1],np.linspace(0,1,121)[1:]):
                    start=local+motion(c,float(first));end=local+motion(c,float(last))
                    sweeps=np.stack((np.minimum(start[:,0],end[:,0]),np.maximum(start[:,1],end[:,1])),axis=1)
                    for i,b in enumerate(sweeps):
                        ids=np.flatnonzero(np.all((hi>b[0]+1e-7)&(lo<b[1]-1e-7),axis=1));broad_pairs+=len(ids)
                        hits=[int(j) for j in ids if prism_hits_triangle(box_vertices(b),tri[j],0.)]
                        if hits:rows.append({'variant':v,'fixed_part':f['part'],'moving_part':c['part'],'interval':[float(first),float(last)],'moving_box':i,'swept_bound':b.tolist(),'triangles':hits})
                checks.append({'variant':v,'fixed_part':f['part'],'moving_part':c['part'],'intervals':120,'actual_fixed_triangles':len(tri),'broad_triangle_pairs':broad_pairs})
    out.mkdir(parents=True)
    report={'asset_sha256':hashlib.sha256(asset.read_bytes()).hexdigest(),'checks':checks,'findings':rows,
            'continuous_proof':'Each source motion coordinate is monotone. Each moving physical primitive stays inside its endpoint union over each interval; SAT uses actual fixed render triangles. Zero intersections proves continuous clearance. Positive swept bounds are conservative and require exact refinement.',
            'engineering_continuous_clear':not rows,'native_passed':False,'art_passed':False,'world_write':False}
    (out/'contract.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({'checks':len(checks),'findings':len(rows),'first':rows[:1]}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--asset',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.asset,a.out)
