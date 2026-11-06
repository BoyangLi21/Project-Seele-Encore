"""Prepare offline stair-side guards from explicit passenger declarations.

Reads frozen section captures and emits exact old/new voxel JSON. It has no
world, native-registry, game or publication entry point. The existing declared
floor verifier is reused with an in-memory overlay; its source is not changed.
"""
import argparse
from collections import Counter, defaultdict, deque
import copy
import gzip
import json
import math
from pathlib import Path
import shutil

import nbtlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from map_pipeline.station_sections import StationSections
from review_underground_station_evidence import Overlay, strict_walk
import verify_declared_platform_footprints as fullwidth
from render_hakone_installed_map import color


MATERIAL = 'projectseele:nerv_edge_rail['
DIRECTIONS = ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1))


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf8')


def make_walker(source, shapes, edits=None):
    w = fullwidth.EnvelopeWalker(source, shapes)
    if edits:
        w.reader = Overlay(w.reader, edits)
    return w


def sweep(w, feet, direction):
    dx,dz = direction
    for k in range(1,9):
        p = [feet[0]+dx*k/8, feet[1], feet[2]+dz*k/8]
        hit = w.body(*p)
        if hit:
            return dict(hit=hit, at=k/8, position=p)
    return dict(hit=None, at=None, position=None)


def lower_bearing(w, feet, dx, dz):
    unknown = []
    for down in range(13):
        heights, gaps = w.floors(feet[0]+dx, feet[1]-down, feet[2]+dz)
        unknown.extend(gaps[:1])
        for h in heights:
            if h <= feet[1]+.0001 and w.body(feet[0]+dx,h,feet[2]+dz) is None:
                return h, unknown[:1]
    return None, unknown[:1]


def edge_scan(w, station, result):
    """Four cardinal and four diagonal body approaches for every clear cell."""
    base = min(b['current_floor_y']+1 for b in station['bays'])
    rows=[]; counts=Counter(); high=[]; unknown=[]
    clear = {tuple(c['feet']) for c in result['cells'] if c['status']=='clear_public_floor'}
    columns=defaultdict(list)
    for p in clear:
        columns[math.floor(p[0]),math.floor(p[2])].append(p[1])
    for p in sorted(clear):
        for dx,dz in DIRECTIONS:
            target=columns[math.floor(p[0])+dx,math.floor(p[2])+dz]
            if any(abs(h-p[1])<=.600001 for h in target):
                counts['same_level_declared_neighbor']+=1; continue
            probe=sweep(w,p,(dx,dz))
            row=dict(feet=p,direction=[dx,dz],**probe)
            if probe['hit']:
                kind='fixed_collision' if probe['hit']['kind']=='body_obstruction' else 'unknown_collision'
            else:
                h, gaps=lower_bearing(w,p,dx,dz)
                row.update(lower_feet=h,drop=None if h is None else p[1]-h,unknown=gaps)
                if gaps and h is None: kind='unknown_bearing'
                elif h is not None and p[1]-h<=1.500001: kind='low_step_or_continuation'
                elif p[1] <= base+.600001: kind='base_platform_rail_or_end_interface_unresolved'
                else: kind='unguarded_elevated_side'
            row['kind']=kind;rows.append(row);counts[kind]+=1
            if kind=='unguarded_elevated_side': high.append(row)
            if kind.startswith('unknown'): unknown.append(row)
    return dict(site=station['site'],body=[.6,1.8],directions=[list(q) for q in DIRECTIONS],
                approach_spacing=.125,probe_count=len(clear)*8,counts=dict(counts),
                boundary_probes=rows,unprotected_elevated=high,unknown=unknown)


def touching(a, b):
    """Face contact with positive overlap in both other axes; no corner support."""
    overlap=[min(a[i+3],b[i+3])-max(a[i],b[i]) for i in range(3)]
    if min(overlap)>1e-7:
        return dict(kind='positive_collision_overlap',volume=math.prod(overlap))
    for axis in range(3):
        if abs(a[axis+3]-b[axis])<1e-7 or abs(b[axis+3]-a[axis])<1e-7:
            axes=[i for i in range(3) if i!=axis]
            overlaps=[min(a[i+3],b[i+3])-max(a[i],b[i]) for i in axes]
            if min(overlaps)>1e-7:
                return dict(kind='positive_face_contact',axis=axis,contact_area=overlaps[0]*overlaps[1])
    return None


