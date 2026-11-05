"""Independent local safety review of the finite airport infill proposal.

No real-world files are opened. Scope is rebuilt from fixed existing station
interiors and measured floor/roof states, rather than trusting proposed columns.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import nbtlib
import numpy as np
from scipy import ndimage

from map_pipeline.station_sections import StationSections

SOIL={'minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]'}
AIR={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:light','minecraft:structure_void'}
DECK={'projectseele:nerv_floor_panel','projectseele:period_station_floor'}
PANEL='projectseele:nerv_structural_panel'
ROOMS=[(365,39,477,81,72,83,'terminal'),(435,18,669,28,72,79,'gallery'),
       (437,28,445,38,72,79,'gallery_link'),(490,73,506,155,72,79,'concourse'),
       (477,71,506,79,72,79,'concourse_link'),(490,80,506,80,72,79,'doorway'),
       (495,105,667,121,104,111,'platform'),(495,135,667,151,104,111,'platform')]


def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')


class MergedSections:
    def __init__(self,latest,context):self.latest=StationSections(latest);self.context=StationSections(context)
    def state(self,x,y,z):
        state=self.latest.state(x,y,z)
        return state if state is not None else self.context.state(x,y,z)
    def box(self,bounds):
        old,pal=self.context.box(bounds);new,names=self.latest.box(bounds);ids={s:i for i,s in enumerate(pal)};mapping=[]
        for s in names:
            if s not in ids:ids[s]=len(pal);pal.append(s)
            mapping.append(ids[s])
        mask=new!=0;old[mask]=np.asarray(mapping,np.uint16)[new[mask]]
        return old,pal


def scope(reader):
    allowed=set();columns=[]
    def add(x,z,f,c,kind,roof=True):
        bearing=reader.state(x,f,z);cap=reader.state(x,c,z) if roof else None
        good=bearing in DECK or kind=='platform' and bearing=='projectseele:station_tactile_warning' or kind=='doorway' and bearing==PANEL
        if kind=='gallery':good=good or (bearing or '').startswith('mtr:escalator_step[') and 'orientation=flat' in bearing
        if kind=='stair':good=good or bearing==PANEL or (bearing or '').startswith(('minecraft:smooth_quartz_stairs[','mtr:escalator_step['))
        if not good:return
        if roof and cap!=PANEL and not (cap or '').startswith('projectseele:nerv_strip_light'):return
        allowed.update((x,y,z)for y in range(f+1,c));columns.append(dict(x=x,z=z,floor=f,roof=c,bearing=bearing,cap=cap,kind=kind,roof_required=roof))
    for x,z,X,Z,f,c,k in ROOMS:
        for xx in range(x,X+1):
            for zz in range(z,Z+1):add(xx,zz,f,c,k)
    for z0 in (108,138):
        for n in range(38):
            f=72+max(0,min(32,n-1))
            for zz in range(z0,z0+8):add(498+n,zz,f,f+5,'stair')
    for xx in range(668,671):
        for zz in range(-2,24):add(xx,zz,72,78,'outside_boarding_approach',False)
    return allowed,columns


def validate(edits,reader,allowed,devices):
    errors=[];seen=set()
    for e in edits:
        p=tuple(e['pos']);observed=reader.state(*p)
        if p in seen:errors.append(['duplicate',list(p)])
        seen.add(p)
        if observed!=e['before']:errors.append(['source_precondition',list(p),observed,e['before']])
        hanger=p[0]==517 and 96<=p[1]<=101 and p[2] in (107,116) and observed=='minecraft:air' and e['after']=='projectseele:nerv_machine_edge'
        x,y,z=p
        gallery_wall=(435<=x<=669 and z==29 or x==670 and 18<=z<=28) and 73<=y<=78 and reader.state(x,72,z)==PANEL and reader.state(x,79,z)==PANEL
        retaining=(x==671 and 14<=z<=23 or x==667 and 14<=z<=16) and 73<=y<=77 and reader.state(x,72,z)=='projectseele:nerv_floor_panel'
        lining=(gallery_wall or retaining) and observed in SOIL and e['after']=='projectseele:nerv_wall_panel'
        if hanger and (reader.state(517,95,p[2])!=PANEL or reader.state(517,102,p[2])!=PANEL):errors.append(['missing_hanger_anchors',list(p)])
        if not hanger and not lining and (observed not in SOIL or e['after']!='minecraft:air'):errors.append(['non_natural_or_non_air_edit',list(p),observed,e['after']])
        if p not in allowed and not hanger and not lining:errors.append(['outside_measured_interior',list(p)])
        if p in devices:errors.append(['device_host',list(p)])
    return errors


def spatial_review(reader,edits):
    bounds=[352,48,-16,687,143,175];x,y,z,X,Y,Z=bounds
    before,palette=reader.box(bounds);after=before.copy()
    changed=np.zeros(before.shape,bool)
    for e in edits:
        xx,yy,zz=e['pos']
        if e['after'] not in palette:palette.append(e['after'])
        after[yy-y,zz-z,xx-x]=palette.index(e['after']);changed[yy-y,zz-z,xx-x]=True
    known=before!=0
    solid_lookup=np.array([s.split('[')[0]not in AIR and s!='__unavailable__' for s in palette])
    bsolid=solid_lookup[before]&known;asolid=solid_lookup[after]&known
    structure=ndimage.generate_binary_structure(3,1)
    bl,bn=ndimage.label(bsolid,structure);al,an=ndimage.label(asolid,structure)
    natural=np.array([s in SOIL for s in palette]);rooted_b=set(map(int,np.unique(bl[0][natural[before[0]]])))
    rooted_a=set(map(int,np.unique(al[0][natural[after[0]]])))
    def boundary(labels):
        return set(map(int,np.unique(np.concatenate([labels[-1].ravel(),labels[:,0,:].ravel(),labels[:,-1,:].ravel(),labels[:,:,0].ravel(),labels[:,:,-1].ravel()]))))
    boundary_b,boundary_a=boundary(bl),boundary(al)
    removed=changed&~asolid
    adjacent=ndimage.binary_dilation(removed,structure)&asolid
    impacted=set(map(int,np.unique(al[adjacent])))-{0};new_unrooted=[];continued=[]
    for label in sorted(impacted):
        points=np.argwhere(al==label);representative=tuple(points[0]);old=int(bl[representative])
        if label in rooted_a:continue
        row=dict(cells=len(points),example=[int(points[0,2])+x,int(points[0,0])+y,int(points[0,1])+z])
        if label in boundary_a:continued.append(row)
        elif old in rooted_b or old in boundary_b:new_unrooted.append(row)
    changed_columns=np.argwhere(removed.any(0));vertical_openings=[]
    for iz,ix in changed_columns:
        removed_y=np.flatnonzero(removed[:,iz,ix]);top=int(removed_y.max())
        if not asolid[top+1:,iz,ix].any():
            vertical_openings.append(dict(x=int(ix)+x,z=int(iz)+z,removed_y=[int(removed_y.min())+y,top+y],
                kind='existing_outdoor_boarding_approach' if 668<=ix+x<=670 and -2<=iz+z<=23 else 'uncapped_interior'))
    # New vertical natural faces can reveal a narrow trench beside the outside
    # approach or residual infill inside a room. Report all runs of >=3 blocks.
    wall_runs=[]
    for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
        neighbor=np.roll(after,(-dz,-dx),(1,2));faces=removed&natural[neighbor]
        if dx==1:faces[:,:,-1]=False
        if dx==-1:faces[:,:,0]=False
        if dz==1:faces[:,-1,:]=False
        if dz==-1:faces[:,0,:]=False
        for iz,ix in np.argwhere(faces.any(0)):
            yy=np.flatnonzero(faces[:,iz,ix]);groups=np.split(yy,np.flatnonzero(np.diff(yy)!=1)+1)
            for run in groups:
                if len(run)>=3:wall_runs.append(dict(air_column=[int(ix)+x,int(iz)+z],face=[dx,dz],y=[int(run[0])+y,int(run[-1])+y],height=len(run)))
    return dict(bounds=bounds,all_cells_known=bool(known.all()),before_components=int(bn),after_components=int(an),
        impacted_remaining_components=len(impacted),new_unrooted_components=new_unrooted,
        remaining_components_continuing_outside_crop=continued,
        support_check='six-face voxel connectivity; existing outside-crop continuations are not declared fully supported',
        newly_sky_open_columns=vertical_openings,new_natural_vertical_faces=wall_runs,
        local_only=True,global_floating_block_review_not_replaced=True)


def review(a):
    a.out.mkdir(exist_ok=False)
    reader=MergedSections(a.source,a.context);allowed,columns=scope(reader)
    edits=json.loads((a.proposal/'proposed-edits.json').read_text('utf8'))
    tags=nbtlib.load(a.source/'devices.dat')['Devices'];devices={tuple(int(t[k])for k in('x','y','z'))for t in tags}
    errors=validate(edits,reader,allowed,devices)
    if errors:raise ValueError(str(errors[:3]))
    negative=[]
    for name,pos in [('delete_floor',(496,72,111)),('delete_roof',(496,79,111)),('delete_stair',(520,93,111)),('outside_natural',(360,73,100))]:
        old=reader.state(*pos)
        if old is None:raise ValueError('Negative test position unknown')
        fault=dict(pos=list(pos),before=old,after='minecraft:air')
        rejected=validate(edits+[fault],reader,allowed,devices)
        if not rejected:raise ValueError('Injected invalid edit accepted: '+name)
        negative.append(dict(case=name,edit=fault,rejected=True,reasons=rejected))
    spatial=spatial_review(reader,edits)
    result=dict(errors=errors,changes=len(edits),source=str(a.source),context=str(a.context),proposal=str(a.proposal),
        guarded_columns=columns,device_hosts_checked=len(devices),negative_cases=negative,spatial=spatial,
        world_opened=False,world_written=False,whole_map_accepted=False)
    write(a.out/'review.json',result)
    print('Independent airport check:',len(edits),'edits;',len(negative),'negative cases rejected')
    print('Local spatial: new unrooted',len(spatial['new_unrooted_components']),'sky openings',len(spatial['newly_sky_open_columns']),'new natural wall runs',len(spatial['new_natural_vertical_faces']))


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('source','context','proposal','out'):p.add_argument('--'+n,type=Path,required=True)
    review(p.parse_args())
