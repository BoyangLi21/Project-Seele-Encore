"""Independent exact proposals for nine remaining narrow island stair accesses.

Uses captured station sections only; no installation, native change or live
world access. Each station is checked with all proposed islands together.
"""
import argparse,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np
import nbtlib
from audit_oldcity_surface_station_access import MainlineSweep,StationNav,SupplementedSections
from build_gora_protected_transfer import IndependentWalker
from audit_mountain_station_access import shape_for
from propose_mountain_station_steps import Overlay
from review_underground_station_evidence import strict_walk
from render_hakone_voxel_3d import render

AIR='minecraft:air';STONE='minecraft:stone_bricks';SLAB='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
FULL=[[0.,0.,0.,1.,1.,1.]]
ALLOWED={'minecraft:light_gray_concrete','projectseele:period_station_floor','projectseele:station_tactile_warning'}
SPECS=[
    dict(id='nerv-surface',site='native-07',axis='x',cross=684,start=-390,base=80,upper=94),
    dict(id='bay-r1',site='native-08',axis='z',cross=360,start=270,base=80,upper=94),
    dict(id='bay-s1',site='native-08',axis='z',cross=316,start=246,base=80,upper=106),
    dict(id='south',site='native-21',axis='z',cross=180,start=730,base=80,upper=94),
    dict(id='west',site='native-23',axis='z',cross=-680,start=210,base=96,upper=110),
    dict(id='shinhakone-r1',site='native-09',axis='x',cross=636,start=-1534,base=104,upper=130),
    dict(id='shinhakone-s1',site='native-09',axis='x',cross=676,start=-1510,base=104,upper=118),
    dict(id='civic',site='native-06',axis='z',cross=-1720,start=330,base=104,upper=118),
    dict(id='technology',site='native-27',axis='x',cross=560,start=-1110,base=104,upper=118),
]

def point(s,u,y,w=0):
    return (u,y,s['cross']+w)if s['axis']=='x'else(s['cross']-w,y,u)

def design(reader,shapes,s):
    start=s['start'];end=start+2*(s['upper']-s['base']);s=dict(s,end=end)
    proposed={};why={};supports=[]
    def get(u,y,w=0):
        p=point(s,u,y,w);return proposed.get(p,reader.state(*p))
    def put(u,y,w,state,label):
        p=point(s,u,y,w);before=reader.state(*p)
        if before is None:raise ValueError(s['id']+' uncaptured '+str(p))
        if before==state:proposed.pop(p,None);why.pop(p,None)
        else:proposed[p]=state;why[p]=label
    def trap(w):
        facing=('north'if w<0 else'south')if s['axis']=='x'else('east'if w<0 else'west')
        return f'minecraft:iron_trapdoor[facing={facing},half=bottom,open=true,powered=false,waterlogged=false]'
    for u in range(start,end+1):
        feet=s['base']+1+(u-start)/2
        for w in(-1,0,1):
            p=point(s,u,s['base'],w);bearing=reader.state(*p);boxes,_=shape_for(bearing,shapes,True)
            if boxes!=FULL:raise ValueError(s['id']+' foundation '+str((p,bearing)))
            top=math.floor(feet)-1 if w==0 else math.ceil(feet)-1
            supports.append(dict(pos=list(p),top=top))
            for y in range(s['base']+1,top+1):
                old=get(u,y,w)
                if old==AIR:put(u,y,w,STONE,'continuous-stair-foundation')
                elif old not in ALLOWED:raise ValueError(s['id']+' structural component '+str((point(s,u,y,w),old)))
        if feet%1:
            y=math.floor(feet);old=get(u,y)
            if old!=AIR and old not in ALLOWED:raise ValueError(s['id']+' tread collision')
            put(u,y,0,SLAB,'half-step')
        for y in range(math.ceil(feet),math.ceil(feet+2.3)):
            old=get(u,y)
            if old in ALLOWED:put(u,y,0,AIR,'centre-stair-headroom')
            elif old!=AIR:raise ValueError(s['id']+' headroom component '+str((point(s,u,y),old)))
        if start<u<end:
            for w in(-1,1):
                y=math.ceil(feet);old=get(u,y,w)
                if old==AIR:put(u,y,w,trap(w),'stair-side-guard')
                elif old not in ALLOWED:raise ValueError(s['id']+' side guard obstruction')
    openings=[]
    for u in range(start,end+1):
        boxes,_=shape_for(get(u,s['upper']),shapes,True)
        if boxes==FULL:continue
        openings.append(u)
        for w in(-1,1):
            if get(u,s['upper']+1,w)not in(AIR,trap(w)):raise ValueError(s['id']+' upper guard obstruction')
            put(u,s['upper']+1,w,trap(w),'upper-apron-guard')
    axis='z'if s['axis']=='x'else'x'
    bars='minecraft:iron_bars[east='+str(axis=='x').lower()+',north='+str(axis=='z').lower()+',south='+str(axis=='z').lower()+',waterlogged=false,west='+str(axis=='x').lower()+']'
    put(min(openings),s['upper']+1,0,bars,'upper-hole-end-guard')
    changes=[dict(pos=list(p),before=reader.state(*p),after=state,purpose=why[p],island=s['id'])for p,state in sorted(proposed.items())]
    return dict(spec=s,changes=changes,supports=supports,lower_goal=list(point(s,start,s['base']+1)),upper_goal=list(point(s,end,s['upper']+1)))

