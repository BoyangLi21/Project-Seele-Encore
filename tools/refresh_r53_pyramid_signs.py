"""Bind pyramid signs to the actual reader, named lifts and current routes."""
import argparse,copy,gzip,hashlib,json,math
from pathlib import Path
import nbtlib
import numpy as np
from scipy.spatial import cKDTree
from query_blocks import iter_block_entities
from measure_world_r40 import MeasuredWorld,properties
from audit_facility_transit_r44 import Geometry
from station_sign_readers_r44 import NORMAL,reader_visibility
from repair_r53_reported_landings import apply

LIFT_NAMES={'s20-command-rear-x12-z253-v4':'西侧主电梯','r25-east-command-gallery':'东侧主电梯',
    's23-commander-office-x28-z321-v1':'总指挥专梯','s20-surface-transit-v2':'湖畔电梯',
    'r25-west-observation':'机库观景梯','s20-compact-cage-x93-z204-v4':'实验区电梯'}
FLOORS={-554:'B1 · 交通接驳层',-541:'1F · 总部门厅',-535:'湖畔电梯接驳层',-527:'2F · 勤务联络层',
    -516:'主指挥台',-513:'3F · 科研联络层',-512:'指挥后方勤务层',-502:'指挥室观察廊',
    -499:'4F · 作战指挥层',-485:'5F · 指挥室上层',-481:'总指挥联络厅',-471:'6F · 上部办公层',
    -457:'7F · 上部观察层',-433:'总指挥会客厅'}

def plan(world,out):
    graph_path=world/'nerv_routes_r24.json.gz';graph=json.loads(gzip.decompress(graph_path.read_bytes()))
    nearest=json.loads(gzip.decompress((world/'nearest_lift_paths_r44.json.gz').read_bytes()))
    sha=hashlib.sha256(graph_path.read_bytes()).hexdigest();assert nearest['graph_sha256']==sha
    nodes=graph['nodes'];coords=np.array([r[:3] for r in nodes]);lookup={tuple(p):i for i,p in enumerate(coords)}
    active=np.flatnonzero(graph['node_active']);tree=cKDTree(coords[active]);ids=[r['id'] for r in graph['goals']]
    landings={tuple(r['actual']):r for r in graph['named_lift_landings']}
    tags={q:t for q,t in iter_block_entities(world,graph['dimension'],(-55,-560,235),(145,-429,438))
        if str(t.get('id',''))=='projectseele:station_departure_board' and bool(t.get('Wayfinding',False)) and 'MapRows' not in t and '通行指引' in str(t.get('Route',''))}
    measured=MeasuredWorld(world,graph['dimension'])
    for q in tags:measured.box((q[0]-7,q[1]-7,q[2]-7),(q[0]+7,q[1]+4,q[2]+7))
    measured.load();geometry=Geometry(measured)
    def optical(state):
        return [] if state and ('glass' in state or 'lift_door_interlock' in state) else geometry.boxes(state)
    def reader(q,state,face):
        dx,dz=NORMAL[face];target=np.array(q)+[dx*3,-2,dz*3]
        candidates=[int(active[k]) for k in tree.query_ball_point(target,5)]
        candidates.sort(key=lambda i:np.linalg.norm(coords[i]-target))
        for i in candidates:
            p=coords[i];forward=(p[0]-q[0])*dx+(p[2]-q[2])*dz;lateral=(p[0]-q[0])*dz-(p[2]-q[2])*dx
            if not(1<=forward<=6 and abs(lateral)<=3 and 1<=q[1]-p[1]<=5):continue
            if reader_visibility(measured.block,optical,q,face,p,direction=True,compact='nerv_direction_panel' in state)['clear']:return i
        return None
    def direction(start,next_node,face):
        cursor=start;path=[start];initial=None
        for _ in range(5):
            nxt=next_node(cursor)
            if nxt==cursor:break
            d=coords[nxt]-coords[cursor]
            if abs(d[1])>1:break
            vector=tuple(np.sign(d[[0,2]]))
            if initial is not None and vector!=initial:break
            initial=vector;path.append(nxt);cursor=nxt
        dx,dz=NORMAL[face];d=coords[path[-1]]-coords[start]
        right=d[0]*dz-d[2]*dx;forward=-d[0]*dx-d[2]*dz
        arrow='●' if len(path)==1 else '→' if right>abs(forward) else '←' if -right>abs(forward) else '↑' if forward>0 else '↓'
        return arrow,[nodes[i][:3] for i in path]
    rows=[];updates=[];held=[]
    for q,old in tags.items():
        state=measured.block(q);face=properties(state).get('facing');i=reader(q,state,face) if face in NORMAL else None
        if i is None:
            held.append(dict(pos=q,reason='No unobstructed registered reader'));continue
        entry=nearest['nodes'][i]
        if entry is None:
            held.append(dict(pos=q,reason='No declared lift walking route'));continue
        landing=landings[tuple(entry['nearest_landing'])];lift=LIFT_NAMES[landing['lift_id']]
        arrow,lift_path=direction(i,lambda k:lookup[tuple(nearest['nodes'][k]['next'])],face)
        texts=[arrow+' '+lift+(' · 经楼梯' if entry['requires_floor_transfer'] else '')];proof=[dict(destination=landing,reader=nodes[i][:3],path=lift_path)]
        for goal,label in (('command','指挥室'),('station','总部车站')):
            col=ids.index(goal);arrow,path=direction(i,lambda k:nodes[k][3+col],face)
            texts.append(arrow+' '+label);proof.append(dict(destination=goal,reader=nodes[i][:3],path=path))
        y=int(coords[i,1]);floor=min(FLOORS,key=lambda h:abs(y-h));title=FLOORS[floor]
        # Restricted SEELE access and the public corridor share a height.
        if floor==-457 and 16<=q[0]<=51 and 300<=q[2]<=317:title='SEELE 会议层 · 门禁'
        new=copy.deepcopy(old);new['Station']=nbtlib.String(title);new['Route']=nbtlib.String('通行指引')
        for n,t in enumerate(texts):new['Row'+str(n)]=nbtlib.String(t)
        if new==old:continue
        rows.append(dict(pos=q,before=state,after=state,before_nbt=old.snbt(),after_nbt=new.snbt(),reason='actual_named_lift_and_reader_relative_directions'))
        updates.append(dict(pos=q,face=face,old=[str(old.get(k,'')) for k in ('Station','Row0','Row1','Row2')],new=[title]+texts,proof=proof))
    out.mkdir(parents=True,exist_ok=True)
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False).encode(),mtime=0))
    report=dict(world=str(world),graph_sha256=sha,checked_boards=len(tags),updated=len(rows),updates=updates,held=held,unknown_shapes=sorted(geometry.unknown),world_written=False)
    (out/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Boards',len(tags),'updated',len(rows),'held',len(held))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    if a.apply:
        record=json.loads((a.output/'PLAN.json').read_text('utf8'))
        assert record['graph_sha256']==hashlib.sha256((a.world/'nerv_routes_r24.json.gz').read_bytes()).hexdigest()
        apply(a.world,a.output)
    else:plan(a.world,a.output)
