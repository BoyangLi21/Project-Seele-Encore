"""Build a finite station-interior and paved-entry repair from offline FULL chunks.

The actual client world, native traffic files and JAR are never opened. All
additional cells must come from the supplied complete-height captures.
"""
import argparse
import copy
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

import nbtlib
import numpy as np

from author_hakone_lakefront import Editor
from audit_hakone_station_walks import Walker
from map_pipeline.station_sections import StationSections
from review_underground_station_evidence import Overlay, strict_walk


SOIL={'minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]'}
AIR={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:light'}
STRUCT='projectseele:nerv_structural_panel'
WALL='projectseele:nerv_wall_panel'
FLOOR='projectseele:period_station_floor'
PAVEMENT={FLOOR,'projectseele:nerv_floor_panel','minecraft:gray_concrete','minecraft:black_concrete','minecraft:white_concrete','minecraft:smooth_stone',STRUCT}


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')


class Sources:
    def __init__(self,full,context):
        self.paths=list(reversed(full));self.readers=[StationSections(p)for p in self.paths]
        self.context=StationSections(context);self.full_chunks={}
        for index,reader in reversed(list(enumerate(self.readers))):
            for site in reader.report['sites']:
                for cx,cz in site['requested_chunks']:
                    r=reader.region(cx//32,cz//32)
                    if r is not None and all((cx,sy,cz)in r['index']for sy in range(-8,20)):
                        self.full_chunks[cx,cz]=index
    def state(self,x,y,z):
        index=self.full_chunks.get((x//16,z//16))
        if index is not None and -128<=y<=319:return self.readers[index].state(x,y,z)
        return self.context.state(x,y,z)
    def current(self,x,y,z):
        if (x//16,z//16)not in self.full_chunks or not -128<=y<=319:raise ValueError('Missing complete current source '+str((x,y,z)))
        return self.readers[self.full_chunks[x//16,z//16]].state(x,y,z)
    def box(self,bounds):
        result,palette=self.context.box(bounds);ids={s:i for i,s in enumerate(palette)}
        for reader in reversed(self.readers):
            values,names=reader.box(bounds);mapping=[]
            for name in names:
                if name not in ids:ids[name]=len(palette);palette.append(name)
                mapping.append(ids[name])
            known=values!=0;result[known]=np.asarray(mapping,np.uint16)[values[known]]
        return result,palette


def profile(z):
    if z<=100:return 72.
    if z<=114:return 72+(z-100)*.5
    if z<=118:return 79.
    if z<=132:return 79+(z-118)*.5
    if z<=136:return 86.
    if z<=150:return 86+(z-136)*.5
    return 93.


class Author:
    def __init__(self,sources,devices):self.s=sources;self.devices=devices;self.edits={};self.owners={};self.kept=Counter()
    def state(self,x,y,z):return self.edits.get((x,y,z),(None,self.s.state(x,y,z)))[1]
    def put(self,x,y,z,target,owner,preserve=False):
        p=x,y,z;old=self.s.current(*p)
        if self.state(*p)==target:return
        if p in self.devices:raise ValueError('Existing device in proposed change '+str(p))
        if old not in SOIL|AIR:
            if preserve:self.kept[old]+=1;return
            raise ValueError('Retained artificial object in proposed change '+str((p,old,target,owner)))
        self.edits[p]=(old,target);self.owners[p]=owner
    def clear(self,x,y,z,owner):
        old=self.state(x,y,z)
        if old in SOIL:self.put(x,y,z,'minecraft:air',owner)
    def surface(self,x,z):
        top=72
        for y in range(73,144):
            if self.s.state(x,y,z)in SOIL:top=y
        return top
    def paved_clear(self,x,z,kind,cap=None):
        floor=self.s.current(x,72,z)
        if floor not in PAVEMENT:return False
        limit=min(self.surface(x,z),cap-1)if cap else self.surface(x,z)
        for y in range(73,limit+1):self.clear(x,y,z,kind)
        return True
    def retaining(self,x,z,kind,limit=120):
        top=min(limit,self.surface(x,z))
        if top<73:return
        for y in range(70,top+1):
            self.put(x,y,z,STRUCT if y<=72 else WALL,kind,preserve=True)


def build(a):
    a.out.mkdir(exist_ok=False);(a.out/'source').mkdir();(a.out/'delta').mkdir()
    s=Sources(a.full_source,a.context)
    # Exclude the unrelated mountain chunk that shares one supplemental capture.
    request=json.loads(a.request.read_text('utf8'));wanted=set(map(tuple,request['combined_airfield_chunks']))
    missing=sorted(wanted-set(s.full_chunks))
    if missing:raise ValueError('Missing FULL-height chunks '+str(missing))
    devices={};actors={}
    for path in a.full_source:
        for tag in nbtlib.load(path/'devices.dat')['Devices']:
            p=tuple(int(tag[k])for k in('x','y','z'))
            if (p[0]//16,p[2]//16)in wanted:devices[p]=copy.deepcopy(tag)
        for tag in nbtlib.load(path/'actors.dat')['Actors']:
            p=list(map(float,tag['Pos']))
            if (math.floor(p[0])//16,math.floor(p[2])//16)in wanted:
                key=tuple(map(int,tag.get('UUID',[])))or(str(tag['id']),tuple(p));actors[key]=copy.deepcopy(tag)
    author=Author(s,devices)
    previous=json.loads((a.proposal/'proposed-edits.json').read_text('utf8'))
    for e in previous:
        p=tuple(e['pos']);old=s.current(*p)
        if old!=e['before']:raise ValueError('Current source differs from interior proposal '+str(p))
        if p in devices:raise ValueError('Interior proposal touches retained device')
        author.edits[p]=(old,e['after']);author.owners[p]='verified_interior_hanger_or_lining'
    paved=[];doors=[]
    # Existing south forecourt: its eastern strip is beneath the retained
    # ground-concourse canopy, rather than an open excavation through its roof.
    for x in range(458,492):
        for z in range(83,101):
            cap=79 if x>=489 else None
            if author.paved_clear(x,z,'south_original_forecourt',cap):paved.append([x,72,z])
    for x in range(376,446):
        for z in range(30,39):
            cap=79 if x>=437 else None
            if author.paved_clear(x,z,'north_original_forecourt',cap):paved.append([x,72,z])
    for x in range(662,671):
        for z in range(12,19):
            cap=79 if z>=17 else None
            if author.paved_clear(x,z,'boarding_original_forecourt',cap):paved.append([x,72,z])
    for name,points,top in [
        ('terminal_south_door',[(x,82)for x in range(470,475)],77),
        ('terminal_north_doors',[(x,38)for x in list(range(379,391))+list(range(398,404))],77),
        ('old_boarding_north_door',[(x,17)for x in range(663,669)],77),
    ]:
        for x,z in points:
            if s.current(x,72,z)not in PAVEMENT:raise ValueError('Missing retained doorway bearing '+str((x,z)))
            for y in range(73,top+1):author.clear(x,y,z,name)
            doors.append(dict(name=name,floor=[x,72,z],clearance=[x,73,z,x,top,z]))
    # Retaining skins stand on the existing paved formation or natural bearing.
    # The south stair portal and the north covered-gallery link stay open.
    boundaries=[(457,z,'south_west_retaining')for z in range(83,101)]
    boundaries += [(x,101,'south_bank_retaining')for x in range(458,489)if x not in (466,467,468)]
    boundaries += [(375,z,'north_west_retaining')for z in range(30,39)]
    boundaries += [(x,29,'north_bank_retaining')for x in range(375,437)]
    boundaries += [(446,z,'north_east_retaining')for z in range(30,39)]
    boundaries += [(661,z,'boarding_west_retaining')for z in range(12,18)]
    for x,z,kind in boundaries:author.retaining(x,z,kind)
    # The existing ground-hall canopy carries its retained bank. Its outer
    # face above the canopy is clad, without obstructing the open hall below.
    for z in range(83,101):
        for y in range(80,author.surface(489,z)+1):author.put(489,y,z,WALL,'south_canopy_bank_face',preserve=True)
    # Original northern apron edge stands on two retained concrete courses.
    for x in range(479,489):author.retaining(x,82,'south_apron_north_retaining')
    path=[];interior=[];walls=[];roofs=[]
    for z in range(100,176):
        floor=profile(z);block=math.ceil(floor);roof=block+5
        # An existing raised paving block at (466,94,174) stays in place.
        # The final three-wide landing passes to its east without narrowing.
        walk_xs=range(467,470) if z>=173 else range(466,470) if z==172 else range(466,469)
        for x in walk_xs:
            if z==100:
                if s.current(x,72,z)not in PAVEMENT:raise ValueError('Forecourt stair does not start on old pavement')
            else:
                for y in range(block-2,block):author.put(x,y,z,STRUCT,'street_stair_foundation',preserve=True)
                state=FLOOR if floor.is_integer() else 'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
                old=s.current(x,block,z)
                if old in PAVEMENT and floor.is_integer():pass
                else:author.put(x,block,z,state,'street_stair_tread')
            top=roof-1 if z<=164 else max(block+3,author.surface(x,z))
            for y in range(block+1,top+1):
                old=author.state(x,y,z)
                if old in SOIL:author.clear(x,y,z,'street_stair_body')
                elif old.split('[')[0]not in AIR and old!='minecraft:air':
                    raise ValueError('Foreign object in pedestrian body '+str((x,y,z,old)))
            interior.append(dict(x=x,z=z,floor=floor,feet=floor+1))
        if 101<=z<=164:
            for x in (465,469):
                for y in range(block-2,roof+1):author.put(x,y,z,STRUCT if y<block or y==roof else WALL,'street_underpass_wall',preserve=True)
                walls.append([x,block-2,z,x,roof,z])
            for x in range(466,469):author.put(x,roof,z,'minecraft:sea_lantern'if x==467 and z%8==0 else STRUCT,'street_underpass_roof',preserve=True)
            roofs.append([465,roof,z,469,roof,z])
        elif 165<=z<=174:
            # The west side joins an existing shop frontage. Do not erect a
            # new wall across its doorway; the uphill east edge retains soil.
            edge_x=470 if z>=172 else 469
            for y in range(block-2,max(block,author.surface(edge_x,z))+1):
                author.put(edge_x,y,z,STRUCT if y<block else WALL,'street_portal_east_retaining',preserve=True)
        path.append([467.5,floor+1,z+.5])
    # The front portal has a structural lintel at Y78. Clad the short bank
    # above it so the entrance presents a framed underpass, not raw soil.
    for x in range(466,469):
        for y in range(79,author.surface(x,101)+1):author.put(x,y,101,WALL,'street_underpass_portal_fascia',preserve=True)
    # Every exact change must be covered by a complete supplemental chunk.
    unexpected=sorted({(x//16,z//16)for x,y,z in author.edits}-wanted)
    if unexpected:raise ValueError('Additional capture needed '+str(unexpected))
    groups=defaultdict(list)
    for cx,cz in sorted(wanted):groups[cx//32,cz//32].append((cx,cz))
    for(rx,rz),coords in groups.items():
        palette=['minecraft:air'];ids={palette[0]:0};blocks=[]
        for cx,cz in coords:
            src=s.readers[s.full_chunks[cx,cz]];region=src.region(rx,rz);mapping=[]
            for name in region['names']:
                if name not in ids:ids[name]=len(palette);palette.append(name)
                mapping.append(ids[name])
            values=np.concatenate([region['blocks'][region['index'][cx,sy,cz]]for sy in range(-8,20)],axis=0)
            blocks.append(np.asarray(mapping,np.uint16)[values])
        np.savez_compressed(a.out/'source'/f'r.{rx}.{rz}.npz',coordinates=np.asarray(coords,np.int32),blocks=np.asarray(blocks,np.uint16),palette=np.asarray(palette))
    editor=Editor(a.out)
    for(x,y,z),(old,new)in author.edits.items():
        if editor.state(x,y,z,True)!=old:raise ValueError('Standard source export differs')
        editor.put(x,y,z,new)
    regions=editor.save();editor.regions.clear()
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](list(devices.values()))}).save(a.out/'captured-devices.dat',gzipped=True)
    nbtlib.File({'Actors':nbtlib.List[nbtlib.Compound](list(actors.values()))}).save(a.out/'captured-actors.dat',gzipped=True)
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([])}).save(a.out/'block-entities.dat',gzipped=True)
    bounds=[min(x for x,z in wanted)*16,min(z for x,z in wanted)*16,max(x for x,z in wanted)*16+15,max(z for x,z in wanted)*16+15]
    capture=dict(world=s.readers[0].report['world'],bounds_xz=bounds,measured_chunks=[list(p)for p in sorted(wanted)],
        source_files=[str(p.relative_to(a.out)).replace('\\','/')for p in sorted((a.out/'source').glob('*.npz'))],
        chunk_statuses={'full':len(wanted)},actors=[dict(id=str(t['id']),pos=list(map(float,t['Pos'])))for t in actors.values()],
        sparse_source_only=True,unlisted_chunks_not_captured=True,exact_station_sources=list(map(str,a.full_source)),world_written=False)
    save(a.out/'capture.json',capture)
    edit_rows=[dict(pos=list(p),before=v[0],after=v[1],owner=author.owners[p])for p,v in sorted(author.edits.items())]
    save(a.out/'exact-edits.json',edit_rows)
    save(a.out/'entry-design.json',dict(paved_columns=paved,doors=doors,street_path=path,interior_columns=interior,
        tunnel_walls=walls,tunnel_roofs=roofs,street_anchor=[467.5,94,175.5],underpass_top_max=98,
        preserved_railway_structure_y=[102,104],retained_non_natural_bearing=dict(author.kept),
        full_source_chunks=[list(p)for p in sorted(wanted)],interior_proposal=str(a.proposal)))
    manifest=dict(world=capture['world'],kind='measured-airfield-station-interior-and-entry-repair',bounds_xz=bounds,
        regions=regions,cells=sum(r['cells']for r in regions),changed_chunks=[list(p)for p in sorted({(x//16,z//16)for x,y,z in author.edits})],
        device_changes=0,actor_changes=0,native_changes=0,jar_changes=0,world_written=False,production_recipe_replay_pending=True,
        source_snapshots=list(map(str,a.full_source)),complete_station_acceptance=False)
    save(a.out/'manifest.json',manifest)
    save(a.out/'functional-check.json',dict(errors=['Independent saved-candidate entry verification pending'],world_written=False))
    print('Saved standard airport candidate',manifest['cells'],'cells,',len(manifest['changed_chunks']),'changed chunks; retained devices',len(devices),'actors',len(actors))


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--full-source',type=Path,action='append',required=True)
    for n in ('context','proposal','request','out'):p.add_argument('--'+n,type=Path,required=True)
    build(p.parse_args())
