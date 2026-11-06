"""Offline overhead island access, avoiding retained lower-hall lamps and rooms."""
import argparse,json,math
from collections import defaultdict
from pathlib import Path
import nbtlib
from audit_oldcity_surface_station_access import MainlineSweep,StationNav,SupplementedSections
from build_gora_protected_transfer import IndependentWalker
from audit_mountain_station_access import shape_for
from propose_mountain_station_steps import Overlay
from review_underground_station_evidence import strict_walk
from propose_remaining_surface_island_access import point,SPECS,FULL

AIR='minecraft:air';STONE='minecraft:stone_bricks';SLAB='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
LIMITS={'bay-r1':(235,365),'bay-s1':(250,350),'south':(695,825),'west':(175,305),
        'shinhakone-r1':(-1545,-1415),'shinhakone-s1':(-1530,-1430),'civic':(310,410),'technology':(-1145,-1015)}

def make(reader,shapes,s,start,side):
    s=dict(s,start=start,end=start+12,side=side);P=s['upper'];end=s['end'];out={};why={};bearings=[]
    def pos(u,y,w=0):return point(s,u,y,side*w)
    def get(u,y,w=0):
        p=pos(u,y,w);return out.get(p,reader.state(*p))
    def put(u,y,w,state,label):
        p=pos(u,y,w);old=reader.state(*p)
        if old is None:raise ValueError('uncaptured '+str(p))
        if old!=AIR and old!=state:raise ValueError('preserved component '+str((p,old)))
        if old!=state:out[p]=state;why[p]=label
    def fill(u,w,top):
        p=pos(u,P,w);b,_=shape_for(reader.state(*p)or'__unavailable__',shapes,True)
        if b!=FULL:raise ValueError('unsupported base '+str(p))
        bearings.append(dict(pos=list(p),top=top))
        for y in range(P+1,top+1):put(u,y,w,STONE,'supported-stair-or-abutment')
    def trap(w):
        # The guard cell lies just outside the supporting tread. Its collision
        # plate touches the inner boundary, leaving the old boarding lane open.
        negative=w<0
        if s['axis']=='x':facing='north'if negative else'south'
        else:facing='east'if negative else'west'
        if side<0:facing={'north':'south','south':'north','east':'west','west':'east'}[facing]
        return f'minecraft:iron_trapdoor[facing={facing},half=bottom,open=true,powered=false,waterlogged=false]'
    def bars(axis):
        return 'minecraft:iron_bars[east='+str(axis=='x').lower()+',north='+str(axis=='z').lower()+',south='+str(axis=='z').lower()+',waterlogged=false,west='+str(axis=='x').lower()+']'
    for u in range(start,end+1):
        feet=P+1+(u-start)/2
        for w in(0,10,11,12):
            fill(u,w,math.floor(feet)-1)
            if feet%1:put(u,math.floor(feet),w,SLAB,'half-step')
            for yy in range(math.ceil(feet),math.ceil(feet+2.3)):
                if get(u,yy,w)!=AIR:raise ValueError('stair headroom '+str((pos(u,yy,w),get(u,yy,w))))
        if start<u<end:
            for w in(-1,1,9,13):
                # First guard is attached to the side of the solid stringer;
                # its upper panel provides a complete handrail height.
                facing_w=-1 if w in(-1,9)else 1
                state=trap(facing_w)
                for y in(math.ceil(feet)-1,math.ceil(feet)):put(u,y,w,state,'attached-thin-stair-guard')
    for u in range(end,end+3):
        fill(u,0,P+6)
        for w in(10,11,12):fill(u,w,P+6)
        for w in range(1,10):
            put(u,P+5,w,'minecraft:iron_block','over-track-girder')
            put(u,P+6,w,'minecraft:smooth_stone','bridge-deck')
    along_guard='z'if s['axis']=='x'else'x'
    for w in range(0,13):
        put(end+2,P+7,w,bars(along_guard),'bridge-rear-guard')
        if 1<=w<=9:put(end,P+7,w,bars(along_guard),'bridge-front-guard')
    for u in range(end,end+3):
        for y in(P+6,P+7):put(u,y,-1,trap(-1),'island-landing-edge-guard')
    put(end+1,P+7,12,bars('x'if s['axis']=='x'else'z'),'outer-landing-edge-guard')
    changes=[dict(pos=list(p),before=reader.state(*p),after=state,purpose=why[p],island=s['id'])for p,state in sorted(out.items())]
    return dict(spec=s,changes=changes,supports=bearings,
        lower_goal=list(pos(start,P+1,0)),upper_goal=list(pos(end+1,P+7,0)),outer_goal=list(pos(start,P+1,11)),
        girder_soffit=P+5,visible_train_top=P+3.787589718748511,visible_vertical_gap=1.212410281251489)

