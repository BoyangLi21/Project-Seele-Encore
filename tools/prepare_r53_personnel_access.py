"""Exact, uninstalled proposal for the two original main lifts.

Preserves in-flight native cage data as well as stationary authored cars.
Coordinates are an architectural decision reviewed against the measured whole
facility, not permission inferred from empty blocks. No world writer exists in
this preparation stage: retirement and native motion clearance remain gates.
"""
from pathlib import Path
import argparse
import collections
import copy
import gzip
import json
import nbtlib
import numpy as np
from query_blocks import read_box, iter_block_entities, AIR
from facility_frame_nbt_r52 import block_entity_in_frame
from facility_frame_nbt_r52 import state_in_frame
from r52_spatial_plan import Frame
from survey_facility_target import role_of

DIM='projectseele:geofront'
STRUCT='projectseele:nerv_structural_panel'
WALL='projectseele:nerv_wall_panel'
FLOOR='projectseele:nerv_floor_panel'
VOID='minecraft:air'
MAIN='s20-command-rear-x12-z253-v4'
EAST='r25-east-command-gallery'
AXES={MAIN:(-42,253),EAST:(58,366)}
NEW_FLOORS={-1030:'发射区检修廊',-1014:'机库登机平台'}


def points(lo,hi):
    for y in range(lo[1],hi[1]+1):
        for z in range(lo[2],hi[2]+1):
            for x in range(lo[0],hi[0]+1):yield x,y,z


def write(path,value):
    text=json.dumps(value,ensure_ascii=False,indent=2)
    if path.suffix=='.gz':path.write_bytes(gzip.compress(text.encode('utf8'),mtime=0))
    else:path.write_text(text,'utf8')


class Proposal:
    def __init__(self,world):
        self.world=world;self.before={};self.tags={};self.after={};self.owners={}
        self.target_tags={};self.known_devices=set();self.holds=[];self.paths=[];self.walk_areas={}

    def read(self,lo,hi):
        self.before.update(read_box(self.world,DIM,lo,hi))
        self.tags.update(iter_block_entities(self.world,DIM,lo,hi))

    def put(self,p,state,owner):
        p=tuple(p);assert p in self.before,('Unmeasured cell',p)
        self.after[p]=state;self.owners[p]=owner

    def box(self,lo,hi,state,owner):
        for p in points(lo,hi):self.put(p,state,owner)

    def final(self,p):return self.after.get(tuple(p),self.before[tuple(p)])

    def hall(self,lo,hi,y,height,owner,ports=()):
        # A wide information face can project into this hall from an anchor
        # just outside its box. Measure that margin before composing walls.
        self.read((lo[0]-2,y-2,lo[1]-2),(hi[0]+2,y+height+2,hi[1]+2))
        self.box((lo[0],y-1,lo[1]),(hi[0],y+height,hi[1]),WALL,owner)
        self.box((lo[0],y-1,lo[1]),(hi[0],y-1,hi[1]),FLOOR,owner)
        self.box((lo[0]+1,y,lo[1]+1),(hi[0]-1,y+height-1,hi[1]-1),VOID,owner)
        for x,_,z in points((lo[0]+1,y,lo[1]+1),(hi[0]-1,y,hi[1]-1)):
            self.walk_areas[x,y,z]=(height,owner)
        for a,b in ports:
            self.box(a,b,VOID,owner+'/port')
            for x,_,z in points((a[0],y,a[2]),(b[0],y,b[2])):self.walk_areas[x,y,z]=(height,owner+'/port')

    def join_halls(self):
        # Compose hall unions once so a later wall cannot close an earlier
        # corridor at a T junction. Native door cells are restored afterwards.
        for (x,y,z),(height,owner) in self.walk_areas.items():
            self.put((x,y-1,z),FLOOR,owner+'/continuous_floor')
            for yy in range(y,y+height):self.put((x,yy,z),VOID,owner+'/continuous_clearance')
        for q,tag in self.tags.items():
            if q in self.after and str(tag['id'])=='projectseele:station_departure_board':
                self.put(q,self.before[q],'retained_existing_wayfinding')
        # Wide boards own their full 3x2 face, including cells outside their
        # block-entity anchor. Recess the ceiling above that existing face.
        roofs=set()
        for q,tag in list(self.tags.items()):
            state=self.before[q]
            if not state.startswith('projectseele:station_departure_board['):continue
            axis='facing=north' in state or 'facing=south' in state
            for width in (-1,0,1):
                for height in (0,1):
                    p=(q[0]+(width if axis else 0),q[1]+height,q[2]+(0 if axis else width))
                    if p!=q and p in self.after and self.after[p]!=self.before[p] and self.after[p] not in AIR:
                        self.put(p,self.before[p],'retained_full_information_face')
                        roofs.add((p[0],q[1]+2,p[2]))
        for p in roofs:
            if p not in self.before:self.read(p,p)
            if self.before[p] in AIR:self.put(p,WALL,'information_face_raised_lintel')

    def save(self,out):
        differences=[]
        for p,s in sorted(self.after.items()):
            old=self.before[p]
            if old==s:continue
            if p in self.tags and p not in self.known_devices:
                self.holds.append(dict(kind='unmoved_existing_device',pos=p,id=str(self.tags[p]['id'])))
            if any(v in old for v in ('stairs[','trapdoor[','wall_artwork','nerv_access_reader','rail[')):
                self.holds.append(dict(kind='authored_fixture_requires_review',pos=p,state=old,owner=self.owners[p]))
            differences.append(dict(pos=p,before=old,after=s,owner=self.owners[p],
                                    before_nbt=self.tags[p].snbt() if p in self.tags else None,
                                    after_nbt=self.target_tags[p].snbt() if p in self.target_tags else None))
        write(out/'EXACT_BLOCK_PROPOSAL.json.gz',differences)
        write(out/'DEVICE_PROPOSAL.json',[dict(pos=p,before_nbt=self.tags[p].snbt() if p in self.tags else None,
            after_nbt=t.snbt()) for p,t in self.target_tags.items()])
        return dict(changed_cells=len(differences),holds=self.holds,
                    owner_counts=dict(collections.Counter(row['owner'] for row in differences)))


