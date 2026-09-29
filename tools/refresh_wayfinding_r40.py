"""Rewrite arrows from the actual reader's facing and measured next path node."""
import argparse,copy,gzip,hashlib,json,math
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
import nbtlib
import regional_voxels as v
from measure_world_r40 import WORLD,ROOT,MeasuredWorld,properties
from query_blocks import AIR,iter_block_entities
OUT=ROOT/'artifacts/world_combat_r40/signage'
NORMAL={'north':(0,-1),'south':(0,1),'west':(-1,0),'east':(1,0)}

def main(apply=False,world=WORLD,out=OUT):
    world=Path(world);out=Path(out);v.WORLD=world;v.OUT=out;out.mkdir(parents=True,exist_ok=True);p=v.Painter()
    with gzip.open(world/'nerv_routes_r24.json.gz','rt',encoding='utf8') as f:graph=json.load(f)
    nodes=np.asarray(graph['nodes']);coords=nodes[:,:3];tree=cKDTree(coords)
    ids=[q['id'] for q in graph['goals']]
    station_cols=[ids.index(k) for k in ('station','pyramid_station','launch_station') if k in ids]
    costs={col:{int(graph['goals'][col]['node']):0.} for col in station_cols}
    lift_edges={tuple(sorted((int(e['a']),int(e['b'])))) for e in graph.get('lift_edges',[])}
    def route_cost(start,col):
        memo=costs[col];path=[];seen=set();cursor=int(start)
        while cursor not in memo:
            if cursor in seen:raise RuntimeError('Cyclic route predecessor')
            seen.add(cursor);nxt=int(nodes[cursor,3+col]);dy=abs(int(coords[nxt,1])-int(coords[cursor,1]))
            weight=4+dy*.12 if tuple(sorted((cursor,nxt))) in lift_edges else 4 if dy else 1
            path.append((cursor,weight));cursor=nxt
        total=memo[cursor]
        for previous,weight in reversed(path):total+=weight;memo[previous]=total
        return memo[int(start)]
    lo=tuple(map(int,coords.min(axis=0)-[4,0,4]));hi=tuple(map(int,coords.max(axis=0)+[4,6,4]))
    tags={q:t for q,t in iter_block_entities(world,v.DIM,lo,hi) if str(t.get('id',''))=='projectseele:station_departure_board' and bool(t.get('Wayfinding',False)) and 'MapRows' not in t and str(t.get('Route',''))!='房间入口'}
    w=MeasuredWorld(world)
    for q in tags:w.around(q,8)
    w.load();updated=[];held=[];upgraded=[]
    def clear(q):return (w.block(q) or '').partition('[')[0] in AIR|{'minecraft:light','projectseele:nerv_ceiling_light'}
    def readable(q,face):
        nx,nz=NORMAL[face];target=np.asarray(q)+[nx*2,-2,nz*2];choices=tree.query_ball_point(target,5)
        choices.sort(key=lambda i:np.linalg.norm(coords[i]-target))
        for i in choices:
            x,y,z=map(int,coords[i]);forward=(x-q[0])*nx+(z-q[2])*nz;lateral=(x-q[0])*nz-(z-q[2])*nx
            if not (1<=forward<=5 and abs(lateral)<=3 and 1<=q[1]-y<=4):continue
            a=np.array([x+.5,y+1.62,z+.5]);b=np.asarray(q)+[.5+nx*.4,.7,.5+nz*.4]
            ray=np.linspace(a,b,max(2,int(np.linalg.norm(a-b)*4)))
            if all(tuple(np.floor(s).astype(int))==q or clear(tuple(np.floor(s).astype(int))) for s in ray):return i
        return None
    def zone(point):
        x,y,z=point
        if z<0:return '机库观景层' if y>=-380 else '机库登机层' if y>=-405 else '发射区交通层'
        return '终极教条区' if y<-520 else '总部车站层' if y<=-465 else '交通接驳层' if y<=-455 else '总部主环廊' if y<=-440 else '作业联络层' if y<=-426 else '技术联络层' if y<=-412 else '指挥联络层' if y<=-399 else '综合服务层' if y<=-384 else '上层接待区' if y<-355 else '总指挥层'
    for q,before in tags.items():
        state=w.block(q);face=properties(state).get('facing')
        if face not in NORMAL:held.append(dict(position=q,reason='Missing orientation'));continue
        i=readable(q,face)
        if i is None:held.append(dict(position=q,reason='No reachable and unobstructed reader',state=state));continue
        station_col=min(station_cols,key=lambda col:route_cost(i,col))
        cols=[ids.index('command'),ids.index('hangars'),station_col]
        labels=['指挥室','机库登机层',graph['goals'][station_col]['name']]
        nx,nz=NORMAL[face];texts=[];proof=[]
        for col,label in zip(cols,labels):
            path=[int(i)];cursor=int(i);lift=False
            for k in range(7):
                nxt=int(nodes[cursor,3+col])
                if nxt==cursor:break
                if abs(coords[nxt,1]-coords[cursor,1])>1:lift=True;path.append(nxt);break
                path.append(nxt);cursor=nxt
            delta=coords[path[-1]]-coords[i];right=delta[0]*nz-delta[2]*nx;forward=-delta[0]*nx-delta[2]*nz
            arrow='●' if len(path)==1 else '↑' if lift and delta[1]>0 else '↓' if lift else '→' if right>abs(forward)*.65 else '←' if -right>abs(forward)*.65 else '↑' if forward>0 else '↓'
            suffix=' · 直梯' if lift else ''
            texts.append(arrow+' '+label+suffix);proof.append(dict(goal=ids[col],reader=coords[i].tolist(),next=coords[path[-1]].tolist(),arrow=arrow))
        after=copy.deepcopy(before);after['Route']=nbtlib.String('通行指引');after['Station']=nbtlib.String(zone(coords[i]))
        for k,text in enumerate(texts):after['Row'+str(k)]=nbtlib.String(text)
        # Upgrade key boards only when the actual 3x2 housing and its backing
        # fit entirely above the walking clearance. Compact plates stay short.
        dest=q;newstate=state
        if state.startswith('projectseele:nerv_direction_panel'):
            candidate=(q[0],q[1]+(1 if q[1]-coords[i,1]<2 else 0),q[2])
            front=[(candidate[0]+(d if nz else 0),candidate[1]+h,candidate[2]+(d if nx else 0)) for d in (-1,0,1) for h in (0,1)]
            back=[(x-nx,y,z-nz) for x,y,z in front]
            backing={'projectseele:nerv_wall_panel','projectseele:nerv_structural_panel','projectseele:nerv_wall_datum','minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:white_concrete','minecraft:black_concrete'}
            if all(c==q or clear(c) for c in front) and all((w.block(c) or '').partition('[')[0] in backing for c in back):
                dest=candidate;newstate=f'projectseele:station_departure_board[facing={face},wayfinding=true]';upgraded.append(dict(before=q,after=dest))
        if dest!=q or newstate!=state:
            if dest!=q:p.match((*q,*q),state,'minecraft:air','r40/retire_low_or_tiny_direction_plate')
            p.match((*dest,*dest),w.block(dest),newstate,'r40/readable_direction_board')
            for name,n in zip(('x','y','z'),dest):after[name]=nbtlib.Int(n)
            p.block_entities[dest]=after
        else:p.update_block_entity(q,state,before,after,'r40/reader_relative_route_arrows')
        updated.append(dict(position=dest,facing=face,rows=texts,proof=proof,station_route_costs={ids[col]:route_cost(i,col) for col in station_cols}))
    p.meta.update(updated=updated,upgraded=upgraded,unreadable=held,graph_nodes=len(nodes),graph_sha256=hashlib.sha256((world/'nerv_routes_r24.json.gz').read_bytes()).hexdigest(),directions='Reader-facing coordinates and actual reachable floor predecessors; closest connected station by walking/lift graph cost, never straight-line distance; no coordinate floor labels')
    p.save_plan('measured_arrows')
    if apply:p.apply('measured_arrows')
    (out/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Directions rewritten',len(updated),'larger boards',len(upgraded),'unreadable pending relocation',len(held))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--world',type=Path,default=WORLD);p.add_argument('--out',type=Path,default=OUT);args=p.parse_args();main(args.apply,args.world,args.out)
