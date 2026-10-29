"""Raise the existing lake-edge shop above the new water and join its old street.

Edits only the uninstalled lake candidate. Complete inventory/sign/bed tags and
the original shop address are retained. The shore follows the cached GSI mask.
"""
import argparse,copy,json,shutil
from pathlib import Path
from collections import defaultdict
import numpy as np
import nbtlib
from query_blocks import iter_block_entities
from apply_s20_approved_semantic_repairs import parse_state
from prepare_hakone_city_cross import packed
from install_r53_carrier_trays import stopped_world


class Editor:
    def __init__(self,folder):self.folder=folder;self.regions={}
    def region(self,x,z):
        key=x//512,z//512
        if key not in self.regions:
            name=f'r.{key[0]}.{key[1]}.npz'
            with np.load(self.folder/'source'/name)as a:
                coords=a['coordinates'];before=a['blocks'];names=list(map(str,a['palette']))
            ids={s:i for i,s in enumerate(names)};index={tuple(p):i for i,p in enumerate(coords)};after=before.copy()
            file=self.folder/'delta'/name
            if file.exists():
                with np.load(file)as a:
                    remap=[]
                    for s in map(str,a['palette']):
                        if s not in ids:ids[s]=len(names);names.append(s)
                        remap.append(ids[s])
                    remap=np.asarray(remap,np.uint16);points,ranges,at,values=(a[k]for k in ('coordinates','ranges','indices','after'))
                    for i,p in enumerate(points):
                        l,r=ranges[i:i+2];after[index[tuple(p)]].reshape(-1)[at[l:r]]=remap[values[l:r]]
            self.regions[key]=dict(name=name,coords=coords,index=index,before=before,after=after,names=names,ids=ids)
        return self.regions[key]
    def state(self,x,y,z,original=False):
        r=self.region(x,z);return r['names'][r['before'if original else 'after'][r['index'][x//16,z//16],y+128,z%16,x%16]]
    def put(self,x,y,z,name):
        if not -128<=y<320:raise ValueError((x,y,z))
        r=self.region(x,z)
        if name not in r['ids']:r['ids'][name]=len(r['names']);r['names'].append(name)
        r['after'][r['index'][x//16,z//16],y+128,z%16,x%16]=r['ids'][name]
    def fill(self,x,y,z,X,Y,Z,name):
        for px in range(x,X+1):
            for pz in range(z,Z+1):
                r=self.region(px,pz)
                if name not in r['ids']:r['ids'][name]=len(r['names']);r['names'].append(name)
                r['after'][r['index'][px//16,pz//16],y+128:Y+129,pz%16,px%16]=r['ids'][name]
    def save(self):
        rows=[]
        for r in self.regions.values():
            coords=[];ranges=[0];indices=[];before=[];after=[]
            for p,b,a in zip(r['coords'],r['before'],r['after']):
                at=np.flatnonzero((a!=b).ravel()).astype(np.uint32)
                if not len(at):continue
                coords.append(p);indices.append(at);before.append(b.ravel()[at]);after.append(a.ravel()[at]);ranges.append(ranges[-1]+len(at))
            path=self.folder/'delta'/r['name']
            backup=self.folder/'before-lakefront'/r['name']
            if path.exists() and not backup.exists():
                backup.parent.mkdir(exist_ok=True);shutil.copy2(path,backup)
            np.savez_compressed(path,coordinates=np.asarray(coords,np.int32),ranges=np.asarray(ranges,np.int64),indices=np.concatenate(indices),
                before=np.concatenate(before),after=np.concatenate(after),palette=np.asarray(r['names']))
            rows.append(dict(path='delta/'+r['name'],cells=ranges[-1]))
        return rows


def author(a):
    report=json.loads((a.candidate/'manifest.json').read_text('utf8'))
    if 'lakefront_shop'in report:raise ValueError('This candidate already has the shoreline adjustment')
    editor=Editor(a.candidate);surface=np.load(a.candidate/'surface.npz')
    x0,z0,_,_=surface['bounds'];lake=surface['lake'];target=surface['target'];held=surface['held']
    changes=[];lo=(-497,80,863);hi=(-455,107,905)
    devices=dict(iter_block_entities(a.world,'projectseele:geofront',lo,hi))
    # The observed four-storey corner shop is lifted in place. Its adjacent
    # residential building remains at its original position and elevation.
    body={(x,y,z):editor.state(x,y,z,True)for x in range(lo[0],hi[0]+1)for z in range(lo[2],hi[2]+1)for y in range(80,108)}
    for x in range(lo[0],hi[0]+1):
        for z in range(lo[2],hi[2]+1):
            wet=bool(lake[z-z0,x-x0]);bed=min(98,int(target[z-z0,x-x0]))if wet else 99
            editor.fill(x,77,z,x,bed,z,'minecraft:stone')
            editor.fill(x,bed+1,z,x,99,z,'minecraft:water[level=0]'if wet else'minecraft:dirt')
            editor.fill(x,100,z,x,128,z,'minecraft:air')
    # Clear the remaining former southern-grid paving inside the real water
    # outline. No native train/bus curve enters this small shoreline strip.
    zs,xs=np.where(lake&held)
    for iz,ix in zip(zs,xs):
        x,z=int(ix+x0),int(iz+z0)
        if not(-490<=x<=-430 and 880<=z<=990):raise ValueError('Unexpected lake infrastructure outside the measured corner shop')
        bed=98
        editor.fill(x,76,z,x,bed,z,'minecraft:gravel');editor.put(x,99,z,'minecraft:water[level=0]')
        editor.fill(x,100,z,x,128,z,'minecraft:air')
    for (x,y,z),state in body.items():editor.put(x,y+20,z,state)
    for pos,tag in devices.items():
        new=copy.deepcopy(tag);new['y']=nbtlib.Int(int(tag['y'])+20);q=(pos[0],pos[1]+20,pos[2])
        changes.append(nbtlib.Compound({'Pos':nbtlib.Long(packed(pos)),'Before':copy.deepcopy(tag)}))
        changes.append(nbtlib.Compound({'Pos':nbtlib.Long(packed(q)),'After':new}))
    # A three-wide stair joins the raised south entrance to the measured old
    # public carriageway, instead of leaving a doorway twenty blocks up.
    end=(-520,80,912)
    if editor.state(*end,original=True).split('[')[0]not in ('minecraft:black_concrete','minecraft:white_concrete','minecraft:smooth_stone'):
        raise ValueError('The selected old-street endpoint is not the recorded paving')
    path=[(-476,100,z)for z in range(902,913)]
    path += [(x,int(round(100-( -476-x)*20/44)),912)for x in range(-477,-521,-1)]
    for x,y,z in path:
        if z==912:
            editor.fill(x,78,z-1,x,y-1,z+1,'minecraft:stone');editor.fill(x,y,z-1,x,y,z+1,'minecraft:smooth_stone')
            editor.fill(x,y+1,z-1,x,y+3,z+1,'minecraft:air')
        else:
            editor.fill(x-1,98,z,x+1,y-1,z,'minecraft:stone');editor.fill(x-1,y,z,x+1,y,z,'minecraft:smooth_stone')
            editor.fill(x-1,y+1,z,x+1,y+3,z,'minecraft:air')
    for previous,current in zip(path,path[1:]):
        if previous[1]==current[1]:continue
        x,y,z=previous
        editor.fill(x,y,z-1,x,y,z+1,'minecraft:stone_brick_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]')
    # Test the authored public stair and the original inventory while it is
    # still an in-memory candidate. This never gates runtime movement.
    errors=[]
    for x,y,z in path:
        across=[(x,zz)for zz in range(z-1,z+2)] if z==912 else [(xx,z)for xx in range(x-1,x+2)]
        for xx,zz in across:
            if editor.state(xx,y,zz).split('[')[0] in ('minecraft:air','minecraft:water'):errors.append(['floor',xx,y,zz])
            if any(editor.state(xx,yy,zz)!='minecraft:air'for yy in (y+1,y+2)):errors.append(['headroom',xx,y,zz])
    for pos,tag in devices.items():
        if editor.state(pos[0],pos[1]+20,pos[2])!=editor.state(*pos,original=True):errors.append(['device',*pos])
    if errors:raise ValueError(errors[:12])
    changed=editor.save();by_path={r['path']:r for r in report['regions']};by_path.update({r['path']:r for r in changed})
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](changes)}).save(a.candidate/'block-entities.dat',gzipped=True)
    report.update(regions=list(by_path.values()),cells=sum(r['cells']for r in by_path.values()),
        lakefront_shop=dict(id='tokyo_south/02-07',delta=[0,20,0],preserved_devices=len(devices),new_floor_y=100,
                           public_stair=[[x,y+1,z]for x,y,z in path]),retired_lake_grid_columns=len(xs))
    (a.candidate/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Lakefront shop and road interface authored; preserved devices:',len(devices),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('world','candidate'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    with stopped_world(a.world):author(a)