class RetiredShafts:
    def __init__(self,base,c):
        historical=base.parent/'map_complete_20261013'
        with np.load(historical/'survey/original_hangar_transfer_launch.npz') as data:
            self.hangar={k:data[k] for k in ('origin','states','palette')}
        self.hangar_mask=np.load(historical/'hangar_component/owner_mask.npz')['move']
        with np.load(historical/'survey/terminal_complete.npz') as data:
            self.terminal={k:data[k] for k in ('origin','states','palette')}
        self.c=c;self.frame=Frame(180,60,-620,88)
        # Use the exact R26 inverse, not an older R25 backup: the latter
        # predates intervening room construction and would restore stone
        # cubes into the present public galleries.
        folder=base.parent/'facility_r26/core_lift/internal_lift_and_retired_exterior_shaft/applied_20260920_114412_647652/delta'
        self.east_before={}
        for cx in (3,4):
            for cz in (18,19):
                with np.load(folder/f'c.{cx}.{cz}.npz') as d:
                    minimum=int(d['minimum']);pal=d['palette']
                    for offset,old in zip(d['offsets'],d['before']):
                        y=minimum+int(offset)//256;z=cz*16+(int(offset)//16)%16;x=cx*16+int(offset)%16
                        if 63<=x<=69 and 299<=z<=306 and -464<=y<=-359:
                            self.east_before[x,y,z]=str(pal[old])

    def source(self,p):
        x,y,z=p
        source=(60-x,y+620,88-z)
        sx,sy,sz=np.asarray(source)-self.hangar['origin'];a=self.hangar['states']
        if 0<=sy<a.shape[0] and 0<=sz<a.shape[1] and 0<=sx<a.shape[2] and self.hangar_mask[sy,sz,sx]:
            state=str(self.hangar['palette'][a[sy,sz,sx]])
            assert not state.startswith('movingelevators:'),('Foreign original device',p)
            return state_in_frame(state,self.frame),'restore_complete_moved_hangar_surface'
        source=(x,y+664,z+7);sx,sy,sz=np.asarray(source)-self.terminal['origin'];a=self.terminal['states']
        if 0<=sy<a.shape[0] and 0<=sz<a.shape[1] and 0<=sx<a.shape[2]:
            state=str(self.terminal['palette'][a[sy,sz,sx]])
            # The one original short Terminal controller was explicitly
            # retired during complete-room migration, not a spare elevator.
            if state.startswith('movingelevators:'):state='minecraft:black_concrete'
            return state,'restore_terminal_architecture_without_retired_controller'
        return None

    def restore(self,p,identity):
        x,y,z=p
        if identity==EAST and -557<=y<=-452:
            if (x,y+93,z) in self.east_before:return self.east_before[x,y+93,z],'restore_exact_R26_shaft_inverse'
            current=self.c.before[p]
            if current.startswith('movingelevators:'):
                assert x==63,'Unrecorded original cage device needs a separate retirement proof'
                return STRUCT,'restore_original_controller_wall'
            return current,'retain_original_non_R26_architecture'
        result=self.source(p)
        if result:return result
        if identity==MAIN and -563<=y<=-497:
            # The old northern tower is retired as a whole. Its new public
            # access spine below defines the replacement floors and walls.
            # Restore the sloping outer skin only where both measured flanks
            # of the known pyramid face agree; no air-derived room inference.
            left=self.c.before.get((5,y,z));right=self.c.before.get((13,y,z))
            if left==right=='projectseele:nerv_pyramid_panel':return left,'restore_pyramid_skin'
            return VOID,'retire_original_main_tower_inside_pyramid'
        return ('minecraft:deepslate[axis=y]' if y<-672 else 'minecraft:stone'),'retire_buried_shaft_in_original_foundation'

    def retire(self,identity,old):
        c=self.c;sx,_,sz=old['floors'][0]['cabin'];ys=[f['cabin'][1] for f in old['floors']]
        lo=(sx-3,min(ys)-2,sz-3);hi=(sx+3,max(ys)+5,sz+4)
        c.read(lo,hi)
        if identity==MAIN:c.read((5,-563,250),(13,-497,257))
        for p in points(lo,hi):
            state,reason=self.restore(p,identity);c.put(p,state,identity+'/'+reason)
        for f in old['floors']:
            for call in f['calls']:
                c.put(call['position'],VOID,identity+'/retire_original_call')
        pieces=[((6,-988,257),(12,-983,287)),((9,-987,288),(11,-984,288))] if identity==MAIN else [((63,-988,306),(69,-984,306)),((64,-988,308),(65,-983,308))]
        for a,b in pieces:
            c.read(a,b)
            for p in points(a,b):
                result=self.source(p)
                assert result is not None,('Old added approach outside owned hangar',p)
                c.put(p,result[0],identity+'/retire_added_deep_approach')
        if identity==MAIN:
            # The original service bypass is still an active machine, and
            # its four wall brackets need independent floor-anchored posts
            # after the surrounding lift shaft is retired.
            for x in (6,12):
                for z,top in ((251,-1050),(255,-1051)):
                    assert c.final((x,top-4,z))=='projectseele:nerv_floor_panel'
                    for y in range(top-3,top+1):
                        assert c.before[x,y,z]==STRUCT
                        c.put((x,y,z),STRUCT,'service_bypass/retained_floor_anchored_post')


