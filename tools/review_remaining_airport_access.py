"""Read-only current-section static review of the two public airport stations."""
import argparse
from collections import Counter,deque
import json
import math
from pathlib import Path
from audit_hakone_station_walks import Walker
from review_underground_station_evidence import strict_walk,Overlay

PAVEMENT={'minecraft:smooth_stone','minecraft:gray_concrete','minecraft:black_concrete','minecraft:white_concrete','minecraft:orange_concrete','minecraft:light_gray_concrete','minecraft:smooth_quartz','minecraft:stone_bricks','minecraft:polished_andesite','minecraft:polished_deepslate','projectseele:period_station_floor','projectseele:nerv_floor_panel','projectseele:nerv_structural_panel','projectseele:station_tactile_warning','mtr:platform'}

def ground_routes(w,start,goals):
    points=[start]+goals;x0=math.floor(min(p[0]for p in points))-10;x1=math.floor(max(p[0]for p in points))+10
    z0=math.floor(min(p[2]for p in points))-10;z1=math.floor(max(p[2]for p in points))+10;feet=start[1]
    root=math.floor(start[0]),math.floor(start[2]);wanted={(math.floor(p[0]),math.floor(p[2]))for p in goals}
    parents={root:None};queue=deque([root]);known={}
    def valid(p):
        if p not in known:
            x,z=p;state=w.reader.state(x,int(feet)-1,z)or''
            known[p]=state.split('[')[0]in PAVEMENT and w.follow([[x+.5,feet,z+.5]]*2)['kind']=='static_clear_provisional'
        return known[p]
    while queue and not wanted.issubset(parents):
        x,z=queue.popleft()
        for p in ((x+1,z),(x-1,z),(x,z+1),(x,z-1)):
            if p in parents or not x0<=p[0]<=x1 or not z0<=p[1]<=z1 or not valid(p):continue
            route=[[x+.5,feet,z+.5],[p[0]+.5,feet,p[1]+.5]]
            if strict_walk(w,route)['kind']!='strict_static_clear'or strict_walk(w,list(reversed(route)))['kind']!='strict_static_clear':continue
            parents[p]=(x,z);queue.append(p)
    result=[]
    for goal in goals:
        p=math.floor(goal[0]),math.floor(goal[2]);path=[]
        if p in parents:
            while p is not None:path.append([p[0]+.5,feet,p[1]+.5]);p=parents[p]
        result.append(path)
    return result,dict(bounds_xz=[x0,z0,x1,z1],visited=len(parents),only_retained_pavement=True)

def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')

