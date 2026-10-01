"""Exact negative control for sleeve walls passing through apron casting."""
from pathlib import Path
import argparse,json,hashlib,numpy as np
from audit_tv_cage_space_r44 import motion
from build_tv_shoulder_shells_r44 import box_vertices
from author_tv_shoulder_installation_r44 import prism_hits_triangle

def main(asset,out):
    asset,out=Path(asset),Path(out)
    if out.exists():raise ValueError('Fresh proof output required')
    d=json.loads(asset.read_text('utf8'));rows=[]
    for variant in range(3):
        for side in ('l','r'):
            name='platform_2_r' if variant==2 and side=='r' else 'platform_'+side
            tri=np.array(d['parts'][name]).reshape(-1,3,6)[:,:,:3];lo,hi=tri.min(1),tri.max(1)
            for component in d['components']:
                if not component['part'].startswith('front_stage') or component['part'][-1]!=side:continue
                for opened in (0.,1.):
                    hits=[]
                    for box in np.array(d['collision_parts'][component['part']])+motion(component,opened):
                        mask=np.all((hi>=box[0])&(lo<=box[1]),axis=1)
                        hits.extend(int(i) for i in np.flatnonzero(mask) if prism_hits_triangle(box_vertices(box),tri[i],0.))
                    if hits:rows.append({'variant':variant,'fixed_part':name,'moving_part':component['part'],'opening':opened,'actual_triangle_intersections':len(set(hits))})
    out.mkdir(parents=True);r={'source_sha256':hashlib.sha256(asset.read_bytes()).hexdigest(),'actual_render_triangle_hits':rows,'native_passed':False,'world_write':False}
    (out/'contract.json').write_text(json.dumps(r,indent=2),'utf8');print(json.dumps({'findings':len(rows),'first':rows[:2]}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--asset',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.asset,a.out)