def translated_floor(old,axis):
    f=copy.deepcopy(old);dx=axis[0]-old['cabin'][0];dz=axis[1]-old['cabin'][2]
    def move(p):return [p[0]+dx,p[1],p[2]+dz]
    for key in ('cabin','controller'):f[key]=move(f[key])
    for key in ('landing_doors','cabin_doors'):
        for row in f[key]:row['pos']=move(row['pos'])
    # Both new lobbies have a south-facing call on the west landing jamb.
    x,y,z=f['cabin'];f['calls']=[dict(kind='vanilla_button',position=[x-3,y+1,z+5],
        state='minecraft:polished_blackstone_button[face=wall,facing=south,powered=false]',
        facing='south',target_controller=f['controller'])]
    assert not f.get('visual_door_uuid'),'Original visual door requires a typed entity move'
    return f


def new_floor(template,y,label):
    f=copy.deepcopy(template);dy=y-template['cabin'][1]
    for key in ('cabin','controller'):f[key][1]+=dy
    f['approach_y']+=dy;f['label']=label;f['restricted']=False
    for key in ('landing_doors','cabin_doors'):
        for row in f[key]:row['pos'][1]+=dy
    for call in f['calls']:
        call['position'][1]+=dy;call['target_controller'][1]+=dy
    return f


