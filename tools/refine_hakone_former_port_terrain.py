"""Daylight the retained station road after relocating the port, offline."""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
from scipy.ndimage import distance_transform_edt
from author_hakone_lakefront import Editor
from map_pipeline.launch_earthworks import ground
from map_pipeline.launch_protection import load,check_candidate
from map_pipeline.corridors import compile_street
from plan_ashi_landscape_r54 import NATURAL,SOIL,PLANTS
from query_blocks import AIR
from hakone_earthworks import road_blocks


def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')


def run(a):
    if a.out.exists():raise ValueError('New candidate required')
    def copy(src,dst):
        if Path(src).parent.name=='source':os.link(src,dst);return dst
        return shutil.copy2(src,dst)
    shutil.copytree(a.source,a.out,copy_function=copy)
    e=Editor(a.out);bounds=[1200,256,1663,639];x,z,X,Z=bounds;shape=(Z-z+1,X-x+1)
    with np.load(a.authority/'network.npz')as f:
        bx,bz,bX,bZ=map(int,f['bounds']);area=np.s_[z-bz:Z-bz+1,x-bx:X-bx+1]
        existing=dict(bounds=np.asarray(bounds),**{k:f[k][area]for k in ('walk','road','grade2')})
    old=ground(e,bounds);hy,_=road_blocks(existing['grade2'])
    # Only the formerly occupied port earthwork receives this additional cut.
    # Retained roads and station members keep their exact current cells.
    zz,xx=np.mgrid[z:Z+1,x:X+1]
    foot=(xx>=1234)&(xx<=1238)&(zz>=432)&(zz<=451)
    seed=(existing['walk']&(xx>=1224)&(xx<=1277)&(zz>=410)&(zz<=451))|foot
    hy[foot]=68
    distance,near=distance_transform_edt(~seed,return_indices=True)
    base=(hy-1)[tuple(near)]
    target=np.minimum(old,np.floor(base+distance*.75)).astype(np.int16)
    target[(xx<1224)|(xx>1536)|(zz<312)|(zz>600)]=old[(xx<1224)|(xx>1536)|(zz<312)|(zz>600)]
    station=[1124,32,452,1244,110,492];report=json.loads((a.out/'manifest.json').read_text('utf8'));guard=load(Path(report['world']));masks={};count=0
    for j,i in np.argwhere(target!=old):
        px,pz=int(i+x),int(j+z);h=int(target[j,i]);g=int(old[j,i]);r=e.region(px,pz);idx=r['index'][px//16,pz//16]
        ys=np.arange(h-3,g+1);v=r['after'][idx,ys+128,pz%16,px%16]
        eligible=np.array([r['names'][code].split('[')[0]in NATURAL for code in v])
        if station[0]<=px<=station[3]and station[2]<=pz<=station[5]:eligible&=~((ys>=station[1])&(ys<=station[4]))
        if existing['walk'][j,i]:eligible&=~((ys>=hy[j,i]-4)&(ys<=hy[j,i]+8))
        names=['minecraft:air','minecraft:grass_block[snowy=false]','minecraft:dirt','minecraft:stone'];codes=[]
        for s in names:
            if s not in r['ids']:r['ids'][s]=len(r['names']);r['names'].append(s)
            codes.append(r['ids'][s])
        values=np.where(ys>h,codes[0],np.where(ys==h,codes[1],np.where(ys>=h-2,codes[2],codes[3]))).astype(np.uint16)
        change=eligible&(v!=values);key=px//16,pz//16
        if key not in masks:masks[key]=guard.chunk_mask(*key)
        if np.any(change&masks[key][ys+128,pz%16,px%16]):raise ValueError('Earthwork enters a mechanism')
        r['after'][idx,ys[change]+128,pz%16,px%16]=values[change];count+=int(change.sum())
    e.save();e.regions.clear()
    # Public access ends beside the existing station floor; no station member
    # is replaced by a new road or generated from a template.
    from verify_hakone_network_candidate import PAVEMENT
    cells={}
    for j,i in np.argwhere(foot&~existing['walk']):
        px,pz=int(i+x),int(j+z)
        for py in range(min(int(target[j,i]),67)-1,72):
            prior=e.state(px,py,pz)
            if prior.split('[')[0]not in NATURAL|PAVEMENT:raise ValueError(('Retained station approach obstruction',px,py,pz,prior))
            state='minecraft:stone'if py<68 else'minecraft:smooth_stone'if py==68 else'minecraft:air'
            if prior!=state:cells[px,py,pz]=state;e.put(px,py,pz,state)
    for px in range(1234,1239):
        if e.state(px,68,452).split('[')[0]not in PAVEMENT or any(e.state(px,k,452).split('[')[0]not in AIR for k in (69,70,71)):
            raise ValueError(('Station entrance must retain a traversable original contact',px))
    result=dict(id='retained-inland-station-approach',status='prepared',walk_columns=int(foot.sum()),changed_cells=len(cells),entrance_contacts=5)
    field=dict(bounds=bounds,old=old,target=target,active=target!=old,walk=foot,road=np.zeros(shape,bool),grade2=np.full(shape,136,np.int16),clearance=3)
    e.save();e.regions.clear();np.savez_compressed(a.out/'earthworks/retained-inland-station-approach.npz',**field)
    np.savez_compressed(a.out/'plan/former-port-earthworks.npz',bounds=bounds,old=old,target=target,active=target!=old)
    write(a.out/'former-port-restoration.json',dict(daylight_cut_cells=count,station_approach=result,station_volume_preserved=station,world_written=False))
    report['regions']=e.save();report['cells']=sum(r['cells']for r in report['regions']);write(a.out/'manifest.json',report)
    write(a.out/'launch-protection.json',check_candidate(guard,a.out))
    print('Former port hillside and station approach prepared',count,len(cells),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','out','authority'):p.add_argument('--'+name,type=Path,required=True)
    run(p.parse_args())
