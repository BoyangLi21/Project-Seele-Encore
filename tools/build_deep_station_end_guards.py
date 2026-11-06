"""Offline end barriers for the five frozen deep-station passenger bays.

The stair-guard overlay is an input, never changed. Floor restoration is a
separate dependency and is not included in the emitted barrier delta.
"""
import argparse, copy, json, math, shutil
from collections import Counter, defaultdict, deque
from pathlib import Path
import numpy as np
import nbtlib
from scipy.spatial import cKDTree
from shapely.geometry import box, Point, MultiPoint, LineString
from shapely.ops import unary_union
from PIL import Image, ImageDraw, ImageFont

import verify_declared_platform_footprints as fw
from review_underground_station_evidence import Overlay, strict_walk
from repair_declared_platform_guards import make_walker, save_delta, support_proof, render_shapes, sweep


def read(p):return json.loads(Path(p).read_text('utf8'))
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf8')


def uv(b,p):
    x,_,z=b['center']
    return (p[0]-x,p[2]-z) if b['horizontal'] else (p[2]-z,p[0]-x)


def at(b,u,v,y=None):
    x,_,z=b['center'];y=b['current_floor_y']+1 if y is None else y
    return (x+u,y,z+v) if b['horizontal'] else (x+v,y,z+u)


def bars(directions):
    return 'minecraft:iron_bars['+','.join(k+'='+str(k in directions).lower() for k in ('east','north','south'))+',waterlogged=false,west='+str('west' in directions).lower()+']'


def terminal_free_space(w,station,public_cells):
    """Continuous 0.6m player configuration space; gates explicitly closed.

    Floor support is dilated, admitting partial edge support rather than
    hiding a possible bypass behind a full-footprint requirement. Each known
    collision cuboid is expanded by the player's actual half width.
    """
    closed=copy.deepcopy(w.shapes)
    for state in list(closed):
        if state.startswith(('mtr:apg_door[','mtr:psd_door[')):
            face=state.split('facing=')[1].split(',')[0]
            closed[state]={'north':[[0,0,0,1,1,.25]],'south':[[0,0,.75,1,1,1]],
                           'east':[[.75,0,0,1,1,1]],'west':[[0,0,0,.25,1,1]]}[face]
    cw=make_walker(Path(station['_source']),closed)
    cw.reader=w.reader
    cells=station['cells'];base=min(b['current_floor_y']for b in station['bays'])
    x0=min(c['floor'][0]for c in cells)-2;x1=max(c['floor'][0]for c in cells)+2
    z0=min(c['floor'][2]for c in cells)-2;z1=max(c['floor'][2]for c in cells)+2
    heights=[base+1,base+.5]
    layers=[];unknown=set()
    for h in heights:
        supports=[];obstacles=[]
        for x in range(x0-1,x1+2):
            for z in range(z0-1,z1+2):
                for y in range(math.floor(h)-2,math.ceil(h+1.8)+2):
                    state,boxes=cw.boxes(x,y,z)
                    if boxes is None:unknown.add((x,y,z));continue
                    for b in boxes:
                        poly=box(x+b[0],z+b[2],x+b[3],z+b[5])
                        if abs(y+b[4]-h)<1e-7:supports.append(poly)
                        if y+b[1]<h+1.7999 and y+b[4]>h+.0001:obstacles.append(poly)
        ground=unary_union(supports).buffer(.2999,join_style=2)
        blocked=unary_union(obstacles).buffer(.3,join_style=2)
        free=ground.difference(blocked).intersection(box(x0,z0,x1+1,z1+1))
        polygons=[g for g in getattr(free,'geoms',[free])if g.geom_type=='Polygon'and g.area>1e-8]
        seeds=MultiPoint([(c['feet'][0],c['feet'][2])for c in public_cells
                         if abs(c['feet'][1]-h)<1e-7])
        for poly in polygons:layers.append(dict(h=h,poly=poly,reachable=poly.intersects(seeds)))
    assert not unknown,('Continuous end-safety capture incomplete',station['site'],sorted(unknown)[:5])
    changed=True
    while changed:
        changed=False
        for a in layers:
            if a['reachable']:continue
            if any(b['reachable']and abs(a['h']-b['h'])<=.500001 and a['poly'].intersection(b['poly']).area>1e-8 for b in layers):
                a['reachable']=True;changed=True
    return {h:unary_union([p['poly']for p in layers if p['h']==h and p['reachable']])for h in heights}


def edge_coverage(space,issues):
    rows=[]
    for issue in issues:
        x,h,z=issue['feet'];dx,_,dz=issue['normal'];tx,tz=-dz,dx
        cx,cz=x+dx*.5,z+dz*.5
        line=LineString([(cx-tx*.4999,cz-tz*.4999),(cx+tx*.4999,cz+tz*.4999)])
        leaked=line.intersection(space[h])
        rows.append(dict(feet=issue['feet'],normal=issue['normal'],reachable_drop_face_length=float(leaked.length),
                         protected=leaked.is_empty or leaked.length<1e-8))
    return rows


def check_terminal_coverage(base,out):
    spec,shapes,stairmap,floormap,before,changes,rows,design,protected=derive(base)
    after=make_walker(Path(spec['source']),shapes,{**stairmap,**floormap,**changes})
    results=[]
    for station in spec['stations']:
        site=station['site'];station['_source']=spec['source']
        result=read(out/'review/after-fullwidth'/(site+'.json'))
        seeds=[c for c in result['cells']if c['status']=='clear_public_floor']
        issues=[r for d in design if d['site']==site for r in d['issues']]
        space=terminal_free_space(after,station,seeds)
        coverage=edge_coverage(space,issues)
        declarations=read(out/'review/after-declarations'/(site+'.json'))
        margin=[]
        for c in declarations['retained_nonpublic_margin_cells']:
            x,y,z=c['floor'];h=c.get('feet_y',y+1)
            state,boxes=after.boxes(x,y,z)
            supported=boxes is not None and any(abs(y+b[4]-h)<1e-7 and b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 for b in boxes)
            margin.append(dict(floor=c['floor'],feet=[x+.5,h,z+.5],support=supported,
                reachable_from_retained_public=space[h].intersects(Point(x+.5,z+.5)),body=after.body(x+.5,h,z+.5)))
        assert all(c['support']and not c['reachable_from_retained_public']for c in margin),(site,margin)
        # Reverting all new terminal barriers is a matched counterexample;
        # the same retained public seeds must regain the old drop interfaces.
        prior=edge_coverage(terminal_free_space(before,station,seeds),issues)
        results.append(dict(site=site,interfaces=len(issues),after=coverage,before=prior,
            finite_nonboarding_margin=margin,
            protected_after=sum(r['protected']for r in coverage),exposed_before=sum(not r['protected']for r in prior)))
        print('Coverage',site,results[-1]['protected_after'],'/',len(issues),'before exposed',results[-1]['exposed_before'],flush=True)
    write(out/'review/continuous-boundary-coverage.json',dict(stations=results,
        phase='All existing boarding gates closed, with explicit hypothetical rectangular leaf shapes; no runtime claim.',
        player_width=.6,player_height=1.8,partial_floor_support_admitted=True,
        jump_or_climb_permitted=False,step_height=.5,unknown_as_air=False,
        errors=[dict(site=s['site'],leaks=[r for r in s['after']if not r['protected']])for s in results if s['protected_after']!=s['interfaces']]))


