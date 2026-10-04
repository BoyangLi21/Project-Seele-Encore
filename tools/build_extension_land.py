"""Measured terrain, half-step roads, tunnels and bridge decks for the extension."""
import argparse,json,math
from collections import defaultdict
import numpy as np
import regional_voxels as vox
from quality_structures import Builder,OUT,OLD,load
from quality_roads import envelopes
from regional_architecture import AIR,DARK,FLOOR,LIGHT,STEEL,WALL

def build(part):
    source=np.load(OUT/'surface_levels_extension_before.npz');base=source['height'];known=source['known'];ox,oz=map(int,source['origin']);nz,nx=base.shape
    plan=load(OUT/'extension_plan.json');rail_samples=load(OUT/'estate_transit_draft/track_samples.json');old_samples=load(OLD/'transit2/track_samples.json')
    mask=np.zeros(base.shape,bool);carriage=np.zeros_like(mask);desired=np.full(base.shape,30000,np.int32);fixed=np.full_like(desired,30000);centres=[]
    for road in plan['roads']:
        r=road['width']//2
        for a,b in zip(road['points'],road['points'][1:]):
            n=max(abs(a[0]-b[0]),abs(a[2]-b[2]))
            for i in range(n+1):
                t=i/max(1,n);x=round(a[0]+(b[0]-a[0])*t);z=round(a[2]+(b[2]-a[2])*t);h2=round(2*(a[1]+(b[1]-a[1])*t+1));ix,iz=x-ox,z-oz
                if not (r+3<=ix<nx-r-3 and r+3<=iz<nz-r-3):raise RuntimeError('Road outside generated envelope')
                mask[iz-r-2:iz+r+3,ix-r-2:ix+r+3]=True
                if not road.get('walkway'):carriage[iz-r:iz+r+1,ix-r:ix+r+1]=True
                v=desired[iz-r-2:iz+r+3,ix-r-2:ix+r+3];np.minimum(v,h2,out=v)
                centres.append((x,z,r,road['id'],int(np.sign(b[0]-a[0])),int(np.sign(b[2]-a[2]))))
            for x,f,z in (a,b):fixed[z-oz,x-ox]=2*(f+1)
    if np.any(mask&~known):raise RuntimeError('Road crosses unknown source columns')
    old_roads=np.load(OUT/'road_surfaces.npz');old_mask=old_roads['mask'];old_h=old_roads['height2'];rx,rz=map(int,old_roads['origin'])
    x0,x1=max(ox,rx),min(ox+nx,rx+old_mask.shape[1]);z0,z1=max(oz,rz),min(oz+nz,rz+old_mask.shape[0])
    if x0<x1 and z0<z1:
        new_slice=np.s_[z0-oz:z1-oz,x0-ox:x1-ox];old_slice=np.s_[z0-rz:z1-rz,x0-rx:x1-rx]
        common=mask[new_slice]&old_mask[old_slice];v=fixed[new_slice];v[common]=old_h[old_slice][common]
    lower_pins=np.full_like(desired,-30000)
    # Cross old trains on a supported bridge, with the entire vehicle envelope below.
    crossings=[]
    for rail in old_samples:
        if rail['mode']!='TRAIN':continue
        for x,y,z in rail['points'][::2]:
            xx,zz=round(x)-ox,round(z)-oz
            if not(2<=xx<nx-2 and 2<=zz<nz-2) or y<0:continue
            area=mask[zz-2:zz+3,xx-2:xx+3]
            if not area.any():continue
            v=lower_pins[zz-2:zz+3,xx-2:xx+3];v[area]=np.maximum(v[area],math.ceil((y+7)*2));crossings.append([x,y,z])
    lower_pins=np.maximum(lower_pins,np.where(fixed<20000,fixed,-30000));lower=-envelopes(mask,np.where(lower_pins>-20000,-lower_pins,30000))
    upper=envelopes(mask,fixed)
    if np.any(mask&(lower>upper)):raise RuntimeError('Bridge conflicts with a fixed road entrance')
    road_h=envelopes(mask,np.where(mask,np.maximum(lower,np.minimum(desired,upper)),30000))
    if not np.array_equal(road_h[fixed<20000],fixed[fixed<20000]):raise RuntimeError('Extension endpoint drift')
    np.savez_compressed(OUT/'extension_road_surfaces.npz',height2=road_h.astype(np.int16),mask=mask,carriage=carriage,origin=[ox,oz])
    target=base.astype(float).copy();weight=np.zeros(base.shape,np.float32);sums=np.zeros_like(weight)
    def grade_rect(x0,x1,z0,z1,height,margin):
        ax=max(0,x0-margin-ox);bx=min(nx,x1+margin-ox+1);az=max(0,z0-margin-oz);bz=min(nz,z1+margin-oz+1)
        xx=np.arange(ax,bx)[None,:]+ox;zz=np.arange(az,bz)[:,None]+oz
        distance=np.hypot(np.maximum(np.maximum(x0-xx,xx-x1),0),np.maximum(np.maximum(z0-zz,zz-z1),0))
        t=np.clip(distance/margin,0,1);w=1-t*t*(3-2*t);weight[az:bz,ax:bx]+=w;sums[az:bz,ax:bx]+=w*height
    x0,x1,z0,z1=plan['estate']['bounds'];grade_rect(x0,x1,z0,z1,70,48)
    # Short continuous benches blend into the same field. Deep valleys and
    # hills use structures, leaving their natural ground and roof in place.
    for road in plan['roads']:
        r=road['width']//2+2
        for a,b in zip(road['points'],road['points'][1:]):
            n=max(abs(a[0]-b[0]),abs(a[2]-b[2]))
            for i in range(0,n+1,8):
                j=min(n,i+7);x=round(a[0]+(b[0]-a[0])*i/max(1,n));z=round(a[2]+(b[2]-a[2])*i/max(1,n));xx=round(a[0]+(b[0]-a[0])*j/max(1,n));zz=round(a[2]+(b[2]-a[2])*j/max(1,n))
                h=(road_h[z-oz,x-ox]+road_h[zz-oz,xx-ox])/4-1
                native=(int(base[z-oz,x-ox])+int(base[zz-oz,xx-ox]))/2
                if abs(native-h)<=8:grade_rect(min(x,xx)-r,max(x,xx)+r,min(z,zz)-r,max(z,zz)+r,h,24)
    w=np.clip(weight,0,1);target=np.rint(target*(1-w)+np.divide(sums,np.maximum(weight,.000001))*w).astype(np.int16)
    active=(weight>0)&known
    if np.any(active&(base<-1000)):raise RuntimeError('Grading an unmeasured source')
    vox.OUT=OUT;p=Builder()
    for zone in load(OLD/'regional_plan.json')['zones']:
        if zone['kind']!='district':continue
        a,b,c,d=zone['bounds'];p.protect((a,32,c,b,255,d),'retained_city',('heightfield',))
    for b in load(OUT/'surface_layout.json')['kept_plots']:
        a,bb,c,d=b['bounds'];f=b['floor'];p.protect((a,f,c,bb,f+b.get('storeys',3)*5+8,d),b['id'])
    if list((OUT/'kirisato_apartments').glob('applied_*/receipt.json')):
        x0,x1,z0,z1=plan['estate']['bounds'];p.protect((x0,70,z0,x1,255,z1),'existing_estate',('heightfield',))
    if list((OUT/'estate_track_envelopes').glob('applied_*/receipt.json')):
        for rail in rail_samples:
            for x,y,z in {tuple(map(round,a)) for a in rail['points'][::2]}:p.protect((x-4,y-3,z-4,x+4,y+7,z+4),'existing_S2',('heightfield',))
    for x0,x1,z0,z1 in [(460,1220,1035,1530),(-2180,-1420,-415,95)]:p.protect((x0,32,z0,x1,255,z1),'retained_airport',('heightfield',))
    for rail in old_samples:
        if rail['mode']!='TRAIN':continue
        for x,y,z in {tuple(map(round,a)) for a in rail['points'][::2]}:
            if y>=0:p.protect((x-2,y,z-2,x+2,y+5,z+2),'existing_train_body')
    if part in ('terrain','all'):
        for cx,cz in load(OUT/'extension_envelope.json')['chunks']:
            ix,iz=cx*16-ox,cz*16-oz;v=active[iz:iz+16,ix:ix+16]
            if v.any():
                h=target[iz:iz+16,ix:ix+16];old=base[iz:iz+16,ix:ix+16];clear=(weight[iz:iz+16,ix:ix+16]>=.9)|(h<old)|(h>old+1)
                p.heightfield(cx,cz,h,v,'extension_continuous_grade',clear)
    if part in ('roads','all'):
        for iz in range(nz):
            xs=np.flatnonzero(mask[iz]);i=0
            while i<len(xs):
                ix=int(xs[i]);h2=int(road_h[iz,ix]);kind=bool(carriage[iz,ix]);j=i+1
                while j<len(xs) and xs[j]==xs[j-1]+1 and road_h[iz,xs[j]]==h2 and bool(carriage[iz,xs[j]])==kind:j+=1
                x0,x1,z=ox+ix,ox+int(xs[j-1]),oz+iz;y=(h2-1)//2
                block='minecraft:black_concrete' if kind else FLOOR
                if h2%2:block=('minecraft:polished_blackstone_slab' if kind else 'minecraft:smooth_stone_slab')+'[type=bottom,waterlogged=false]'
                p.fill(x0,y-2,z,x1,y-1,z,DARK,'extension/road_deck');p.fill(x0,y,z,x1,y,z,block,'extension/road');p.fill(x0,y+1,z,x1,y+5,z,AIR,'extension/road_clear');i=j
        seen=set()
        for number,(x,z,r,name,dx,dz) in enumerate(centres):
            if (x,z) in seen:continue
            seen.add((x,z));y=(int(road_h[z-oz,x-ox])-1)//2;native=int(target[z-oz,x-ox])
            if native<y-8 and number%24==0:
                p.fill(x,native+1,z,x,y-3,z,'minecraft:polished_basalt[axis=y]','extension/road_pier')
                p.fill(x-r-2,y-2,z-r-2,x+r+2,y-2,z+r+2,STEEL,'extension/road_crossbeam')
            # Judge each entire roadside bearing. The centre may be level
            # while its outer shoulder hangs over the actual valley wall.
            for sign in (-1,1):
                side=sign*(r+3);xx,zz=x-dz*side,z+dx*side
                ix,iz=xx-ox,zz-oz
                if not (0<=ix<nx and 0<=iz<nz):
                    p.meta.setdefault('whole_road_section_holds',[]).append(dict(x=x,z=z,side=side,reason='Unknown complete guard bearing profile'))
                    continue
                edge=int(target[iz,ix])
                if edge<y:
                    # Full cantilever coping ties into the already founded
                    # original complete road deck; bars never float alone.
                    for reach in range(r+1,r+4):
                        sx,sz=x-dz*sign*reach,z+dx*sign*reach
                        p.fill(sx,y-2,sz,sx,y-1,sz,STEEL,'extension/whole_guard_frame')
                    p.put(xx,y,zz,FLOOR,'extension/whole_guard_coping')
                    p.fill(xx,y+1,zz,xx,y+2,zz,'minecraft:iron_bars[east=true,north=true,south=true,waterlogged=false,west=true]','extension/bridge_guard')
            # A tunnel shell needs cover over its complete roof, not only one
            # centre sample that later grades could leave outside the hill.
            a,b=x-r-3-ox,x+r+3-ox;c,d=z-r-3-oz,z+r+3-oz
            covered=0<=a<=b<nx and 0<=c<=d<nz and int(target[c:d+1,a:b+1].min())>=y+9
            if native>y+8 and not covered:
                p.meta.setdefault('whole_road_section_holds',[]).append(dict(x=x,z=z,reason='Centre-only tunnel rejected: complete final roof cover absent'))
            if native>y+8 and covered:
                p.fill(x-r-3,y+6,z-r-3,x+r+3,y+7,z+r+3,WALL,'extension/road_tunnel_roof')
                for side in (-r-3,r+3):
                    xx,zz=x-dz*side,z+dx*side;p.fill(xx,y+1,zz,xx,y+5,zz,WALL,'extension/road_tunnel_wall')
                if number%12==0:p.put(x,y+6,z,LIGHT,'extension/tunnel_light')
        for o in list(p.ops):
            if o.owner=='extension/road_clear':p.fill(*o.box,o.state,o.owner)
        for o in list(p.ops):
            if o.owner=='extension/road':p.fill(*o.box,o.state,o.owner)
        for o in list(p.ops):
            if o.owner=='extension/tunnel_light':p.fill(*o.box,o.state,o.owner)
        p.meta['road_crossings']=crossings;p.meta['road_cells']=int(mask.sum())
    np.savez_compressed(OUT/'extension_terrain_target.npz',height=target,active=active,origin=[ox,oz])
    return p

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--part',choices=['terrain','roads','all'],default='all');ap.add_argument('--apply',action='store_true');args=ap.parse_args();p=build(args.part)
    p.apply('extension_land_'+args.part) if args.apply else p.save_plan('extension_land_'+args.part)
