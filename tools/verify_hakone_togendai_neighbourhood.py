"""Independent saved-block/NBT checks for the composed station neighbourhood."""
import argparse,copy,json
from pathlib import Path
from collections import deque,Counter
import numpy as np
import nbtlib
from scipy.ndimage import label
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from map_pipeline.corridors import alignment
from prepare_hakone_togendai_neighbourhood import save_json
from verify_hakone_network_candidate import PAVEMENT
from query_blocks import AIR
from plan_ashi_landscape_r54 import SOIL

def verify(candidate):
    with np.load(candidate/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);e=Editor(candidate);errors=[];walk=d['walk'];g=d['grade2'];checked=0
    from map_pipeline.retained_public import verify as verify_retained_public
    retained_public=verify_retained_public(candidate,e);errors.extend(retained_public['errors'])
    save_json(candidate/'retained-public-check.json',retained_public)
    covered=d.get('covered',np.zeros(walk.shape,bool))
    specs=json.loads((candidate/'plan/authored-design.json').read_text('utf8'))
    from map_pipeline.entrance_infill import validated_apron_infill
    apron_infill=validated_apron_infill(e,specs,json.loads((candidate/'plan/buildings.json').read_text('utf8')),
                                       json.loads((candidate/'plan/native-curves.json').read_text('utf8')))
    for pos,state in apron_infill.items():
        if e.state(*pos)!=state:errors.append(['protected exterior apron infill differs',*pos,e.state(*pos)])
    pavement=PAVEMENT|set(specs.get('retained_pavement_materials',[]))
    empty=AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern'}
    for j,i in np.argwhere(walk):
        px,pz=int(i+x),int(j+z);floor,slab=road_blocks(g[j,i]);floor=int(floor);state=e.state(px,floor,pz)
        if state.split('[')[0]not in pavement or ('type=bottom'in state)!=bool(slab):errors.append(['pavement',px,floor,pz,state,bool(slab)])
        for Y in range(floor+1,floor+(5 if d['road'][j,i]or covered[j,i]else 4)):
            state=e.state(px,Y,pz)
            if state.split('[')[0]not in empty:errors.append(['headroom',px,Y,pz,state])
        # The deck needs a real bearing immediately below it. A passable top
        # surface alone would still accept a floating or hollow road tray.
        for Y in range(floor-2,floor):
            state=e.state(px,Y,pz)
            if state.split('[')[0]in AIR|{'minecraft:water','minecraft:light'}:
                pocket=[px,Y,pz]in specs.get('retained_water_bearing_pockets',[])
                bank=any(e.state(px+dx,Y,pz+dz).split('[')[0]in SOIL for dx,dz in ((-1,0),(1,0),(0,-1),(0,1)))
                if not(pocket and Y==floor-2 and state==e.state(px,Y,pz,True) and state.startswith('minecraft:water') and bank):
                    errors.append(['pavement bearing',px,Y,pz,state])
        checked+=1
    covered_roofs=[]
    for j,i in np.argwhere(covered&walk):
        px,pz=int(i+x),int(j+z);floor=int(road_blocks(g[j,i])[0]);roof=None
        for Y in range(floor+5,min(320,floor+13)):
            state=e.state(px,Y,pz);bare=state.split('[')[0]
            if bare in SOIL|PAVEMENT or bare.endswith('_concrete')or bare in {'minecraft:stone_bricks','minecraft:deepslate_bricks'}:
                roof=[px,Y,pz];break
        if roof is None:errors.append(['covered road has no continuous roof',px,floor,pz])
        else:covered_roofs.append(dict(pos=roof,clear_blocks=roof[1]-floor-1))
    seed=specs.get('connectivity_seed',[-287,1000]);start=(seed[1]-z,seed[0]-x)
    if not walk[start]:raise ValueError(('Connectivity seed is not public pavement',seed))
    seen=np.zeros(walk.shape,bool);queue=deque([start]);seen[start]=True
    while queue:
        j,i=queue.popleft()
        for J,I in ((j-1,i),(j+1,i),(j,i-1),(j,i+1)):
            if 0<=J<walk.shape[0] and 0<=I<walk.shape[1] and walk[J,I] and not seen[J,I] and abs(int(g[J,I])-int(g[j,i]))<=1:
                seen[J,I]=True;queue.append((J,I))
    disconnected=walk&~seen
    groups,n=label(disconnected);sizes=np.bincount(groups.ravel())
    if disconnected.any():
        for k in range(1,n+1):
            j,i=np.argwhere(groups==k)[0];errors.append(['disconnected public surface',int(i+x),int(j+z),int(sizes[k])])
    outdoor={tuple(r['pos']):r for r in json.loads((candidate/'outdoor-apron-corrections.json').read_text('utf8'))}
    payload_cells=0;payload_exceptions=0;payloads=list(sorted((candidate/'payloads').glob('*.npz'),key=lambda p:int(p.stem)))
    for path in payloads:
        with np.load(path)as f:box=f['bounds'];dy=int(f['dy']);shift=list(map(int,f['translation']))if 'translation'in f else[0,dy,0];v=f['blocks'];names=list(map(str,f['palette']))
        for sx in range(int(box[0]),int(box[3])+1):
            for sz in range(int(box[2]),int(box[5])+1):
                px,pz=sx+shift[0],sz+shift[2]
                r=e.region(px,pz);col=r['after'][r['index'][px//16,pz//16],int(box[1])+dy+128:int(box[4])+dy+129,pz%16,px%16]
                actual=np.asarray(r['names'])[col];expected=np.asarray(names)[v[:,sz-box[2],sx-box[0]]]
                expected=expected.astype(object)
                for k in range(len(expected)):
                    correction=outdoor.get((px,int(box[1])+dy+k,pz))
                    if correction:
                        payload_exceptions+=1
                        if expected[k]!=correction['before']:errors.append(['unmatched outdoor exception',px,int(box[1])+dy+k,pz])
                        expected[k]=correction['after']
                if not np.array_equal(actual,expected):errors.append(['parcel payload changed',path.name,px,pz,int(np.sum(actual!=expected))])
                payload_cells+=len(col)
    rows=json.loads((candidate/'plan/buildings.json').read_text('utf8'));goals=[]
    for row in rows:
        px,py,pz=row['approach'];floor=py-1
        if e.state(px,floor,pz).split('[')[0]not in PAVEMENT:errors.append(['parcel landing floor',row['id'],px,py,pz])
        reached=False
        for dz,dx in ((1,0),(-1,0),(0,1),(0,-1),(0,0)):
            j,i=pz+dz-z,px+dx-x
            if seen[j,i] and abs(int(g[j,i])-2*floor)<=1:reached=True
        if not reached:errors.append(['parcel approach disconnected',row['id'],px,py,pz])
        goals.append(dict(id=row['id'],approach=row['approach'],connected=reached))
        door=e.state(*row['door'])
        if 'door'not in door:errors.append(['retained entrance changed',row['id'],door])
    originals={tuple(int(t[k])for k in ('x','y','z')):t for t in nbtlib.load(candidate/'captured-devices.dat')['Devices']}
    cable_columns={}
    for row in json.loads((candidate/'plan/native-curves.json').read_text('utf8'))['ropeway']:
        for px,py,pz in row['points']:
            px,py,pz=map(int,np.floor([px,py,pz]))
            if px<x-3 or px>X+3 or pz<z-3 or pz>Z+3:continue
            for Q in range(px-3,px+4):
                for R in range(pz-3,pz+4):
                    if x<=Q<=X and z<=R<=Z:cable_columns.setdefault((Q,R),set()).update(range(py-10,py+7))
    cable_cells=0
    for (px,pz),ys in cable_columns.items():
        for py in ys:
            if e.state(px,py,pz)!=e.state(px,py,pz,True):errors.append(['native cable swept volume changed',px,py,pz])
            cable_cells+=1
    train_cells=0;train_ground_exemptions=0;train_ground_changes=0
    if specs.get('preserve_train_corridors',False):
        underpass_prior=None
        if specs.get('train_underpasses'):
            with np.load(Path(specs['train_underpass_prior_plan'])/'network.npz')as f:
                underpass_prior={k:f[k]for k in ('bounds','walk','grade2')}
        columns={}
        for row in json.loads((candidate/'plan/native-curves.json').read_text('utf8'))['trains']:
            for px,py,pz in row['points']:
                px,py,pz=map(int,np.floor([px,py,pz]))
                if px<x-8 or px>X+8 or pz<z-8 or pz>Z+8 or py<-100 or py>310:continue
                for Q in range(px-8,px+9):
                    for R in range(pz-8,pz+9):
                        if not(x<=Q<=X and z<=R<=Z):continue
                        lo,hi=columns.get((Q,R),(320,-129));columns[Q,R]=(min(lo,py-30),max(hi,py+7))
        deck_limits={}
        if specs.get('train_underpass_roof_infill'):
            from map_pipeline.rail_underpasses import physical_deck_ceilings
            for box in specs['train_underpass_roof_infill']:
                deck_limits.update(physical_deck_ceilings(json.loads((candidate/'plan/native-curves.json').read_text('utf8'))['trains'],[box[0],box[2],box[3],box[5]]))
        for (px,pz),(lo,hi)in columns.items():
            r=e.region(px,pz);idx=r['index'][px//16,pz//16];a,b=max(-128,lo)+128,min(319,hi)+129
            original=r['before'][idx,a:b,pz%16,px%16];actual=r['after'][idx,a:b,pz%16,px%16]
            keep=np.ones(len(original),bool)
            if underpass_prior is not None:
                from map_pipeline.rail_underpasses import editable_underpass_column
                ux,uz,_,_=map(int,underpass_prior['bounds'])
                keep&=~editable_underpass_column(e,px,pz,a-128,b-129,specs['train_underpasses'],underpass_prior['walk'][pz-uz,px-ux],underpass_prior['grade2'][pz-uz,px-ux])
            if specs.get('train_underpass_roof_infill'):
                from map_pipeline.rail_underpasses import allowed_roof_infill_column
                keep&=~allowed_roof_infill_column(e,px,pz,a-128,b-129,specs['train_underpass_roof_infill'],deck_limits.get((px,pz)))
            if not np.array_equal(original[keep],actual[keep]):errors.append(['native rail structure or clearance changed',px,pz,int(((original!=actual)&keep).sum())])
            train_cells+=int(keep.sum())
            train_ground_exemptions+=int((~keep).sum())
            train_ground_changes+=int(((original!=actual)&~keep).sum())
    changes=nbtlib.load(candidate/'block-entities.dat')['Changes'];before={};after={}
    for r in changes:
        for key,table in [('Before',before),('After',after)]:
            if key in r:
                tag=r[key];pos=tuple(int(tag[k])for k in ('x','y','z'));table[pos]=tag
    preserved_cells=0
    retained_boxes=json.loads((candidate/'plan/retained-buildings.json').read_text('utf8'))
    retained_boxes=[[b[0]-2,b[1]-3,b[2]-2,b[3]+2,b[4]+8,b[5]+2]for b in retained_boxes]
    for box in list(specs.get('protected_volumes',[]))+retained_boxes:
        # Designs can carry the complete global station inventory. Only the
        # intersection with this finite capture can be edited or verified.
        box=[max(box[0],x),box[1],max(box[2],z),min(box[3],X),box[4],min(box[5],Z)]
        if box[0]>box[3] or box[2]>box[5]:continue
        for cx in range(box[0]//16,box[3]//16+1):
            for cz in range(box[2]//16,box[5]//16+1):
                r=e.region(cx*16,cz*16);idx=r['index'].get((cx,cz))
                if idx is None:raise ValueError(('Protected native volume outside captured FULL chunks',box,cx,cz))
                a,b=max(box[1],-128)+128,min(box[4],319)+129
                area=np.s_[a:b,max(box[2]-cz*16,0):min(box[5]-cz*16+1,16),max(box[0]-cx*16,0):min(box[3]-cx*16+1,16)]
                original=r['before'][idx][area];actual=r['after'][idx][area]
                different=original!=actual;exempt=0
                for pos,state in apron_infill.items():
                    px,py,pz=pos
                    if px//16!=cx or pz//16!=cz or not all(box[k]<=pos[k]<=box[k+3]for k in range(3)):continue
                    if e.state(*pos)==state:
                        different[py-(a-128),pz-max(box[2],cz*16),px-max(box[0],cx*16)]=False;exempt+=1
                if different.any():errors.append(['native room or mechanism volume changed',box,cx,cz,int(different.sum())])
                preserved_cells+=original.size-exempt
    moved_positions={tuple(pos)for row in rows for pos in row['devices']}
    retained_tags=0
    for pos,tag in originals.items():
        if pos in moved_positions:continue
        if pos in before or pos in after:errors.append(['unexpected retained device NBT change',pos])
        if e.state(*pos)!=e.state(*pos,True):errors.append(['retained device block changed',pos])
        retained_tags+=1
    checked_tags=0
    for row in rows:
        for pos in row['devices']:
            pos=tuple(pos);tag=originals[pos];shift=row.get('translation',[0,row['dy'],0]);q=tuple(pos[i]+shift[i]for i in range(3));new=copy.deepcopy(tag)
            for key,value in zip(('x','y','z'),q):new[key]=nbtlib.Int(value)
            if before.get(pos)!=tag or after.get(q)!=new:errors.append(['full device NBT changed',row['id'],pos])
            checked_tags+=1
    added_fixtures=0
    if (candidate/'street-details.json').is_file():
        from map_pipeline.retained_street_lamps import verify as verify_lamps
        details=json.loads((candidate/'street-details.json').read_text('utf8'))
        errors.extend(verify_lamps(e,details))
        if len(details.get('retained_lamps',[]))!=len(specs.get('retained_road_lamp_payloads',[])):
            errors.append(['complete retained lamp count'])
        for fixture in json.loads((candidate/'street-details.json').read_text('utf8')).get('native_fixtures',[]):
            pos=tuple(fixture['pos']);kind=fixture['kind'];tag=after.get(pos);state=e.state(*pos)
            if pos in originals or pos in before or not tag or str(tag.get('id'))!='projectseele:period_fixture' or 'kind='+kind not in state:
                errors.append(['new native fixture identity',pos,kind])
            for dy in range(1,fixture['upper_cells']+1):
                if e.state(pos[0],pos[1]+dy,pos[2])!=f'projectseele:period_fixture_part[offset={dy}]':errors.append(['native fixture upper picking cell',pos,dy])
            for dx in (-1,0,1):
                for dz in (-1,0,1):
                    if dx==dz==0:continue
                    for dy in range(3):
                        if e.state(pos[0]+dx,pos[1]+dy,pos[2]+dz).split('[')[0]not in empty:errors.append(['native fixture mesh clearance',pos,dx,dy,dz])
            added_fixtures+=1
    specs=json.loads((candidate/'plan/authored-design.json').read_text('utf8'));profiles=[]
    for row in specs['streets']:
        curve,s=alignment(row);samples=np.arange(0,s[-1]+.1,1.0);cx=np.rint(np.interp(samples,s,curve[:,0])).astype(int);cz=np.rint(np.interp(samples,s,curve[:,2])).astype(int)
        y=g[cz-z,cx-x]/2+1;ten=abs(y[10:]-y[:-10])/10
        span=min(10,len(y)-1)
        profiles.append(dict(id=row['id'],length=float(s[-1]),maximum_actual_10m_grade=float(ten.max())if len(ten)else None,measured_profile_span_metres=span,maximum_actual_profile_grade=float((abs(y[span:]-y[:-span])/span).max())if span else None,maximum_continuous_grade=float((abs(np.diff(curve[:,1]))/np.linalg.norm(np.diff(curve[:,[0,2]],axis=0),axis=1)).max())))
    # A retained seam must remain in the same standing component, including
    # its full surveyed width. No rounded road cap may erase its continuation.
    seams=[]
    for port in specs['retained_ports']:
        row=next(r for r in specs['streets']if r['id']==port['street']);px,py,pz=row['points'][port['end']]
        ys,xs=np.where(d['retained_walk']&((np.indices(walk.shape)[1]+x-px)**2+(np.indices(walk.shape)[0]+z-pz)**2<18**2));contacts=0
        for j,i in zip(ys,xs):
            for J,I in ((j-1,i),(j+1,i),(j,i-1),(j,i+1)):
                if not (0<=J<walk.shape[0]and 0<=I<walk.shape[1]and seen[J,I]):continue
                h=int((g[J,I]+1)//2)
                for fy in range(h-2,h+3):
                    state=e.state(int(i+x),fy,int(j+z));height2=2*fy+(1 if 'type=bottom'in state else 2)
                    if state.split('[')[0]in PAVEMENT and abs(height2-int(g[J,I])-2)<=1 and all(e.state(int(i+x),fy+k,int(j+z)).split('[')[0]in empty for k in (1,2,3)):
                        contacts+=1;break
        seams.append(dict(street=row['id'],contacts=contacts))
        if contacts==0:errors.append(['retained street disconnected',row['id']])
    retained_access=[]
    for route in specs.get('retained_ground_access',[]):
        points=route['points']
        if len(points)<2:errors.append(['empty retained access',route['id']])
        for p,q in zip(points,points[1:]):
            if abs(p[0]-q[0])+abs(p[2]-q[2])!=1 or abs(p[1]-q[1])>.5:errors.append(['noncontinuous retained access',route['id'],p,q])
        for px,py,pz in points:
            floor=int(np.ceil(py))-1
            if e.state(px,floor,pz).split('[')[0]not in pavement|SOIL:errors.append(['retained access floor',route['id'],px,floor,pz])
            if any(e.state(px,Y,pz).split('[')[0]not in empty for Y in range(floor+1,floor+4)):errors.append(['retained access headroom',route['id'],px,py,pz])
            if any(e.state(px,Y,pz)!=e.state(px,Y,pz,True)for Y in range(floor,floor+4)):errors.append(['retained access changed',route['id'],px,py,pz])
        retained_access.append(dict(id=route['id'],columns=len(points),start=points[0],end=points[-1]))
    if (candidate/'underpass-structure.json').exists():
        from finish_hakone_road_underpass import check_structure
        errors.extend(check_structure(candidate))
    report=dict(errors=errors,full_width_columns=checked,reachable_columns=int(seen.sum()),parcel_payload_cells_checked=payload_cells,parcel_payload_cells_exact=payload_cells-payload_exceptions,approved_outdoor_cells=payload_exceptions,complete_device_tags_exact=checked_tags,retained_device_tags_unchanged=retained_tags,native_room_volume_cells_unchanged=preserved_cells,native_rail_corridor_cells_unchanged=train_cells,native_cable_swept_cells_unchanged=cable_cells,parcel_goals=goals,streets=profiles,retained_interfaces=seams,retained_ground_access=retained_access,visual_verified=False,world_written=False)
    report['new_native_fixtures_checked']=added_fixtures
    report['protected_exterior_air_infill_cells']=len(apron_infill)
    report['finite_rail_ground_exception_cells']=train_ground_exemptions
    report['finite_rail_ground_changed_cells']=train_ground_changes
    report['covered_road_columns']=len(covered_roofs)
    report['covered_road_minimum_clearance']=min((r['clear_blocks']for r in covered_roofs),default=None)
    save_json(candidate/'covered-road-roofs.json',covered_roofs)
    save_json(candidate/'independent-check.json',report)
    prior=json.loads((candidate/'functional-check.json').read_text('utf8'));prior.setdefault('composition_errors',prior['errors']);prior['independent_verification_errors']=errors;prior['errors']=prior['composition_errors']+errors;save_json(candidate/'functional-check.json',prior)
    print(json.dumps({k:v for k,v in report.items()if k not in ('errors','parcel_goals')},ensure_ascii=False),flush=True)
    print('Errors',len(errors),Counter(r[0]for r in errors),errors[:18],flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True)
    if verify(p.parse_args().candidate)['errors']:raise SystemExit(1)
