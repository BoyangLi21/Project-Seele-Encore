"""Read-only current mountain station access review from captured sections.

This is conservative static geometry evidence, not live passenger or signal
validation. Unknown cells and unknown collision states are never assumed air.
Closed ordinary Minecraft wooden doors have a separate conditional-open pass;
native ticket barriers and other mod doors are never opened by this audit.
"""
import argparse,json,math,re
from collections import Counter,deque
from pathlib import Path
import numpy as np
from map_pipeline.station_sections import StationSections
from verify_hakone_network_candidate import PAVEMENT
from query_blocks import AIR

FULL=[0.,0.,0.,1.,1.,1.]
FLOORS=PAVEMENT|{'minecraft:yellow_concrete','minecraft:light_gray_concrete',
    'minecraft:smooth_stone','minecraft:stone_bricks','minecraft:polished_andesite',
    'projectseele:period_station_floor','projectseele:station_tactile_path',
    'projectseele:station_tactile_warning'}

def wooden_door(state):
    return state.startswith('minecraft:') and '_door[' in state and not state.startswith('minecraft:iron_door[')

def shape_for(state,shapes,opened=False):
    if state=='__unavailable__':return None,'uncaptured'
    base=state.split('[')[0]
    if base in AIR|{'minecraft:light'}:return [],'empty'
    if wooden_door(state):
        props=dict(q.split('=') for q in state.split('[',1)[1][:-1].split(','))
        facing=props['facing'];is_open=opened or props['open']=='true'
        # Vanilla DoorBlock's 3/16-thick cardinal planes. This conditional
        # calculation never changes the saved door or bypasses a native gate.
        side={'east':'west','west':'east','north':'south','south':'north'}[facing]
        if is_open:
            left=props['hinge']=='left'
            side=({'east':'north','west':'south','north':'west','south':'east'} if left
                  else {'east':'south','west':'north','north':'east','south':'west'})[facing]
        return [{'west':[0,0,0,.1875,1,1],'east':[.8125,0,0,1,1,1],
                 'north':[0,0,0,1,1,.1875],'south':[0,0,.8125,1,1,1]}[side]],'vanilla-door'
    if state in shapes:return shapes[state],'recorded-native-shape'
    if base.startswith('minecraft:') and (base.endswith('_planks') or base.endswith('_log')):
        return [FULL],'vanilla-full-cube'
    if base.startswith('minecraft:') and base.endswith('_stairs'):
        equivalent='minecraft:dark_oak_stairs'+state[len(base):]
        if equivalent in shapes:return shapes[equivalent],'same-vanilla-stair-properties'
    return None,'unclassified'