def remap_cage_controls(cage,refs):
    result=copy.deepcopy(cage);changed=0
    def walk(v):
        nonlocal changed
        if isinstance(v,nbtlib.Compound):
            if 'controllerX' in v:
                names=('controllerX','controllerY','controllerZ')
                old=tuple(int(v[k]) for k in names);assert old in refs,('Unmapped cage control',old)
                for k,n in zip(names,refs[old]):v[k]=type(v[k])(n)
                changed+=1
            for value in v.values():walk(value)
        elif isinstance(v,nbtlib.List):
            for value in v:walk(value)
    walk(result);return result,changed


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',type=Path,required=True)
    args=ap.parse_args();world=args.base/'CANDIDATE';out=args.base/'personnel-access-proposal';out.mkdir(exist_ok=True)
    c=Proposal(world);manifest=json.loads((world/'personnel_lifts_r52.json').read_text('utf8'))
    caps=nbtlib.load(world/'dimensions/projectseele/geofront/data/capabilities.dat')
    groups=caps['data']['movingelevators:elevator_groups'];before_groups=copy.deepcopy(groups)
    manifest_before=copy.deepcopy(manifest);manifest['ready']=False;native=[];retirement=RetiredShafts(args.base,c)
    for role_name,role in manifest['main_lifts'].items():
        lift=next(l for l in manifest['lifts'] if l['id']==role['lift_id']);old=copy.deepcopy(lift)
        identity=lift['id'];x,z=AXES[identity];sx,_,sz=old['floors'][0]['cabin'];dx,dz=x-sx,z-sz
        source_key=f'{old["floors"][0]["controller"][0]};{sz}';target_key=f'{x-3};{z}'
        assert target_key not in groups
        original=groups[source_key];group=copy.deepcopy(original);g=group['group']
        assert list(map(int,g['floors']))==[f['cabin'][1] for f in old['floors']]
        moving=bool(g['isMoving']);available=[int(y) for y,f in zip(g['floors'],g['floorData']) if bool(f['isCageAvailable'])]
        assert not available if moving else len(available)==1
        if moving:assert 'cage' in g and 'currentY' in g and 'targetY' in g
        source_template=next(f for f in old['floors'] if f['cabin'][1]==role['hangar_floor'])
        new=[translated_floor(f,(x,z)) for f in old['floors']]
        new += [translated_floor(new_floor(source_template,y,label),(x,z)) for y,label in NEW_FLOORS.items()]
        new.sort(key=lambda f:f['cabin'][1]);lift['floors']=new
        role['observation_floor']=role['hangar_floor'];role['hangar_floor']=-1014;role['launch_floor']=-1030
        role['shaft_translation']=[x-role['source_axis']['cabin'][0],z-role['source_axis']['cabin'][1]]
        refs={tuple(a['controller']):tuple(next(f for f in new if f['cabin'][1]==a['cabin'][1])['controller']) for a in old['floors']}
        ys=[f['cabin'][1] for f in new]
        c.read((x-3,min(ys)-2,z-3),(x+3,max(ys)+5,z+4))
        c.box((x-3,min(ys)-2,z-3),(x+3,max(ys)+5,z+3),STRUCT,identity+'/continuous_shaft')
        c.box((x-2,min(ys)-1,z-2),(x+2,max(ys)+4,z+2),VOID,identity+'/continuous_cage_sweep')
        # Keep the measured outer pyramid skin where the new shaft meets it.
        for p in points((x-3,min(ys)-2,z-3),(x+3,max(ys)+5,z+3)):
            if c.before[p]=='projectseele:nerv_pyramid_panel' and (p[0] in (x-3,x+3) or p[2] in (z-3,z+3) or p[1] in (min(ys)-2,max(ys)+5)):
                c.put(p,c.before[p],identity+'/retained_pyramid_skin')
        for f in old['floors']:
            p=tuple(f['controller']);c.read(p,p);assert p in c.tags
            c.known_devices.add(p)
            for call in f['calls']:
                q=tuple(call['position']);c.read(q,q);assert c.before[q]==call['state']
        retirement.retire(identity,old)
        frame=Frame(0,dx,0,dz)
        for f in new:
            y=f['cabin'][1]
            src=next((a for a in old['floors'] if a['cabin'][1]==y),source_template)
            source=tuple(src['controller']);dest=tuple(f['controller']);tag=copy.deepcopy(c.tags[source])
            for k,n in zip(('x','y','z'),dest):tag[k]=type(tag[k])(n)
            tag['data']['name']=nbtlib.String(f['label'])
            c.target_tags[dest]=tag;c.put(dest,c.before[source],identity+'/native_controller')
            c.read((x-3,y-1,z+4),(x+3,y+3,z+6))
            c.box((x-2,y-1,z+3),(x+2,y-1,z+5),FLOOR,identity+'/landing_threshold')
            c.box((x-2,y,z+3),(x+2,y+2,z+3),VOID,identity+'/landing_opening')
            for xx in (x-3,x+3):c.box((xx,y,z+4),(xx,y+2,z+4),STRUCT,identity+'/landing_jamb')
            c.box((x-3,y+3,z+4),(x+3,y+3,z+4),STRUCT,identity+'/landing_lintel')
            for door in f['landing_doors']:c.put(door['pos'],door['closed_state'],identity+'/landing_door')
            for call in f['calls']:c.put(call['position'],call['state'],identity+'/call')
        # Stationary authored cage stays the same collection of blocks/NBT.
        if not moving:
            y=available[0];lo=(sx-2,y-1,sz-2);hi=(sx+2,y+4,sz+2);c.read(lo,hi)
            for p in points(lo,hi):
                q=frame.block(p);c.put(q,c.before[p],identity+'/original_stationary_cage')
                if p in c.tags:
                    c.known_devices.add(p)
                    c.target_tags[q]=block_entity_in_frame(c.tags[p],frame,reference_positions=refs)
        group['pos']['x']=nbtlib.Int(x-3);group['pos']['z']=nbtlib.Int(z)
        floor_data={int(y):copy.deepcopy(f) for y,f in zip(g['floors'],g['floorData'])}
        template=copy.deepcopy(floor_data[role['observation_floor']])
        for y,label in NEW_FLOORS.items():
            row=copy.deepcopy(template);row['name']=nbtlib.String(label);row['isCageAvailable']=nbtlib.Byte(0);floor_data[y]=row
        g['floors']=nbtlib.IntArray(ys);g['floorData']=nbtlib.List[nbtlib.Compound]([floor_data[y] for y in ys])
        refs_changed=0
        if moving:g['cage'],refs_changed=remap_cage_controls(g['cage'],refs)
        # All movement progress and exact local cage geometry are unchanged.
        for k,v in original['group'].items():
            if k not in ('floors','floorData','cage'):assert g[k]==v,(identity,k)
        if moving:
            for k in ('blockStates','collisionBoxes','xSize','ySize','zSize'):assert g['cage'][k]==original['group']['cage'][k]
        del groups[source_key];groups[target_key]=group
        native.append(dict(lift_id=identity,source_key=source_key,target_key=target_key,
                           source_nbt=original.snbt(),target_nbt=group.snbt(),moving=moving,
                           preserved_current_y=float(g['currentY']) if moving else available[0],
                           cage_control_references_moved=refs_changed))
    # North public spine connects the original command-room ports without
    # altering their steps, furniture, artwork or room interior.
    main=manifest['main_lifts']['command_rear']
    for y in main['headquarters_floors']+[-1230]:
        height=2 if y in (-516,-512,-502) else 3
        end=1 if y==-502 else 8
        c.hall((-46,257),(end,261),y,height,MAIN+'/north_public_spine',
            [((-44,y,257),(-40,y+height-1,257)),((end,y,258),(end,y+height-1,259))])
        if y==-502:
            # The original quartz flight descends west-to-east at x5..8,
            # z258..260. Go around its north end through the retired lift
            # footprint instead of cutting its full stair width.
            c.hall((-3,250),(1,261),y,2,MAIN+'/original_stair_north_bypass',
                [((-2,y,250),(0,y+1,250)),((-3,y,258),(-3,y+1,260))])
            c.hall((-3,250),(14,255),y,2,MAIN+'/original_stair_north_bypass',
                [((-2,y,255),(0,y+1,255)),((10,y,255),(13,y+1,255))])
            c.hall((9,254),(14,261),y,2,MAIN+'/original_stair_east_handoff',
                [((10,y,254),(13,y+1,254)),((11,y,261),(13,y+1,261))])
            c.read((5,-503,258),(9,-499,260))
            for q in points((5,-503,258),(9,-499,260)):
                if 'smooth_quartz_stairs[' in c.before[q]:
                    c.put(q,c.before[q],MAIN+'/retained_original_quartz_stairs')
        c.read((9,y-1,258),(13,y+height,259))
        c.box((9,y-1,258),(13,y-1,259),FLOOR,MAIN+'/original_entry_handoff')
        c.box((9,y,258),(13,y+height-1,259),VOID,MAIN+'/original_entry_handoff')
        c.paths.append(dict(owner=MAIN,y=y,ends=[[-42,y,259],[12,y,260]],width=3,original_handoff_width=2,
            bands=[[-45,7,258,260],[8,13,258,259],[11,13,260,261]] if y!=-502 else None))
    # Short rear lobbies join the existing east public ring at each floor.
    east=manifest['main_lifts']['east_gallery']
    for y in east['headquarters_floors']:
        end=88 if y<=-541 else 76 if y<=-485 else 67
        c.hall((54,370),(end,375),y,3,EAST+'/rear_public_lobby',
            [((56,y,370),(60,y+2,370)),((end,y,371),(end,y+2,373))])
        # Existing signs belong to the ring. Retain their blocks and full NBT.
        for q,tag in c.tags.items():
            if q in c.after and str(tag['id'])=='projectseele:station_departure_board':
                c.put(q,c.before[q],EAST+'/retained_existing_sign')
        c.paths.append(dict(owner=EAST,y=y,ends=[[58,y,372],[end,y,372]],width=3))
    # Hangar entries use the retained west gallery and a rear boarding annex.
    for y in (-1014,-987):
        c.hall((-46,257),(-37,264),y,3,MAIN+'/west_hangar_lobby',
            [((-44,y,257),(-40,y+2,257)),((-44,y,264),(-39,y+2,264))])
        c.hall((49,370),(62,376),y,3,EAST+'/rear_hangar_lobby',
            [((56,y,370),(60,y+2,370)),((50,y,370),(53,y+2,370))])
        c.hall((49,357),(54,371),y,3,EAST+'/rear_boarding_link',
            [((50,y,357),(53,y+2,357)),((50,y,371),(53,y+2,371))])
        c.paths.extend([dict(owner=MAIN,y=y,ends=[[-42,y,259],[-42,y,265]],width=4),
                        dict(owner=EAST,y=y,ends=[[58,y,373],[51,y,373],[51,y,356]],width=4,
                             endpoint_step=.5 if y==-987 else 0)])
    # The launch floor is an enclosed personnel gallery outside the EVA lanes.
    y=-1030
    c.hall((-53,10),(-46,378),y,4,'launch/west_personnel_gallery',
        [((-51,y,377),(-47,y+3,377))])
    c.hall((-52,371),(62,378),y,4,'launch/rear_personnel_gallery',
        [((-51,y,371),(-47,y+3,371)),((56,y,371),(60,y+3,371))])
    c.hall((-47,257),(-38,264),y,3,MAIN+'/launch_lobby',
        [((-44,y,257),(-40,y+2,257)),((-47,y,259),(-47,y+2,262))])
    c.read((55,y-1,370),(61,y+4,371))
    c.box((56,y-1,370),(60,y-1,371),FLOOR,EAST+'/launch_threshold')
    c.box((56,y,371),(60,y+2,371),VOID,EAST+'/launch_threshold')
    c.join_halls()
    # Landing devices take precedence over architectural shell, including
    # the 3-high native doorway of the two closely spaced command floors.
    for lift in manifest['lifts']:
        if lift['id'] not in AXES:continue
        for f in lift['floors']:
            x,y,z=f['cabin']
            for row in f['landing_doors']:c.put(row['pos'],row['closed_state'],lift['id']+'/landing_door')
            for call in f['calls']:c.put(call['position'],call['state'],lift['id']+'/call')
    # No third lift or other native group/progress changes are allowed.
    touched={row['source_key'] for row in native}
    for key,g in before_groups.items():
        if key not in touched:assert groups[key]==g,('Unrelated group changed',key)
    report=c.save(out)
    report.update(world_written=False,ready=False,axes=AXES,native_progress_preserved=True,
        frozen_source='Original R53 server save; CANDIDATE contains only documented static repairs',
        pending=['Retire both old shafts and old entrances as complete components',
                 'Full mechanical sweep clearance for new architectural footprints',
                 'Full-width native walking and all lift calls including in-flight restart',
                 'Human boarding and all three launch inspection interfaces',
                 'Regenerate dependent wayfinding after installed routes pass',
                 'Actual game view acceptance'],
        lobby_paths=c.paths,whole_hall_walk_cells=[list(p) for p in sorted(c.walk_areas)])
    write(out/'personnel_lifts_PROPOSAL.json',manifest)
    write(out/'personnel_lifts_BEFORE.json',manifest_before)
    write(out/'NATIVE_GROUP_PROPOSAL.json',native)
    write(out/'REVIEW.json',report)
    print(json.dumps({k:report[k] for k in ('world_written','changed_cells','native_progress_preserved')},ensure_ascii=False))
    print('Review holds:',len(report['holds']),dict(collections.Counter(h['kind'] for h in report['holds'])))


if __name__=='__main__':main()