def main(a):
    a.out.mkdir(exist_ok=False)
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    cases=json.loads((a.metadata/'quality_walk_cases.json').read_text('utf8'))
    native=json.loads(a.native.read_text('utf8'));walker=Walker(a.source,shapes);rows=[];errors=[];chunks=set()
    ownership=json.loads(a.manifest.read_text('utf8'))
    for name in('箱根湾机场','新箱根机场'):
        site=next(s for s in walker.reader.report['sites']if s['name']==name)
        bound=site['bounds'];paths=[];changes={};gate_rows=[];manual_doors=[]
        for g in ownership['gates']:
            if int(g['station_id'])%(1<<64)!=int(site['native_id'])%(1<<64):continue
            p=tuple(g['position']);observed=walker.reader.state(*p)
            if observed!=g['closed_state']:raise ValueError('Public gate capture does not match manifest '+str(p))
            changes[p]=g['open_state'];gate_rows.append(g)
        opened=Walker(a.source,shapes);opened.reader=Overlay(walker.reader,changes)
        def dense_stair(route):
            z=math.floor(route[0][2]);xlo=math.floor(min(p[0]for p in route));xhi=math.floor(max(p[0]for p in route))
            ylo=int(min(p[1]for p in route))-1;yhi=int(max(p[1]for p in route));steps=[]
            for x in range(xlo,xhi+1):
                for y in range(ylo,yhi+1):
                    state=walker.reader.state(x,y,z)or''
                    if state.startswith('minecraft:smooth_quartz_stairs[facing=east,half=bottom,shape=straight'):
                        steps.append([x+.5,y+1,z+.5])
            if not steps:raise ValueError('No real measured stair treads')
            return [route[0],[steps[0][0]-1,steps[0][1]-1,steps[0][2]]]+steps+[[steps[-1][0]+1,steps[-1][1],steps[-1][2]],route[-1]]
        for c in cases:
            ident=c.get('id','');route=c.get('path')or[c.get('start'),c.get('end')]
            if ident.endswith('/return')or not any(token in ident for token in('/airport/','/station/','/station_entrance/','/station_map/'))or any(p is None for p in route):continue
            if not all(bound[0]<=p[0]<=bound[3]and bound[2]<=p[2]<=bound[5]for p in route):continue
            forward=strict_walk(walker,route);reverse=strict_walk(walker,list(reversed(route)))
            exact=dense_stair(route)if 'stair_'in ident else route
            if '管制塔'in ident:
                point=forward.get('position')or forward.get('pos');issue=walker.body(*point)if point else None
                if issue and issue.get('state','').startswith('minecraft:oak_door['):
                    p=issue['pos'];base=p[1]if 'half=lower'in issue['state']else p[1]-1
                    for y in(base,base+1):
                        cell=p[0],y,p[2];state=walker.reader.state(*cell);target=state.replace('open=false','open=true')
                        if target not in shapes:raise ValueError('Unmeasured manual door state')
                        changes[cell]=target;manual_doors.append(dict(pos=list(cell),closed=state,open=target))
                    opened.cache.clear()
            conditional_forward=strict_walk(opened,exact);conditional_reverse=strict_walk(opened,list(reversed(exact)))
            paths.append(dict(id=ident,path=route,forward=forward,reverse=reverse,
                passed=all(r['kind']=='strict_static_clear'for r in(forward,reverse)),historical_path_not_edit_authority=True,
                measured_stair_path=exact,conditional_open_forward=conditional_forward,conditional_open_reverse=conditional_reverse,
                conditional_static_pass=all(r['kind']=='strict_static_clear'for r in(conditional_forward,conditional_reverse))))
        platform_ids={r['platform_id']for r in native['resolved_platforms']if r['station_name']==name}
        platforms=[p for p in native['platforms']if str(p['id'])in platform_ids]
        def ending(suffix):return next(r for r in paths if r['id'].endswith(suffix))
        stationpath=ending('/terminal_station')['path'];boarding=ending('/station_boarding')['path']
        transfers=[];train=next(p for p in platforms if p['transportMode']=='TRAIN')
        stairs={side:ending('/ordinary_stair_'+str(side))['measured_stair_path']for side in(-1,1)}
        ground,ground_proof=ground_routes(opened,boarding[-1],[stairs[-1][0],stairs[1][0],stationpath[0]])
        ground_by_side={-1:ground[0],1:ground[1]}
        for side in(-1,1):
            stair=stairs[side]
            deck_z=ending('/boarding_corridor_'+str(side))['path'][0][2]
            low,high=sorted((train['position1']['x'],train['position2']['x']))
            for x in range(low,high+1,10):
                prefix=[[x+.5,95,deck_z],[stair[-1][0],95,deck_z]]+list(reversed(stair))
                tail=ground_by_side[side]
                if not tail:transfers.append(dict(id=f'train_{side}_{x}_to_aircraft',path=None,forward=dict(kind='no_paved_ground_connection'),reverse=dict(kind='no_paved_ground_connection'),passed=False));continue
                route=prefix+tail
                f=strict_walk(opened,route);r=strict_walk(opened,list(reversed(route)))
                transfers.append(dict(id=f'train_{side}_{x}_to_aircraft',path=route,forward=f,reverse=r,passed=all(p['kind']=='strict_static_clear'for p in(f,r))))
        full_entries=[];center=(train['position1']['x']+train['position2']['x'])/2+.5
        for side in(-1,1):
            to_air=ground[2];stair_ground=ground_by_side[side];join={tuple(p):i for i,p in enumerate(stair_ground)}
            matches=[(i,join[tuple(p)])for i,p in enumerate(to_air)if tuple(p)in join]
            if not matches:errors.append(['terminal_paved_connection_missing',name,side]);continue
            i,j=matches[0];route=to_air[:i+1]+list(reversed(stair_ground[:j]))+stairs[side][1:]
            deck_z=ending('/boarding_corridor_'+str(side))['path'][0][2];center=(train['position1']['x']+train['position2']['x'])/2+.5
            route += [[route[-1][0],95,deck_z],[center,95,deck_z]]
            f=strict_walk(opened,route);r=strict_walk(opened,list(reversed(route)))
            full_entries.append(dict(id=f'terminal_front_to_train_{side}',path=route,forward=f,reverse=r,passed=all(p['kind']=='strict_static_clear'for p in(f,r))))
        north=ending('/overbridge_stair_-1')['measured_stair_path'];south=ending('/overbridge_stair_1')['measured_stair_path']
        north_z=ending('/boarding_corridor_-1')['path'][0][2];south_z=ending('/boarding_corridor_1')['path'][0][2]
        route=[[center,95,north_z],[north[0][0],95,north_z]]+north+list(reversed(south))+[[south[0][0],95,south_z],[center,95,south_z]]
        f=strict_walk(opened,route);r=strict_walk(opened,list(reversed(route)))
        full_entries.append(dict(id='platforms_via_existing_overbridge',path=route,forward=f,reverse=r,passed=all(p['kind']=='strict_static_clear'for p in(f,r))))
        negative=[]
        for label,cell,target,route in [('missing_boarding_floor',(math.floor(boarding[-1][0]),80,math.floor(boarding[-1][2])),'minecraft:air',[boarding[-1]]*2),
            ('glass_in_boarding_headroom',(math.floor(boarding[-1][0]),82,math.floor(boarding[-1][2])),'minecraft:glass',[boarding[-1]]*2)]:
            fault=Walker(a.source,shapes);fault.reader=Overlay(opened.reader,{cell:target});proof=strict_walk(fault,route);reject=proof['kind']!='strict_static_clear'
            negative.append(dict(case=label,pos=list(cell),original=opened.reader.state(*cell),fault=target,rejected=reject,result=proof))
            if not reject:errors.append(['negative_case_accepted',name,label])
        all_routes=[r['measured_stair_path']for r in paths]+[r['path']for r in transfers+full_entries if r['path']]
        track_hits=[]
        for ri,route in enumerate(all_routes):
            for aa,bb in zip(route,route[1:]):
                n=max(1,math.ceil(math.hypot(bb[0]-aa[0],bb[2]-aa[2])*2))
                for k in range(n+1):
                    v=[aa[i]+(bb[i]-aa[i])*k/n for i in range(3)]
                    for xx in (math.floor(v[0]-.3),math.floor(v[0]+.3)):
                        for zz in (math.floor(v[2]-.3),math.floor(v[2]+.3)):chunks.add((xx//16,zz//16))
                    for platform in platforms:
                        p=platform['position1'];q=platform['position2']
                        if not p['y']-.5<=v[1]<=p['y']+4.2:continue
                        dx,dz=q['x']-p['x'],q['z']-p['z'];u=max(0,min(1,((v[0]-p['x']-.5)*dx+(v[2]-p['z']-.5)*dz)/(dx*dx+dz*dz)))
                        if math.hypot(v[0]-p['x']-.5-u*dx,v[2]-p['z']-.5-u*dz)<2:track_hits.append(dict(route=ri,platform=str(platform['id']),point=v));break
        if track_hits:errors.append(['platform_track_space_crossing',name,len(track_hits)])
        row=dict(name=name,site=site['id'],bounds=bound,platforms=platforms,paths=paths,paths_checked=len(paths),passed=sum(r['passed']for r in paths),
            conditional_static_passed=sum(r['conditional_static_pass']for r in paths),public_gate_manifest_rows=gate_rows,manual_door_states=manual_doors,
            conditional_train_aircraft_transfers=transfers,transfer_passed=sum(r['passed']for r in transfers),
            measured_paved_ground_routes=ground,ground_graph=ground_proof,
            full_terminal_entry_and_platform_exchange=full_entries,negative_cases=negative,platform_track_space_hits=track_hits,
            whole_station_accepted=False,world_opened=False,world_written=False)
        rows.append(row);print(name,len(paths),'paths,',row['passed'],'passed',flush=True)
        print('Conditional measured paths',row['conditional_static_passed'],'/',len(paths),'transfers',row['transfer_passed'],'/',len(transfers),flush=True)
        for path in paths:
            if not path['conditional_static_pass']:print(str((path['id'],path['conditional_open_forward'],path['conditional_open_reverse']))[:500],flush=True)
        bad=[r for r in transfers if not r['passed']]
        for path in paths:
            if not path['conditional_static_pass']:errors.append(['conditional_existing_path',name,path['id']])
        for path in transfers+full_entries:
            if not path['passed']:errors.append(['full_path',name,path['id']])
        for path in bad[:3]:print(str((path['id'],path['forward'],path['reverse']))[:500],flush=True)
        for path in full_entries:
            if not path['passed']:print(str((path['id'],path['forward'],path['reverse']))[:500],flush=True)
    write(a.out/'review.json',dict(errors=errors,stations=rows,source=str(a.source),metadata=str(a.metadata),native=str(a.native),repairs=0,
        touched_path_chunks=[list(c)for c in sorted(chunks)],source_y_envelope=[78,104],
        source_is_offline_snapshot=True,public_gate_manifest=str(a.manifest),world_opened=False,world_written=False,remaining=['live native doors and boarding','current-runtime shape confirmation','snapshot identity against latest world remains main-agent check']))
    print('Final static errors',len(errors),'path chunks',len(chunks),flush=True)
    for e in errors[:5]:print(str(e)[:500],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','metadata','native','manifest','out'):p.add_argument('--'+n,type=Path,required=True)
    main(p.parse_args())
