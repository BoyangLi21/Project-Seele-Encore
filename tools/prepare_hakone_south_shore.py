"""Rebase the southern lake streets on the current saved shore, without DEM replay.

The earlier candidate supplies road alignments and the port programme only.
Current saved blocks are the sole construction baseline. This script prepares
a reversible candidate; publication uses the ordinary cold map installer.
"""
import argparse
import json
import os
from pathlib import Path
import numpy as np
from shapely.geometry import LineString

from hakone_earthworks import grade_ground, min_slope_envelope, road_blocks
from plan_ashi_landscape_r54 import NATURAL
from author_hakone_south_ports import author
from author_hakone_district_blocks import Frontage


def read_arrays(path):
    with np.load(path) as f:return {k:f[k] for k in f.files}


def joint_street_grades(desired,developed,fixed,sections,level_groups=(),minimum=None,maximum=None):
    """Solve fixed whole plots, nearby branches and full road widths together.

    Each L1 grid edge permits one half-block; every pair of pixels in a road
    cross section permits one half-block too. Propagate the same constraints
    for both fixed bounds and the desired grades, so width leveling cannot
    invalidate a previously fitted port/terrain bound.
    """
    section_indices=[tuple(np.asarray(sorted(points),np.int32).T)for points in sections]
    passes=[]
    def envelope(values):
        values=np.asarray(values,np.float32).copy()
        for iteration in range(128):
            values=min_slope_envelope(values,1.0);changed=False
            for index in section_indices:
                current=values[index];limit=current.min()+1
                if np.any(current>limit):values[index]=np.minimum(current,limit);changed=True
            for area in level_groups:
                current=values[area];level=np.floor(current.min()/2)*2
                if np.any(current!=level):values[area]=level;changed=True
            if not changed:
                passes.append(iteration+1);return values
        raise ValueError('Joint road width/terrain envelope did not converge')
    low=np.full(desired.shape,np.inf,np.float32);high=low.copy()
    if minimum is not None:low[developed]=-minimum[developed]
    if maximum is not None:high[developed]=maximum[developed]
    low[fixed]=np.minimum(low[fixed],-desired[fixed]);high[fixed]=np.minimum(high[fixed],desired[fixed])
    lower=-envelope(low);upper=envelope(high)
    if np.any(lower>upper):
        locations=np.argwhere(lower>upper)
        raise ValueError(('Public plot levels cannot share the commissioned road widths',len(locations),
            [[int(z),int(x),float(lower[z,x]),float(upper[z,x])]for z,x in locations[:12]]))
    fitted=envelope(np.where(developed,np.clip(desired,lower,upper),np.inf))
    if np.any(fitted[developed]<lower[developed])or not np.array_equal(fitted[fixed],desired[fixed]):
        raise ValueError('Joint road solve changed a fixed public plot')
    result=desired.copy();result[developed]=np.rint(fitted[developed]).astype(np.int16)
    return result,passes


