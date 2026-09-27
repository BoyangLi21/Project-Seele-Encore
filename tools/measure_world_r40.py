"""Compact exact section cache for R40; all save reads go through query_blocks."""
from pathlib import Path
from collections import defaultdict
import numpy as np
from math import floor
from query_blocks import iter_selected_sections,chunk_statuses,AIR
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R40_REVIEW'
DIM='projectseele:geofront'

class MeasuredWorld:
    def __init__(self,world=WORLD):
        self.world=Path(world);self.selected=defaultdict(set);self.tiles={};self.status={}
    def box(self,lo,hi):
        for x in range(lo[0]//16,hi[0]//16+1):
            for z in range(lo[2]//16,hi[2]//16+1):self.selected[x,z].update(range(lo[1]//16,hi[1]//16+1))
    def around(self,point,radius=3):
        self.box(tuple(floor(a)-radius for a in point),tuple(floor(a)+radius for a in point))
    def load(self):
        self.status=chunk_statuses(self.world,DIM,self.selected)
        for x,z,y,palette,ids in iter_selected_sections(self.world,DIM,self.selected,skip_unfinished=True):
            self.tiles[x,y,z]=(tuple(map(canonical_state,palette)),np.asarray(ids,dtype=np.uint16))
        return self
    def get(self,x,y,z):
        x,y,z=map(floor,(x,y,z));key=x//16,y//16,z//16
        if self.status.get((x//16,z//16))!='full' or y//16 not in self.selected.get((x//16,z//16),()):return None
        data=self.tiles.get(key)
        if data is None:return 'minecraft:air'
        palette,ids=data;return palette[int(ids[((y&15)<<8)|((z&15)<<4)|(x&15)])]
    def block(self,point):return self.get(*point)

def properties(state):
    return dict(s.split('=',1) for s in state.partition('[')[2].rstrip(']').split(',') if '=' in s)

def empty(state):
    if state is None:return False
    name=state.partition('[')[0]
    return name in AIR or name in {'minecraft:light','minecraft:tripwire'} or any(name.endswith(x) for x in ('_button','_wall_sign','_pressure_plate','_carpet','_torch'))
