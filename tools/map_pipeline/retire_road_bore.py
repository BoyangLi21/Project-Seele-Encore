"""Restore the exterior of a specifically surveyed superseded road bore.

Only the supplied plan footprint and vertical reconstruction interval confer
ownership. The current geographical field supplies the restored surface; it
does not authorize removal of any facility, device or launch volume.
"""
import argparse,gzip,json,os,shutil,struct
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from map_pipeline.launch_earthworks import ground
from map_pipeline.launch_protection import load,check_candidate
from plan_ashi_landscape_r54 import SOIL,PLANTS
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT


def restore(a):
    spec=json.loads(a.design.read_text('utf8'));x,z,X,Z=spec['bounds']
    a.out.mkdir(parents=True,exist_ok=False)
    for sub in ('source','delta','earthworks','plan'):(a.out/sub).mkdir()
    for f in(a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    for f in a.plan.glob('*.json'):shutil.copy2(f,a.out/'plan'/f.name)
    with np.load(a.plan/'network.npz')as f:d={k:f[k]for k in f.files}
    px,pz,_,_=map(int,d['bounds']);area=np.s_[z-pz:Z-pz+1,x-px:X-px+1]
    zz,xx=np.mgrid[z:Z+1,x:X+1];retired=np.zeros(xx.shape,bool)
    for bx,by,bz,bX,bY,bZ in spec['volumes']:
        retired|=(xx>=bx)&(xx<=bX)&(zz>=bz)&(zz<=bZ)&d['walk'][area]
    raw=gzip.decompress(a.field.read_bytes());magic,fx,fz,step,w,h=struct.unpack('>6i',raw[:24])
    if magic!=0x484B3535:raise ValueError('Unknown field format')
    hgt=np.frombuffer(raw[24:24+w*h*2],'>i2').reshape(h,w)/16
    if x<fx or X>fx+(w-1)*step or z<fz or Z>fz+(h-1)*step:raise ValueError('Retirement outside surveyed field')
    qx=(xx-fx)/step;qz=(zz-fz)/step;ix=qx.astype(int);iz=qz.astype(int);dx=qx-ix;dz=qz-iz
    target=np.rint((hgt[iz,ix]*(1-dx)+hgt[iz,ix+1]*dx)*(1-dz)+(hgt[iz+1,ix]*(1-dx)+hgt[iz+1,ix+1]*dx)*dz).astype(np.int16)
    e=Editor(a.out);old=ground(e,spec['bounds']);target[~retired]=old[~retired]
    catalog=json.loads((a.plan/'catalog.json').read_text('utf8'))
    boxes=[[bx,by-3,bz,bX,bY,bZ]for bx,by,bz,bX,bY,bZ in (r['occupied_bounds']for r in catalog)]
    boxes+=json.loads((a.plan/'station-volumes.json').read_text('utf8'))
    devices={tuple(row['pos'])for f in a.measure.glob('*.json')for row in json.loads(f.read_text('utf8')).get('devices',[])}
    permitted=SOIL|PLANTS|AIR|PAVEMENT|{'minecraft:light'}
    writes={};errors=[];observed=[]
    keep={tuple(r['pos']):r['state']for r in spec.get('preserved_points',[])}
    for pos,state in keep.items():
        if e.state(*pos)!=state:raise ValueError(('Retained original object changed',pos))
    for j,i in np.argwhere(retired):
        xx,zz=int(x+i),int(z+j);lo,hi=next((by,bY)for bx,by,bz,bX,bY,bZ in spec['volumes']if bx<=xx<=bX and bz<=zz<=bZ)
        # The source interval includes only the commissioned old road layers,
        # not all paving elsewhere in this column or all subterranean air.
        pavement=[yy for yy in range(lo,hi+1)if e.state(xx,yy,zz).split('[')[0]in PAVEMENT]
        if not pavement:errors.append(['missing former roadway',xx,zz]);continue
        bottom=min(min(pavement)-1,int(old[j,i])-3,int(target[j,i])-3)
        top=max(max(pavement),int(old[j,i]),int(target[j,i]))
        if bottom<lo or top>hi:errors.append(['restoration exceeds explicit interval',xx,zz,bottom,top]);continue
        observed.append([xx,zz,min(pavement),max(pavement)])
        for yy in range(bottom,top+1):
            before=e.state(xx,yy,zz);bare=before.split('[')[0]
            if (xx,yy,zz)in keep:continue
            if yy<min(pavement)-1 and bare in AIR:continue
            after=('minecraft:air' if yy>target[j,i]else 'minecraft:grass_block[snowy=false]' if yy==target[j,i]
                   else 'minecraft:dirt' if yy>=target[j,i]-3 else 'minecraft:stone')
            if before==after:continue
            if bare not in permitted or (xx,yy,zz)in devices or any(bx<=xx<=bX and by<=yy<=bY and bz<=zz<=bZ for bx,by,bz,bX,bY,bZ in boxes):
                errors.append(['unowned retained cell',xx,yy,zz,before]);continue
            writes[xx,yy,zz]=after
    report=dict(errors=errors,columns=int(retired.sum()),observed_road_layers=observed,scope=spec,world_written=False)
    (a.out/'retirement-check.json').write_text(json.dumps(report,indent=2),'utf8')
    if errors:raise ValueError(str(errors[:10]))
    for pos,state in writes.items():e.put(*pos,state)
    rows=e.save()
    for key in ('walk','road','marking','tunnel'):d[key][area][retired]=False
    d['ground'][area][retired]=target[retired]
    np.savez_compressed(a.out/'plan/network.npz',**d)
    np.savez_compressed(a.out/'retired-surface.npz',bounds=spec['bounds'],old=old,target=target,retired=retired)
    (a.out/'manifest.json').write_text(json.dumps(dict(world=spec['world'],regions=rows,cells=sum(r['cells']for r in rows),world_written=False),indent=2),'utf8')
    (a.out/'launch-protection.json').write_text(json.dumps(check_candidate(load(Path(spec['world'])),a.out),indent=2),'utf8')
    print('Retired road columns',int(retired.sum()),'changed cells',sum(r['cells']for r in rows),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in ('source','plan','measure','design','field','out'):p.add_argument('--'+k,type=Path,required=True)
    restore(p.parse_args())