def prepare(a):
    capture=json.loads((a.source/'capture.json').read_text('utf8'))
    current=read_arrays(a.source/'measured.npz')
    previous=read_arrays(a.gis/'lakeshore-candidate-v2/valley-surface.npz')
    prior=json.loads((a.gis/'lakeshore-candidate-v2/manifest.json').read_text('utf8'))
    bounds=previous['bounds'];x0,z0,x1,z1=map(int,bounds)
    mx,mz,_,_=map(int,current['bounds']);area=np.s_[z0-mz:z1-mz+1,x0-mx:x1-mx+1]
    measured={k:current[k][area].copy() for k in ('top','highest','protected','full','actors')}
    if not measured['full'].all():raise ValueError('The complete source must be native FULL')
    shape=measured['top'].shape;zz,xx=np.mgrid[z0:z1+1,x0:x1+1]
    # The northward connection across the airport edge is a separate corridor
    # design. Do not restore the obsolete high road through its lowered slope.
    scope=(zz>=1664)&(zz<=2511)&(xx>=128)&(xx<=959)
    walk=previous['walk']&scope
    road=previous['road']&walk
    bridge=previous['bridge']&walk
    obstacles=measured['protected']|measured['actors']
    if np.any(walk&obstacles):
        points=np.argwhere(walk&obstacles)
        raise ValueError(('Existing objects need explicit road routing',len(points),[[int(x+x0),int(z+z0)]for z,x in points[:15]]))
    water=np.zeros(shape,bool)
    for file in sorted((a.source/'source').glob('*.npz')):
        with np.load(file)as f:coords=f['coordinates'];blocks=f['blocks'];names=list(map(str,f['palette']))
        watery=np.array([s.startswith('minecraft:water[')or s=='minecraft:water'for s in names])
        for (cx,cz),block in zip(coords,blocks):
            x,z=int(cx)*16,int(cz)*16
            if x<x0 or z<z0 or x>x1 or z>z1:continue
            area=np.s_[z-z0:z-z0+16,x-x0:x-x0+16]
            water_top=np.where(watery[block],np.arange(-128,320)[:,None,None],-129).max(0)
            water[area]=water_top>measured['top'][area]
    desired=previous['road2'].copy()
    discrepancy=np.abs(desired//2-measured['top'])
    desired[walk&(discrepancy>4)]=measured['top'][walk&(discrepancy>4)]*2
    plots=[];fixed=np.zeros(shape,bool);developed=walk.copy()
    # Public terminals and cafes have explicit current-water-relative levels.
    public_sites=[dict(centre=[531,2029],floor=100,half=[12,7],rotation=3),
                  dict(centre=[402,2342],floor=100,half=[12,7],rotation=0),
                  dict(centre=[603,2000],floor=116,half=[5,6],rotation=1),
                  dict(centre=[385,2370],floor=101,half=[7,8],rotation=0)]
    for index,site in enumerate(public_sites):
        hx,hz=site['half'];frame=Frontage(site)
        first=frame.point(-hx-1,0,-hz-1);last=frame.point(hx+1,0,hz+3)
        left,right=sorted((first[0],last[0]));north,south=sorted((first[2],last[2]))
        box=np.s_[north-z0:south-z0+1,left-x0:right-x0+1]
        plots.append(box);developed[box]=True;fixed[box]=True;desired[box]=site['floor']*2
    sections=[]
    for street in prior['streets']:
        if street['tunnel'] or not street['width']:continue
        line=LineString(street['points'])
        for distance in np.arange(1,line.length,2):
            p=np.asarray(line.interpolate(distance).coords[0]);x,z=np.rint(p).astype(int)
            if not(x0+10<=x<=x1-10 and z0+10<=z<=z1-10 and scope[z-z0,x-x0]):continue
            tangent=np.asarray(line.interpolate(min(distance+1,line.length)).coords[0])-np.asarray(line.interpolate(max(distance-1,0)).coords[0])
            length=np.linalg.norm(tangent)
            if not length:continue
            normal=np.array([-tangent[1],tangent[0]])/length
            radius=street['width']/2+1.5
            points=np.rint(p+np.linspace(-radius,radius,int(street['width'])+4)[:,None]*normal).astype(int)
            section={(int(Z-z0),int(X-x0))for X,Z in points if walk[Z-z0,X-x0]}
            if len(section)>1:sections.append(section)
    grade,passes=joint_street_grades(desired,developed,fixed,sections)
    # Only the commissioned streets and complete public plots grade soil.
    anchors=(walk&~bridge)|fixed
    anchor_y=(road_blocks(grade)[0]-1).astype(np.int16)
    anchor_y[fixed]=desired[fixed]//2-1
    ground,conflicts=grade_ground(measured['top'],anchors,anchor_y,slope=1.0)
    if conflicts.any():
        points=[[int(x+x0),int(z+z0),int(anchor_y[z,x]),bool(anchors[z,x]),bool(fixed[z,x])]
                for z,x in np.argwhere(conflicts)]
        (a.out.parent/'work/south-shore-grade-conflicts.json').write_text(json.dumps(points,indent=2),'utf8')
        raise ValueError(('Contradictory street/port earthworks',len(points),points[:8]))
    ground[water|bridge]=measured['top'][water|bridge]
    active=ground!=measured['top']
    if np.any(active&obstacles):raise ValueError('Earthworks reach retained structures or actors')
    if any(edge.any() for edge in (active[0],active[-1],active[:,0],active[:,-1])):
        raise ValueError('Earthworks did not meet current ground before source boundary')
    maximum=int(np.abs(ground-measured['top'])[active].max(initial=0))
    if maximum>12:
        points=[[int(x+x0),int(z+z0),int(measured['top'][z,x]),int(ground[z,x]),bool(walk[z,x])]
                for z,x in np.argwhere(np.abs(ground-measured['top'])>12)]
        (a.out.parent/'work/south-shore-deep-cut-review.json').write_text(json.dumps(points,indent=2),'utf8')
        raise ValueError(('New roads require separate bridge/tunnel design',maximum,points[:12]))
    a.out.mkdir(parents=True,exist_ok=False)
    for sub in ('source','delta'):(a.out/sub).mkdir()
    for file in(a.source/'source').glob('*.npz'):os.link(file,a.out/'source'/file.name)
    (a.out/'capture.json').write_text(json.dumps(capture,ensure_ascii=False,indent=2),'utf8')
    held=obstacles|~scope|water
    np.savez_compressed(a.out/'valley-surface.npz',bounds=bounds,target=ground,road2=grade,road=road,walk=walk,
        wet=water,water_y=np.full(shape,99,np.int16),river=previous['river'],held=held,
        protected=obstacles,bridge=bridge,blocked_road=np.zeros(shape,bool))
    np.savez_compressed(a.out/'current-grading.npz',bounds=bounds,old_ground=measured['top'],ground=ground,
        water=water,active=active,scope=scope,highest=measured['highest'])
    manifest=dict(world=capture['world'],bounds_xz=bounds.tolist(),regions=[],cells=0,streets=prior['streets'],
        world_written=False,source=str(a.source),old_candidate_geometry_replayed=False,
        construction_scope=[128,1664,959,2511],north_airport_connection_pending=True,
        current_public_sites=public_sites)
    (a.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (a.out/'street-design.json').write_text(json.dumps(dict(walk_columns=int(walk.sum()),road_columns=int(road.sum()),
        bridge_columns=int(bridge.sum()),cross_sections=len(sections),earthwork_columns=int(active.sum()),
        maximum_earthwork=maximum,existing_object_conflicts=0,port_plots=len(plots),grade_envelope_passes=passes),indent=2),'utf8')
    print('Current shoreline design',int(walk.sum()),'street columns;',maximum,'maximum earthwork',flush=True)


def compose(a):
    d=read_arrays(a.out/'valley-surface.npz');q=read_arrays(a.out/'current-grading.npz')
    x0,z0,x1,z1=map(int,d['bounds']);yy=np.arange(-128,320)[:,None,None];regions=[]
    for file in sorted((a.out/'source').glob('*.npz')):
        with np.load(file)as f:coords=f['coordinates'];blocks=f['blocks'];names=list(map(str,f['palette']))
        lookup={s:i for i,s in enumerate(names)}
        def code(name):
            if name not in lookup:lookup[name]=len(names);names.append(name)
            return lookup[name]
        air,stone,dirt,grass,asphalt,pave,aslab,pslab=[code(s)for s in('minecraft:air','minecraft:stone','minecraft:dirt',
            'minecraft:grass_block[snowy=false]','minecraft:black_concrete','minecraft:smooth_stone',
            'projectseele:road_asphalt_slab[type=bottom,waterlogged=false]','minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')]
        natural=np.array([s.split('[')[0]in NATURAL for s in names])
        selected=[];ranges=[0];indices=[];before=[];after=[]
        for (cx,cz),old in zip(coords,blocks):
            x,z=int(cx)*16,int(cz)*16
            if x<x0 or z<z0 or x>x1 or z>z1:continue
            area=np.s_[z-z0:z-z0+16,x-x0:x-x0+16];walk=d['walk'][area];active=q['active'][area]
            if not(active.any()or walk.any()):continue
            ground=q['ground'][area];new=old.copy()
            lower=np.minimum(q['old_ground'][area],ground)-3;upper=np.maximum(q['highest'][area],ground+5)
            band=active&(yy>=lower)&(yy<=upper)
            proposed=np.where(yy>ground,air,np.where(yy==ground,grass,np.where(yy>=ground-3,dirt,stone))).astype(np.uint16)
            if np.any(band&~natural[old]&(old!=proposed)):raise ValueError(('Earthwork enters original construction',int(cx),int(cz)))
            new[band]=proposed[band]
            y,slab=road_blocks(d['road2'][area]);road=d['road'][area]
            material=np.where(road,np.where(slab,aslab,asphalt),np.where(slab,pslab,pave))
            roadband=walk&(yy>=y-2)&(yy<=y+5)
            final=np.where(yy>y,air,np.where(yy==y,material,stone)).astype(np.uint16)
            if np.any(roadband&~natural[old]&(old!=final)):raise ValueError(('Street enters original construction',int(cx),int(cz)))
            new[roadband]=final[roadband]
            zz,xx=np.mgrid[z:z+16,x:x+16]
            supports=walk&d['bridge'][area]&((xx+zz)%12==0)
            pile_band=supports&(yy>ground)&(yy<y-2)
            if np.any(pile_band&~natural[old]&(old!=stone)):raise ValueError('Bridge pile enters retained construction')
            new[pile_band]=stone
            at=np.flatnonzero((new!=old).ravel()).astype(np.uint32)
            if len(at):
                selected.append((cx,cz));ranges.append(ranges[-1]+len(at));indices.append(at)
                before.append(old.ravel()[at]);after.append(new.ravel()[at])
        if selected:
            name='delta/'+file.name
            np.savez_compressed(a.out/name,coordinates=np.asarray(selected,np.int32),ranges=np.asarray(ranges,np.int64),
                indices=np.concatenate(indices),before=np.concatenate(before),after=np.concatenate(after),palette=np.asarray(names))
            regions.append(dict(path=name,cells=ranges[-1]))
            print('Prepared current shore street region',file.name,ranges[-1],flush=True)
    path=a.out/'manifest.json';manifest=json.loads(path.read_text('utf8'))
    manifest.update(regions=regions,cells=sum(r['cells']for r in regions))
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    if not getattr(a,'skip_author',False):author(argparse.Namespace(candidate=a.out,gis=a.gis))


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('gis','source','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--phase',choices=('design','compose'),required=True)
    a=p.parse_args()
    from finish_hakone_south_shore import design as finish_design,compose as finish_compose
    if a.phase=='design':
        prepare(a)
        author(argparse.Namespace(candidate=a.out,gis=a.gis,layout_only=True))
        finish_design(a.out)
    else:finish_compose(a.out)