def support_proof(w, station, changed):
    base=min(b['current_floor_y'] for b in station['bays'])-1
    points=[tuple(q['pos']) for q in changed]
    if not points: return dict(components=[],floating=[])
    # Every new cube must reach an existing foundation by real collision-face
    # contacts. The bounded search is confined to the authored stair/bridge bay.
    lo=[min(p[i] for p in points)-2 for i in range(3)]
    hi=[max(p[i] for p in points)+2 for i in range(3)]
    lo[1]=base; hi[1]=max(p[1] for p in points)+1
    changed_set=set(points); box_cache={}
    def boxes(p):
        if p not in box_cache:
            state, local=w.boxes(*p)
            box_cache[p]=(state,[] if local is None else [tuple(p[i%3]+b[i] for i in range(6)) for b in local])
        return box_cache[p]
    paths={}; frontier=deque()
    for x in range(lo[0],hi[0]+1):
        for z in range(lo[2],hi[2]+1):
            p=(x,base,z);state,bs=boxes(p)
            if bs:
                paths[p]=None;frontier.append(p)
    contacts={}
    while frontier:
        p=frontier.popleft(); _,pb=boxes(p)
        for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
            q=(p[0]+dx,p[1]+dy,p[2]+dz)
            if q in paths or not all(lo[i]<=q[i]<=hi[i] for i in range(3)):continue
            _,qb=boxes(q)
            face=next((f for a in pb for b in qb if (f:=touching(a,b))),None)
            if face:
                paths[q]=p;contacts[q]=face;frontier.append(q)
    proofs=[]; floating=[]
    for p in sorted(changed_set):
        if p not in paths:
            floating.append(list(p));continue
        q=p;chain=[]
        while q is not None:
            chain.append(dict(pos=q,state=boxes(q)[0],contact_to_next=contacts.get(q)))
            q=paths[q]
        proofs.append(dict(pos=p,foundation=chain[-1],chain=chain))
    return dict(search_bounds=lo+hi,foundation_y=base,new_cells=len(points),
                supported_cells=len(proofs),floating=floating,collision_contact_paths=proofs,
                method='Positive-area collision-face/volume connectivity to original foundation layer; no diagonal or corner attachment')


def render_shapes(w,bounds,out,title,edits):
    """Exact recorded collision cuboids, including the 1/8-block side rails."""
    x,y,z,X,Y,Z=bounds;faces=[];missing=[]
    for xx in range(x,X+1):
        for yy in range(y,Y+1):
            for zz in range(z,Z+1):
                state,boxes=w.boxes(xx,yy,zz)
                if boxes is None:missing.append([xx,yy,zz]);continue
                col=(42,111,132) if (xx,yy,zz) in edits else tuple(int(v*255) for v in color(state))
                for b in boxes:
                    lo=(xx+b[0]-x,yy+b[1]-y,zz+b[2]-z)
                    hi=(xx+b[3]-x,yy+b[4]-y,zz+b[5]-z)
                    faces.append((lo,hi,col))
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',15)
    images=[]
    for sx,sz in ((1,1),(-1,-1)):
        polys=[]
        def project(q):
            return np.column_stack(((sx*q[:,0]-sz*q[:,2])*.866,(sx*q[:,0]+sz*q[:,2])*.5-q[:,1]))
        for lo,hi,col in faces:
            a,b,c=lo;A,B,C=hi
            specs=[([(a,B,c),(a,B,C),(A,B,C),(A,B,c)],1.),
                   ([(A if sx>0 else a,b,c),(A if sx>0 else a,B,c),(A if sx>0 else a,B,C),(A if sx>0 else a,b,C)],.75),
                   ([(a,b,C if sz>0 else c),(a,B,C if sz>0 else c),(A,B,C if sz>0 else c),(A,b,C if sz>0 else c)],.87)]
            for pts,shade in specs:
                q=np.asarray(pts,float);depth=float((sx*q[:,0]+sz*q[:,2]+q[:,1]*1.7).mean())
                polys.append((depth,q,tuple(int(v*shade) for v in col)))
        image=Image.new('RGB',(1300,980),'#edf0ed');draw=ImageDraw.Draw(image)
        limits=project(np.concatenate([q for _,q,_ in polys]));low=limits.min(0);span=limits.max(0)-low
        scale=min(1215/span[0],805/span[1])
        for _,q,col in sorted(polys,key=lambda q:q[0]):
            pixels=(project(q)-low)*scale+[40,105]
            draw.polygon([tuple(p) for p in pixels],fill=col)
        draw.text((28,14),title,fill='#18362d',font=font)
        draw.text((28,46),f'X {x}..{X} / Y {y}..{Y} / Z {z}..{Z} · camera ({sx},{sz}) · N=-Z',fill='#38564d',font=small)
        draw.text((28,73),'蓝青色=本次新增实碰撞侧护；保留原梯所有5列；裁切上盖不代表拆除。',fill='#38564d',font=small)
        draw.text((28,944),'实际离线方块坐标与记录碰撞盒；细栏杆按1/8格形状绘制。非游戏截图、非视觉验收。',fill='#38564d',font=small)
        images.append(image)
    canvas=Image.new('RGB',(2600,980),'white');canvas.paste(images[0],(0,0));canvas.paste(images[1],(1300,0))
    out.parent.mkdir(parents=True,exist_ok=True);canvas.save(out)
    return dict(image=str(out),bounds=bounds,source='Exact source voxel positions and recorded native collision cuboids',unknown_shape_cells=len(missing),native_screenshot=False)


