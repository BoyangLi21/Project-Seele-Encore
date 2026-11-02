"""Verify installed-ready bank voxels and the complete touched water perimeter."""
import argparse,json
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import PLANTS
from query_blocks import AIR


def verify(a):
    e=Editor(a.candidate);tiles={};errors=[];retained=json.loads((a.candidate/'retained-foundations.json').read_text())
    by_region={}
    for row in retained:by_region.setdefault((row[0]//512,row[2]//512),[]).append(row)
    for path in sorted(a.survey.glob('r.*.npz')):
        rx,rz=map(int,path.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        wet=np.zeros((512,512),bool);open_face=wet.copy();full=wet.copy()
        fluid=np.array([s.split('[')[0]=='minecraft:water'for s in r['names']])
        passable=np.array([s.split('[')[0]in AIR|PLANTS for s in r['names']])
        for q,v in zip(r['coords'],r['after']):
            cx,cz=map(int,q);ar=np.s_[cz%32*16:cz%32*16+16,cx%32*16:cx%32*16+16]
            wet[ar]=fluid[v[190]];open_face[ar]=passable[v[190]];full[ar]=True
        for x,y,z,state in by_region.get((rx,rz),[]):
            if e.state(x,y,z)!=state:errors.append(['retained foundation',x,y,z])
        tiles[rx,rz]=(wet,open_face,full);e.regions.clear()
    faces=0
    for (rx,rz),(wet,opened,known)in tiles.items():
        for axis in(0,1):
            low=[slice(None),slice(None)];high=low.copy();low[axis]=slice(None,-1);high[axis]=slice(1,None)
            low=tuple(low);high=tuple(high)
            hit=known[low]&known[high]&((wet[low]&opened[high])|(wet[high]&opened[low]))
            faces+=int(hit.sum())
            for j,i in np.argwhere(hit)[:5]:errors.append(['open water face',rx*512+int(i),62,rz*512+int(j),axis])
        for dx,dz in((1,0),(0,1)):
            if(rx+dx,rz+dz)not in tiles:continue
            other,air,full=tiles[rx+dx,rz+dz]
            left=np.s_[:,-1]if dx else np.s_[-1,:];right=np.s_[:,0]if dx else np.s_[0,:]
            hit=known[left]&full[right]&((wet[left]&air[right])|(other[right]&opened[left]))
            faces+=int(hit.sum())
            if hit.any():errors.append(['cross-region water faces',rx,rz,dx,dz,int(hit.sum())])
    report=dict(errors=errors,exposed_Y62_water_faces=faces,regions=len(tiles),retained_foundation_cells=len(retained),
        source='candidate voxel states; all known neighboring water-face columns',visual_acceptance=False)
    (a.candidate/'water-bank-check.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report),flush=True)
    if errors:raise ValueError('Unclosed bank geometry')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in('candidate','survey'):p.add_argument('--'+k,type=Path,required=True)
    verify(p.parse_args())