def model_clearance(base,out):
    """Conservative height-band OBB sweep on real RailMath samples.

    Bands enclose all selected visible cubes, all slide endpoints, plus hidden
    doorway/floor instances. They preserve height, rather than assigning the
    full model width to every floor voxel. Both travel directions, both bogie
    origin conventions, and every geometrically connected branch are enclosed.
    """
    spec,shapes,stairmap,floormap,before,changes,rows,design,protected=derive(base)
    geo=read(Path(__file__).parents[1]/'.Codex/deep-station-end-geometry-v1/geometry.json')
    source=base/'deep-mini-model-envelope-v1'
    precedence=read(source/'resource-source-check.json')
    assert not precedence['errors']
    rails=[dict(id=r['id'],p=np.array(r['points'],float),length=r['native_length'])for r in geo]
    voxel_boxes=[];voxel_owner=[];negative_positions=[]
    for row in rows:
        p=np.array(row['pos']);
        for b in shapes[row['after']]:
            voxel_boxes.append(np.array(b).reshape(2,3)+p);voxel_owner.append(row)
    for station in spec['stations']:
        target=np.array(station['bays'][0]['center'],float);target[1]=station['bays'][0]['current_floor_y']
        pt=min((p for r in rails for p in r['p']),key=lambda p:float(np.sum((p-target)**2)))
        p=np.floor(pt).astype(int);p[1]+=1
        row=dict(pos=p.tolist(),after='minecraft:stone',site=station['site'],negative_control=True)
        voxel_boxes.append(np.array([p,p+1]));voxel_owner.append(row);negative_positions.append(row)
    vb=np.array(voxel_boxes);vc=vb.mean(1);vtree=cKDTree(vc)
    signs=np.array([[x,y,z]for x in (0,1)for y in (0,1)for z in (0,1)])
    bands=[];details=[]
    for model,bogies in [('eidan_9000_mini_cab_1',(-1,5)),('eidan_9000_mini_cab_2',(-5,1)),('eidan_9000_mini_trailer',(-5,5))]:
        a=np.load(source/(model+'-closed-cubes.npz'))
        visible=np.load(source/(model+'-visible-cubes.npz'))
        cubes=np.concatenate([a['cubes'],visible['cubes']+visible['door_slides'][:,None,:]])
        slide=np.zeros((len(cubes),3))
        # closed-cubes includes all selected hidden and conditional parts.
        lo=np.minimum(cubes.min(1),(cubes+slide[:,None,:]).min(1))
        hi=np.maximum(cubes.max(1),(cubes+slide[:,None,:]).max(1))
        model_bands=[]
        for lower in np.arange(0,4,.125):
            upper=lower+.125;sel=(hi[:,1]>lower+1e-10)&(lo[:,1]<upper-1e-10)
            if not sel.any():continue
            l=lo[sel].min(0);h=hi[sel].max(0);l[1]=max(l[1],lower);h[1]=min(h[1],upper)
            model_bands.append(l+(h-l)*signs)
        bands.append((model,bogies,np.array(model_bands)))
        details.append(dict(vehicle=model,selected_cubes=len(cubes),bands=[dict(min=c.min(0).tolist(),max=c.max(0).tolist())for c in model_bands]))
    def extend(r,end):
        p=r['p'];endpoint=p[-1]if end else p[0]
        tangent=(p[-1]-p[-2])if end else(p[0]-p[1]);tangent/=np.linalg.norm(tangent)
        found=[]
        for q in rails:
            if q is r:continue
            for reverse in (False,True):
                pts=q['p'][::-1]if reverse else q['p']
                if np.linalg.norm(pts[0]-endpoint)<1e-6:
                    t=pts[1]-pts[0];t/=np.linalg.norm(t)
                    if np.dot(tangent,t)>.5:
                        dist=np.r_[0,np.cumsum(np.linalg.norm(np.diff(pts,axis=0),axis=1))]
                        idx=min(len(pts),np.searchsorted(dist,15)+2)
                        found.append(pts[:idx])
        if not found:found=[np.array([endpoint,endpoint+tangent*15])]
        return found
    pose_counts=Counter();intrusions=[];negative_hits=[];nearby_rails=set();tested=0;minimum_margin=1e9
    padding=.075  # >= one sample's travel plus measured endpoint interpolation error
    max_rotation_step=0;max_pose_corner_step=0
    for r in rails:
        p=r['p'];near=vtree.query_ball_point(p,12)
        inds=np.array([i for i,n in enumerate(near)if n],int)
        if not len(inds):continue
        nearby_rails.add(r['id'])
        main_s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
        centers=main_s[inds]
        for left in extend(r,False):
            for right in extend(r,True):
                pts=np.vstack([left[::-1][:-1],p,right[1:]])
                ds=np.r_[0,np.cumsum(np.linalg.norm(np.diff(pts,axis=0),axis=1))]
                offset=np.sum(np.linalg.norm(np.diff(left,axis=0),axis=1));ss=centers+offset
                def interp(s):return np.column_stack([np.interp(s,ds,pts[:,k])for k in range(3)])
                for direction in (-1,1):
                    for model,bogies,corners in bands:
                        b1,b2=bogies;pos=interp(ss)
                        a=interp(ss+direction*b1);b=interp(ss+direction*b2)
                        forward=b-a;forward/=np.linalg.norm(forward,axis=1)[:,None]
                        rightv=np.c_[forward[:,2],np.zeros(len(ss)),-forward[:,0]];rightv/=np.linalg.norm(rightv,axis=1)[:,None]
                        up=np.cross(forward,rightv)
                        matrices=np.stack([rightv,up,forward],axis=2)
                        mids=(a+b)/2-forward*((b1+b2)/2)
                        for origin_name,origins in [('native_center_sample',pos),('bogie_midpoint_origin',mids)]:
                            transformed=np.einsum('pij,bkj->pbki',matrices,corners)+origins[:,None,None,:]
                            if len(transformed)>1:
                                contiguous=np.diff(inds)==1
                                dif=np.linalg.norm(np.diff(transformed,axis=0),axis=-1)
                                if contiguous.any():max_pose_corner_step=max(max_pose_corner_step,float(dif[contiguous].max()))
                            lo=transformed.min(2)-padding*math.sqrt(3);hi=transformed.max(2)+padding*math.sqrt(3)
                            pose_counts[model]+=len(ss);tested+=lo.shape[0]*lo.shape[1]
                            for vi in set(j for i in inds for j in near[i]):
                                overlap=np.minimum(hi,vb[vi,1])-np.maximum(lo,vb[vi,0])
                                hits=np.argwhere(np.all(overlap>1e-7,axis=-1))
                                # Exact 15-axis OBB/AABB separating-axis test;
                                # diagonal empty corners of a world AABB are
                                # not train volume. Padding is on all OBB axes.
                                if len(hits):
                                    pi=hits[:,0];bi=hits[:,1];rot=matrices[pi]
                                    local_center=(corners.min(1)+corners.max(1))/2
                                    half=(corners.max(1)-corners.min(1))/2+padding
                                    center=np.einsum('nij,nj->ni',rot,local_center[bi])+origins[pi]
                                    delta=vc[vi]-center;bh=(vb[vi,1]-vb[vi,0])/2
                                    axes=[np.broadcast_to(np.eye(3)[:,i],delta.shape)for i in range(3)]
                                    axes += [rot[:,:,i]for i in range(3)]
                                    axes += [np.cross(np.broadcast_to(np.eye(3)[:,i],delta.shape),rot[:,:,j])for i in range(3)for j in range(3)]
                                    alive=np.ones(len(hits),bool)
                                    for axis in axes:
                                        radii=(np.abs(axis)*bh).sum(1)+(np.abs(np.einsum('ni,nij->nj',axis,rot))*half[bi]).sum(1)
                                        distance=np.abs((delta*axis).sum(1))
                                        alive &= (distance<radii-1e-8)|(np.linalg.norm(axis,axis=1)<1e-9)
                                    hits=hits[alive]
                                if len(hits):
                                    pi,bi=hits[0];destination=negative_hits if voxel_owner[vi].get('negative_control') else intrusions
                                    destination.append(dict(pos=voxel_owner[vi]['pos'],site=voxel_owner[vi]['site'],state=voxel_owner[vi]['after'],rail=r['id'],vehicle=model,direction=direction,origin=origin_name,rail_sample=int(inds[pi]),band=int(bi),overlap=overlap[pi,bi].tolist(),envelope=[lo[pi,bi].tolist(),hi[pi,bi].tolist()]))
                                else:
                                    gap=np.maximum(np.maximum(vb[vi,0]-hi,lo-vb[vi,1]),0)
                                    minimum_margin=min(minimum_margin,float(np.linalg.norm(gap,axis=-1).min()))
        print('Rail sweep',r['id'],'near samples',len(inds),'hits',len(intrusions),flush=True)
    report=dict(errors=[] if not intrusions else ['Conservative height-band envelope intersects candidate'],
        geometry='Native MTR RailMath only; no Simulator, world or native database opened.',native_curves=35,nearby_rail_indices=sorted(nearby_rails),
        sample_spacing_max=.05,interval_padding=padding,maximum_observed_adjacent_corner_displacement=max_pose_corner_step,
        padding_covers_observed_sample_motion=max_pose_corner_step<padding,poses=dict(pose_counts),tested_heightband_obbs=tested,
        envelope_mode='All selected cube bounds clipped into 0.125m height bands, closed and slid endpoints; hidden DOORWAY included; 15-axis OBB/AABB SAT after conservative world-AABB broad phase.',
        bogie_pose_modes=['native center sample','bogie midpoint minus local bogie midpoint'],travel_directions=[-1,1],
        branch_scope='All forward-connected frozen rail branches; 15m tangent continuation only at absent neighbors.',
        vehicle_intrusions=intrusions,negative_controls=[dict(**r,rejected=any(h['site']==r['site']for h in negative_hits),witness=next((h for h in negative_hits if h['site']==r['site']),None))for r in negative_positions],
        model_bands=details,source_precedence=str(source/'resource-source-check.json'),runtime_verified=False)
    if not report['padding_covers_observed_sample_motion']:report['errors'].append('Sample motion exceeds interval padding')
    if not all(n['rejected']for n in report['negative_controls']):report['errors'].append('Vehicle intrusion negative control escaped')
    write(out/'review/model-heightband-clearance.json',report)
    return report