class Nav:
    def __init__(self,reader,box,shapes,opened=False):
        self.box=box;self.arr,self.palette=reader.box(box);self.opened=opened
        self.shapes=[];self.origins=[];self.unknown=Counter();self.edge_cache={}
        self.states=Counter({s:int((self.arr==i).sum()) for i,s in enumerate(self.palette) if (self.arr==i).any()})
        for s in self.palette:
            b,origin=shape_for(s,shapes,opened);self.shapes.append(b);self.origins.append(origin)
        self.nodes={};self.column={}
        x,y,z,X,Y,Z=box
        for iz in range(self.arr.shape[1]):
            for ix in range(self.arr.shape[2]):
                for iy in range(self.arr.shape[0]-2):
                    k=int(self.arr[iy,iz,ix]);state=self.palette[k];base=state.split('[')[0]
                    if base not in FLOORS and not (base.startswith('minecraft:') and (base.endswith('_planks') or base.endswith('_stairs'))):continue
                    shapes_here=self.shapes[k]
                    if shapes_here is None:continue
                    tops=sorted({iy+y+b[4] for b in shapes_here if b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2},reverse=True)
                    for top in tops:
                        if top*2!=round(top*2):continue
                        q=(ix+x,round(top*2),iz+z)
                        if self.body(q[0]+.5,top,q[2]+.5) is None:
                            self.nodes[q]=state;self.column.setdefault((q[0],q[2]),[]).append(q)
                            break

    def get(self,x,y,z):
        a,b,c,A,B,C=self.box
        if not(a<=x<=A and b<=y<=B and c<=z<=C):return '__unavailable__',None
        k=int(self.arr[y-b,z-c,x-a]);return self.palette[k],self.shapes[k]

    def body(self,x,y,z):
        lo=x-.3,y+.00001,z-.3;hi=x+.3,y+1.79999,z+.3
        for X in range(math.floor(lo[0]),math.floor(hi[0]-.00001)+1):
            for Y in range(math.floor(lo[1])-1,math.floor(hi[1])+1):
                for Z in range(math.floor(lo[2]),math.floor(hi[2]-.00001)+1):
                    state,bs=self.get(X,Y,Z)
                    if bs is None:
                        self.unknown[state]+=1
                        return {'kind':'unknown','pos':[X,Y,Z],'state':state}
                    for b in bs:
                        if all(lo[i]<(X,Y,Z)[i]+b[i+3] and hi[i]>(X,Y,Z)[i]+b[i] for i in range(3)):
                            return {'kind':'solid','pos':[X,Y,Z],'state':state}
        return None

    def edge(self,a,b):
        key=tuple(sorted((a,b)))
        if key in self.edge_cache:return self.edge_cache[key]
        if abs(a[1]-b[1])>2:return False
        if abs(a[1]-b[1])==2:
            # A real stair can rise one block over a whole block of travel,
            # but every local collision step must still be <= 0.5. Full-cube
            # one-block risers cannot use this exception.
            result=self.stair_edge(a,b) and self.stair_edge(b,a)
            self.edge_cache[key]=result;return result
        # Lift by at most half a block before horizontal advance, then descend;
        # every swept 0.6 x 1.8 player box is measured at 1/8-block intervals.
        top=max(a[1],b[1])/2
        result=all(self.body(a[0]+.5+(b[0]-a[0])*i/8,top,a[2]+.5+(b[2]-a[2])*i/8) is None for i in range(9))
        self.edge_cache[key]=result;return result

    def stair_edge(self,a,b):
        top=a[1]/2
        touched_stair=False
        for i in range(1,9):
            x=a[0]+.5+(b[0]-a[0])*i/8;z=a[2]+.5+(b[2]-a[2])*i/8
            options=[]
            for X in range(math.floor(x-.29999),math.floor(x+.29999)+1):
                for Z in range(math.floor(z-.29999),math.floor(z+.29999)+1):
                    for Y in range(math.floor(top)-2,math.floor(top)+1):
                        state,boxes=self.get(X,Y,Z)
                        if boxes is None:continue
                        if '_stairs[' in state:touched_stair=True
                        for box in boxes:
                            height=Y+box[4]
                            if x-.29999<X+box[3] and x+.29999>X+box[0] and z-.29999<Z+box[5] and z+.29999>Z+box[2] and abs(height-top)<=.50001:
                                options.append(height)
            supported=[height for height in sorted(set(options),reverse=True) if self.body(x,height,z) is None]
            if not supported:return False
            top=supported[0]
        return touched_stair and abs(top-b[1]/2)<.0001

    def nearest_goal(self,p):
        x,y,z=p;options=self.column.get((int(x),int(z)),[])
        options=[q for q in options if abs(q[1]/2-y)<=1.01]
        return min(options,key=lambda q:abs(q[1]/2-y)) if options else None

    def routes(self,goals,start_name):
        selected={name:self.nearest_goal(p) for name,p in goals.items()};start=selected[start_name]
        parents={start:None} if start else {};queue=deque(parents)
        while queue:
            a=queue.popleft()
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                for b in self.column.get((a[0]+dx,a[2]+dz),[]):
                    if b not in parents and self.edge(a,b):parents[b]=a;queue.append(b)
        rows=[]
        for name,p in goals.items():
            q=selected[name];path=[]
            if q in parents:
                while q is not None:path.append([q[0]+.5,q[1]/2,q[2]+.5]);q=parents[q]
                path.reverse()
            rows.append(dict(name=name,requested=p,measured_goal=selected[name],reachable=bool(path),path=path))
        return rows,len(parents)

class SupplementedSections:
    def __init__(self,source,supplement=None):
        self.base=StationSections(source);self.extra=StationSections(supplement) if supplement else None
    def state(self,x,y,z):
        state=self.extra.state(x,y,z)if self.extra else None
        return self.base.state(x,y,z)if state is None else state
    def box(self,bounds):
        blocks,palette=self.base.box(bounds)
        if self.extra is None:return blocks,palette
        fresh,names=self.extra.box(bounds);ids={s:i for i,s in enumerate(palette)};remap=[]
        for state in names:
            if state not in ids:ids[state]=len(palette);palette.append(state)
            remap.append(ids[state])
        mask=fresh!=0;blocks[mask]=np.asarray(remap,np.uint16)[fresh[mask]]
        return blocks,palette