def run(a):
    a.out.mkdir(exist_ok=False);reader=SupplementedSections(a.source,a.supplement)
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'));aliases=[]
    for facing in('east','west'):
        state=f'minecraft:iron_trapdoor[facing={facing},half=bottom,open=true,powered=false,waterlogged=false]';equiv=state.replace('iron_trapdoor','oak_trapdoor')
        if state not in shapes:shapes[state]=shapes[equiv];aliases.append(dict(state=state,same_collision_class_and_properties_as=equiv))
    devices={tuple(int(t[k])for k in('x','y','z'))for t in nbtlib.load(a.source/'devices.dat')['Devices']}
    grouped=defaultdict(list);failures=[]
    for s in SPECS:
        if s['id']=='nerv-surface':continue
        low,high=LIMITS[s['id']];preferred=(low+high)//2-24
        starts=sorted(range(low+8,high-18),key=lambda u:abs(u-preferred));tried=[];found=None
        for side in(1,-1):
            for start in starts:
                try:
                    q=make(reader,shapes,s,start,side)
                    if any(tuple(c['pos'])in devices for c in q['changes']):raise ValueError('protected device')
                    found=q;break
                except ValueError as e:tried.append(dict(start=start,side=side,error=str(e)))
            if found:break
        if found:
            grouped[s['site']].append(found);print('Designed overpass',s['id'],found['spec']['start'],found['spec']['side'],len(found['changes']),'cells',flush=True)
        else:
            failures.append(dict(spec=s,attempts=tried));print('No preserved-component placement',s['id'],len(tried),'attempts',flush=True)
    snap=json.loads(a.native.read_text('utf8'));model=json.loads((a.models/'summary.json').read_text('utf8'));summary=[]
    for site,items in grouped.items():
        baseline=json.loads((a.review/(site+'.json')).read_text('utf8'));changes=[c for q in items for c in q['changes']]
        after=Overlay(reader,changes);sweep=MainlineSweep(snap,model,baseline['bounds']);nav=StationNav(after,baseline['bounds'],shapes,sweep)
        goals={q['key']:q['goal']for q in baseline['measurements']if q['supported']}
        for q in items:
            for suffix in('lower','upper','outer'):goals[q['spec']['id']+'_'+suffix]=q[suffix+'_goal']
        rows,count=nav.routes(goals,baseline['selected_graph_root']);walker=IndependentWalker(after,shapes,sweep);proofs=[];errors=[]
        for r in rows:
            if not r['reachable']:errors.append('Unreachable '+r['name']);continue
            proof=dict(goal=r['name'],path=r['path'],forward=strict_walk(walker,r['path']),reverse=strict_walk(walker,list(reversed(r['path']))))
            if any(proof[d]['kind']!='strict_static_clear'for d in('forward','reverse')):errors.append('Independent walk failed '+r['name'])
            proofs.append(proof)
        intrusion=[];support_issues=[];aprons=[]
        for c in changes:
            x,y,z=c['pos'];boxes,_=shape_for(c['after'],shapes,True)
            if boxes is None:errors.append('Unknown new shape');continue
            for b in boxes:
                if sweep.intersects(x+(b[0]+b[3])/2,z+(b[2]+b[5])/2,(b[3]-b[0])/2,(b[5]-b[2])/2,y+b[1],y+b[4]):intrusion.append(c);break
        for q in items:
            s=q['spec'];P=s['upper']
            for col in q['supports']:
                x,y,z=col['pos']
                for yy in range(y,col['top']+1):
                    b,_=shape_for(after.state(x,yy,z),shapes,True)
                    if b!=FULL:support_issues.append([x,yy,z])
            for sign in(-1,1):
                path=[[p[0]+.5,p[1],p[2]+.5]for p in[point(s,u,P+1,sign)for u in range(s['start']-3,s['end']+6)]]
                proof=dict(island=s['id'],side=sign,forward=strict_walk(walker,path),reverse=strict_walk(walker,list(reversed(path))))
                if any(proof[d]['kind']!='strict_static_clear'for d in('forward','reverse')):errors.append('Island apron blocked '+s['id'])
                aprons.append(proof)
        if intrusion:errors.append('Vehicle intrusion')
        if support_issues:errors.append('Broken structural support')
        chunks=sorted({(c['pos'][0]//16,c['pos'][2]//16)for c in changes});bounds=[min(c['pos'][k]for c in changes)for k in range(3)]+[max(c['pos'][k]for c in changes)for k in range(3)]
        report=dict(station=baseline['name'],site=site,islands=items,changes=changes,changed_cells=len(changes),bounds=bounds,
            errors=errors,goals=proofs,reachable_nodes=count,vehicle_intrusions=intrusion,support_issues=support_issues,
            boarding_apron_proofs=aprons,shape_aliases=aliases,full_chunks_needed=chunks,full_y_needed=[-128,319],
            device_changes=0,native_changes=0,original_blocks_modified=0,world_written=False,installed=False,full_source_export_pending=True)
        (a.out/(site+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
        summary.append({k:report[k]for k in('station','site','changed_cells','bounds','errors','full_chunks_needed')})
        print('Verified overpass',baseline['name'],len(proofs),'goals; errors',str(errors)[:350],flush=True)
    (a.out/'summary.json').write_text(json.dumps(dict(stations=summary,design_failures=failures,shape_aliases=aliases,world_written=False),ensure_ascii=False,indent=2),'utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('source','supplement','metadata','review','native','models','out'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
