"""Verify a declared station overlay against exact saved collision shapes."""
from pathlib import Path
import collections, math
import numpy as np
from author_hakone_lakefront import Editor
from audit_hakone_station_walks import Walker
from map_pipeline.delivery_check import read


def verify(candidate, authority, layout):
    e=Editor(candidate)
    w=Walker.__new__(Walker);w.reader=e;w.shapes=read(layout['collision_shapes']);w.cache={}
    nodes={tuple(p) for p in layout['station_multi_level_nodes']}
    if len(nodes)!=len(layout['station_multi_level_nodes']):
        raise ValueError('Duplicate walking surfaces')
    for x,g,z in sorted(nodes):
        feet=g/2+1
        heights,unknown=w.floors(x+.5,feet,z+.5)
        if unknown or not any(abs(h-feet)<1e-6 for h in heights) or w.body(x+.5,feet,z+.5):
            raise ValueError(f'Unverified declared pedestrian surface: {x},{g},{z}')
    ground={tuple(p) for p in layout['ground_access_columns']}
    if not ground or len(ground)!=len(layout['ground_access_columns']):
        raise ValueError('Missing or duplicated ground access')
    if any((x,g,z)not in nodes for x,z,g in ground):
        raise ValueError('Ground access is outside measured walking surfaces')
    if len({(x,z)for x,z,g in ground})!=len(ground):
        raise ValueError('Several ground grades at one column')
    with np.load(Path(authority)/'network.npz')as f:
        ax,az,bx,bz=map(int,f['bounds']);oldwalk=f['walk'];oldgrade=f['grade2'];oldroad=f['road']
    def node_of(p):
        x,y,z=p
        return math.floor(x),round((y-1)*2),math.floor(z)
    starts=[]
    ids=[]
    for station in layout['stations']:
        ids.append(station['id'])
        start=node_of(station['approach'])
        if start not in nodes:raise ValueError('Street approach not in measured overlay')
        x,g,z=start
        if not(oldwalk[z-az,x-ax]or oldroad[z-az,x-ax])or int(oldgrade[z-az,x-ax])!=g:
            raise ValueError('Station does not reach an existing authoritative street')
        starts.append(start)
        reached={start};queue=collections.deque(reached)
        while queue:
            x,g,z=queue.popleft()
            for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
                for dg in(-1,0,1):
                    q=x+dx,g+dg,z+dz
                    if q in nodes and q not in reached:reached.add(q);queue.append(q)
        for destination in station['destinations']:
            if node_of(destination)not in reached:raise ValueError('Station destination not connected to street')
        station['_reachable']=reached
    if len(ids)!=len(set(ids))or not ids:raise ValueError('Invalid station identities')
    reached=set().union(*(s.pop('_reachable')for s in layout['stations']))
    if reached!=nodes:raise ValueError('Declared public surfaces contain unreachable cells')
    for x,z,g in ground:
        if not ax<=x<=bx or not az<=z<=bz:raise ValueError('Ground access outside authority')
        if (oldwalk[z-az,x-ax]or oldroad[z-az,x-ax])and int(oldgrade[z-az,x-ax])!=g:
            raise ValueError('Ground overlay changes an existing street elevation')
    return dict(errors=[],nodes=len(nodes),reachable_nodes=len(reached),ground_columns=len(ground),world_written=False)