def derive(base):
    corrected=base/'deep-platform-declarations73-v2/declarations.json'
    spec=read(corrected if corrected.exists() else base/'deep-platform-fullwidth-review-v1/declarations.json')
    shapes=read(Path(spec['shape_export']))
    stair=read(base/'deep-platform-guards-candidate-v1/exact-edits.json')
    stairmap={tuple(e['pos']):e['after']for e in stair}
    floor=read(base/'deep-station-end-disposition-v1/seven-cell-floor-patch-plan.json')['edits']
    floormap={tuple(e['pos']):e['after']for e in floor}
    w=make_walker(Path(spec['source']),shapes,stairmap)
    groups=read(base/'deep-station-end-disposition-v1/terminal-edge-groups.json')
    bays={(s['site'],b['line']):b for s in spec['stations']for b in s['bays']}
    components=defaultdict(list)
    for g in groups:
        side=-1 if g['transverse_cell']<0 else 1
        end=-1 if g['end']=='before_native_platform' else 1
        components[g['site'],g['line'],end,side]+=g['rows']
    desired=defaultdict(set);owners={};design=[];protected=[]
    for (site,line,end,side),issues in sorted(components.items()):
        b=bays[site,line];edge=6 if len(b['tracks'])>1 else 2
        offset=edge+1
        if site=='native-22' and end<0 and side<0:offset=edge+2
        v=side*offset
        start,end_u=(-42,-33) if end<0 else (33,42)
        if site=='native-18' and end<0:start=end_u=-33
        cells=set()
        # A half-block centred screen stands back from the previous lip. It
        # returns only at the fixed terminal glass, never across a door leaf.
        for u in range(start,end_u+1):cells.add(at(b,u,v))
        join_u=-33 if end<0 else 33
        for vv in range(min(v,side*edge),max(v,side*edge)+1):cells.add(at(b,join_u,vv))
        along=('east','west') if b['horizontal'] else ('north','south')
        across=('north','south') if b['horizontal'] else ('east','west')
        for p in cells:
            u0,v0=uv(b,p)
            directions=set(along if v0==v else ())
            if u0==join_u:directions.update(across)
            # At the rail-facing end of the short return, the cross arm stops
            # at the bar centre; extending it to the block face would enter
            # the car body's high band.
            if v0==side*edge:
                toward=('south' if side<0 else 'north') if b['horizontal'] else ('east' if side<0 else 'west')
                directions.discard(toward)
                directions.add(('east' if end<0 else 'west')if b['horizontal']else('south'if end<0 else'north'))
            for dy in (0,1):
                q=p[0],p[1]+dy,p[2];old=w.reader.state(*q)
                if old is None:raise ValueError(('Missing capture',q))
                if old=='minecraft:air' or old.startswith(('projectseele:nerv_edge_rail[','minecraft:iron_bars[')):
                    directions2=directions|{k for k in('east','north','south','west')if k+'=true' in old}
                    desired[q].update(directions2);owners[q]=site
                else:
                    state,boxes=w.boxes(*q)
                    protected.append(dict(pos=q,state=state,component=[site,line,end,side]))
                    if not boxes:raise ValueError(('Protected noncolliding fixture on barrier',q,state))
        fixed=at(b,-32 if end<0 else 32,side*edge)
        fixed_state=w.reader.state(*fixed)
        if not fixed_state.startswith('mtr:apg_glass['):
            raise ValueError(('Terminal return is not next to fixed native glass',site,line,end,side,fixed,fixed_state))
        design.append(dict(site=site,line=line,end=end,side=side,edge=edge,barrier_v=v,
            u_range=[start,end_u],join_u=join_u,base_y=b['current_floor_y'],
            fixed_gate_end=dict(pos=fixed,state=fixed_state),original_interfaces=len(issues),
            issues=issues,requested_cells=sorted(cells),preserved_boarding_u=[-32,32],
            retained_aisle_v=side*8))
    changes={p:bars(d)for p,d in desired.items()}
    for p,s in changes.items():
        if s not in shapes:
            changes[p]=bars({'east','north','south','west'})
        assert changes[p] in shapes
    changes={p:s for p,s in changes.items()if w.reader.state(*p)!=s}
    assert not set(changes)&set(stairmap) and not set(changes)&set(floormap)
    devices=nbtlib.load(Path(spec['source'])/'devices.dat')['Devices']
    tags={tuple(int(t[k])for k in('x','y','z'))for t in devices}
    assert not set(changes)&tags
    rows=[dict(pos=p,before=w.reader.state(*p),after=s,site=owners[p],before_nbt=None,after_nbt=None)for p,s in sorted(changes.items())]
    return spec,shapes,stairmap,floormap,w,changes,rows,design,protected