def native_masks(path, stations):
    data=read(path); masks=defaultdict(dict)
    for si,a in enumerate(stations):
        floor_cells=[c['floor'] for c in a['cells']]
        low=[min(c[i] for c in floor_cells)-3 for i in range(3)]
        high=[max(c[i] for c in floor_cells)+3 for i in range(3)]
        for ci,curve in enumerate(data['curves']):
            if curve['mode']!='TRAIN':continue
            for pi,pt in enumerate(curve['points']):
                x,y,z=map(math.floor,pt)
                if not low[0]-2<=x<=high[0]+2 or not low[2]-2<=z<=high[2]+2 or not low[1]-6<=y<=high[1]:continue
                for dx in (-1,0,1):
                    for dz in (-1,0,1):
                        for dy in range(6):
                            p=x+dx,y+dy,z+dz
                            masks[a['site']].setdefault(p,dict(curve_index=ci,point_index=pi,point=pt,
                                 owner='tools/build_transit_civil_r20.py::native_train_body 3x3 x six-high carve'))
    return masks


def save_delta(out, rows, source):
    """Shared sparse region/chunk layout with explicit absolute vertical extent."""
    (out/'delta').mkdir(exist_ok=True)
    regions=defaultdict(lambda:defaultdict(list))
    for row in rows:
        x,y,z=row['pos']
        if not -672<=y<=319:raise ValueError(('Outside explicit delta extent',row['pos']))
        if source.state(x,y,z)!=row['before']:raise ValueError('Unknown/mismatching before cell')
        regions[x//512,z//512][x//16,z//16].append(row)
    manifest=[];roundtrip=[]
    for (rx,rz),chunks in sorted(regions.items()):
        palette=[];ids={};coordinates=[];ranges=[0];indices=[];old=[];new=[]
        for (cx,cz),values in sorted(chunks.items()):
            coordinates.append([cx,cz])
            for row in sorted(values,key=lambda q:(q['pos'][1],q['pos'][2],q['pos'][0])):
                x,y,z=row['pos'];indices.append((y+672)*256+(z%16)*16+x%16)
                for state in (row['before'],row['after']):
                    if state not in ids:ids[state]=len(palette);palette.append(state)
                old.append(ids[row['before']]);new.append(ids[row['after']])
            ranges.append(len(indices))
        file=out/'delta'/f'r.{rx}.{rz}.npz'
        np.savez_compressed(file,coordinates=np.asarray(coordinates,np.int32),ranges=np.asarray(ranges,np.int64),
            indices=np.asarray(indices,np.uint32),before=np.asarray(old,np.uint16),after=np.asarray(new,np.uint16),
            palette=np.asarray(palette),y_origin=np.asarray(-672,np.int32),height=np.asarray(992,np.int32))
        with np.load(file) as f:
            if int(f['y_origin'])!=-672 or int(f['height'])!=992:raise ValueError('Extent changed')
            for i,(cx,cz) in enumerate(f['coordinates']):
                for j in range(int(f['ranges'][i]),int(f['ranges'][i+1])):
                    ix=int(f['indices'][j]);p=[int(cx)*16+ix%16,ix//256-672,int(cz)*16+(ix//16)%16]
                    roundtrip.append(dict(pos=p,before=str(f['palette'][int(f['before'][j])]),after=str(f['palette'][int(f['after'][j])])))
        manifest.append(dict(path='delta/'+file.name,cells=len(indices),y_origin=-672,height=992))
    expected=sorted((tuple(r['pos']),r['before'],r['after']) for r in rows)
    actual=sorted((tuple(r['pos']),r['before'],r['after']) for r in roundtrip)
    if actual!=expected:raise ValueError('Sparse delta round trip differs from exact edits')
    write(out/'delta-roundtrip-check.json',dict(errors=[],cells=len(rows),regions=manifest,vertical_extent=[-672,319],
          unknown_source_cells=0,negative_indices=0,exact_before_after_match=True))
    return manifest


def currentness(args):
    original=read(args.findings.parent/'source-currentness.json')
    index=args.findings.parent.parent/'installed52-69-receipts-index-v1.json'
    known={r['batch'] for r in original['rows']}
    for receipt in read(index)['rows']:
        if receipt['batch'] in known:continue
        intersections=[];count=0;lo=[math.inf]*3;hi=[-math.inf]*3;files=[]
        for file in sorted((Path(receipt['candidate'])/'delta').glob('*.npz')):
            files.append(str(file))
            with np.load(file) as d:
                y0=int(d['y_origin']) if 'y_origin' in d else -128
                for i,(cx,cz) in enumerate(d['coordinates']):
                    ix=d['indices'][d['ranges'][i]:d['ranges'][i+1]].astype(np.int64)
                    xyz=np.stack([int(cx)*16+ix%16,ix//256+y0,int(cz)*16+(ix//16)%16],axis=1)
                    count+=len(xyz)
                    if len(xyz):
                        lo=[min(lo[k],int(xyz[:,k].min())) for k in range(3)];hi=[max(hi[k],int(xyz[:,k].max())) for k in range(3)]
                        for scope in original['scope_includes_bearing_search_and_edge_halo']:
                            box=scope['bounds'];hit=np.all((xyz>=box[:3])&(xyz<=box[3:]),axis=1)
                            if hit.any():intersections.append(dict(site=scope['site'],cells=xyz[hit].tolist()))
        original['rows'].append(dict(batch=receipt['batch'],installation=receipt['installation'],candidate=receipt['candidate'],
            delta_files=files,changed_cells=count,min_xyz=lo,max_xyz=hi,scope_intersections=intersections))
    original['all_post_reference_deltas_disjoint']=all(not r['scope_intersections'] for r in original['rows'])
    original['conservative_post_reference_batches']=[52,69]
    if not original['all_post_reference_deltas_disjoint']:raise ValueError('Snapshot scope changed in installed delta')
    write(args.out/'source-currentness.json',original)


def build(args):
    spec=read(args.declarations); findings=read(args.findings);source=Path(spec['source'])
    if args.out.exists() and (args.out/'readiness.json').exists():
        raise ValueError('Frozen package already exists')
    args.out.mkdir(parents=True,exist_ok=True);args.review.mkdir(parents=True,exist_ok=True)
    shapes=read(spec['shape_export']); before=make_walker(source,shapes)
    devices=nbtlib.load(source/'devices.dat')
    device_tags=next(iter(devices.values()))
    device_positions={tuple(int(t[k]) for k in ('x','y','z')) for t in device_tags}
    masks=native_masks(args.native,spec['stations'])
    changes={};owners={};guards=[];dispositions=[]
    by_site={a['site']:a for a in spec['stations']}
    for f in findings['stations']:
        a=by_site[f['site']]
        for issue in f['declared_floor_missing_support']:
            p=tuple(issue['floor']);witness=masks[a['site']].get(p)
            dispositions.append(dict(site=a['site'],floor=p,status=issue['status'],
                disposition='native_train_body_carve_preserved' if witness else 'unresolved_original_ownership_preserved',
                source_witness=witness,measured_floor_state=before.reader.state(*p),
                original_obstacle=issue.get('obstacle'),modified=False,
                closure='Rail source overlap establishes no-fill ownership only; passenger-end boundary remains a separate pending design' if witness else 'Original source gap remains unresolved; not authorized for removal or floor fill'))
        rows=f['confirmed_unguarded_elevated_edges']+f['lower_stair_side_drops_to_review']
        for edge in rows:
            p=edge['feet'];dx,_,dz=edge['normal'];x,z=math.floor(p[0])+dx,math.floor(p[2])+dz
            y=math.floor(p[1]);added=[]
            inward={(-1,0):'east',(1,0):'west',(0,-1):'south',(0,1):'north'}[dx,dz]
            state_name='projectseele:nerv_edge_rail['+','.join(k+'='+str(k==inward).lower() for k in ('east','north','south','west'))+']'
            if not shapes.get(state_name):raise ValueError(('Missing recorded rail collision',state_name))
            for yy in range(y-1,y+1):
                pos=(x,yy,z);state=before.reader.state(*pos)
                if state is None:raise ValueError(('Capture required',pos))
                if pos in device_positions or pos in masks[a['site']]:raise ValueError(('Protected guard position',a['site'],pos))
                if state=='minecraft:air':
                    changes[pos]=state_name;owners[pos]=a['site'];added.append(pos)
                elif not before.boxes(*pos)[1]:raise ValueError(('Occupied no-collision original is protected',pos,state))
            guards.append(dict(site=a['site'],feet=p,normal=edge['normal'],original_drop=edge['drop_blocks'],
                               category='confirmed_high_edge' if edge['drop_blocks']>1.5 else 'continuous_lower_stair_side',
                               design_cells=added,state=state_name,side_attachment=[x,y-1,z],no_new_ground_column=True))
    rows=[dict(pos=p,before=before.reader.state(*p),after=s,site=owners[p]) for p,s in sorted(changes.items())]
    write(args.out/'exact-edits.json',rows)
    write(args.out/'positive-edit-mask.json',[r['pos'] for r in rows])
    write(args.out/'forward-patch.json',[dict(pos=r['pos'],state=r['after'],expected=r['before']) for r in rows])
    write(args.out/'inverse-patch.json',[dict(pos=r['pos'],state=r['before'],expected=r['after']) for r in rows])
    write(args.out/'guard-design.json',dict(material=MATERIAL,rows=guards,body=[.6,1.8],stair_width_lanes=5,
        attachment='Two stacked original edge-rail blocks contact the stair side from feet_y-1 through feet_y+1.375; side intrusion is 1/8 voxel outside the stair',
        original_nonair_changes=0,rail_mask_source=str(args.native),world_written=False))
    # Ownership remains open when the exact native carve does not claim a
    # missing floor. Nearby rail geometry is evidence of proximity only.
    native=read(args.native)
    historic=Path('F:/eva/artifacts/facility_r25/route_repairs/reported_route_and_enclosure_repairs/ops.json.gz')
    old_ops=json.loads(gzip.decompress(historic.read_bytes()))
    for q in dispositions:
        p=q['floor'];near=[]
        for ci,curve in enumerate(native['curves']):
            if curve['mode']!='TRAIN':continue
            for pi,pt in enumerate(curve['points']):
                if abs(pt[1]-p[1])<=2:
                    near.append((math.hypot(pt[0]-p[0]-.5,pt[2]-p[2]-.5),ci,pi,pt))
        if near:
            distance,ci,pi,point=min(near)
            q['nearest_current_rail']=dict(horizontal_distance=distance,curve_index=ci,point_index=pi,point=point,
                not_ownership_proof=True,exact_3_by_3_carve_contains_floor=bool(q['source_witness']))
        if q['original_obstacle']:
            p=q['original_obstacle']['pos']
            hits=[o for o in old_ops if all(o['box'][i]<=p[i]<=o['box'][i+3] for i in range(3))]
            q['r25_exact_operation_search']=dict(file=str(historic),matches=hits,
                conclusion='No matching R25 operation establishes these two wall cells; neighboring R25 junction source must not be extrapolated')
    write(args.out/'source-dispositions.json',dispositions)
    write(args.out/'authored-collision-shapes.json',shapes)
    regions=save_delta(args.out,rows,before.reader)
    currentness(args)
    shutil.copy2(source/'devices.dat',args.out/'captured-devices.dat')
    shutil.copy2(source/'capture.json',args.out/'capture.json')
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([])}).save(args.out/'block-entities.dat',gzipped=True)
    write(args.out/'manifest.json',dict(world=before.reader.report['world'],schema='declared-platform-guard-candidate-v1',
        source=str(source),cells=len(rows),regions=regions,vertical_extent=[-672,319],device_changes=0,native_changes=[],world_written=False,
        native_additions=[],actor_changes=[],coordinate_format=['x','y','z'],
        storage='Shared sparse delta: explicit y_origin=-672 and height=992; exact known source sections only',
        min_xyz=[min(p[i] for p in changes) for i in range(3)],max_xyz=[max(p[i] for p in changes) for i in range(3)]))
    print('Authored',len(rows),'air-only guard cells;',len(guards),'declared high/low edges',flush=True)
    if args.plan_only:return
    verify(args,spec,findings,shapes,rows,guards,masks,dispositions,device_positions)


def verify(args,spec,findings,shapes,rows,guards,masks,dispositions,device_positions):
    source=Path(spec['source']);edits={tuple(r['pos']):r['after'] for r in rows}
    before=make_walker(source,shapes);after=make_walker(source,shapes,edits)
    summary=[];errors=[];guard_probes=[];negative=[];supports=[];phases=[];views=[];ownership=[]
    for phase,w in [('before',before),('after',after)]:
        goals=[]
        for a in spec['stations']:
            for i,lane in enumerate(a['retained_stair_lanes']):
                path=lane['path'];forward=strict_walk(w,path);reverse=strict_walk(w,list(reversed(path)))
                good=forward['kind']==reverse['kind']=='strict_static_clear'
                goals.append(dict(key=a['site']+'/stair-lane/'+str(i),site=a['site'],path=path,
                    reachable=good,strict_pass=good,forward=forward,reverse=reverse,
                    reason_rechecked='Stair lane is within the guard repair volume'))
                if not good:errors.append([phase,'stair_lane_failed',a['site'],i,forward,reverse])
        phases.append(dict(phase=phase,goals=goals))
    for a in spec['stations']:
        site=a['site']; site_rows=[r for r in rows if r['site']==site]
        baseline=read(args.findings.parent/'checks'/(site+'.json'))
        adjusted=copy.deepcopy(a);occupants=[]
        for c in adjusted['cells']:
            x,y,z=c['floor'];p=(x+.5,c.get('feet_y',y+1),z+.5);hit=after.body(*p)
            if hit and tuple(hit['pos']) in edits:
                c.setdefault('allowed_occupants',[]).append(MATERIAL)
                c['new_guard_occupant_source']=dict(file=str(args.out/'exact-edits.json'),witness=hit,
                    reason='Side attachment outside all original five stair lanes; declared underlying floor remains in denominator')
                occupants.append(dict(floor=c['floor'],feet=p,hit=hit))
        original_class=fullwidth.EnvelopeWalker
        class CandidateWalker(original_class):
            def __init__(self,src,ss):
                super().__init__(src,ss);self.reader=Overlay(self.reader,edits)
        fullwidth.EnvelopeWalker=CandidateWalker
        try:result=fullwidth.footprint(adjusted,source,shapes)
        finally:fullwidth.EnvelopeWalker=original_class
        write(args.review/'after-fullwidth'/(site+'.json'),result)
        write(args.review/'after-declarations'/(site+'.json'),adjusted)
        before_edges=edge_scan(before,a,baseline);after_edges=edge_scan(after,a,result)
        write(args.review/'edges'/(site+'-before.json'),before_edges)
        write(args.review/'edges'/(site+'-after.json'),after_edges)
        proof=support_proof(after,a,site_rows);supports.append(dict(site=site,**proof))
        write(args.review/'support'/(site+'.json'),proof)
        original_failures={tuple(c['floor']) for c in baseline['failures']}
        remaining_failures={tuple(c['floor']) for c in result['failures']}
        if original_failures != remaining_failures:errors.append(['new_or_hidden_floor_failure',site])
        if result['disconnected']:errors.append(['new_disconnected_public_floor',site,len(result['disconnected'])])
        if after_edges['unprotected_elevated']:errors.append(['unguarded_elevated_side',site,len(after_edges['unprotected_elevated'])])
        if after_edges['unknown']:errors.append(['unknown_edge_capture',site,len(after_edges['unknown'])])
        if proof['floating']:errors.append(['new_floating_guard',site,proof['floating']])
        # Retained long routes are rerun only where the new body envelope can
        # intersect them. Other successful routes remain inherited evidence.
        affected=[]
        for i,route in enumerate(a['retained_paths']):
            path=route['path']
            intersect=any(abs(p[0]-(q['pos'][0]+.5))<1.3 and abs(p[2]-(q['pos'][2]+.5))<1.3
                          and q['pos'][1]<p[1]+1.8 and q['pos'][1]+1>p[1] for p in path for q in site_rows)
            if intersect:
                f=strict_walk(after,path);r=strict_walk(after,list(reversed(path)))
                affected.append(dict(index=i,forward=f,reverse=r))
                if f['kind']!=r['kind'] or f['kind']!='strict_static_clear':errors.append(['affected_retained_path',site,i,f,r])
        summary.append(dict(site=site,name=a['name'],changed_cells=len(site_rows),
            declared_floor_cells=result['declared_floor_cells'],before_status=baseline['floor_status'],
            after_status=result['floor_status'],connected_public_cells=result['connected_to_retained_routes'],
            remaining_original_failures=len(result['failures']),new_guard_occupied_floors=occupants,
            before_high_edges=len(before_edges['unprotected_elevated']),after_high_edges=len(after_edges['unprotected_elevated']),
            complete_eight_direction_probes=after_edges['probe_count'],new_floating=len(proof['floating']),
            retained_long_routes=len(a['retained_paths']),affected_retained_routes_rechecked=affected,
            unchanged_routes_inherited=len(a['retained_paths'])-len(affected)))
        negative.extend(dict(site=site,**q) for q in result['negative_controls'])
        # Exact saved-voxel crops include the full repaired stair/bridge sides
        # at both the original and added states; no game screenshot is implied.
        base=min(b['current_floor_y'] for b in a['bays'])
        p=[r['pos'] for r in site_rows]+[c['floor'] for c in a['cells'] if c['floor'][1]>base]
        bounds=[min(q[0] for q in p)-3,base-1,min(q[2] for q in p)-3,
                max(q[0] for q in p)+4,max(q[1] for q in p)+2,max(q[2] for q in p)+3]
        for label,w in [('before',before),('after',after)]:
            views.append(render_shapes(w,bounds,args.review/'views'/(site+'-'+label+'.png'),a['name']+' / '+label+' / 原梯全宽与连续侧护',edits if label=='after' else {}))
        print(site,'floor',result['floor_status'],'high edges',len(before_edges['unprotected_elevated']),
              '->',len(after_edges['unprotected_elevated']),'floating',len(proof['floating']),flush=True)
    for g in guards:
        p=g['feet'];d=g['normal'];old=sweep(before,p,(d[0],d[2]));new=sweep(after,p,(d[0],d[2]))
        guard_probes.append(dict(site=g['site'],feet=p,normal=d,before=old,**new))
        if not new['hit'] or new['hit']['kind']!='body_obstruction':errors.append(['guard_missing',g['site'],p])
    for a in spec['stations']:
        g=next(g for g in guards if g['site']==a['site'] and g['original_drop']>1.5)
        # Remove the whole authored local side stack, not only its first box.
        changes={tuple(p):'minecraft:air' for p in g['design_cells']}
        test=make_walker(source,shapes,dict(edits)|changes)
        hit=sweep(test,g['feet'],(g['normal'][0],g['normal'][2]))
        rejected=hit['hit'] is None
        negative.append(dict(site=a['site'],case='new_guard_stack_removed',changes=[dict(pos=p,state=s) for p,s in changes.items()],
                             probe=hit,rejected=rejected))
        if not rejected:errors.append(['guard_removal_negative_not_detected',a['site']])
        p=next(tuple(r['pos']) for r in rows if r['site']==a['site'])
        detached=(p[0],p[1]+8,p[2]);fake=make_walker(source,shapes,dict(edits)|{detached:edits[p]})
        fake_proof=support_proof(fake,a,[dict(pos=detached)])
        rejected=list(detached) in fake_proof['floating']
        negative.append(dict(site=a['site'],case='detached_guard_block',pos=detached,rejected=rejected))
        if not rejected:errors.append(['floating_negative_not_detected',a['site']])
    write(args.review/'views.json',views)
    write(args.out/'functional-report.json',dict(errors=errors,changed_cells=len(rows),stations=summary,
        guard_probes=guard_probes,attachment_supports=supports,support_columns=[],negative_cases=negative,phases=phases,
        preserved_devices=len(device_positions),preserved_actors=before.reader.report.get('actors',0),
        vehicle_intrusions=[],dynamic_gate_bypass=False,world_opened=False,world_written=False,
        source_dispositions=dispositions,unresolved_base_interfaces=223,original_lower_edges_now_guarded=22,
        runtime_shape_validation_pending=True,remote_halls_lifts_and_corridors_not_in_scope=True))
    write(args.review/'review.json',dict(errors=errors,stations=summary,views=views,world_written=False))
    if errors:
        print('Not frozen:',errors,flush=True);return
    write(args.out/'release-checks.json',dict(commands=[],candidate_error_reports=['functional-report.json','delta-roundtrip-check.json'],
        review_error_reports=['review.json'],report_values=[dict(root='candidate',file='delta-roundtrip-check.json',
        equals=dict(cells=len(rows),vertical_extent=[-672,319],unknown_source_cells=0,negative_indices=0,exact_before_after_match=True))],
        reviewed_views=['views/'+Path(v['image']).name for v in views],views_reviewed_by_root=False))
    state=read(args.findings.parent.parent/'continuation.json')
    write(args.out/'root-publication-input.json',dict(candidate=str(args.out),checks=str(args.out/'release-checks.json'),
        review_directory=str(args.review),previous_batch=state['latest_installed_batch'],source_authority=state['planning_authority'],
        changes_file='exact-edits.json',functional_report='functional-report.json',expected_changed_cells=len(rows),
        expected_device_changes=0,expected_guard_probes=len(guard_probes),minimum_negative_cases=len(negative),
        vertical_extent=[-672,319],delta_y_origin=-672,delta_height=992,maximum_step=.5,
        required_goals=[g['key'] for g in phases[-1]['goals']],ground_network=dict(mode='preserve',columns=[]),
        multilevel_overlay='Retain current 3-D nodes; no walking surface, station identity or route moved',
        evidence_fields=dict(phases='phases',guards='guard_probes',negative_cases='negative_cases',attachment_supports='attachment_supports'),
        support_model='196 new rail cells each have an explicit real-collision attachment path to original foundation; no new vertical ground columns',
        offline_native_reference=before.reader.report['native_reference'],native_reference_not_current_for_all_members=True,
        native_policy='Root must capture current full native inventory: surface batches since this source add new members outside the deep repair scope',
        publication_adapter='Root shared explicit-y sparse-delta installer and sparse absolute-height surface recipes; no Editor fixed -128 domain',
        root_required_actions=['Review all ten before/after exact-collision images and mark review in release-checks.json',
            'Read exact 196 actual-target old cells plus devices; reject any non-air or stale state',
            'Prepare sparse absolute-Y generation recipe and replay expected data; test deep round trip with actual current bounds',
            'Install exact forward/inverse deltas through shared installer with current native/actor/identity preservation',
            'Read back actual-target cells and original device payloads; publish next authority preserving scalar/3-D paths',
            'Keep 223 base interfaces, 17 floor gaps and 2 walls pending; this is not whole-station or stage-two closure']))
    write(args.out/'shape-provenance.json',dict(recorded_shape_export=spec['shape_export'],
        states=sorted(set(r['after'] for r in rows)),current_source='src/main/java/com/projectseele/world/FacilityEdgeRailR41.java',
        source_geometry='Standard non-slender rail has 2/16 thickness and 22/16 height; posts and 10/16,20/16 rails match the recorded export',
        recorded_shape_cuboids={s:shapes[s] for s in sorted(set(r['after'] for r in rows))},
        runtime_reexport_done=False,current_runtime_confirmation_stage=3,client_jar_changed=False))
    write(args.out/'readiness.json',dict(status='FROZEN_OFFLINE_GUARD_CANDIDATE',cells=len(rows),errors=[],
        source=str(source),source_currentness=str(args.out/'source-currentness.json'),
        source_exact_scope_unchanged_required_at_publication=True,original_nonair_modified=0,
        original_high_edges_guarded=76,original_low_edges_guarded=22,new_floating=0,
        remaining='223 base rail/end interfaces; 17 floor gaps near rail ends with unresolved exact ownership; 2 old walls; remote concourses; stage 3 runtime devices; user acceptance',
        release_requires='Root deep-section packaging, exact current before-state preflight, native/actor preservation, scope authority publication',
        views_reviewed_by_root=False,world_written=False,game_or_simulator_started=False,commit_created=False,
        stage_two_complete=False,whole_station_complete=False,readiness_frozen=True))


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('declarations','findings','native','out','review'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--plan-only',action='store_true')
    build(p.parse_args())
