"""Join the existing R07 port road and retain the complete R21 airport room."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.ndimage import distance_transform_edt
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid
from plan_hakone_network_repair import raster,network_grade
from hakone_earthworks import min_slope_envelope,road_blocks
from plan_ashi_landscape_r54 import NATURAL,SOIL
from verify_hakone_network_candidate import PAVEMENT

def run(a):
    e=Editor(a.candidate);d=load_grid(a.plan/'network.npz');x0,z0,x1,z1=map(int,d['bounds']);zz,xx=np.mgrid[z0:z1+1,x0:x1+1]
    oldwalk=d['walk'].copy();oldgrade=d['grade2'].copy();oldground=d['ground'].copy()
    airport=(xx>=350)&(xx<=1350)&(zz>=-177)&(zz<=86)
    d['held']|=airport;d['walk']&=~airport;d['road']&=~airport;d['ground'][airport]=d['old_ground'][airport]
    restored=0;changed=set()
    for rx in (0,1,2):
        for rz in (-1,0):
            r=e.region(rx*512,rz*512)
            for (cx,cz),b,v in zip(r['coords'],r['before'],r['after']):
                Z,X=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16];mask=(X>=350)&(X<=1350)&(Z>=-177)&(Z<=86)
                diff=(v[191:252]!=b[191:252])&mask
                if diff.any():restored+=int(diff.sum());v[191:252][diff]=b[191:252][diff];changed.add((int(cx),int(cz)))
            e.save();e.regions.clear()
    rows=json.loads((a.world/'quality_walk_cases.json').read_text('utf8'))
    path=next(r['path']for r in rows if r.get('id')=='r07/connection/port_road')
    # A retained 3x3 live viaduct pier stands at (1084,436). The whole
    # carriageway bends north of it; keep both its identity and its support.
    prior_port=d['walk'].copy()
    local=np.s_[420-z0:445-z0,1060-x0:1112-x0]
    d['road'][local]=False;d['walk'][local]=False
    points=[[p[0],p[2]-min(5,max(0,(p[0]-1056)/2),max(0,(1116-p[0])/2))]for p in path]
    route=dict(points=points,road=9,walk=13)
    road=raster(d['bounds'],[route],'road')&~d['held'];walk=raster(d['bounds'],[route],'walk')&~d['held']
    d['road']|=road;d['walk']|=walk
    retired=prior_port&~d['walk']&~airport
    d['grade2'][walk&~oldwalk]=d['ground'][walk&~oldwalk]*2
    entrances=np.full(d['walk'].shape,np.nan,np.float32)
    catalog=json.loads((a.plan/'catalog.json').read_text('utf8'))
    for row in catalog:
        for x,y,z in row.get('footway',[]):
            if x0<=x<=x1 and z0<=z<=z1 and d['walk'][z-z0,x-x0]:entrances[z-z0,x-x0]=oldgrade[z-z0,x-x0];break
    end=path[-1];ex,ez=int(end[0]),int(end[2]);entrances[ez-z0,ex-x0]=2*int(end[1]-1)
    d['grade2']=network_grade(d['grade2'],d['walk'],d['core'],entrances)
    affected=walk|((oldgrade!=d['grade2'])&d['walk'])
    upper=min_slope_envelope(np.where(affected,d['grade2']//2,np.inf),.75)
    lower=-min_slope_envelope(np.where(affected,-(d['grade2']//2),np.inf),.75)
    d['ground']=np.rint(np.clip(d['ground'],lower,upper)).astype(np.int16);d['ground'][d['held']|d['core']]=oldground[d['held']|d['core']];d['ground'][airport]=d['old_ground'][airport]
    # Existing footprints remain engineered plots with their complete rooms.
    for row in catalog:
        x,y,z,X,Y,Z=row['occupied_bounds'];ar=np.s_[z-z0-3:Z-z0+4,x-x0-3:X-x0+4];d['ground'][ar]=oldground[ar]
    # Shoulder grading must not refill a neighbouring existing street whose
    # grade did not otherwise change during the new port-road solve.
    d['ground'][d['walk']]=np.minimum(d['ground'][d['walk']],d['grade2'][d['walk']]//2)
    affected|=d['walk']&(d['ground']!=oldground)
    edit=affected|retired|(d['ground']!=oldground);zs,xs=np.nonzero(edit);points=sorted(((int(x+x0),int(z+z0))for z,x in zip(zs,xs)),key=lambda q:(q[0]//512,q[1]//512))
    mutable=NATURAL|PAVEMENT|{'minecraft:iron_bars','minecraft:stone_brick_wall','minecraft:sea_lantern','minecraft:polished_andesite'}
    # Preserve the real native structural bed rather than the old road datum.
    mutable.discard('minecraft:light_gray_concrete')
    errors=[];last=None
    for x,z in points:
        key=x//512,z//512
        if last is not None and key!=last:e.save();e.regions.clear()
        last=key;ij=z-z0,x-x0;h=int((d['grade2'][ij]+1)//2);floor=int(d['ground'][ij])
        if affected[ij]:
            states=[e.state(x,Y,z).split('[')[0]for Y in range(h,h+3)]
            if any(s not in mutable for s in states):errors.append(['retained-port-obstacle',x,h,z,states]);continue
            oldh=int((oldgrade[ij]+1)//2);top=max(oldh,int(oldground[ij]),h)
            # The retired R07 pavement is a declared whole corridor, not an
            # arbitrary black roof: include its former deck at the saved datum.
            if walk[ij]:top=max(top,82)
            for Y in range(h-2,min(319,top+8)+1):
                s=e.state(x,Y,z).split('[')[0]
                if s in mutable:e.put(x,Y,z,'minecraft:air'if Y>h else'minecraft:stone')
            slab=bool(d['grade2'][ij]%2);car=bool(d['road'][ij]);mark=bool(d['marking'][ij])or(walk[ij]and z==round(np.interp(x,[p[0]for p in path],[p[2]for p in path]))and x%12<5)
            mat=(('projectseele:road_marking_slab'if mark else 'projectseele:road_asphalt_slab'if car else 'minecraft:smooth_stone_slab')+'[type=bottom,waterlogged=false]')if slab else'minecraft:white_concrete'if mark else'minecraft:black_concrete'if car else'minecraft:smooth_stone'
            e.put(x,h,z,mat);changed.add((x//16,z//16))
        elif retired[ij]:
            for Y in range(min(floor,int(oldground[ij]))-3,max(83,floor+8)):
                if e.state(x,Y,z).split('[')[0]in mutable:e.put(x,Y,z,'minecraft:air'if Y>floor else'minecraft:grass_block[snowy=false]'if Y==floor else'minecraft:dirt');changed.add((x//16,z//16))
        elif not d['held'][ij]and not d['core'][ij]:
            for Y in range(min(floor,int(oldground[ij]))-3,max(floor,int(oldground[ij]))+1):
                if e.state(x,Y,z).split('[')[0]in NATURAL:
                    e.put(x,Y,z,'minecraft:air'if Y>floor else'minecraft:grass_block[snowy=false]'if Y==floor else'minecraft:dirt');changed.add((x//16,z//16))
    regions=e.save();meta=json.loads((a.candidate/'manifest.json').read_text('utf8'));meta.update(regions=regions,cells=sum(r['cells']for r in regions));(a.candidate/'manifest.json').write_text(json.dumps(meta,indent=2),'utf8')
    p=a.candidate/'transport-changed-chunks.json';changed|=set(map(tuple,json.loads(p.read_text('utf8'))));p.write_text(json.dumps(sorted(changed)),'utf8')
    np.savez_compressed(a.plan/'network.npz',**d)
    report=dict(airport_restored_cells=restored,road_source='quality_walk_cases.json:r07/connection/port_road',port_endpoint=end,port_walk_columns=int(walk.sum()),errors=errors)
    (a.candidate/'retained-port-completion.json').write_text(json.dumps(report,indent=2),'utf8')
    check=json.loads((a.candidate/'functional-check.json').read_text('utf8'));check['errors']=[r for r in check['errors']if r[0]!='retained-port-obstacle']+errors;(a.candidate/'functional-check.json').write_text(json.dumps(check,indent=2),'utf8');print(report,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('candidate','plan','world'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