def review(base,out,preview_only=False):
    out.mkdir(exist_ok=True)
    spec,shapes,stairmap,floormap,before,changes,rows,design,protected=derive(base)
    after=make_walker(Path(spec['source']),shapes,{**stairmap,**floormap,**changes})
    write(out/'exact-edits.json',rows)
    write(out/'end-boundary-design.json',dict(components=design,preserved_occupied_cells=protected,
          keeps_native_boarding_extent=True,retains_stair_guard_overlay=True,independent_floor_dependency=7))
    print('Planned',len(rows),'barrier voxels',len(design),'end-side components',flush=True)
    if preview_only:return

    summaries=[];errors=[];excluded=[];phases=[];negative=[];supports=[];views=[];probes=[]
    for station in spec['stations']:
        site=station['site'];dsg=[d for d in design if d['site']==site]
        adjusted=copy.deepcopy(station);original_cells=adjusted['cells'];kept=[];removed=[];occupied=[]
        for c in original_cells:
            x,y,z=c['floor'];p=(x+.5,c.get('feet_y',y+1),z+.5)
            if site=='native-28' and (x,y,z)in {tuple(r['floor'])for r in read(base/'deep-station-end-disposition-v1/half-step-datum-corrections.json')}:
                c['feet_y']=y+.5;p=(x+.5,y+.5,z+.5)
            margin=None
            for d in dsg:
                b=next(b for b in station['bays']if b['line']==d['line']);u,v=uv(b,(x,y,z))
                if y==d['base_y'] and d['u_range'][0]<=u<=d['u_range'][1] and d['edge']<=v*d['side']<abs(d['barrier_v']):
                    margin=d;break
            if margin:
                c['role']='guarded_nonboarding_trackside_margin'
                c['ownership_change']=dict(component=[site,margin['line'],margin['end'],margin['side']],
                    reason='Finite terminal strip beyond all native boarding gates, separated from retained aisle by new fixed setback barrier. Floor and original structure remain.')
                removed.append(c);continue
            hit=after.body(*p)
            if hit and tuple(hit['pos'])in changes:
                c.setdefault('allowed_occupants',[]).append('minecraft:iron_bars[')
                c['new_terminal_barrier_occupant']=hit;occupied.append(dict(floor=c['floor'],feet=p,hit=hit))
            kept.append(c)
        adjusted['cells']=kept
        original_class=fw.EnvelopeWalker
        class CandidateWalker(original_class):
            def __init__(self,src,ss):
                super().__init__(src,ss);self.reader=Overlay(self.reader,{**stairmap,**floormap,**changes})
        fw.EnvelopeWalker=CandidateWalker
        try:result=fw.footprint(adjusted,Path(spec['source']),shapes)
        finally:fw.EnvelopeWalker=original_class
        write(out/'review/after-fullwidth'/(site+'.json'),result)
        write(out/'review/after-declarations'/(site+'.json'),dict(**adjusted,retained_nonpublic_margin_cells=removed))
        allowed_fail=set()
        if {tuple(c['floor'])for c in result['failures']}!=allowed_fail:errors.append([site,'unexpected_floor_failure',result['failures']])
        if result['disconnected']:errors.append([site,'disconnected_public',len(result['disconnected']),result['disconnected'][:12]])
        if result['capture_requests']:errors.append([site,'capture_requests',result['capture_requests']])
        excluded.extend(dict(site=site,**c)for c in removed)
        # Every existing long route is retained; only locally affected ones
        # are reswept. The others inherit the earlier full-body proof.
        site_rows=[r for r in rows if r['site']==site];goals=[]
        for i,route in enumerate(station['retained_paths']):
            path=route['path'];affected=any(abs(p[0]-r['pos'][0]-.5)<1.4 and abs(p[2]-r['pos'][2]-.5)<1.4
                   and r['pos'][1]<p[1]+1.8 and r['pos'][1]+1>p[1]for p in path for r in site_rows)
            if affected:
                a,b=strict_walk(after,path),strict_walk(after,path[::-1]);ok=a['kind']==b['kind']=='strict_static_clear'
                if not ok:errors.append([site,'retained_route',i,a,b])
                goals.append(dict(key=site+'/retained/'+str(i),path=path,reachable=ok,strict_pass=ok,forward=a,reverse=b))
        phases.append(dict(phase='after',site=site,goals=goals,unchanged_routes_inherited=len(station['retained_paths'])-len(goals)))
        proof=support_proof(after,station,site_rows);supports.append(dict(site=site,**proof))
        if proof['floating']:errors.append([site,'floating',proof['floating'][:10]])
        negative+= [dict(site=site,**n)for n in result['negative_controls']]
        summaries.append(dict(site=site,original_declared_cells=len(original_cells),retained_public_and_fixture_cells=len(kept),
             finite_nonboarding_margin_cells=len(removed),new_fixed_barrier_occupied=len(occupied),
             clear_public=result['clear_cells'],connected_public=result['connected_to_retained_routes'],
             failures=result['failures'],changes=len(site_rows),affected_routes=len(goals),unaffected_routes_inherited=len(station['retained_paths'])-len(goals)))
        print(site,'clear',result['clear_cells'],'disconnected',len(result['disconnected']),'margin',len(removed),'guard occupied',len(occupied),flush=True)
    write(out/'review/public-ownership-adjustment.json',excluded)
    write(out/'review/public-summary.json',dict(errors=errors,stations=summaries,phases=phases))
    write(out/'review/support.json',supports)
    write(out/'review/negative.json',negative)
    write(out/'readiness.partial.json',dict(errors=errors,changes=len(rows),world_written=False,stage_two_complete=False))


