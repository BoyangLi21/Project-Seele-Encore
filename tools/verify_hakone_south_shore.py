"""Read every southern shore street/path column and complete plot interface.

This consumes final block arrays independently of the author. It never starts
the client, mutates a world, or treats a centreline walk as a width proof.
"""
import argparse,json
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.ndimage import label
from author_hakone_lakefront import Editor
from prepare_hakone_south_shore import read_arrays
from hakone_earthworks import road_blocks
from author_hakone_district_blocks import Frontage


def verify(candidate):
    d=read_arrays(candidate/'valley-surface.npz');q=read_arrays(candidate/'current-grading.npz')
    final=read_arrays(candidate/'final-grading.npz')
    layout=json.loads((candidate/'valley-buildings.json').read_text('utf8'))
    manifest=json.loads((candidate/'manifest.json').read_text('utf8'))
    e=Editor(candidate);x0,z0,x1,z1=map(int,d['bounds']);errors=[];counts=Counter()
    road=d['walk'].copy();public=road.copy();required=np.where(road,np.where(d['road'],5,3),0).astype(np.uint8)
    for spec in layout['paving_specs']:
        radius=spec['width']//2;clearance=5 if spec['role']in('bay','bus-approach')else 3
        for x,_,z in spec['points']:
            area=np.s_[z-z0-radius:z-z0+radius+1,x-x0-radius:x-x0+radius+1]
            public[area]=True;required[area]=np.maximum(required[area],clearance)
    full={'minecraft:black_concrete','minecraft:smooth_stone','minecraft:spruce_planks'}
    slabs={'projectseele:road_asphalt_slab','minecraft:smooth_stone_slab','minecraft:spruce_slab'}
    air={'minecraft:air','minecraft:cave_air','minecraft:void_air'}
    def error(kind,*details):
        counts[kind]+=1
        if len(errors)<200:errors.append([kind,*details])
    def empty(state):return state.split('[')[0]in air or state.split('[')[0].endswith('_wall_sign')
    for iz,ix in np.argwhere(public):
        x,z=int(ix+x0),int(iz+z0);y,slab=map(int,road_blocks(d['road2'][iz,ix]));state=e.state(x,y,z)
        name=state.split('[')[0]
        if name not in(slabs if slab else full)or(slab and 'type=bottom'not in state):
            error('paving-height-or-material',x,y,z,state,int(d['road2'][iz,ix]))
        for Y in(y-1,y-2):
            state=e.state(x,Y,z)
            if empty(state)or state.split('[')[0]in('minecraft:water','minecraft:lava'):
                error('unsupported-paving',x,Y,z,state)
        for Y in range(y+1,y+1+int(required[iz,ix])):
            state=e.state(x,Y,z)
            if not empty(state):error('public-headroom',x,Y,z,state,int(required[iz,ix]))
    for x,bed,z,top in layout['supports']:
        for y in range(bed+1,top+1):
            if e.state(x,y,z).split('[')[0]not in('minecraft:stone_bricks','minecraft:stone'):
                error('pier-pile-gap',x,y,z)
        if e.state(x,bed,z).split('[')[0]in air|{'minecraft:water'}:error('pier-bed-gap',x,bed,z)
    for amenity in layout['amenities']:
        x,z=amenity['column']
        for y in range(amenity['bed']+1,amenity['top']+1):
            if empty(e.state(x,y,z)):error('amenity-support-gap',amenity['kind'],x,y,z)
    bridge_piles=0
    for iz,ix in np.argwhere(d['bridge']&d['walk']):
        x,z=int(ix+x0),int(iz+z0)
        if (x+z)%12:continue
        y=int((d['road2'][iz,ix]+1)//2);bed=int(final['ground'][iz,ix]);bridge_piles+=1
        for Y in range(bed+1,y-1):
            if e.state(x,Y,z).split('[')[0]not in('minecraft:stone','minecraft:stone_bricks'):
                error('bridge-pile-gap',x,Y,z)
    if np.any(public&final['water']&(d['road2']<200)):error('public-deck-below-lake')
    ground=final['ground'];active=final['active'];dry=~final['water']
    # Read the soil under every changed exterior column, below any new trees.
    exterior=active&~final['developed']&dry
    for iz,ix in np.argwhere(exterior):
        x,z=int(ix+x0),int(iz+z0);y=int(ground[iz,ix])
        if e.state(x,y,z).split('[')[0]not in('minecraft:grass_block','minecraft:dirt'):
            error('external-ground',x,y,z,e.state(x,y,z))
    interface_edges=0
    for axis in(0,1):
        A=[slice(None)]*2;B=A.copy();A[axis]=slice(1,None);B[axis]=slice(None,-1);A,B=tuple(A),tuple(B)
        boundary=(final['developed'][A]^final['developed'][B])&dry[A]&dry[B]
        interface_edges+=int(boundary.sum())
        if np.any(boundary&(abs(ground[A]-ground[B])>1)):
            error('whole-plot-soil-step',axis,int((boundary&(abs(ground[A]-ground[B])>1)).sum()))
        shared=public[A]&public[B]
        if np.any(shared&(abs(d['road2'][A]-d['road2'][B])>1)):
            error('public-half-step',axis,int((shared&(abs(d['road2'][A]-d['road2'][B])>1)).sum()))
    if np.any(ground[final['water']]!=q['old_ground'][final['water']]):error('changed-water-bed')
    if np.any(active[[0,-1]])or np.any(active[:,[0,-1]]):error('source-edge-earthwork')
    if int(abs(ground-q['old_ground']).max())>12:error('earthwork-limit')
    components,n=label(public);sizes=np.bincount(components.ravel())[1:]
    road_goals=[]
    through=public.copy()
    for row in layout['buildings']:
        x,_,z=row['road'];road_goals.append(int(components[z-z0,x-x0]))
        if not road[z-z0,x-x0]:error('building-goal-is-not-a-street',row['label'],x,z)
        if row.get('kind')=='station':
            site=row['site'];hx,hz=site['half'];c=Frontage(site)
            # The independent room traversal proves this public terminal's
            # front and rear doors; only those terminals join outside paths.
            a=c.point(-hx,0,-hz);b=c.point(hx,0,hz)
            left,right=sorted((a[0],b[0]));north,south=sorted((a[2],b[2]))
            through[north-z0:south-z0+1,left-x0:right-x0+1]=True
            for local_x in range(-2,3):
                for y in(1,2,3):
                    p=c.point(local_x,y,-hz)
                    if not empty(e.state(*p)):error('waterside-door-blocked',*p)
    _,through_components=label(through)
    if through_components!=1:error('unconnected-local-public-network',int(through_components))
    report=dict(errors=errors,error_counts=dict(counts),streets=[dict(id='HS-SOUTH',full_width_columns=int(road.sum()))],
        public_columns=int(public.sum()),public_path_specs=len(layout['paving_specs']),exterior_soil_columns=int(exterior.sum()),
        whole_plot_interface_edges=interface_edges,pile_columns=len(layout['supports']),
        bridge_pile_columns=bridge_piles,through_terminal_components=int(through_components),
        public_components=int(n),component_sizes=sorted(map(int,sizes),reverse=True),building_goal_components=sorted(set(road_goals)),
        source_edges_unchanged=not any(k.startswith('source-edge')for k in counts),water_beds_unchanged='changed-water-bed'not in counts,
        maximum_earthwork=int(abs(ground-q['old_ground']).max()),global_north_connection_pending=True,visual_verified=False)
    (candidate/'independent-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k not in('component_sizes','errors')},ensure_ascii=False),flush=True)
    if errors:
        print(json.dumps(errors[:12],ensure_ascii=False),flush=True)
        raise ValueError('The final shoreline geometry is not ready')
    # Publish the finite compiled corridor inventory required by the installer.
    # The surveyed input lines stay available separately for future extensions.
    manifest.setdefault('survey_streets',manifest['streets'])
    manifest['streets']=[dict(id='HS-SOUTH',status='prepared',walk_columns=int(road.sum()))]
    manifest['candidate_kind']='southern_shore_whole_plots'
    (candidate/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (candidate/'authored-design.json').write_text(json.dumps(dict(streets=[dict(id='HS-SOUTH',tunnel=False,
        description='Current-source southern lake streets, graded whole plots and public port access')]),indent=2),'utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True)
    verify(p.parse_args().candidate)
