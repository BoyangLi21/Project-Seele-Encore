"""Dedicated read-only patch authoring for R45 school and Hakone station.

This module has no apply method. All Minecraft reads stay in query_blocks.
Original block entities are immutable, including engine fields and full SNBT.
"""
from __future__ import annotations

from pathlib import Path
from collections import Counter
import gzip
import hashlib
import json

import nbtlib

from measure_world_r40 import MeasuredWorld
from query_blocks import AIR, iter_block_entities
from regional_voxels import canonical_state

ROOT = Path(__file__).resolve().parents[1]
DIM = 'projectseele:geofront'
ART = ROOT/'artifacts/rebuild_r45/school_hakone_agent'
NATURAL = AIR | {'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:coarse_dirt','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:sand','minecraft:gravel'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Candidate:
    def __init__(self, world, bounds, owner):
        self.world = Path(world)
        self.lo, self.hi = tuple(bounds[:3]), tuple(bounds[3:])
        self.owner = owner
        self.measured = MeasuredWorld(self.world, DIM)
        self.measured.box(self.lo, self.hi)
        self.measured.load()
        if any(v != 'full' for v in self.measured.status.values()):
            raise RuntimeError('All candidate chunks must already be FULL; no world generation is authorized')
        self.tags = {q: t.snbt() for q,t in iter_block_entities(self.world,DIM,self.lo,self.hi)}
        self.target = {}
        self.hard = set()
        self.preserved = set()
        self.rooms = []
        self.cases = []
        self.components = []
        self.cameras = []
        self.floors = []
        self.foundations = []
        self.ports = []

    def state(self, q):
        q=tuple(q)
        return self.target[q]['after'] if q in self.target else self.measured.block(q)

    def put(self, q, state, reason, nbt=None, owner=None):
        q=tuple(map(int,q))
        if not all(self.lo[i] <= q[i] <= self.hi[i] for i in range(3)):
            raise RuntimeError(('Outside measured finite component',q,self.lo,self.hi))
        before=self.measured.block(q)
        if before is None:
            raise RuntimeError(('Unmeasured coordinate',q))
        state=canonical_state(state)
        if q in self.hard:
            self.preserved.add(q)
            return
        if q in self.tags:
            # A pre-existing fixture is part of the entire existing facility.
            # Its complete state and NBT stay unchanged even under a roof edit.
            self.preserved.add(q)
            return
        if before==state and nbt is None:
            self.target.pop(q,None)
            return
        self.target[q]=dict(pos=list(q),before=before,after=state,before_nbt=None,after_nbt=nbt,owner=owner or self.owner,reason=reason)

    def fill(self, box, state, reason, owner=None):
        x,y,z,X,Y,Z=box
        for yy in range(y,Y+1):
            for zz in range(z,Z+1):
                for xx in range(x,X+1):
                    self.put((xx,yy,zz),state,reason,owner=owner)

    def foundation(self, rect, floor, label):
        x,z,X,Z=rect
        rows=[]
        for zz in range(z,Z+1):
            for xx in range(x,X+1):
                observed=[]
                for yy in range(self.lo[1],floor+8):
                    s=self.measured.get(xx,yy,zz)
                    if s.partition('[')[0]=='minecraft:water':
                        raise RuntimeError(('New school terrace cannot fill a natural wetland',xx,zz,yy))
                    if s.partition('[')[0] not in NATURAL:
                        raise RuntimeError(('New school component overlaps independent authored fabric',xx,yy,zz,s))
                    if s.partition('[')[0] not in AIR|{'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern'}:
                        observed.append(yy)
                if not observed:
                    raise RuntimeError(('No actual dry natural bearing',xx,zz))
                g=max(observed)
                for yy in range(min(g,floor)-1,floor):
                    edge=xx in [x,X] or zz in [z,Z]
                    self.put((xx,yy,zz),'minecraft:stone_bricks' if edge else 'minecraft:stone','Complete '+label+' bearing / finite retaining wall on actual dry ground')
                self.put((xx,floor,zz),'minecraft:smooth_stone','Complete '+label+' surface')
                for yy in range(floor+1,max(floor+5,g+1)):
                    self.put((xx,yy,zz),'minecraft:air','Finite '+label+' headroom; no wetland grading')
                rows.append(dict(pos=[xx,zz],actual_bearing_y=g,deck_y=floor,cut_fill=floor-g))
        self.foundations.append(dict(component=label,columns=rows,maximum_abs_cut_fill=max(abs(c['cut_fill']) for c in rows)))

    def fixture(self, q, kind, title, lines=(), facing='south'):
        q=tuple(q)
        tag=nbtlib.Compound({'id':nbtlib.String('projectseele:period_fixture'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'Title':nbtlib.String(title),'Lines':nbtlib.List[nbtlib.String]([nbtlib.String(t) for t in lines]),'Clock':nbtlib.Long(0)})
        self.put(q,f'projectseele:period_fixture[facing={facing},kind={kind}]','Original human-scale '+kind+' fixture with complete native NBT',tag.snbt())
        extra=2 if kind=='public_phone' else 1 if kind in {'notice_board','newspaper_rack','coffee_machine','tech_bench','parked_bicycle','vending_machine','letter_box'} else 0
        for dy in range(1,extra+1):
            self.put((q[0],q[1]+dy,q[2]),f'projectseele:period_fixture_part[offset={dy}]','Entire reserved fixture collision envelope, matching original native renderer')

    def sign(self, q, lines, facing='south'):
        q=tuple(q)
        texts=nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps({'text':t},ensure_ascii=False,separators=(',',':'))) for t in (list(lines)+['']*4)[:4]])
        side=nbtlib.Compound({'messages':texts,'color':nbtlib.String('black'),'has_glowing_text':nbtlib.Byte(0)})
        tag=nbtlib.Compound({'id':nbtlib.String('minecraft:sign'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'front_text':side,'back_text':nbtlib.Compound(side),'is_waxed':nbtlib.Byte(1)})
        self.put(q,f'minecraft:oak_wall_sign[facing={facing},waterlogged=false]','Readable original facility label on an actual backing wall',tag.snbt())

    def empty_container(self, q, state, kind):
        x,y,z=q
        tag=nbtlib.Compound({'id':nbtlib.String('minecraft:'+kind),'x':nbtlib.Int(x),'y':nbtlib.Int(y),'z':nbtlib.Int(z),'Items':nbtlib.List[nbtlib.Compound]([])})
        self.put(q,state,'Complete original empty '+kind+' storage block and NBT; no invented user inventory',tag.snbt())

    def bed(self, q):
        x,y,z=q
        for zz,part in [(z,'foot'),(z-1,'head')]:
            tag=nbtlib.Compound({'id':nbtlib.String('minecraft:bed'),'x':nbtlib.Int(x),'y':nbtlib.Int(y),'z':nbtlib.Int(zz)})
            self.put((x,y,zz),f'minecraft:white_bed[facing=north,occupied=false,part={part}]','Complete two-part school infirmary bed with native NBT',tag.snbt())

    def door(self, q, facing='south', hinge='left', label='door'):
        x,y,z=q
        for half,dy in [('lower',0),('upper',1)]:
            self.put((x,y+dy,z),f'projectseele:city_personnel_door[facing={facing},half={half},hinge={hinge},open=false,powered=false]','Complete '+label+' leaf; existing original native door implementation')
        self.ports.append(dict(id=self.owner+'/'+label,position=list(q),facing=facing,states=['closed','open'],native_verified=False))

    def path(self, label, points, **extra):
        for suffix,p in [('',points),('/return',list(reversed(points)))]:
            self.cases.append(dict(id=self.owner+'/'+label+suffix,path=p,native_passed=False,**extra))

    def camera(self, label, position, look_at, coverage):
        self.cameras.append(dict(id=self.owner+'/'+label,position=position,look_at=look_at,coverage=coverage,native_photographed=False))

    def export(self, out, contract):
        out=Path(out)
        if ART.resolve()!=out.resolve() and ART.resolve() not in out.resolve().parents:
            raise RuntimeError('Candidate output must stay in the dedicated R45 agent artifact directory')
        if out.exists():
            raise RuntimeError(('Refuse to replace an existing candidate epoch',str(out)))
        out.mkdir(parents=True)
        rows=[self.target[q] for q in sorted(self.target)]
        for name,inverse in [('forward',False),('inverse',True)]:
            with gzip.open(out/(name+'.jsonl.gz'),'wt',encoding='utf8') as f:
                for row in rows:
                    r=dict(row)
                    if inverse:
                        r['before'],r['after']=row['after'],row['before']
                        r['before_nbt'],r['after_nbt']=row['after_nbt'],row['before_nbt']
                    f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
        with gzip.open(out/'positive_edit_mask.jsonl.gz','wt',encoding='utf8') as f:
            for r in rows:f.write(json.dumps(r['pos'])+'\n')
        for name,data in [('native_cases.json',self.cases),('camera_itinerary.json',self.cameras),('components.json',self.components),('rooms.json',self.rooms),('floor_regions.json',self.floors),('ports.json',self.ports),('foundations.json',self.foundations),('preserved_block_entities.json',[dict(pos=list(q),state=self.measured.block(q),snbt=t) for q,t in self.tags.items()])]:
            (out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
        states=sorted({r['after'] for r in rows})
        (out/'requested_native_states.json').write_text(json.dumps(states,indent=2),'utf8')
        # Export the existing exact-match operation format for root integration.
        # No apply invocation or world file is created by this producer.
        opdir=out/'root_operation_plan'
        opdir.mkdir()
        with gzip.open(opdir/'ops.json.gz','wt',encoding='utf8') as f:
            json.dump([dict(box=r['pos']+r['pos'],state=r['after'],owner=r['owner'],mode='match',extra=[r['before']]) for r in rows],f)
        (opdir/'block_entities.json').write_text(json.dumps([dict(pos=r['pos'],snbt=r['after_nbt']) for r in rows if r['after_nbt'] is not None],ensure_ascii=False),'utf8')
        (opdir/'states.json').write_text(json.dumps(states),'utf8')
        (opdir/'chunks.json').write_text(json.dumps(sorted({(r['pos'][0]//16,r['pos'][2]//16) for r in rows})),'utf8')
        (opdir/'protected.json').write_text('[]','utf8')
        (opdir/'places.json').write_text(json.dumps(dict(rooms=self.rooms,walk_nodes=self.cases,landmarks=self.components,doors=self.ports),ensure_ascii=False),'utf8')
        contract.update(world=str(self.world.resolve()),dimension=DIM,bounds=list(self.lo)+list(self.hi),world_written=False,exact_cells=len(rows),preserved_original_block_entities=len(self.tags),modified_original_block_entities=0,new_block_entities=sum(r['after_nbt'] is not None for r in rows),component_count=len(self.components),room_count=len(self.rooms),walk_cases=len(self.cases),native_passed=False,visual_passed=False,user_approved=False,release_ready=False,readback_required=True,full_nbt_inverse=True)
        contract['files']={n:dict(path=str((out/n).resolve()),sha256=sha(out/n)) for n in ['forward.jsonl.gz','inverse.jsonl.gz','positive_edit_mask.jsonl.gz','native_cases.json','camera_itinerary.json','preserved_block_entities.json']}
        (out/'contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),'utf8')
        print(self.owner,'exact cells',len(rows),'original BE preserved',len(self.tags),'new BE',contract['new_block_entities'],'native cases',len(self.cases),flush=True)
        return out