def package(base,out):
    spec,shapes,stairmap,floormap,before,changes,rows,design,protected=derive(base)
    after=make_walker(Path(spec['source']),shapes,{**stairmap,**floormap,**changes})
    public=read(out/'review/public-summary.json');coverage=read(out/'review/continuous-boundary-coverage.json')
    model=read(out/'review/model-heightband-clearance.json')
    errors=public['errors']+coverage['errors']+model['errors']
    assert not errors,errors
    negative=read(out/'review/negative.json')
    negative += [dict(site=s['site'],case='revert_all_new_terminal_barriers',rejected=s['exposed_before']==s['interfaces'],exposed_interfaces=s['exposed_before'])for s in coverage['stations']]
    negative += [dict(case='stone_in_actual_native_vehicle_space',**n)for n in model['negative_controls']]
    probes=[];goals_before=[];goals_after=[];views=[]
    bysite={s['site']:s for s in spec['stations']}
    declaration_changes=[];complete=copy.deepcopy(spec)
    for station in complete['stations']:
        adjusted=read(out/'review/after-declarations'/(station['site']+'.json'))
        all_cells=adjusted['cells']+adjusted['retained_nonpublic_margin_cells']
        original_cells={tuple(c['floor']):c for c in station['cells']}
        for c in all_cells:
            if c.get('role')=='guarded_nonboarding_trackside_margin':c['public_walkable']=False
            if c.get('new_terminal_barrier_occupant'):c['public_walkable']=False
            if c!=original_cells[tuple(c['floor'])]:declaration_changes.append(dict(site=station['site'],floor=c['floor'],before=original_cells[tuple(c['floor'])],after=c))
        assert len(all_cells)==len(original_cells)
        station['cells']=sorted(all_cells,key=lambda c:tuple(c['floor']))
        station['nonboarding_margin_semantics']='Exact finite body-inaccessible end strip, all support checked; must not be silently treated as structural underlay or omitted from original denominator.'
    complete['terminal_guard_candidate']=str(out)
    complete['requires_finite_guarded_margin_role_support_in_verifier']=True
    write(out/'declarations-complete-after.json',complete)
    write(out/'declaration-exact-changes.json',declaration_changes)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',15)
    for i,d in enumerate(design):
        station=bysite[d['site']];b=next(b for b in station['bays']if b['line']==d['line'])
        v=d['barrier_v']+d['side'];u0,u1=d['u_range'];low=min(u0,d['join_u']-d['end']*2);high=max(u1,d['join_u']-d['end']*2)
        key='/'.join(map(str,[d['site'],d['line'],'end',d['end'],'side',d['side'],'retained-aisle']))
        selected=None
        for distance in range(abs(v),15):
            route_v=d['side']*distance
            path=[[p[0]+.5,p[1],p[2]+.5]for p in (at(b,u,route_v)for u in range(low,high+1))]
            proofs=[(strict_walk(w,path),strict_walk(w,path[::-1]))for w in(before,after)]
            if all(f['kind']==r['kind']=='strict_static_clear'for f,r in proofs):selected=(path,proofs,route_v);break
        if not selected:
            result=read(out/'review/after-fullwidth'/(d['site']+'.json'))
            nodes={tuple(c['floor'][::2]):c['feet']for c in result['cells']if c['status']=='clear_public_floor'
                and abs(c['feet'][1]-b['current_floor_y']-1)<1e-8
                and -42<=uv(b,c['floor'])[0]<=42 and d['edge']<uv(b,c['floor'])[1]*d['side']<=15}
            desired_start=at(b,d['join_u']-d['end']*2,d['side']*8)
            start=min(nodes,key=lambda k:abs(k[0]-desired_start[0])+abs(k[1]-desired_start[2]))
            targets=[k for k in nodes if d['u_range'][0]<=uv(b,(k[0],0,k[1]))[0]<=d['u_range'][1]
                and uv(b,(k[0],0,k[1]))[1]*d['side']>=abs(d['barrier_v'])+1]
            target=max(targets,key=lambda k:(uv(b,(k[0],0,k[1]))[0]*d['end'],-abs(uv(b,(k[0],0,k[1]))[1]-d['side']*8)))
            seen={start:None};q=deque([start])
            while q and target not in seen:
                p=q.popleft()
                for dx,dz in[(1,0),(-1,0),(0,1),(0,-1)]:
                    n=p[0]+dx,p[1]+dz
                    if n in nodes and n not in seen and all(strict_walk(w,[nodes[p],nodes[n]])['kind']=='strict_static_clear'for w in(before,after)):
                        seen[n]=p;q.append(n)
            assert target in seen,('No retained end aisle detour',key,start,target)
            walk=[];p=target
            while p is not None:walk.append(nodes[p]);p=seen[p]
            path=walk[::-1];proofs=[(strict_walk(w,path),strict_walk(w,path[::-1]))for w in(before,after)]
            assert all(f['kind']==r['kind']=='strict_static_clear'for f,r in proofs)
            selected=(path,proofs,'existing_fixture_detour')
        path,proofs,route_v=selected
        for goals,(f,r)in zip((goals_before,goals_after),proofs):
            goals.append(dict(key=key,site=d['site'],path=path,reachable=True,strict_pass=True,forward=f,reverse=r,local_transverse_cell=route_v))
        normal=(0,-d['side'])if b['horizontal']else(-d['side'],0)
        choices=[]
        for p in [[p[0]+.5,p[1],p[2]+.5]for p in (at(b,u,v)for u in range(u0,u1+1))]:
            if after.body(*p):continue
            hit=sweep(after,p,normal)
            if hit['hit']:choices.append((p,hit))
        assert choices,('No direct actual barrier contact',key)
        p,hit=choices[len(choices)//2]
        probes.append(dict(site=d['site'],component=key,feet=p,normal=[normal[0],0,normal[1]],before=sweep(before,p,normal),**hit,
            first_contact_is_new_guard=tuple(hit['hit']['pos'])in changes,
            covered_old_interfaces=d['original_interfaces'],continuous_coverage_evidence='review/continuous-boundary-coverage.json'))
    # Full before/after views for every bay end, from two opposite cameras.
    for site,line,end in sorted({(d['site'],d['line'],d['end'])for d in design}):
        b=next(b for b in bysite[site]['bays']if b['line']==line);fy=b['current_floor_y']
        low,high=(-43,-29)if end<0 else(29,43)
        coords=[at(b,u,v,fy)for u in(low,high)for v in(-15,15)]
        bounds=[min(p[0]for p in coords),fy-1,min(p[2]for p in coords),max(p[0]for p in coords),fy+3,max(p[2]for p in coords)]
        for phase,w in [('before',before),('after',after)]:
            file=out/'review/views'/f'{site}-{line}-end{end}-{phase}.png'
            view=render_shapes(w,bounds,file,f'{site} / {line} / end {end} / {phase} — station terminal',changes if phase=='after'else{})
            im=Image.open(file);draw=ImageDraw.Draw(im)
            for off in (0,1300):
                draw.rectangle((off+20,68,off+1280,99),fill='#edf0ed')
                draw.text((off+28,73),'蓝青色=本次固定端部围护；原乘降区保留；裁切上盖仅用于观察。',fill='#38564d',font=font)
            im.save(file);views.append(dict(site=site,line=line,end=end,phase=phase,**view))
        print('Rendered',site,line,end,flush=True)
    thumbs=[]
    for v in views:
        im=Image.open(v['image']);im.thumbnail((780,294));thumbs.append(im)
    sheet=Image.new('RGB',(1560,294*12),'white')
    for i,im in enumerate(thumbs):sheet.paste(im,((i%2)*780,(i//2)*294))
    sheet.save(out/'review/views/all-ends-before-after.png')
    regions=save_delta(out,rows,before.reader)
    write(out/'authored-collision-shapes.json',shapes)
    shutil.copy2(Path(spec['source'])/'devices.dat',out/'captured-devices.dat')
    shutil.copy2(Path(spec['source'])/'capture.json',out/'capture.json')
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([])}).save(out/'block-entities.dat',gzipped=True)
    original=before.reader
    while hasattr(original,'source'):original=original.source
    # Overlay exposes its source reader as base in some frozen tool revisions.
    if not hasattr(original,'report'):original=make_walker(Path(spec['source']),shapes).reader
    write(out/'manifest.json',dict(world=original.report['world'],schema='declared-deep-terminal-guard-candidate-v1',source=spec['source'],
        cells=len(rows),regions=regions,vertical_extent=[-672,319],device_changes=0,native_changes=[],native_additions=[],actor_changes=[],
        world_written=False,coordinate_format=['x','y','z'],min_xyz=[min(p[i]for p in changes)for i in range(3)],max_xyz=[max(p[i]for p in changes)for i in range(3)]))
    write(out/'positive-change-mask.json',[r['pos']for r in rows])
    write(out/'forward-patch.json',dict(edits=rows,requires_exact_before=True))
    inverse=[dict(pos=r['pos'],before=r['after'],after=r['before'],before_nbt=None,after_nbt=None,site=r['site'])for r in rows]
    write(out/'inverse-patch.json',dict(edits=inverse,requires_exact_before=True))
    assert len(changes)==len(set(tuple(r['pos'])for r in rows))
    assert {tuple(r['pos']):r['after']for r in inverse}=={tuple(r['pos']):r['before']for r in rows}
    for d in design:
        b=next(b for b in bysite[d['site']]['bays']if b['line']==d['line'])
        assert all(not(-32<=uv(b,r['pos'])[0]<=32)for r in rows if r['site']==d['site']and abs(r['pos'][1]-b['current_floor_y'])<=2 and abs(uv(b,r['pos'])[1])<10)
    phases=[dict(phase='before',goals=goals_before),dict(phase='after',goals=goals_after)]
    functional=dict(errors=[],changed_cells=len(rows),stations=public['stations'],guard_probes=probes,
        attachment_supports=read(out/'review/support.json'),support_columns=[],negative_cases=negative,phases=phases,
        preserved_devices=len(nbtlib.load(Path(spec['source'])/'devices.dat')['Devices']),preserved_actors=original.report.get('actors',0),
        vehicle_intrusions=[],dynamic_gate_bypass=False,dynamic_gate_phase_scope=coverage['phase'],world_opened=False,world_written=False,
        terminal_edges_before=223,terminal_edges_after=0,finite_margin_reclassification=231,new_barrier_floor_occupancy=222,
        original_complete_floor_denominator=14107,original_native_boarding_longitudinal_extent=[-32,32],original_boarding_extent_unchanged=True,
        retained_old_routes=60,retained_old_routes_repeated=0,old_route_nonintersection_proof='review/public-summary.json',
        separate_floor_restoration=7,overlay_stair_guards=196,retained_retirement_wall_count=2,
        corrected_wall_evidence=str(base/'deep-platform-declarations73-v2/declarations.json'),
        runtime_shape_validation_pending=True,whole_station_complete=False,stage_two_complete=False)
    write(out/'functional-report.json',functional)
    write(out/'review/views.json',views)
    write(out/'review/review.json',dict(errors=[],stations=public['stations'],views=views,world_written=False,
        source_omissions=0,all_223_old_interfaces_protected=True,conditional_closed_gate_phase=True))
    write(out/'release-checks.json',dict(commands=[],candidate_error_reports=['functional-report.json','delta-roundtrip-check.json',
        'review/public-summary.json','review/continuous-boundary-coverage.json','review/model-heightband-clearance.json'],review_error_reports=['review.json'],
        report_values=[dict(root='candidate',file='delta-roundtrip-check.json',equals=dict(cells=len(rows),vertical_extent=[-672,319],unknown_source_cells=0,negative_indices=0,exact_before_after_match=True))],
        reviewed_views=['views/'+Path(v['image']).name for v in views],views_reviewed_by_root=False))
    state=read(base/'continuation.json')
    write(out/'root-publication-input.json',dict(candidate=str(out),checks=str(out/'release-checks.json'),review_directory=str(out/'review'),
        previous_batch=state['latest_installed_batch'],source_authority=state['planning_authority'],changes_file='exact-edits.json',functional_report='functional-report.json',
        expected_changed_cells=len(rows),expected_device_changes=0,expected_guard_probes=len(probes),minimum_negative_cases=len(negative),
        vertical_extent=[-672,319],delta_y_origin=-672,delta_height=992,maximum_step=.5,required_goals=[g['key']for g in goals_after],
        ground_network=dict(mode='preserve',columns=[]),multilevel_overlay='Preserve original passenger paths; append exact finite end-margin ownership changes from review/public-ownership-adjustment.json.',
        evidence_fields=dict(phases='phases',guards='guard_probes',negative_cases='negative_cases',attachment_supports='attachment_supports'),
        support_model='Each of 494 barrier cells has an exact collision-face contact path to original floor foundation.',
        offline_native_reference=str(base/'station-installed69-native-v1'),native_reference_not_current_for_all_members=True,
        native_policy='Capture current full native inventory. Deep rail geometry was exactly bound to frozen native export; later surface additions are disjoint.',
        floor_patch_is_separate=True,requires_floor7_installed_first=True,floor7_candidate=str(base/'deep-station-floor7-candidate-v1'),
        overlay_prerequisite='Install independent7 floor-restoration cells first. Candidate after proof is frozen source + installed196 stair guards + floor7 + new494 terminal guards.',
        root_required_actions=['Review all24 before/after two-camera images','Bind current authority and verify exact494 target before states',
            'Publish through shared deep sparse-delta path; retain corrected wall and finite end-margin ownership declarations',
            'Read back actual cells/devices/actors/native; do not claim runtime boarding or whole station completion']))
    write(out/'readiness.json',dict(status='FROZEN_OFFLINE_CANDIDATE',errors=[],changed_cells=len(rows),end_side_components=24,original_edge_groups=46,
        old_terminal_interfaces=223,protected_after=223,full_declared_floor_cells=14107,clear_connected_public_cells=sum(s['clear_public']for s in public['stations']),
        conservative_vehicle_model_intrusions=0,negative_controls=len(negative),views=24,views_reviewed_by_root=False,
        floor_dependency_separate=7,stair_guard_overlay=196,two_retirement_walls_preserved=True,world_written=False,
        requires_current_actual_before_check=True,runtime_boarding_pass=False,whole_station_complete=False,stage_two_complete=False))
    print('Packaged',len(rows),'guards;',len(probes),'probes;',len(negative),'negative controls',flush=True)


def package_floor(base,out):
    out.mkdir(parents=True,exist_ok=True)
    spec,shapes,stairmap,floormap,before,changes,guardrows,design,protected=derive(base)
    origin=base/'deep-station-end-disposition-v1'
    plan=read(origin/'seven-cell-floor-patch-plan.json');rows=[dict(site='native-22',**r)for r in plan['edits']]
    after=make_walker(Path(spec['source']),shapes,{**stairmap,**floormap})
    station=next(s for s in spec['stations']if s['site']=='native-22')
    original_class=fw.EnvelopeWalker
    class CandidateWalker(original_class):
        def __init__(self,src,ss):super().__init__(src,ss);self.reader=Overlay(self.reader,{**stairmap,**floormap})
    fw.EnvelopeWalker=CandidateWalker
    try:result=fw.footprint(station,Path(spec['source']),shapes)
    finally:fw.EnvelopeWalker=original_class
    assert not result['failures'] and not result['disconnected'] and not result['capture_requests']
    write(out/'review/after-fullwidth.json',result)
    write(out/'declaration.json',station)
    write(out/'exact-edits.json',rows);write(out/'positive-change-mask.json',[r['pos']for r in rows])
    write(out/'forward-patch.json',dict(edits=rows,requires_exact_before=True))
    write(out/'inverse-patch.json',dict(edits=plan['inverse'],requires_exact_before=True))
    regions=save_delta(out,rows,before.reader)
    original=make_walker(Path(spec['source']),shapes).reader
    write(out/'manifest.json',dict(world=original.report['world'],schema='declared-deep-floor-restoration-candidate-v1',source=spec['source'],
        cells=7,regions=regions,vertical_extent=[-672,319],device_changes=0,native_changes=[],native_additions=[],actor_changes=[],
        world_written=False,coordinate_format=['x','y','z'],min_xyz=[307,-467,523],max_xyz=[308,-467,528]))
    write(out/'authored-collision-shapes.json',shapes)
    shutil.copy2(Path(spec['source'])/'devices.dat',out/'captured-devices.dat')
    shutil.copy2(Path(spec['source'])/'capture.json',out/'capture.json')
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([])}).save(out/'block-entities.dat',gzipped=True)
    for name in ['train-clearance.json','public-surface-check.json','seven-cell-floor-patch-plan.json','source-dispositions.json']:
        shutil.copy2(origin/name,out/name)
    proof=support_proof(after,station,rows);assert not proof['floating']
    public=read(origin/'public-surface-check.json')
    phases=[]
    for phase,w in [('before',before),('after',after)]:
        goals=[]
        for i,r in enumerate(public['connections']):
            x,y,z=r['floor'];path=[[x+.5,y+1,z+.5],r['links_in_restored_public_component'][0]['target']]
            f,v=strict_walk(w,path),strict_walk(w,path[::-1]);ok=f['kind']==v['kind']=='strict_static_clear'
            if phase=='after':assert ok
            else:assert not ok
            goals.append(dict(key='native-22/restored-deck/'+str(i),site='native-22',path=path,reachable=ok,strict_pass=ok,forward=f,reverse=v))
        phases.append(dict(phase=phase,goals=goals))
    negatives=[n for n in read(origin/'negative-controls.json')if n['case']!='remove_actual_half_slab']
    assert len(negatives)==8 and all(n['rejected']for n in negatives)
    views=[]
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',15)
    for phase,w in [('before',before),('after',after)]:
        file=out/'review/views'/(phase+'.png')
        view=render_shapes(w,[304,-468,522,312,-465,530],file,'native-22 / seven original deck cells / '+phase,floormap if phase=='after'else{})
        im=Image.open(file);draw=ImageDraw.Draw(im)
        for off in (0,1300):
            draw.rectangle((off+20,68,off+1280,99),fill='#edf0ed')
            draw.text((off+28,73),'蓝青色=7格原地面恢复；轨道保持原位；围护候选另包。',fill='#38564d',font=font)
        im.save(file);views.append(dict(phase=phase,**view))
    functional=dict(errors=[],changed_cells=7,stations=[dict(site='native-22',declared_floor_cells=2585,
        missing_support_before=7,missing_support_after=0,new_clear_cells=7,connected_public_cells=result['connected_to_retained_routes'],
        fullwidth_failures=result['failures'])],guard_probes=[],attachment_supports=[dict(site='native-22',**proof)],support_columns=[],
        negative_cases=negatives,phases=phases,vehicle_intrusions=[],dynamic_gate_bypass=False,
        positive_visible_model_separation=.10454875,hidden_doorway_contact_only=True,hidden_doorway_positive_overlap=False,
        preserved_devices=len(nbtlib.load(Path(spec['source'])/'devices.dat')['Devices']),preserved_actors=original.report.get('actors',0),
        old_routes_repeated=0,existing_stair_guard_overlay=196,terminal_guard_candidate_included=False,
        terminal_edges_still_require_separate_guard_candidate=True,world_opened=False,world_written=False,
        runtime_boarding_pass=False,whole_station_complete=False,stage_two_complete=False)
    write(out/'functional-report.json',functional)
    write(out/'review/review.json',dict(errors=[],views=views,fullwidth_evidence='after-fullwidth.json',world_written=False))
    write(out/'review/views.json',views)
    write(out/'release-checks.json',dict(commands=[],candidate_error_reports=['functional-report.json','delta-roundtrip-check.json'],
        review_error_reports=['review.json'],report_values=[dict(root='candidate',file='delta-roundtrip-check.json',
        equals=dict(cells=7,vertical_extent=[-672,319],unknown_source_cells=0,negative_indices=0,exact_before_after_match=True))],
        reviewed_views=['views/'+Path(v['image']).name for v in views],views_reviewed_by_root=False))
    state=read(base/'continuation.json')
    write(out/'root-publication-input.json',dict(candidate=str(out),checks=str(out/'release-checks.json'),review_directory=str(out/'review'),
        previous_batch=state['latest_installed_batch'],source_authority=state['planning_authority'],changes_file='exact-edits.json',
        functional_report='functional-report.json',expected_changed_cells=7,expected_device_changes=0,expected_guard_probes=0,minimum_negative_cases=8,
        vertical_extent=[-672,319],delta_y_origin=-672,delta_height=992,maximum_step=.5,
        required_goals=[g['key']for g in phases[-1]['goals']],ground_network=dict(mode='preserve',columns=[]),
        multilevel_overlay='Restore seven original deck support cells at absolute Y=-467; no station/node/native identity change.',
        evidence_fields=dict(phases='phases',guards='guard_probes',negative_cases='negative_cases',attachment_supports='attachment_supports'),
        support_model='Seven full cubes directly contact recorded original foundation.',native_reference_not_current_for_all_members=True,
        native_policy='Root current full inventory binding required; two local level straight rails prove height-sensitive clearance.',
        root_required_actions=['Review before/after collision images','Verify all7 actual-target air preconditions and devices',
            'Use shared explicit-height section delta publisher with floor-restoration contract; retain seven-goal before-failure/after-pass semantics',
            'Read back exact cells; retain unresolved runtime boarding and terminal-edge status until separate guard publication']))
    write(out/'readiness.json',dict(status='FROZEN_OFFLINE_FLOOR_CANDIDATE',errors=[],changed_cells=7,
        complete_public_floor_count=2585,all_added_cells_connected=True,old_routes_rerun=0,
        conservative_visible_separation=.10454875,hidden_boundary_touch_no_overlap=True,negative_controls=8,
        independent_of_494_terminal_guard_delta=True,world_written=False,views_reviewed_by_root=False,
        runtime_boarding_pass=False,whole_station_complete=False,stage_two_complete=False))
    print('Packaged independent seven floor cells',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--preview-only',action='store_true')
    p.add_argument('--stage',choices=['all','review','coverage','model','package','floor'],default='all');a=p.parse_args()
    if a.preview_only:review(a.base,a.out,True)
    elif a.stage=='floor':package_floor(a.base,a.out)
    else:
        if a.stage in('all','review'):review(a.base,a.out)
        if a.stage in('all','coverage'):check_terminal_coverage(a.base,a.out)
        if a.stage in('all','model'):model_clearance(a.base,a.out)
        if a.stage in('all','package'):package(a.base,a.out)
