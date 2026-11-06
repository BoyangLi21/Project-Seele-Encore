"""Current offline old-city platform/stair/concourse geometry triage.

Historical entrance and stair coordinates are probes, never excavation orders.
No static gate is opened. Train space includes all nearby native curves and the
measured mainline visible motion envelope, including long end caps.
"""
import argparse,json,math
from collections import Counter
from pathlib import Path
import numpy as np
import audit_mountain_station_access as mountain
from audit_mountain_station_access import Nav,shape_for,SupplementedSections
from build_gora_protected_transfer import TrainSweep,IndependentWalker
from review_underground_station_evidence import strict_walk
from audit_underground_station_access import parallel_track_inside

NAMES=['第三新东京中央','NERV 地面入口','NERV 港口','湾岸防卫区','南部住宅区',
       '西部城区','新箱根中央','新箱根市民广场','地区技术中心','雾里住宅区']
mountain.FLOORS|={'mtr:platform','mtr:escalator_step','minecraft:smooth_quartz'}
NATURAL_WALK={'minecraft:grass_block','minecraft:dirt','minecraft:gravel','minecraft:stone','minecraft:sand','minecraft:coarse_dirt'}
mountain.FLOORS|=NATURAL_WALK

class MainlineSweep(TrainSweep):
    def __init__(self,snapshot,model,box):
        self.half_width=max(max(abs(q)for q in(v['visible_motion_bounds'][0][0],v['visible_motion_bounds'][1][0]))for v in model['vehicles'])+.15
        self.half_length=max(max(abs(q)for q in(v['visible_motion_bounds'][0][2],v['visible_motion_bounds'][1][2]))for v in model['vehicles'])+.15
        self.bottom=-.25;self.top=4.;self.curve_ids=[];points=[];tangents=[]
        for row in snapshot['curves']:
            p=np.asarray(row['points'],float)
            if row['mode']!='TRAIN' or not np.any((p[:,0]>box[0]-24)&(p[:,0]<box[3]+24)&(p[:,2]>box[2]-24)&(p[:,2]<box[5]+24)):continue
            self.curve_ids.append(row['id'])
            for a,b in zip(p,p[1:]):
                d=b-a;length=np.linalg.norm(d[[0,2]])
                if length<1e-8:continue
                for t in np.linspace(0,1,math.ceil(length/.25)+1):points.append(a+t*d);tangents.append(d[[0,2]]/length)
        self.p=np.asarray(points);self.t=np.asarray(tangents);self.n=np.column_stack((-self.t[:,1],self.t[:,0]))
        self.ax=self.half_length*np.abs(self.t[:,0])+self.half_width*np.abs(self.n[:,0]);self.az=self.half_length*np.abs(self.t[:,1])+self.half_width*np.abs(self.n[:,1]);self.buckets={}
        for i,(p,ax,az)in enumerate(zip(self.p,self.ax,self.az)):
            for bx in range(math.floor((p[0]-ax-1)/8),math.floor((p[0]+ax+1)/8)+1):
                for bz in range(math.floor((p[2]-az-1)/8),math.floor((p[2]+az+1)/8)+1):self.buckets.setdefault((bx,bz),[]).append(i)
        self.buckets={k:np.asarray(v,np.int32)for k,v in self.buckets.items()}
    def info(self):
        return dict(curves=len(self.curve_ids),poses=len(self.p),curve_ids=self.curve_ids,
            half_width_with_margin=self.half_width,half_length_with_margin=self.half_length,
            mainline_math_model_motion_included=True,rendered_frame_verified=False,vertical_reserve=[self.bottom,self.top])

class StationNav(Nav):
    def __init__(self,reader,box,shapes,sweep):self.sweep=sweep;super().__init__(reader,box,shapes,True)
    def body(self,x,y,z):
        if self.sweep.intersects(x,z,.3,.3,y,y+1.8):return {'kind':'running-train-reservation'}
        return super().body(x,y,z)

def cell_goal(p):return [math.floor(p[0]),p[1],math.floor(p[2])]
def xyz(p):return [p[k]for k in('x','y','z')]
def inside(p,b):return b[0]<=p[0]<=b[3]+1 and b[2]<=p[2]<=b[5]+1