def run(a):
    a.out.mkdir(parents=True,exist_ok=True)
    reader=SupplementedSections(a.source,a.supplement);shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    catalog=json.loads((a.authority/'catalog.json').read_text('utf8'))
    with np.load(a.authority/'network.npz') as f:
        ax,az,aX,aZ=map(int,f['bounds']);walk=f['walk'];grade=f['grade2']
    metadata_candidates=[]
    specs=[dict(id='gora',name='強羅駅',bounds=[888,45,608,1018,71,688],
        goals={'rail_platform':[934,56,650],'funicular_waiting':[918,56,650],
               'hall':[950,56,643],'entrance':[959,56,643],'street':[971,54,649],'bus_forecourt':[989,52,658]},
        superseded_goals={'street':[971,52,649]},
        street_height_evidence={'network_grade2':int(grade[649-az,971-ax]),'standing_height':54})]
    for row in catalog:
        if row.get('kind')!='station' or row.get('station_id') not in ('yumoto','tonosawa','ohiradai','miyanoshita','kowakudani','chokoku'):continue
        points=[row[k] for k in ('entrance','approach','road','platform')]
        if row.get('upper'):points.append(row['upper'])
        if row.get('occupied_bounds'):points.extend((row['occupied_bounds'][:3],row['occupied_bounds'][3:]))
        points+=row.get('footway',[]);bounds=[math.floor(min(p[k] for p in points)-12)for k in range(3)]+[math.ceil(max(p[k] for p in points)+12)for k in range(3)]
        goals={key:list(row[key]) for key in ('entrance','approach','road','platform')}
        goals['platform'][1]+=1
        if row.get('footway'):
            current=list(row['footway'][-1]);x,y,z=current
            if not walk[z-az,x-ax] or abs(grade[z-az,x-ax]/2+1-y)>.01:
                raise ValueError('Retained footway does not end on declared current street: '+row['id'])
            goals['road']=current
            if row['road']!=current:
                metadata_candidates.append(dict(catalog_id=row['id'],station_id=row['station_id'],field='road',
                    before=row['road'],after=current,source='retained catalog footway last point',
                    current_authority_walk=True,current_authority_grade2=int(grade[z-az,x-ax]),
                    feet_height_semantics=True,world_block_changes=0))
        if row.get('upper'):goals['upper_room']=row['upper']
        specs.append(dict(id=row['station_id'],name=row['label'],bounds=bounds,goals=goals,catalog_id=row['id'],
            superseded_goals={'road':row['road']} if row['road']!=goals['road'] else {}))
    specs.extend([
        dict(id='ubako',name='姥子',bounds=[-42,133,807,5,157,852],start='entrance',
             goals={'entrance':[-21,140,829],'ticket_hall':[-21,140,823],
                    'ropeway_boarding':[-21,146,823],'street':[-5,139,842]}),
        dict(id='owakudani',name='大涌谷',bounds=[250,173,811,304,204,863],start='entrance',
             goals={'entrance':[272,180,842],'concourse':[272,180,830],
                    'ropeway_west':[272,186,827],'terrace':[272,180,848],'street':[280,179,853]}),
        dict(id='sounzan',name='早雲山',bounds=[625,92,740,708,130,805],start='funicular_platform',
             goals={'entrance':[669,111,777],'funicular_platform':[667,105,765],
                    'ropeway_boarding':[640,117,762],'viewing_terrace':[652,117,791],
                    'street':[704,97,789]}),
        dict(id='togendai',name='桃源台 / 桃源台港',bounds=[-332,95,977,-244,125,1085],start='entrance',
             goals={'entrance':[-287,110,1000],'ticket_hall':[-286,110,1013],
                    'restaurant':[-286,105,1014],'boat_hall':[-286,101,1025],
                    'pontoon':[-286,101,1078],'ropeway_boarding':[-264,115,1004],
                    'bus_west':[-313,110,992],'bus_east':[-272,110,992]})
    ])
    result=[]
    for spec in specs:
        passes=[]
        for opened in (False,True):
            nav=Nav(reader,spec['bounds'],shapes,opened);routes,seen=nav.routes(spec['goals'],spec.get('start','rail_platform' if spec['id']=='gora' else 'platform'))
            passes.append(dict(ordinary_wooden_doors_assumed_open=opened,reachable_nodes=seen,
                goals=routes,known_paved_nodes=len(nav.nodes),unknown_cells=int((nav.arr==0).sum()),
                unknown_shape_or_capture_queries=dict(nav.unknown),dynamic_doors=[s for s in nav.states if wooden_door(s)],
                native_gate_states=[s for s in nav.states if s.startswith('mtr:') and any(v in s for v in ('ticket','gate','barrier','door'))],
                shape_sources=dict(Counter(origin for origin,s in zip(nav.origins,nav.palette) if s in nav.states))))
            print(spec['id'],'open' if opened else 'saved',seen,'nodes',[(r['name'],r['reachable']) for r in routes],flush=True)
        result.append(dict(**spec,passes=passes,complete_station_acceptance=False,rail_crossing_and_live_boarding_pending=True))
    report=dict(stations=result,measured_station_count=len(result),source=str(a.source),authority=str(a.authority),
        player_width=.6,player_height=1.8,maximum_step=.5,sweep_spacing=.125,
        current_native_collision_export_required=True,recorded_shape_metadata=str(a.metadata),
        supplementary_source=str(a.supplement)if a.supplement else None,
        historical_station_walks_cover_these_stations=False,world_written=False,repairs_authorized_by_failures=False,
        limitation='Unknown shape/capture and conservative centre-node stair representation can reject a real route. Static success requires native door, boarding and crossing review before final acceptance.')
    (a.out/'access-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    for patch in metadata_candidates:
        st=next(s for s in result if s.get('catalog_id')==patch['catalog_id'])
        goal=next(g for g in st['passes'][-1]['goals'] if g['name']=='road')
        patch['current_measured_route_reachable']=goal['reachable']
        patch['path_from_platform']=goal['path']
    (a.out/'catalog-road-correction-candidate.json').write_text(json.dumps(dict(
        authority=str(a.authority),changes=metadata_candidates,authority_modified=False,
        note='Only apply after exact before-value comparison. No voxel, native transit, entity, JAR, or route changes.'),ensure_ascii=False,indent=2),'utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in ('source','metadata','authority','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--supplement',type=Path)
    run(p.parse_args())
