"""Check finite cable-station walking routes against the assigned cabin envelope.

Ngong Ping 360's installed Blockbench model uses a -5 m offset: the lowest
body face is -5.125 m. The separate grip reaches +0.625 m. A 2.4 m horizontal
radius contains every rotated body part, including open doors and the doorway.
The upper suspension uses its independently measured narrower envelope; this
permits real overhead bearings without putting beams through the cabin body.
This applies only to the explicitly surveyed station; generic reserves stay.
"""
import math,json
from collections import deque
import numpy as np
from scipy.spatial import cKDTree
from author_hakone_lakefront import Editor
from query_blocks import AIR
from map_pipeline.rail_civil_geometry import dense_points,block_top
from verify_hakone_network_candidate import PAVEMENT

class CabinReserve:
    TIERS=((-5.25,-2.25,2.45),(-2.25,.75,1.05))
    def __init__(self,curves,bounds):
        x,z,X,Z=bounds
        points=[]
        for r in curves['ropeway']:
            p=dense_points(r['points'],.1)
            keep=(p[:,0]>=x-5)&(p[:,0]<=X+5)&(p[:,2]>=z-5)&(p[:,2]<=Z+5)
            points.extend(p[keep])
        self.p=np.array(points);self.tree=cKDTree(self.p[:,[0,2]])
        self.cache={}
    def levels(self,x,z,radius=2.45):
        key=x,z,radius
        if key not in self.cache:
            p=self.p[self.tree.query_ball_point([x+.5,z+.5],radius+.71)]
            if len(p):
                dx=np.maximum(np.maximum(x-p[:,0],p[:,0]-x-1),0);dz=np.maximum(np.maximum(z-p[:,2],p[:,2]-z-1),0)
                p=p[dx*dx+dz*dz<radius**2]
            self.cache[key]=p[:,1]if len(p)else np.array([])
        return self.cache[key]
    def intersects(self,x,low,z,high):
        for bottom,top,radius in self.TIERS:
            ys=self.levels(x,z,radius)
            if np.any((high>ys+bottom+1e-6)&(low<ys+top-1e-6)):return True
        return False
    def block(self,p,state):
        return self.intersects(p[0],p[1],p[2],block_top(p[1],state))

def journeys(e,reserve,goals,bounds):
    x,y,z,X,Y,Z=bounds;standing=set()
    floors=PAVEMENT|{'minecraft:stone_bricks','minecraft:polished_andesite','projectseele:period_station_floor'}
    empty=AIR|{'minecraft:light'}
    for px in range(x,X+1):
        for pz in range(z,Z+1):
            for h in range(y-1,Y):
                s=e.state(px,h,pz)
                if s.split('[')[0]not in floors:continue
                foot=block_top(h,s)
                if any(e.state(px,q,pz).split('[')[0]not in empty for q in range(h+1,math.ceil(foot+1.8))):continue
                if reserve.intersects(px,foot,pz,foot+1.8):continue
                standing.add((px,round(foot*2),pz))
    start=tuple([goals['street'][0],round(goals['street'][1]*2),goals['street'][2]])
    prev={start:None}if start in standing else{};queue=deque(prev)
    while queue:
        p=queue.popleft()
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            for dy in (0,1,-1):
                q=p[0]+dx,p[1]+dy,p[2]+dz
                if q in standing and q not in prev:prev[q]=p;queue.append(q)
    routes=[];errors=[]
    for name,goal in goals.items():
        q=(goal[0],round(goal[1]*2),goal[2]);path=[]
        if q not in prev:errors.append(['unreachable cable station destination',name,goal])
        else:
            while q is not None:path.append([q[0],q[1]/2,q[2]]);q=prev[q]
            path.reverse()
        routes.append(dict(name=name,path=path))
    return dict(errors=errors,journeys=routes,reachable_positions=len(prev),maximum_step_height=.5,passenger_height=1.8,cabin_reserve=dict(tiers=reserve.TIERS),game_ui_verification=False)
