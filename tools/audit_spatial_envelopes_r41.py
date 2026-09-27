"""Read-only whole-space defects, independent of historical walking centre lines.

The output is a triage queue, not permission to fill a railway or delete a wall.
All blocks are read by query_blocks; unknown/chunk boundaries are not air.
"""
from pathlib import Path
from collections import defaultdict, Counter
import argparse, json, time
import numpy as np
from query_blocks import iter_matching_sections, iter_selected_sections, chunk_statuses, AIR
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/spatial_repair_r41'
WORLD=ART/'source_world_backup'
DIM='projectseele:geofront'
FLOORS={'projectseele:nerv_floor_panel','projectseele:nerv_machine_panel','projectseele:nerv_hazard_paving',
        'minecraft:smooth_stone','minecraft:polished_deepslate','minecraft:polished_blackstone',
        'minecraft:polished_andesite','minecraft:stone_bricks','minecraft:smooth_quartz',
        'minecraft:quartz_block','minecraft:iron_block'}
WALLS={'projectseele:nerv_wall_panel','projectseele:nerv_structural_panel','projectseele:clear_glass',
       'minecraft:glass','minecraft:polished_blackstone_bricks','minecraft:polished_deepslate',
       'minecraft:deepslate_bricks','minecraft:stone_bricks'}


def kinds(state):
    name=state.partition('[')[0]
    floor=name in FLOORS or name.endswith('_concrete') or name.startswith('mtr:platform') or name=='mtr:escalator_step'
    wall=name in WALLS or name.endswith('_stained_glass')
    return floor,wall,name=='mtr:escalator_step'


def index(world,out):
    out.mkdir(parents=True,exist_ok=True);stats={};sections=[];clock=time.monotonic();last=clock
    for cx,cz,sy,palette,ids in iter_matching_sections(world,DIM,[''],stats):
        flags=np.array([any(kinds(s)) for s in palette])
        if flags[ids].any():sections.append([cx,sy,cz])
        if time.monotonic()-last>25:
            print('Index:',stats['chunks_read'],'chunks,',len(sections),'candidate sections',flush=True);last=time.monotonic()
    record=dict(world=str(world),stats=stats,sections=sections,seconds=time.monotonic()-clock)
    (out/'index.json').write_text(json.dumps(record,separators=(',',':')),'utf8')
    print('Full frozen-world index complete:',stats,flush=True)


