"""Check the changed assembly against frozen shaft and road observations."""
import argparse,json
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import SOIL


def verify(a):
    f=np.load(a.roads/'classification.npz');v=f['points'];retain=f['retain']
    e=Editor(a.candidate);manifest=json.loads((a.candidate/'manifest.json').read_text('utf8'))
    boxes=manifest['preserved_launch_boxes'];errors=[];checked=0;newly_buried=[];preserved=0
    regions={(int(p[0])//512,int(p[2])//512)for p in v[retain]}
    regions|={tuple(map(int,Path(r['path']).stem.split('.')[1:]))for r in manifest['regions']}
    for rx,rz in sorted(regions):
        r=e.region(rx*512,rz*512);soil=np.array([s.split('[')[0]in SOIL for s in r['names']])
        rows=np.flatnonzero((v[:,0]//512==rx)&(v[:,2]//512==rz))
        p=v[rows];ci=np.array([r['index'][int(x)//16,int(z)//16]for x,_,z in p[:,:3]],dtype=np.int64)
        for dy in(1,2,3):
            iy=p[:,1]+128+dy;valid=iy<448;iy=np.minimum(iy,447)
            after=soil[r['after'][ci,iy,p[:,2]%16,p[:,0]%16]]&valid
            before=soil[r['before'][ci,iy,p[:,2]%16,p[:,0]%16]]&valid
            errors.extend([['retained-road-soil',*map(int,q[:3]),dy]for q in p[after&retain[rows]]])
            newly_buried.extend([list(map(int,q[:3]))+[dy]for q in p[after&~before&~retain[rows]]])
        checked+=int(retain[rows].sum())
        for (cx,cz),before,after in zip(r['coords'],r['before'],r['after']):
            zz,xx=np.mgrid[int(cz)*16:int(cz)*16+16,int(cx)*16:int(cx)*16+16];yy=np.arange(-128,320)[:,None,None]
            for x,y,z,X,Y,Z in boxes:
                if x>xx.max()or X<xx.min()or z>zz.max()or Z<zz.min():continue
                protected=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)&(yy>=y)&(yy<=Y)
                if np.any(protected&(before!=after)):errors.append(['changed-launch-volume',int(cx),int(cz)])
                preserved+=int(protected.sum())
        e.regions.clear()
    report=dict(road_layers_checked=checked,unchanged_launch_volume_cells=preserved,new_soil_above_unclassified_paving=newly_buried,errors=errors)
    (a.roads/'verification.json').write_text(json.dumps(report,indent=2),'utf8')
    check=json.loads((a.candidate/'functional-check.json').read_text('utf8'));check['errors']+=errors;check['launch_and_retained_road_check']={k:v for k,v in report.items()if k not in('errors','new_soil_above_unclassified_paving')}
    (a.candidate/'functional-check.json').write_text(json.dumps(check,indent=2),'utf8')
    print({k:len(v)if isinstance(v,list)else v for k,v in report.items()},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--roads',type=Path,required=True)
    verify(p.parse_args())
