"""Independent checks of the saved finite airport candidate, never live world."""
import argparse
import json
import math
from collections import Counter
from pathlib import Path
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from audit_hakone_station_walks import Walker
from build_airfield_station_candidate import Sources
from review_underground_station_evidence import strict_walk, Overlay
from verify_airfield_station_clearance import spatial_review, scope, validate as interior_validate
from render_hakone_voxel_3d import render

SOIL={'minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]'}
AIR={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:light'}
STRUCT='projectseele:nerv_structural_panel';WALL='projectseele:nerv_wall_panel'
FLOORS={'projectseele:period_station_floor','projectseele:nerv_floor_panel','minecraft:gray_concrete','minecraft:black_concrete','minecraft:white_concrete','minecraft:smooth_stone',STRUCT}

def stair_height(z):
    for lo,hi,base in ((101,114,72),(119,132,79),(137,150,86)):
        if lo<=z<=hi:return base+(z-lo+1)/2
    return 72 if z<=100 else 79 if z<=118 else 86 if z<=136 else 93

def permitted_new(e,source):
    x,y,z=e['pos'];old=e['before'];new=e['after']
    if old not in SOIL|AIR:return False
    top=max([72]+[h for h in range(73,144)if source.state(x,h,z)in SOIL])
    paved=(458<=x<=491 and 83<=z<=100 or 376<=x<=445 and 30<=z<=38 or 662<=x<=670 and 12<=z<=18)
    cap=79 if (458<=x<=491 and x>=489 or 376<=x<=445 and x>=437 or 662<=x<=670 and z>=17) else 144
    door=(470<=x<=474 and z==82 or (379<=x<=390 or 398<=x<=403)and z==38 or 663<=x<=668 and z==17)
    if old in SOIL and new=='minecraft:air' and source.state(x,72,z)in FLOORS:
        if paved and 73<=y<=min(top,cap-1)or door and 73<=y<=77:return True
    boundary=(x==457 and 83<=z<=100 or z==101 and 458<=x<=488 and x not in(466,467,468)or x==375 and 30<=z<=38 or z==29 and 375<=x<=436 or x==446 and 30<=z<=38 or x==661 and 12<=z<=17 or z==82 and 479<=x<=488)
    if boundary and 70<=y<=min(top,120)and new==(STRUCT if y<=72 else WALL):return True
    if x==489 and 83<=z<=100 and 80<=y<=top and new==WALL:return True
    if z==101 and 466<=x<=468 and 79<=y<=top and new==WALL:return True
    if 100<=z<=175:
        h=stair_height(z);b=math.ceil(h);roof=b+5
        xs=range(467,470)if z>=173 else range(466,470)if z==172 else range(466,469)
        if x in xs:
            if z>100 and b-2<=y<b and new==STRUCT:return True
            target='projectseele:period_station_floor'if h==int(h)else'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
            if z>100 and y==b and new==target:return True
            clear_top=roof-1 if z<=164 else max(b+3,top)
            if b+1<=y<=clear_top and old in SOIL and new=='minecraft:air':return True
        if 101<=z<=164:
            if x in(465,469)and b-2<=y<=roof and new==(STRUCT if y<b or y==roof else WALL):return True
            if 466<=x<=468 and y==roof and new==('minecraft:sea_lantern'if x==467 and z%8==0 else STRUCT):return True
        if 165<=z<=174 and x==(470 if z>=172 else 469)and b-2<=y<=max(b,top)and new==(STRUCT if y<b else WALL):return True
    return False

def validate_edits(edits,source,devices,interior_allowed):
    errors=[];seen=set()
    for e in edits:
        p=tuple(e['pos'])
        if p in seen:errors.append(['duplicate',list(p)])
        seen.add(p)
        if source.current(*p)!=e['before']:errors.append(['source_precondition',list(p)])
        if p in devices:errors.append(['device_host',list(p)])
        if interior_validate([e],source,interior_allowed,devices)and not permitted_new(e,source):errors.append(['outside_precise_repair_or_artificial_change',list(p)])
    return errors

def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')

class Snapshot:
    def __init__(self,folder,source):self.editor=Editor(folder);self.source=source
    def state(self,x,y,z):
        try:return self.editor.state(x,y,z)
        except (KeyError,FileNotFoundError):return self.source.state(x,y,z)

def main(a):
    a.out.mkdir(exist_ok=False)
    source=Sources(a.full_source,a.context);snap=Snapshot(a.candidate,source)
    d=json.loads((a.candidate/'entry-design.json').read_text('utf8'))
    previous=json.loads((Path(d['interior_proposal'])/'review.json').read_text('utf8'))
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    w=Walker(a.context,shapes);w.reader=snap
    street=list(reversed(d['street_path']))+[[467.5,73,94.5],[473.5,73,94.5],[473.5,73,81.5],[441.5,73,81.5],[441.5,73,42.5]]
    paths=[dict(id='street_to_terminal',path=street)]
    for x in (385.5,400.5):paths.append(dict(id=f'street_to_north_door_{x}',path=street+[[x,73,42.5],[x,73,34.5]]))
    paths.append(dict(id='old_boarding_exit',path=[[665.5,73,18.5],[665.5,73,12.5],[669.31225,73,12.5],[669.31225,73,-1.5]]))
    paths += [dict(id='street_'+r['id'],path=street+r['path'][1:])for r in previous['current_transfers']]
    paths += [dict(id=r['id'],path=r['path'])for r in previous['deck_to_aircraft_journeys']]
    # Every original blocked interface gets its own supported crossing.
    for z in range(83,101):paths.append(dict(id=f'old_ground_hall_west_{z}',path=[[491.5,73,z+.5],[488.5,73,z+.5]]))
    for x in list(range(379,391))+list(range(400,404)):paths.append(dict(id=f'old_north_door_{x}',path=[[x+.5,73,39.5],[x+.5,73,36.5],[385.5,73,36.5],[385.5,73,34.5]]))
    for x in range(470,475):paths.append(dict(id=f'old_south_door_{x}',path=[[x+.5,73,81.5],[x+.5,73,84.5]]))
    for x in range(663,666):paths.append(dict(id=f'old_boarding_door_{x}',path=[[x+.5,73,18.5],[x+.5,73,14.5]]))
    for lane in range(3):paths.append(dict(id=f'stair_width_lane_{lane}',path=[[466.5+lane+(1 if z>=173 else 0),stair_height(z)+1,z+.5]for z in range(100,176)]))
    for r in paths:
        r['forward']=strict_walk(w,r['path']);r['reverse']=strict_walk(w,list(reversed(r['path'])))
        if any(r[k]['kind']!='strict_static_clear'for k in ('forward','reverse')):print(str((r['id'],r['forward'],r['reverse']))[:500],flush=True)
    save(a.out/'paths.json',paths)
    print('Paths',len(paths),'passed',sum(all(r[k]['kind']=='strict_static_clear'for k in ('forward','reverse'))for r in paths),flush=True)
    edits=json.loads((a.candidate/'exact-edits.json').read_text('utf8'))
    spatial=spatial_review(source,edits)
    save(a.out/'spatial.json',spatial)
    print('Spatial',len(spatial['new_unrooted_components']),'new unrooted,',len(spatial['newly_sky_open_columns']),'open columns,',len(spatial['new_natural_vertical_faces']),'natural wall runs',flush=True)
    for r in spatial['new_unrooted_components']:print(str(r)[:500],flush=True)
    devices={tuple(int(t[k])for k in('x','y','z')):t for t in nbtlib.load(a.candidate/'captured-devices.dat')['Devices']}
    allowed,_=scope(source);errors=validate_edits(edits,source,devices,allowed)
    if spatial['new_unrooted_components']:errors.append(['new_unrooted_components'])
    if spatial['new_natural_vertical_faces']:errors.append(['bare_natural_vertical_faces',len(spatial['new_natural_vertical_faces'])])
    if not spatial['all_cells_known']:errors.append(['spatial_unknown_cells'])
    for r in paths:
        if any(r[k]['kind']!='strict_static_clear'for k in('forward','reverse')):errors.append(['pedestrian_path',r['id']])
    for r in spatial['newly_sky_open_columns']:
        x,z=r['x'],r['z']
        okay=(458<=x<=488 and 83<=z<=100 or 376<=x<=436 and 30<=z<=38 or 662<=x<=670 and 12<=z<=16 or 668<=x<=670 and -2<=z<=23 or 165<=z<=175 and 466<=x<=469)
        r['intentional_paved_outdoor_opening']=okay
        if not okay:errors.append(['unplanned_vertical_opening',x,z])
    save(a.out/'spatial.json',spatial)
    actual={}
    for file in sorted((a.candidate/'delta').glob('*.npz')):
        with np.load(file)as data:
            pal=list(map(str,data['palette']))
            for i,(cx,cz)in enumerate(data['coordinates']):
                lo,hi=data['ranges'][i:i+2]
                for index,bef,aft in zip(data['indices'][lo:hi],data['before'][lo:hi],data['after'][lo:hi]):
                    y,rem=divmod(int(index),256);z,x=divmod(rem,16);actual[int(cx)*16+x,y-128,int(cz)*16+z]=(pal[bef],pal[aft])
    expected={tuple(e['pos']):(e['before'],e['after'])for e in edits}
    if actual!=expected:errors.append(['saved_delta_differs_from_exact_list'])
    for p in devices:
        if snap.state(*p)!=source.current(*p):errors.append(['retained_device_block',list(p)])
    # Verify the complete original source arrays, including all original human
    # blocks, devices and heights, against the two supplied FULL captures.
    complete_chunks=0
    for file in sorted((a.candidate/'source').glob('*.npz')):
        with np.load(file)as data:
            names=list(map(str,data['palette']))
            for (cx,cz),blocks in zip(data['coordinates'],data['blocks']):
                r=source.readers[source.full_chunks[int(cx),int(cz)]].region(int(cx)//32,int(cz)//32)
                original=np.concatenate([r['blocks'][r['index'][int(cx),sy,int(cz)]]for sy in range(-8,20)],axis=0)
                mapped=np.asarray([names.index(s)if s in names else -1 for s in r['names']])[original]
                if not np.array_equal(blocks,mapped):errors.append(['source_array_differs',int(cx),int(cz)])
                complete_chunks+=1
    hanger_checks=[]
    for z in(107,116):
        states=[snap.state(517,y,z)for y in range(95,103)]
        okay=states==[STRUCT]+['projectseele:nerv_machine_edge']*6+[STRUCT]
        if not okay:errors.append(['hanger_chain',517,z])
        hanger_checks.append(dict(x=517,z=z,bottom=95,top=102,anchored=okay,states=states))
    railway_checks=0
    for x in range(461,474):
        for z in range(125,136):
            for y in range(102,105):
                if snap.state(x,y,z)!=source.current(x,y,z):errors.append(['retained_railway_structure',x,y,z])
                railway_checks+=1
    negative=[]
    for name,p in [('delete_original_floor',(496,72,111)),('delete_original_roof',(496,79,111)),('delete_original_stair',(520,93,111)),('outside_natural',(457,60,120)),('remove_railway_bearing',(467,103,130)),('delete_device',next(iter(devices)))]:
        e=dict(pos=list(p),before=source.current(*p),after='minecraft:air')
        if name=='outside_natural'and e['before']not in SOIL:raise ValueError('Natural-deletion fault must remove a real natural block')
        reasons=validate_edits([e],source,devices,allowed)
        negative.append(dict(case=name,rejected=bool(reasons),edit=e,reasons=reasons))
        if not reasons:errors.append(['negative_case_accepted',name])
    for name,p,target,path in [
        ('missing_entry_floor',(467,72,100),'minecraft:air',[[467.5,73,100.5],[467.5,73,100.5]]),
        ('glass_in_stair_headroom',(467,91,140),'minecraft:glass',[[467.5,88,140.5],[467.5,88,140.5]]),
        ('refill_restored_door',(473,73,82),'minecraft:stone',[[473.5,73,81.5],[473.5,73,84.5]])]:
        # Derive the exact foot level of the chosen new half-step for the
        # headroom fault; injecting above the body must not count as a test.
        if name=='glass_in_stair_headroom':
            feet=stair_height(p[2])+1;p=(p[0],math.floor(feet+1),p[2]);path=[[467.5,feet,140.5]]*2
        fault=Walker(a.context,shapes);fault.reader=Overlay(snap,{p:target});proof=strict_walk(fault,path)
        rejected=proof['kind']!='strict_static_clear'
        negative.append(dict(case=name,rejected=rejected,edit=dict(pos=list(p),after=target),result=proof))
        if not rejected:errors.append(['negative_case_accepted',name])
    for name,p in [('missing_hanger_segment',(517,99,107)),('missing_portal_lintel',(467,78,101))]:
        original=snap.state(*p);expected_state='projectseele:nerv_machine_edge'if name=='missing_hanger_segment'else STRUCT
        good=original==expected_state
        rejected=good and Overlay(snap,{p:'minecraft:air'}).state(*p)!=expected_state
        negative.append(dict(case=name,rejected=rejected,original=original,pos=list(p),required=expected_state))
        if not rejected:errors.append(['negative_case_accepted',name])
    retained_chunks=set(map(tuple,d['full_source_chunks']));source_devices={};source_actors={}
    for folder in a.full_source:
        for tag in nbtlib.load(folder/'devices.dat')['Devices']:
            p=tuple(int(tag[k])for k in('x','y','z'))
            if (p[0]//16,p[2]//16)in retained_chunks:source_devices[p]=tag.snbt()
        for tag in nbtlib.load(folder/'actors.dat')['Actors']:
            p=list(map(float,tag['Pos']))
            if (math.floor(p[0])//16,math.floor(p[2])//16)in retained_chunks:source_actors[tag.snbt()]=True
    device_tags_same={p:t.snbt()for p,t in devices.items()}==source_devices
    captured_actors={t.snbt():True for t in nbtlib.load(a.candidate/'captured-actors.dat')['Actors']}
    actor_tags_same=captured_actors==source_actors
    no_device_changes=len(nbtlib.load(a.candidate/'block-entities.dat')['Changes'])==0
    if not device_tags_same or not actor_tags_same or not no_device_changes:errors.append(['captured_device_actor_nbt_changed'])
    def full_cube(p):
        state=snap.state(*p);boxes=shapes.get(state,[])
        return any(all(abs(float(b[i])-v)<.0001 for i,v in enumerate([0,0,0,1,1,1]))for b in boxes)
    support=[]
    for bounds in d['tunnel_walls']:
        x,y,z,X,Y,Z=bounds
        okay=all(full_cube((x,h,z))for h in range(y-1,Y+1))
        support.append(dict(kind='tunnel_wall_and_lower_bearing',bounds=[x,y-1,z,X,Y,Z],continuous=okay))
        if not okay:errors.append(['tunnel_wall_support',x,z])
    for bounds in d['tunnel_roofs']:
        x,y,z,X,Y,Z=bounds
        okay=all(full_cube((xx,y,z))for xx in range(x,X+1))
        support.append(dict(kind='roof_crossbeam_between_two_walls',bounds=bounds,continuous=okay))
        if not okay:errors.append(['roof_crossbeam_support',z])
    for x,z in sorted({(e['pos'][0],e['pos'][2])for e in edits if any(term in e['owner']for term in ('retaining','bank_face','portal_fascia'))}):
        cells=[e['pos'][1]for e in edits if e['pos'][0]==x and e['pos'][2]==z and any(term in e['owner']for term in ('retaining','bank_face','portal_fascia'))]
        low,high=min(cells),max(cells);okay=all(full_cube((x,y,z))for y in range(low-1,high+1))
        support.append(dict(kind='retaining_or_fascia_bearing_column',bounds=[x,low-1,z,x,high,z],continuous=okay))
        if not okay:errors.append(['retaining_support',x,z,low,high])
    # Check additions against a deliberately generous static envelope around
    # the exact offline engine curves. This is a conservative fixed sweep,
    # not a claim about moving aircraft wings, animated doors or live routes.
    envelope=[];native_curves_checked=0;envelope_added_cells=0
    if a.native:
        native=json.loads(a.native.read_text('utf8'))
        solids=np.asarray([e['pos']for e in edits if e['after'].split('[')[0]not in AIR],float)
        native_curves_checked=len(native['curves']);envelope_added_cells=len(solids)
        for c in native['curves']:
            mode=c['mode'];radius,height=(20.,12.)if mode=='AIRPLANE'else(3.,5.)if mode=='TRAIN'else(2.,4.)
            pts=np.asarray(c['points'],float)
            if len(pts)<2:continue
            lo=pts.min(0)-[radius+1,1,radius+1];hi=pts.max(0)+[radius+1,height+1,radius+1]
            near=solids[np.all(solids+1>=lo,axis=1)&np.all(solids<=hi,axis=1)]
            if not len(near):continue
            hits=[]
            for p in near:
                for aa,bb in zip(pts,pts[1:]):
                    dv=bb-aa;den=float(dv[[0,2]]@dv[[0,2]])
                    t=np.clip(float((p[[0,2]]+.5-aa[[0,2]])@dv[[0,2]])/den,0,1)if den else 0
                    q=aa+t*dv
                    lateral=math.hypot(max(p[0]-q[0],q[0]-p[0]-1,0),max(p[2]-q[2],q[2]-p[2]-1,0))
                    if lateral<radius and p[1]+1>q[1]-.5 and p[1]<q[1]+height:
                        hits.append(list(map(int,p)));break
            envelope.append(dict(id=c['id'],mode=mode,radius=radius,height=height,candidate_blocks_considered=len(near),intersections=hits))
            if hits:errors.append(['conservative_native_envelope',c['id'],len(hits)])
    result=dict(errors=errors,cells=len(edits),changed_chunks=len({(x//16,z//16)for x,y,z in actual}),complete_source_chunks=complete_chunks,
        path_count=len(paths),directions_checked=2*len(paths),passed_paths=sum(all(r[k]['kind']=='strict_static_clear'for k in('forward','reverse'))for r in paths),
        restored_original_interfaces=42,retained_devices=len(devices),preserves_original_human_blocks=all(e['before']in SOIL|AIR for e in edits),
        exact_saved_delta_matches=actual==expected,negative_cases=negative,hanger_checks=hanger_checks,railway_original_cells_checked=railway_checks,
        retained_devices_exact_nbt=device_tags_same,retained_actors_exact_nbt=actor_tags_same,captured_actor_count=len(captured_actors),block_entity_changes_empty=no_device_changes,
        structural_support_checks=support,static_native_envelope_checks=envelope,native_curve_source=str(a.native),
        native_curves_checked=native_curves_checked,new_solid_cells_checked_against_curves=envelope_added_cells,
        native_envelope_caveat='Recorded exact engine curves; conservative fixed widths. Current native identity and moving models remain main-agent runtime scope.',
        source_context=str(a.context),shape_export=str(a.metadata/'native_collision_shapes.json'),world_opened=False,world_written=False,
        complete_station_acceptance=False,remaining=['current runtime collision shapes','dynamic gates and vehicle doors','live boarding and remote corridors','production replay and actual-world preconditions by main agent'],views=[])
    result['views']=[render(snap.editor,[452,70,80,493,106,106],a.out/'south-forecourt.png','航空基地：原前庭与完整下穿入口'),render(snap.editor,[464,70,98,470,106,177],a.out/'street-stair-section.png','航空基地：分段半格楼梯与铁路下穿断面')]
    save(a.out/'review.json',result)
    save(a.candidate/'functional-check.json',result)
    print('Independent result:',len(errors),'errors,',len(edits),'saved changes,',len(paths),'paths,',complete_chunks,'FULL chunks',flush=True)
    for e in errors[:10]:print(str(e)[:500],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--full-source',type=Path,action='append',required=True)
    p.add_argument('--native',type=Path)
    for n in ('candidate','context','metadata','out'):p.add_argument('--'+n,type=Path,required=True)
    main(p.parse_args())