class Atlas:
    def __init__(self,world,cores):
        self.palette=['UNKNOWN','minecraft:air'];lookup={s:i for i,s in enumerate(self.palette)}
        selected=defaultdict(set)
        for cx,sy,cz in cores:
            for dx in (-1,0,1):
                for dz in (-1,0,1):selected[cx+dx,cz+dz].update((sy-1,sy,sy+1))
        self.status=chunk_statuses(world,DIM,selected);self.tiles={};self.selected=selected
        for cx,cz,sy,pal,ids in iter_selected_sections(world,DIM,selected,skip_unfinished=True):
            mapping=[]
            for state in pal:
                state=canonical_state(state)
                if state not in lookup:lookup[state]=len(self.palette);self.palette.append(state)
                mapping.append(lookup[state])
            self.tiles[cx,sy,cz]=np.asarray(mapping,np.uint16)[ids].reshape(16,16,16)
        shapes_path=world/'native_collision_shapes.json'
        shapes={canonical_state(k):v for k,v in json.loads(shapes_path.read_text('utf8')).items()}
        self.missing=set();flags=[];physical=[];edge_guards=[];head_guards=[]
        for state in self.palette:
            name=state.partition('[')[0];boxes=shapes.get(state)
            if boxes is None:
                if name in AIR|{'minecraft:light'}:boxes=[]
                elif name=='mtr:escalator_step' and 'orientation=flat' in state:boxes=[[0,0,0,1,.9375,1]]
                else:boxes=[[0,0,0,1,1,1]];self.missing.add(state)
            def clear(h):return not any(b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 and b[1]<h and b[4]>.001 for b in boxes)
            wet=any(v in name for v in ('water','lava','lcl'))
            supported=any(b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and .90<=b[4]<=1.01 for b in boxes)
            floor,wall,moving=kinds(state)
            flags.append((clear(1) and not wet and state!='UNKNOWN',clear(.8) and not wet and state!='UNKNOWN',supported,floor,wall,moving))
            physical.append((clear(1) and state!='UNKNOWN',clear(.8) and state!='UNKNOWN'))
            low=[];high=[]
            for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:
                axis=0 if dx else 2;tangent=2 if dx else 0;positive=dx+dz>0
                def spans(b):
                    return b[tangent]<=.2 and b[tangent+3]>=.8 and (b[axis+3]>=.7 if positive else b[axis]<=.3)
                low.append(any(spans(b) and b[4]>.6 and b[1]<1.8 for b in boxes))
                high.append(any(spans(b) and b[4]>0 and b[1]<.8 for b in boxes))
            edge_guards.append(low);head_guards.append(high)
        self.free,self.head,self.support,self.floor,self.wall,self.moving=np.asarray(flags,bool).T
        self.physical_free,self.physical_head=np.asarray(physical,bool).T
        self.edge_guards=np.asarray(edge_guards,bool);self.head_guards=np.asarray(head_guards,bool)
        print('Loaded',len(self.tiles),'exact sections;',len(self.palette),'states',flush=True)

    def volume(self,core):
        cx,sy,cz=core;lo=np.array([cx*16-2,sy*16-8,cz*16-2]);hi=lo+[19,39,19]
        a=np.zeros((40,20,20),np.uint16)
        for X in range(lo[0]//16,hi[0]//16+1):
            for Z in range(lo[2]//16,hi[2]//16+1):
                if self.status.get((X,Z))!='full':continue
                for Y in range(lo[1]//16,hi[1]//16+1):
                    if Y not in self.selected.get((X,Z),()):continue
                    low=np.maximum([X*16,Y*16,Z*16],lo);high=np.minimum([X*16+15,Y*16+15,Z*16+15],hi)
                    dst=tuple(slice(low[i]-lo[i],high[i]-lo[i]+1) for i in (1,2,0))
                    tile=self.tiles.get((X,Y,Z))
                    if tile is None:a[dst]=1
                    else:
                        base=np.array([X,Y,Z])*16
                        src=tuple(slice(low[i]-base[i],high[i]-base[i]+1) for i in (1,2,0));a[dst]=tile[src]
        return a,lo


def inspect(atlas,core):
    a,lo=atlas.volume(core);free=atlas.free[a];head=atlas.head[a];support=atlas.support[a];floor=atlas.floor[a];wall=atlas.wall[a]
    walk=np.zeros(a.shape,bool);walk[1:-1]=support[:-2]&free[1:-1]&head[2:]
    public=np.zeros(a.shape,bool);public[1:-1]=walk[1:-1]&floor[:-2]
    rows=[]
    def report(mask,kind,extra=None):
        mask=mask.copy();mask[:8]=False;mask[24:]=False;mask[:,:2]=False;mask[:,18:]=False;mask[:,:,:2]=False;mask[:,:,18:]=False
        for yy,zz,xx in np.argwhere(mask):
            q=(np.array([xx,yy,zz])+lo).tolist();row=dict(kind=kind,pos=q,state=atlas.palette[int(a[yy,zz,xx])])
            if extra:row.update(extra(yy,zz,xx))
            rows.append(row)
    # Examine every side of every constructed standing cell. Even a one-metre
    # unguarded step into a track bed is a defect candidate; requiring a lethal
    # fall would miss an unfinished pedestrian/rail boundary.
    for direction,(dx,dz) in enumerate([(1,0),(-1,0),(0,1),(0,-1)]):
        def near(v):return np.roll(v,(-dz,-dx),axis=(1,2))
        beside=near(atlas.physical_free[a]);clearance=np.zeros(a.shape,bool);clearance[:-1]=beside[:-1]&near(atlas.physical_head[a])[1:]
        depth=np.ones(a.shape,bool)
        depth[1:]&=beside[:-1];depth[:1]=False
        guarded=atlas.edge_guards[a,direction]|near(atlas.edge_guards[a,direction^1])
        guarded[:-1]|=atlas.head_guards[a[1:],direction]|near(atlas.head_guards[a[1:],direction^1])
        risky=public&clearance&depth&~guarded
        roof=np.zeros(a.shape,bool)
        for dy in range(2,11):roof[:-dy]|=~free[dy:]&(a[dy:]!=0)
        report(risky,'unguarded_drop',lambda y,z,x:dict(normal=[dx,0,dz],enclosed=bool(roof[y,z,x]),
            drop_blocks=next((d-1 for d in range(2,min(y+1,9)) if not beside[y-d,z,x]),None)))
    # A wall end with walkable floor on three sides is still a candidate even
    # when the player can detour around it. Door jambs need an explicit decision.
    neighbours=np.zeros(a.shape,np.uint8)
    for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:neighbours+=np.roll(walk,(dz,dx),axis=(1,2))
    base=np.zeros(a.shape,bool);base[1:]=support[:-1]&floor[:-1]
    report(base&wall&(neighbours>=3),'wall_intrusion',lambda y,z,x:dict(walkable_sides=int(neighbours[y,z,x])))
    # A vertical sheet continuing beyond both adjacent floor fields remains
    # detectable when its far end is attached to the newer building.
    bottom=wall.copy()
    for dy in (1,2,3):bottom[dy:]&=free[:-dy];bottom[:dy]=False
    for dy in (1,2,3):bottom[:-dy]&=wall[dy:];bottom[-dy:]=False
    for axis in (1,2):
        thin=bottom.copy()
        for dy in (0,1,2):
            side=np.roll(free,1,axis)&np.roll(free,-1,axis)
            if dy:thin[:-dy]&=side[dy:];thin[-dy:]=False
            else:thin&=side
        report(thin,'attached_sheet_candidate',lambda y,z,x:dict(thickness_axis='z' if axis==1 else 'x'))
    # Each half of a two-wide native moving walk has its own outgoing space.
    # Test the true facing axis in both directions, never a nearby air cell.
    for yy,zz,xx in np.argwhere(atlas.moving[a][8:24,2:18,2:18]):
        yy+=8;zz+=2;xx+=2;state=atlas.palette[int(a[yy,zz,xx])]
        if 'orientation=flat' not in state:continue
        facing=next(f for f in ('north','south','east','west') if 'facing='+f in state)
        if not (free[yy+1,zz,xx] and head[yy+2,zz,xx]):
            rows.append(dict(kind='moving_walk_obstructed',pos=(np.array([xx,yy+1,zz])+lo).tolist(),
                state=atlas.palette[int(a[yy+1,zz,xx])],head_state=atlas.palette[int(a[yy+2,zz,xx])],facing=facing))
        dx,dz={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}[facing]
        for sign in (-1,1):
            X,Z=xx+dx*sign,zz+dz*sign
            if atlas.moving[a[yy,Z,X]]:continue
            # An adjacent inclined native step is handled by the stair audit,
            # and a one-block descent must not be counted as a level landing.
            if any(atlas.moving[a[yy+d,Z,X]] for d in (-1,1)):continue
            if support[yy,Z,X] and free[yy+1,Z,X] and head[yy+2,Z,X]:continue
            q=(np.array([X,yy+1,Z])+lo).tolist()
            rows.append(dict(kind='moving_walk_exit',pos=q,state=atlas.palette[int(a[yy+1,Z,X])],step=(np.array([xx,yy,zz])+lo).tolist(),facing=facing,side='left' if 'side=left' in state else 'right'))
    return rows


def scan(world,out,samples=False):
    out.mkdir(parents=True,exist_ok=True)
    if samples:
        boxes=[((83,-448,-63),(113,-432,-23)),((86,-399,-63),(116,-380,-23)),((73,-399,-284),(102,-386,-252))]
        cores=sorted({(x,y,z) for lo,hi in boxes for x in range(lo[0]//16,hi[0]//16+1) for y in range(lo[1]//16,hi[1]//16+1) for z in range(lo[2]//16,hi[2]//16+1)})
    else:
        record=json.loads((out/'index.json').read_text('utf8'));assert Path(record['world']).resolve()==world.resolve();assert record['stats']['complete'];cores=record['sections']
    atlas=Atlas(world,cores);rows=[];start=time.monotonic()
    for i,core in enumerate(cores):
        rows+=inspect(atlas,core)
        if i and i%1000==0:print('Spatial envelopes',i,'/',len(cores),len(rows),'findings',round(time.monotonic()-start,1),'seconds',flush=True)
    unique={json.dumps(row,sort_keys=True):row for row in rows};rows=list(unique.values())
    name='samples' if samples else 'findings'
    (out/(name+'.json')).write_text(json.dumps(dict(world=str(world),read_only=True,core_sections=len(cores),counts=dict(Counter(r['kind'] for r in rows)),missing_shapes=sorted(atlas.missing),findings=rows),ensure_ascii=False,separators=(',',':')),'utf8')
    print(name,'completed',dict(Counter(r['kind'] for r in rows)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['index','scan','samples']);p.add_argument('--world',type=Path,default=WORLD);p.add_argument('--out',type=Path,default=ART/'envelopes');args=p.parse_args()
    index(args.world,args.out) if args.action=='index' else scan(args.world,args.out,args.action=='samples')
