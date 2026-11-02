"""Fit complete current port/town plots before final planting and verification."""
import argparse
import copy,json
from pathlib import Path
import numpy as np
from hakone_earthworks import grade_ground,road_blocks
from prepare_hakone_south_shore import read_arrays,joint_street_grades
from author_hakone_district_blocks import Frontage
from prepare_hakone_main_districts import route
from scipy.ndimage import label,distance_transform_edt,maximum_filter


def complete_local_network(candidate,d,layout,manifest):
    """Close short survey gaps around whole plots; defer disconnected far roads.

    The two terminals are public through buildings, with both doorways tested
    by the separate block traversal. Other buildings are routing obstacles.
    """
    if 'network_links'in layout:return
    x0,z0,x1,z1=map(int,d['bounds']);shape=d['walk'].shape
    plots=np.zeros(shape,bool);terminals=np.zeros(shape,bool);obstacles=d['held'].copy()
    for row in layout['buildings']:
        site=row['site'];hx,hz=site['half'];c=Frontage(site)
        a=c.point(-hx-1,0,-hz-1);b=c.point(hx+1,0,hz+3)
        left,right=sorted((a[0],b[0]));north,south=sorted((a[2],b[2]))
        ar=np.s_[north-z0:south-z0+1,left-x0:right-x0+1];plots[ar]=True
        if row.get('kind')=='station':terminals[ar]=True
    obstacles|=plots
    for row in layout['amenities']:
        x,z=row['column'];obstacles[z-z0,x-x0]=True
    public=d['walk']&~plots
    for spec in layout['paving_specs']:
        r=spec['width']//2
        for x,_,z in spec['points']:public[z-z0-r:z-z0+r+1,x-x0-r:x-x0+r+1]=True
    links=[];deferred=[]
    for iteration in range(32):
        labs,n=label(public|terminals);sizes=np.bincount(labs.ravel());sizes[0]=0;main=int(sizes.argmax())
        others=[k for k in range(1,n+1)if k!=main]
        if not others:break
        dist,inds=distance_transform_edt(labs!=main,return_indices=True)
        k=min(others,key=lambda k:float(dist[labs==k].min()))
        zz,xx=np.where(labs==k);order=np.argsort(dist[zz,xx]);minimum=float(dist[zz[order[0]],xx[order[0]]])
        bounds=[int(xx.min()+x0),int(zz.min()+z0),int(xx.max()+x0),int(zz.max()+z0)]
        if minimum>32:
            scope=manifest['construction_scope']
            if not any(bounds[i]==scope[i]for i in range(4)):
                raise ValueError(('An internal street needs a designed regional connection',bounds,minimum))
            remove=labs==k;d['walk'][remove]=False;d['road'][remove]=False;public[remove]=False
            deferred.append(dict(bounds=bounds,columns=int(remove.sum()),reason='Separate regional corridor beyond this port programme; not composed'))
            continue
        width=5 if d['road'][labs==k].any()else 3;r=width//2
        blocked=maximum_filter(obstacles,size=width)>0;found=None
        for i in order[:500]:
            iz,ix=int(zz[i]),int(xx[i]);tz,tx=map(int,inds[:,iz,ix])
            if blocked[iz,ix]or blocked[tz,tx]:continue
            path=route((ix+x0,iz+z0),(tx+x0,tz+z0),blocked,list(map(int,d['bounds'])),12000)
            if path and len(path)<=96:found=path;break
        if found is None:raise ValueError(('No full-width local street connection',bounds,minimum))
        sx,sz=found[0];ex,ez=found[-1];Y=int((d['road2'][sz-z0,sx-x0]+1)//2);E=int((d['road2'][ez-z0,ex-x0]+1)//2)
        points=[[x,round(Y+(E-Y)*i/max(1,len(found)-1)),z]for i,(x,z)in enumerate(found)]
        spec=dict(points=points,width=width,material='minecraft:black_concrete'if width==5 else'minecraft:smooth_stone',role='local-road'if width==5 else'local-link')
        links.append(spec);layout['paving_specs'].append(spec);layout['approaches'].append(points)
        for x,_,z in points:
            ar=np.s_[z-z0-r:z-z0+r+1,x-x0-r:x-x0+r+1];public[ar]=True;d['walk'][ar]=True
            if width==5:d['road'][ar]=True
    else:raise ValueError('Local network closure did not converge')
    layout['network_links']=links;manifest['deferred_regional_roads']=deferred
    (candidate/'valley-buildings.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2),'utf8')
    (candidate/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    np.savez_compressed(candidate/'valley-surface.npz',**d)
    print('Closed local gaps:',len(links),'deferred external road fragments:',len(deferred),flush=True)


def design(candidate):
    d=read_arrays(candidate/'valley-surface.npz');q=read_arrays(candidate/'current-grading.npz')
    layout=json.loads((candidate/'valley-buildings.json').read_text('utf8'))
    manifest=json.loads((candidate/'manifest.json').read_text('utf8'))
    complete_local_network(candidate,d,layout,manifest)
    x0,z0,x1,z1=map(int,d['bounds'])
    developed=d['walk'].copy();desired=d['road2'].copy();fixed=np.zeros(developed.shape,bool);sections=[]
    pins=np.zeros(desired.shape,np.int16)
    # The first programme entries are the port/cafe public realm; every later
    # village adds exactly one frontage approach. Keep the level quay/bus areas.
    for index,row in enumerate(layout['paving_specs']):
        radius=row['width']//2
        for point_index,(x,y,z) in enumerate(row['points']):
            area=np.s_[z-z0-radius:z-z0+radius+1,x-x0-radius:x-x0+radius+1]
            developed[area]=True;desired[area]=y*2
            if row.get('role')in ('pier','bay','aisle','forecourt'):
                if np.any(fixed[area]&(pins[area]!=y*2)):raise ValueError('Conflicting fixed public paving')
                fixed[area]=True;pins[area]=y*2
            before=row['points'][max(0,point_index-1)];after=row['points'][min(len(row['points'])-1,point_index+1)]
            tangent=np.array([after[0]-before[0],after[2]-before[2]],float);length=np.linalg.norm(tangent)
            if length:
                normal=np.array([-tangent[1],tangent[0]])/length
                points=np.rint(np.array([x,z])+np.arange(-radius,radius+1)[:,None]*normal).astype(int)
                sections.append({(int(Z-z0),int(X-x0))for X,Z in points})
    plots=np.zeros(developed.shape,bool)
    public={tuple(site['centre']):site['floor']for site in manifest['current_public_sites']}
    groups=[]
    for row in layout['buildings']:
        site=row['site'];x,z=site['centre'];hx,hz=site['half'];frame=Frontage(site)
        first=frame.point(-hx-1,0,-hz-1);last=frame.point(hx+1,0,hz+3)
        X0,X1=sorted((first[0],last[0]));Z0,Z1=sorted((first[2],last[2]))
        area=np.s_[Z0-z0:Z1-z0+1,X0-x0:X1-x0+1];groups.append(area)
        if plots[area].any():raise ValueError('Whole building plots overlap')
        plots[area]=True;developed[area]=True;desired[area]=site['floor']*2
        if (x,z)in public:
            value=public[x,z]*2
            if np.any(fixed[area]&(pins[area]!=value)):raise ValueError('Public building crosses a different fixed level')
            fixed[area]=True;pins[area]=value
    # A later sloping approach must never overwrite the surveyed quay/bay
    # elevation merely because its footprint overlaps the fixed surface.
    desired[fixed]=pins[fixed]
    # Include transverse road constraints as contiguous rows and columns of the
    # already fitted carriageway: preserve its surveyed width grade envelope.
    for row in manifest['streets']:
        if row['tunnel']or not row['width']:continue
        from shapely.geometry import LineString
        line=LineString(row['points']);radius=row['width']/2+1.5
        for distance in np.arange(1,line.length,2):
            p=np.asarray(line.interpolate(distance).coords[0]);x,z=np.rint(p).astype(int)
            if not(x0+10<=x<=x1-10 and z0+10<=z<=z1-10 and d['walk'][z-z0,x-x0]):continue
            tangent=np.asarray(line.interpolate(min(distance+1,line.length)).coords[0])-np.asarray(line.interpolate(max(distance-1,0)).coords[0]);length=np.linalg.norm(tangent)
            if not length:continue
            normal=np.array([-tangent[1],tangent[0]])/length
            points=np.rint(p+np.linspace(-radius,radius,int(row['width'])+4)[:,None]*normal).astype(int)
            section={(int(Z-z0),int(X-x0))for X,Z in points if d['walk'][Z-z0,X-x0]}
            if len(section)>1:sections.append(section)
    # Pier/bridge deck levels are independent of lake-bed earthwork limits.
    spanning=q['water']|d['bridge']
    grade,passes=joint_street_grades(desired,developed,fixed,sections,groups,
        minimum=np.where(spanning,-30000,(q['old_ground']-12+1)*2),
        maximum=np.where(spanning,30000,(q['old_ground']+12+1)*2))
    height=road_blocks(grade)[0].astype(np.int16)
    bridge=d['bridge']&((height-q['old_ground']>2)|q['water'])
    anchors=developed&~q['water']&~bridge
    ground,conflicts=grade_ground(q['old_ground'],anchors,height-1,slope=1.0)
    if conflicts.any():
        points=[[int(x+x0),int(z+z0),int(height[z,x]),bool(plots[z,x]),bool(anchors[z,x])]
                for z,x in np.argwhere(conflicts)]
        (candidate/'plot-grade-conflicts.json').write_text(json.dumps(points,indent=2),'utf8')
        raise ValueError(('Complete plots and public paths conflict',len(points),points[:8]))
    ground[q['water']|bridge]=q['old_ground'][q['water']|bridge]
    active=ground!=q['old_ground']
    if any(edge.any()for edge in(active[0],active[-1],active[:,0],active[:,-1])):
        raise ValueError('Final plot slope reaches the source edge')
    np.savez_compressed(candidate/'final-grading.npz',bounds=d['bounds'],ground=ground,
        developed=developed,plots=plots,grade2=grade,active=active,water=q['water'],bridge=bridge)
    revised=copy.deepcopy(layout)
    for row in revised['buildings']:
        x,z=row['site']['centre'];old=row['site']['floor'];new=int(grade[z-z0,x-x0])//2
        row['site']['floor']=new;row['floor_shift']=new-old
    (candidate/'regraded-layout.json').write_text(json.dumps(revised,ensure_ascii=False,indent=2),'utf8')
    report=dict(buildings=len(layout['buildings']),public_paving_specs=len(layout['paving_specs']),
        developed_columns=int(developed.sum()),earthwork_columns=int(active.sum()),
        maximum_earthwork=int(abs(ground-q['old_ground'])[active].max(initial=0)),
        source_edges_unchanged=True,water_beds_unchanged=True,composed=False,
        envelope_passes=passes,moved_buildings=sum(bool(r['floor_shift'])for r in revised['buildings']),
        maximum_building_shift=max(abs(r['floor_shift'])for r in revised['buildings']))
    (candidate/'final-grading.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report),flush=True)


def compose(candidate):
    if any((candidate/'delta').glob('*.npz')):
        raise ValueError('Compose the solved layout into a fresh candidate, never over an old town')
    from prepare_hakone_south_shore import compose as compose_streets
    from author_hakone_south_ports import author
    final=read_arrays(candidate/'final-grading.npz');q=read_arrays(candidate/'current-grading.npz')
    surface=read_arrays(candidate/'valley-surface.npz')
    if np.any(final['active']&surface['protected']):raise ValueError('Plot slopes enter retained objects')
    surface.update(target=final['ground'],road2=final['grade2'],bridge=final['bridge'])
    # Road polygons underneath new plots are superseded by the public building
    # programme; do not claim a vehicle lane through the ticket room.
    surface['walk']&=~final['plots'];surface['road']&=surface['walk']
    layout=json.loads((candidate/'regraded-layout.json').read_text('utf8'))
    x0,z0,_,_=map(int,final['bounds'])
    # The port programme replaces the old road alignment inside each waiting
    # forecourt. Explicit seven-wide bay links lead outside these precincts.
    for left,north,right,south in layout['forecourt_zones']:
        surface['road'][north-z0:south-z0+1,left-x0:right-x0+1]=False
    for spec in layout['paving_specs']:
        if spec['role']not in('bay','bus-approach'):continue
        radius=spec['width']//2
        for x,_,z in spec['points']:
            surface['road'][z-z0-radius:z-z0+radius+1,x-x0-radius:x-x0+radius+1]=True
    for row in layout['amenities']:
        x,z=row['column'];surface['walk'][z-z0,x-x0]=False;surface['road'][z-z0,x-x0]=False
    q.update(ground=final['ground'],active=final['active'])
    np.savez_compressed(candidate/'valley-surface.npz',**surface)
    np.savez_compressed(candidate/'current-grading.npz',**q)
    compose_streets(argparse.Namespace(out=candidate,gis=candidate.parent.parent,skip_author=True))
    author(argparse.Namespace(candidate=candidate,gis=candidate.parent.parent))
    path=candidate/'manifest.json';manifest=json.loads(path.read_text('utf8'))
    manifest['final_plot_slopes_composed']=True
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    path=candidate/'final-grading.json';report=json.loads(path.read_text('utf8'))
    report.update(composed=True,final_cells=manifest['cells'])
    path.write_text(json.dumps(report,indent=2),'utf8')
    print('Composed solved street, whole plots and public programme:',manifest['cells'],'changes',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--phase',choices=('design','compose'),required=True)
    a=p.parse_args();{'design':design,'compose':compose}[a.phase](a.candidate)