def run(a):
    a.out.mkdir(exist_ok=False)
    reader=SupplementedSections(a.source,a.supplement)
    report=json.loads((a.source/'capture.json').read_text('utf8'))
    snap=json.loads(a.native.read_text('utf8'));model=json.loads((a.models/'summary.json').read_text('utf8'))
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'));cases=json.loads((a.metadata/'quality_walk_cases.json').read_text('utf8'))
    summaries=[]
    for name in NAMES:
        site=next(q for q in report['sites']if q.get('name')==name and q['kind']=='existing');box=list(site['bounds'])
        if name=='南部住宅区'and a.supplement:box[4]=175
        ids={p['platform_id']for p in snap['resolved_platforms']if p.get('station_name')==name}
        platforms=[p for p in snap['platforms']if str(p['id'])in ids]
        sweep=MainlineSweep(snap,model,box);nav=StationNav(reader,box,shapes,sweep)
        goals={};probes=[];deck=[];historical=[]
        for case in cases:
            ident=case['id'];path=case.get('path')or[case.get('start'),case.get('end')]
            if any(p is None for p in path):continue
            matched=any('/'+pid+'/'in ident for pid in ids)
            if ident.startswith('r42/station_entrance/')and'/return'not in ident and all(inside(p,box)for p in path):
                key='entry_'+ident.split('/')[2];goals[key]=cell_goal(path[0]);probes.append(dict(key=key,old_id=ident,old_path=path,kind='historical-entry-anchor'))
            if matched and 'ordinary_stair'in ident and'/return'not in ident:
                for label,p in [('foot',path[0]),('landing',path[-1])]:
                    key='stair_'+str(len(probes))+'_'+label;goals[key]=cell_goal(p);probes.append(dict(key=key,old_id=ident,kind='historical-stair-'+label))
            if matched and'/return'not in ident:historical.append(case)
        for p in platforms:
            a0,b=xyz(p['position1']),xyz(p['position2']);dx,dz=b[0]-a0[0],b[2]-a0[2];length=math.hypot(dx,dz);nx,nz=-dz/length,dx/length
            for side in(-1,1):
                for fraction in(.1,.3,.5,.7,.9):
                    cx=a0[0]+fraction*dx+.5;cz=a0[2]+fraction*dz+.5;possible=[];edge_states=[]
                    for off in(2,3,4,5,6,7,8):
                        goal=[math.floor(cx+nx*side*off),a0[1]+1,math.floor(cz+nz*side*off)]
                        state=reader.state(goal[0],a0[1],goal[2]);edge_states.append(dict(pos=[goal[0],a0[1],goal[2]],state=state))
                        if off>=3 and nav.nearest_goal(goal) is not None:possible.append((off,goal))
                    key='deck_'+str(len(deck));row=dict(key=key,platform_id=str(p['id']),side=side,fraction=fraction,edge_states=edge_states)
                    if possible:
                        off,goal=possible[0];goals[key]=goal;row.update(offset=off,goal=goal,status='sampled')
                    else:
                        paired=parallel_track_inside(p,platforms,nx,nz,side)
                        has_edge=any((r['state']or'').startswith(('mtr:platform[','projectseele:station_tactile_warning'))for r in edge_states)
                        row.update(status='non_boarding_track_interior'if paired and not has_edge else'no_safe_deck_sample',adjacent_parallel_platform=paired)
                    deck.append(row)
        if name=='南部住宅区':
            goals['current_surface_entrance']=[151,161,777];goals['current_surface_street']=[151,160.5,786];goals['current_lower_concourse']=[164,81,761]
        # Start inside the retained station stair entrance, rather than an
        # arbitrary platform island whose only access might itself be missing.
        start=next((q['key']for q in probes if q['kind']=='historical-stair-foot'and nav.nearest_goal(goals[q['key']])is not None),None)
        if start is None:start=next((q['key']for q in deck if q['key']in goals),None)
        routes,count=nav.routes(goals,start)if start else([],0)
        by={r['name']:r for r in routes};walker=IndependentWalker(reader,shapes,sweep)
        measured=[]
        for row in routes:
            detail=dict(key=row['name'],goal=row['requested'],supported=row['measured_goal']is not None,reachable=row['reachable'])
            if not row['reachable']:
                x,y,z=row['requested'];detail['body_at_requested']=walker.body(x+.5,y,z+.5)
                detail['below']=reader.state(x,math.floor(y)-1,z)
            else:
                detail['forward']=strict_walk(walker,row['path']);detail['reverse']=strict_walk(walker,list(reversed(row['path'])))
                detail['path']=row['path']
                surface=Counter()
                for x,y,z in row['path']:
                    state=reader.state(math.floor(x),math.ceil(y)-1,math.floor(z))
                    if state is not None:surface[state.split('[')[0]]+=1
                detail['natural_ground_samples']=sum(v for k,v in surface.items()if k in NATURAL_WALK)
                detail['floor_material_samples']=dict(surface)
            measured.append(detail)
        for row in deck:
            if row['key']in by:row['status']='reached'if by[row['key']]['reachable']else'separate_component'
        arr,palette=reader.box(box);gates=[]
        for i,state in enumerate(palette):
            if 'ticket_barrier'in state:
                for y,z,x in np.argwhere(arr==i):gates.append(dict(pos=[int(x)+box[0],int(y)+box[1],int(z)+box[2]],state=state))
        row=dict(name=name,site_id=site['id'],bounds=box,native_station_id=site['native_id'],native_platforms=platforms,
            selected_graph_root=start,available_nodes=len(nav.nodes),reachable_nodes=count,deck_counts=dict(Counter(r['status']for r in deck)),
            platform_deck_samples=deck,anchors=probes,measurements=measured,historical_cases=historical,
            dynamic_gates=gates,native_track_reservation=sweep.info(),world_written=False,repair_authorized=False,
            natural_walkable_ground_included_and_separately_reported=True,
            all_station_street_connections_proven=False,ordinary_doors_conditionally_open=True,native_gates_bypassed=False,
            current_model_rendering_and_runtime_collision_pending=True)
        (a.out/(site['id']+'.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8')
        summary={k:row[k]for k in('name','site_id','available_nodes','reachable_nodes','deck_counts')}
        summary.update(anchor_count=len(probes),reachable_anchor_count=sum(by[p['key']]['reachable']for p in probes),dynamic_gate_count=len(gates))
        summaries.append(summary)
        (a.out/'summary.json').write_text(json.dumps(dict(stations=summaries,complete=len(summaries)==len(NAMES),world_written=False),ensure_ascii=False,indent=2),'utf8')
        print(name,'deck',row['deck_counts'],'anchors',summary['reachable_anchor_count'],'/',len(probes),'gates',len(gates),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('source','native','models','metadata','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--supplement',type=Path);run(p.parse_args())