def run(a):
    a.out.mkdir(exist_ok=False);reader=SupplementedSections(a.source,a.supplement)
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'));aliases=[]
    for facing in('east','west'):
        target=f'minecraft:iron_trapdoor[facing={facing},half=bottom,open=true,powered=false,waterlogged=false]'
        same=target.replace('iron_trapdoor','oak_trapdoor')
        if target not in shapes:
            if same not in shapes:raise ValueError('No equivalent vanilla trapdoor collision')
            shapes[target]=shapes[same];aliases.append(dict(state=target,same_collision_class_and_properties_as=same))
    snap=json.loads(a.native.read_text('utf8'));model=json.loads((a.models/'summary.json').read_text('utf8'))
    devices={tuple(int(t[k])for k in('x','y','z'))for t in nbtlib.load(a.source/'devices.dat')['Devices']}
    grouped=defaultdict(list);designs=[];failures=[]
    for s in SPECS:
        try:
            q=design(reader,shapes,s)
            if any(tuple(c['pos'])in devices for c in q['changes']):raise ValueError('Protected device intersects '+s['id'])
            grouped[s['site']].append(q);designs.append(q)
            print('Designed',s['id'],len(q['changes']),'cells',flush=True)
        except ValueError as e:
            failures.append(dict(spec=s,error=str(e)));print('Revise',str(e)[:450],flush=True)
    summaries=[]
    for site,items in grouped.items():
        baseline=json.loads((a.review/(site+'.json')).read_text('utf8'));changes=[c for q in items for c in q['changes']]
        if len({tuple(c['pos'])for c in changes})!=len(changes):raise ValueError('Overlapping island proposals')
        after=Overlay(reader,changes);sweep=MainlineSweep(snap,model,baseline['bounds']);nav=StationNav(after,baseline['bounds'],shapes,sweep)
        goals={q['key']:q['goal']for q in baseline['measurements']if q['supported']}
        for q in items:
            goals[q['spec']['id']+'_lower']=q['lower_goal'];goals[q['spec']['id']+'_upper']=q['upper_goal']
        routes,count=nav.routes(goals,baseline['selected_graph_root']);w=IndependentWalker(after,shapes,sweep);proofs=[];errors=[]
        for r in routes:
            if not r['reachable']:errors.append('Unreachable '+r['name']);continue
            proof=dict(goal=r['name'],path=r['path'],forward=strict_walk(w,r['path']),reverse=strict_walk(w,list(reversed(r['path']))))
            if any(proof[d]['kind']!='strict_static_clear'for d in('forward','reverse')):errors.append('Independent path failed '+r['name'])
            proofs.append(proof)
        intrusions=[];support_issues=[];aprons=[]
        for c in changes:
            x,y,z=c['pos'];boxes,_=shape_for(c['after'],shapes,True)
            if boxes is None:errors.append('Unknown added collision');continue
            for b in boxes:
                if sweep.intersects(x+(b[0]+b[3])/2,z+(b[2]+b[5])/2,(b[3]-b[0])/2,(b[5]-b[2])/2,y+b[1],y+b[4]):intrusions.append(c);break
        for q in items:
            s=q['spec']
            for column in q['supports']:
                x,y,z=column['pos']
                for yy in range(y,column['top']+1):
                    bs,_=shape_for(after.state(x,yy,z),shapes,True)
                    if bs!=FULL:support_issues.append([x,yy,z])
            for side in(-1,1):
                path=[[p[0]+.5,p[1],p[2]+.5]for p in[point(s,u,s['upper']+1,side)for u in range(s['start']-3,s['end']+4)]]
                apron=dict(island=s['id'],side=side,forward=strict_walk(w,path),reverse=strict_walk(w,list(reversed(path))))
                aprons.append(apron)
                if any(apron[d]['kind']!='strict_static_clear'for d in('forward','reverse')):errors.append('Boarding apron interrupted '+s['id'])
        if intrusions:errors.append('Visible vehicle envelope intrusion')
        if support_issues:errors.append('Foundation discontinuity')
        chunks=sorted({(c['pos'][0]//16,c['pos'][2]//16)for c in changes})
        bounds=[min(c['pos'][k]for c in changes)for k in range(3)]+[max(c['pos'][k]for c in changes)for k in range(3)]
        row=dict(station=baseline['name'],site=site,islands=items,changes=changes,changed_cells=len(changes),bounds=bounds,
            errors=errors,goals=proofs,reachable_nodes=count,vehicle_intrusions=intrusions,support_issues=support_issues,
            boarding_apron_proofs=aprons,shape_aliases=aliases,full_chunks_needed=chunks,full_y_needed=[-128,319],
            device_changes=0,native_changes=0,world_written=False,installed=False,full_source_export_pending=True,
            current_runtime_collision_and_model_render_validation_pending=True)
        (a.out/(site+'.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8')
        summaries.append({k:row[k]for k in('station','site','changed_cells','bounds','errors','full_chunks_needed')})
        print('Verified',baseline['name'],len(proofs),'goals; errors',str(errors)[:350],flush=True)
    (a.out/'summary.json').write_text(json.dumps(dict(stations=summaries,design_failures=failures,shape_aliases=aliases,world_written=False),ensure_ascii=False,indent=2),'utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('source','supplement','metadata','review','native','models','out'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
