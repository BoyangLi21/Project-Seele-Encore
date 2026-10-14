"""Read-only exact follow-up lift candidates for the Root-owned R53 world.

Writes only a fresh .Codex directory. No apply option, map writer, invented
car, new native group, ready flag, actor rewrite or generation installation.
Depth and compact retirement are independent, disjoint capability subtrees.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path

import nbtlib

from build_two_main_lifts_complete import MAIN, EAST, OFFICE, closed_material
from facility_frame_nbt_r52 import block_entity_in_frame
from query_blocks import AIR, iter_block_entities, read_box
from r52_spatial_plan import Frame
from verify_main_r20 import entities

ROOT = Path(__file__).resolve().parents[1]
DIM = 'projectseele:geofront'
CAP = Path('dimensions/projectseele/geofront/data/capabilities.dat')
INTERNAL = 'r25-west-observation'
COMPACT = 's20-compact-cage-x93-z204-v4'
BE_TYPES = {'movingelevators:elevator_tile', 'movingelevators:button_tile', 'movingelevators:display_tile'}
SHIFT = -384


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf8')


def coord(tag):
    return tuple(int(tag[k]) for k in ('x', 'y', 'z'))


def points(lo, hi):
    for y in range(lo[1], hi[1] + 1):
        for z in range(lo[2], hi[2] + 1):
            for x in range(lo[0], hi[0] + 1):
                yield x, y, z


def valid_group(saved, expected, parked):
    group = saved['group']
    need(list(map(int, group['floors'])) == expected, 'Current native floors differ from authorized before')
    need(not bool(group['isMoving']), 'A moving native car requires explicit pose/progress migration')
    need(len(group['floorData']) == len(expected), 'Incomplete native floorData')
    need([y for y, d in zip(expected, group['floorData']) if bool(d['isCageAvailable'])] == [parked], 'Original unique parked car changed')
    need(all(int(group[k]) == v for k, v in {'cageSizeX':5, 'cageSizeY':6, 'cageSizeZ':5,
        'cageHeightOffset':-1, 'cageSideOffset':0, 'cageDepthOffset':0}.items()), 'Actual native car dimensions changed')


def group_change(key, identity, before, mapping, parked, parked_after, retired=(), label=None):
    after = copy.deepcopy(before)
    old = list(map(int, before['group']['floors']))
    rows = [(mapping[y], copy.deepcopy(data)) for y, data in zip(old, before['group']['floorData']) if y not in retired]
    rows.sort(key=lambda r:r[0])
    if retired:
        for y, data in rows:
            data['isCageAvailable'] = type(data['isCageAvailable'])(y == parked_after)
            if label and y == parked_after:
                data['name'] = type(data['name'])(label)
    after['group']['floors'] = nbtlib.IntArray([y for y, _ in rows])
    after['group']['floorData'] = nbtlib.List[nbtlib.Compound]([data for _, data in rows])
    for k in before['group']:
        if k not in {'floors', 'floorData'}:
            need(after['group'][k].snbt() == before['group'][k].snbt(), 'Native progress/config changed: ' + k)
    need(after['pos'].snbt() == before['pos'].snbt(), 'Native group identity/axis changed')
    need([y for y, d in rows if bool(d['isCageAvailable'])] == [parked_after], 'Unique original car lost')
    return dict(key=key, lift_id=identity, before_snbt=before.snbt(), after_snbt=after.snbt(),
        floor_mapping={str(k):v for k,v in mapping.items()}, retired_floors=list(retired),
        parked_before=parked, parked_after=parked_after, original_identity_preserved=True,
        original_progress_preserved=True, allowed_changes=['group.floors', 'group.floorData'] if retired else ['group.floors'])


def shift_floor(floor, dy):
    out = copy.deepcopy(floor)
    for field in ('cabin', 'controller'):
        out[field] = [floor[field][0], floor[field][1] + dy, floor[field][2]]
    out['approach_y'] += dy
    for source, call in zip(floor['calls'], out['calls']):
        for field in ('position', 'target_controller'):
            call[field] = [source[field][0], source[field][1] + dy, source[field][2]]
    for field in ('landing_doors', 'cabin_doors'):
        for door in out[field]:
            door['pos'][1] += dy
    return out


class Readback:
    def __init__(self, world):
        self.world = world
        self.cells = {}
        self.tags = {}

    def box(self, lo, hi):
        self.cells.update(read_box(self.world, DIM, lo, hi))
        self.tags.update(iter_block_entities(self.world, DIM, lo, hi))

    def state(self, p):
        p = tuple(p)
        need(p in self.cells, 'Missing measured source cell: ' + str(p))
        return self.cells[p]

    def native(self, p, kind):
        p = tuple(p)
        t = self.tags.get(p)
        need(t is not None and str(t['id']) == kind, 'Actual native device missing or foreign: ' + str(p))
        return t


def original_car(read, identity, x, z, parked, target_y, be_rows, refs):
    lo, hi = (x-2, parked-1, z-2), (x+2, parked+4, z+2)
    read.box(lo, hi)
    frame = Frame(0, 0, target_y-parked, 0)
    cells = [dict(source=p, target=frame.block(p), state=read.state(p)) for p in points(lo,hi)]
    need(len(cells) == 150, 'Complete 5x5x6 original car required, including interior air')
    native = [(p,t) for p,t in read.tags.items() if all(lo[k] <= p[k] <= hi[k] for k in range(3))]
    # The original east car has an additional retained display at +3. It was
    # present in the frozen/v7 complete car and is not disposable redundancy.
    expected = ['movingelevators:button_tile'] + ['movingelevators:display_tile'] * (2 if identity==EAST else 1)
    need(sorted(str(t['id']) for _,t in native) == expected, 'Original car has foreign/missing native devices')
    for p,t in native:
        after = block_entity_in_frame(t, frame, reference_positions=refs)
        be_rows.append(dict(lift_id=identity, role='original_car_device', source=p, target=coord(after),
            before_nbt=t.snbt(), after_nbt=after.snbt(), state=read.state(p),
            changed=p!=coord(after) or t.snbt()!=after.snbt(),
            action='move_original_once' if p!=coord(after) else 'update_native_reference_in_retained_original_car'))
    return dict(lift_id=identity, parked_before=parked, parked_after=target_y,
        source_box=[lo,hi], target_box=frame.box(lo,hi), cells=cells,
        current_native_devices=[dict(position=p,nbt=t.snbt()) for p,t in native],
        original_car_preserved=True, new_car_created=False)


def measured_binding(read, identity, saved, cabin, controller, exit_side, inside, floor_ys):
    x,z = cabin
    read.box((x-5,min(floor_ys)-2,z-7),(x+5,max(floor_ys)+5,z+7))
    lift = dict(id=identity,cabin=cabin,floors=floor_ys,exit=exit_side,cells=read.cells)
    landing_state = closed_material(lift,4,2)
    car_state = closed_material(lift,2,1)
    side = 'west' if controller[0] < x else 'east'
    facing = 'east' if side=='west' else 'west'
    binding = dict(id=identity,controller_side=side,controller_facing=facing,
        inside_button_offset=inside,inside_display_offset=[inside[0],inside[1]+1,inside[2]],floors=[])
    labels = {int(y):str(d['name']) for y,d in zip(saved['group']['floors'],saved['group']['floorData'])}
    for y in floor_ys:
        sign = 1 if exit_side=='south' else -1
        call = (x-3*sign,y+1,z+5*sign)
        state = read.state(call)
        need(state == f'minecraft:polished_blackstone_button[face=wall,facing={exit_side},powered=false]', 'Measured original call state differs: '+str(call))
        ctrl = [controller[0],y,controller[1]]
        read.native(ctrl,'movingelevators:elevator_tile')
        row = dict(label=labels[y],cabin=[x,y,z],exit=exit_side,approach_y=y,controller=ctrl,
            calls=[dict(kind='vanilla_button',position=list(call),state=state,facing=exit_side,target_controller=ctrl)],restricted=False)
        for name,distance,half,material in [('landing_doors',4,2,landing_state),('cabin_doors',2,1,car_state)]:
            row[name]=[dict(pos=[x+sx,y+dy,z+sign*distance],closed_state=material) for sx in range(-half,half+1) for dy in range(3)]
        binding['floors'].append(row)
    return binding


def device_interfaces(read, before_binding, after_binding):
    rows=[]
    for old,new in zip(before_binding['floors'],after_binding['floors']):
        if old['cabin'][1]==new['cabin'][1]:
            continue
        for role,source,target in [('controller',old['controller'],new['controller'])]+[
                ('outside_call',a['position'],b['position'])for a,b in zip(old['calls'],new['calls'])]+[
                (kind,a['pos'],b['pos'])for kind in('landing_doors','cabin_doors')for a,b in zip(old[kind],new[kind])]:
            rows.append(dict(lift_id=before_binding['id'],role=role,source=source,target=target,
                measured_source_state=read.state(source),target_state=read.state(source),
                remove_old_reference=True,geometry_apply_owner='Root single composed civil/component patch'))
    return rows


def build(world,out,kind,base_manifest):
    raw=(world/CAP).read_bytes()
    caps=nbtlib.File.parse(io.BytesIO(gzip.decompress(raw)))
    groups=caps['data']['movingelevators:elevator_groups']
    (out/'capabilities_before.dat').write_bytes(raw)
    read=Readback(world);be_rows=[];cars=[];ops=[];interfaces=[];retired=[]
    native_before={k:v.snbt()for k,v in groups.items()}
    if kind=='depth':
        specs=[('6;253',MAIN,[-846,-603,-541,-516,-512,-502],-541,(9,253)),
               ('63;302',EAST,[-603,-554,-541,-527,-513,-499,-485,-471,-457],-554,(66,302)),
               ('86;366',INTERNAL,[-704,-630,-603],-630,(89,366))]
        original=json.loads(base_manifest.read_text('utf8'));manifest=copy.deepcopy(original)
        need(manifest['epoch']==53 and manifest['ready']is False,'Use original reviewed epoch53 draft')
        need({r['id']for r in manifest['lifts']}=={MAIN,EAST,OFFICE},'Exact original three reviewed bindings required')
        before_bindings={r['id']:r for r in original['lifts']}
        before_bindings[INTERNAL]=measured_binding(read,INTERNAL,groups['86;366'],(89,366),(86,366),'south',[-2,1,0],[-704,-630,-603])
        for key,identity,ys,parked,cabin in specs:
            valid_group(groups[key],ys,parked)
            mapping={y:y+SHIFT if(identity==INTERNAL or y in(-846,-603))else y for y in ys}
            ops.append(group_change(key,identity,groups[key],mapping,parked,mapping[parked]))
            labels = {-1230:'终极教条层',-987:'机库上层观察廊'} if identity in(MAIN,EAST) else {}
            if labels:
                renamed_group=nbtlib.parse_nbt(ops[-1]['after_snbt'])
                for yy,data in zip(renamed_group['group']['floors'],renamed_group['group']['floorData']):
                    if int(yy)in labels:data['name']=type(data['name'])(labels[int(yy)])
                ops[-1]['after_snbt']=renamed_group.snbt()
                ops[-1]['allowed_changes'].append('group.floorData.name only at explicitly moved main stops')
            ctrl=tuple(map(int,key.split(';')))
            refs={(ctrl[0],y,ctrl[1]):(ctrl[0],new,ctrl[1])for y,new in mapping.items()}
            read.box((cabin[0]-5,min(ys)-2,cabin[1]-7),(cabin[0]+5,max(ys)+5,cabin[1]+7))
            for y,new in mapping.items():
                if y==new:continue
                p=(ctrl[0],y,ctrl[1]);before=read.native(p,'movingelevators:elevator_tile')
                after=block_entity_in_frame(before,Frame(0,0,new-y,0),reference_positions=refs)
                if new in labels:after['data']['name']=type(after['data']['name'])(labels[new])
                be_rows.append(dict(lift_id=identity,role='floor_controller',source=p,target=coord(after),before_nbt=before.snbt(),after_nbt=after.snbt(),state=read.state(p),changed=True,action='move_original_once'))
            cars.append(original_car(read,identity,*cabin,parked,mapping[parked],be_rows,refs))
            before=before_bindings[identity]
            need([f['cabin'][1]for f in before['floors']]==ys,'Reviewed binding/current group mismatch')
            after=copy.deepcopy(before);after['floors']=[shift_floor(f,mapping[f['cabin'][1]]-f['cabin'][1])for f in before['floors']]
            for floor in after['floors']:
                if floor['cabin'][1]in labels:floor['label']=labels[floor['cabin'][1]]
            interfaces+=device_interfaces(read,before,after)
            if identity==INTERNAL:manifest['lifts'].append(after)
            else:manifest['lifts'][next(i for i,r in enumerate(manifest['lifts'])if r['id']==identity)]=after
        valid_group(groups['31;321'],[-481,-457,-433],-481)
        refs={(31,y,321):(31,y,321)for y in(-481,-457,-433)}
        office_car=original_car(read,OFFICE,28,321,-481,-481,be_rows,refs);cars.append(office_car)
        for role in manifest['main_lifts'].values():
            role['hangar_floor']+=SHIFT
            if'terminal_floor'in role:role['terminal_floor']+=SHIFT
        need(manifest['office_access']==original['office_access'],'Office access changed')
        need(next(r for r in manifest['lifts']if r['id']==OFFICE)==next(r for r in original['lifts']if r['id']==OFFICE),'Original office binding changed')
        partial_bindings=manifest
        remaining=['Current retained compact and public surface lift entries must be merged explicitly before final ready; no legacy fallback',
            'Root extends both shaft solids and composes new hallways with the moved whole hangar/Terminal once',
            'Root retires old -603/-846 doors/calls/controllers and old hall cut-outs; do not keep dual stops',
            'Internal original native car/BE snapshot is a component-move interface, not permission to move that car twice']
    else:
        key='96;-52';identity=COMPACT;ys=[-468,-442,-394,-370];valid_group(groups[key],ys,-394)
        mapping={-468:-468,-442:-442,-394:-442,-370:-370}
        ops.append(group_change(key,identity,groups[key],mapping,-394,-442,retired=(-394,-370),label='原机库站接驳层'))
        before=measured_binding(read,identity,groups[key],(93,-52),(96,-52),'south',[2,1,0],[-468,-442])
        after=copy.deepcopy(before);after['floors'][1]['label']='原机库站接驳层'
        refs={(96,y,-52):(96,mapping[y],-52)for y in ys}
        cars.append(original_car(read,identity,93,-52,-394,-442,be_rows,refs))
        # This is not a reset: the exact original parked 150 cells move once.
        lo=(88,-470,-60);hi=(100,-363,-42);read.box(lo,hi)
        for y in(-394,-370):
            p=(96,y,-52);tag=read.native(p,'movingelevators:elevator_tile')
            be_rows.append(dict(lift_id=identity,role='retired_floor_controller',source=p,target=None,before_nbt=tag.snbt(),after_nbt=None,state=read.state(p),changed=True,action='remove_retired_original_endpoint'))
            # Upper source stop is NORTH-facing and approach is y+1; source
            # controller survives even where the old called door has gone.
            side='north'if y==-370 else'south';sign=-1 if side=='north'else 1
            q=(93-3*sign,y+1,-52+5*sign)
            members=[(q,'call')]+[((93+dx,y+dy,-52+4*sign),'landing_door')for dx in range(-2,3)for dy in range(3)]
            retired.append(dict(floor=y,exit=side,approach_y=y+1 if y==-370 else y,
                hardware=[dict(position=p,role=role,state=read.state(p),nbt=None if p not in read.tags else read.tags[p].snbt())for p,role in members],
                no_replacement_endpoint=True,whole_shaft_and_attached_hall_retirement='Root must use its full component ownership, not this hardware list as deletion mask'))
        p=(96,-442,-52);tag=read.native(p,'movingelevators:elevator_tile');renamed=copy.deepcopy(tag);renamed['data']['name']=nbtlib.String('原机库站接驳层')
        be_rows.append(dict(lift_id=identity,role='retained_station_controller_name',source=p,target=p,before_nbt=tag.snbt(),after_nbt=renamed.snbt(),state=read.state(p),changed=True,action='rename_retained_original_endpoint'))
        # The destination threshold must open only for this now-present car.
        leaves=[]
        for d in after['floors'][1]['landing_doors']:
            p=tuple(d['pos']);leaves.append(dict(position=p,before=read.state(p),after='minecraft:air',kind='landing_door'))
        interfaces.append(dict(lift_id=COMPACT,role='original_car_now_at_retained_station',landing_open_state=leaves,
            source_only_car_removal='Root civil retirement fills/removes old shaft; must not leave duplicate 150-cell cage',
            target_car='Complete original 150-cell snapshot contains original cabin-door current state'))
        partial_bindings=dict(schema='projectseele.r53.retained-lift-fragment.v1',ready=False,lifts=[after])
        remaining=['Root retires complete original -394/-370 shaft/hall/attached sign components, preserves all retained lower shaft cells',
            'Read actual target shaft/cabin/landing source before composing original car and station open landing',
            'Station remains existing live MTR station; tracks, schedules and entity progress must not change']
    # Entire actor inventory is inspected only for cargo within original cars.
    occupied=[]
    for entity_id,tag in entities(world).items():
        p=tuple(map(float,tag.get('Pos',[])))
        if len(p)!=3:continue
        for car in cars:
            lo,hi=car['source_box']
            if all(lo[k]<=p[k]<hi[k]+1 for k in range(3)):
                occupied.append(dict(lift_id=car['lift_id'],entity_uuid_words=list(map(int,entity_id)),nbt=tag.snbt()))
    need(not occupied,'Actual actor occupies a source car; explicit actor graph migration required')
    need((world/CAP).read_bytes()==raw,'Capabilities changed during read-only candidate preparation')
    # Read destinations, but never bless stone/air as construction permission.
    destination=[]
    for row in be_rows:
        if row['target']is None:continue
        q=tuple(row['target']);cells=read_box(world,DIM,q,q);tags=dict(iter_block_entities(world,DIM,q,q))
        destination.append(dict(position=q,measured_state=cells.get(q,'MISSING_OR_UNGENERATED'),measured_nbt=None if q not in tags else tags[q].snbt(),
            intended_nbt=row['after_nbt'],apply_requires_root_composition=True))
    changed={r['key']for r in ops}
    write(out/'NATIVE_GROUP_PATCH.json',dict(schema='projectseele.r53.exact-native-group-patch.v1',world=str(world),kind=kind,capabilities_sha256=sha(raw),
        operations=ops,unchanged_groups={k:sha(v.encode())for k,v in native_before.items()if k not in changed},
        disjoint_peer_candidate_allowed=True,full_caps_replacement_forbidden=True,world_written=False))
    write(out/'NATIVE_BE_PATCH.json',dict(operations=be_rows,destination_readback=destination,world_written=False))
    write(out/'ORIGINAL_CARS.json',dict(cars=cars,new_cars=0,deleted_original_cars=0,source_cars_occupied=occupied,world_written=False))
    write(out/'CIVIL_DEVICE_INTERFACE.json',dict(interfaces=interfaces,retired_landing_hardware=retired,not_a_world_patch=True))
    write(out/'personnel_lifts_CANDIDATE_NOT_INSTALLED.json',partial_bindings)
    write(out/'REPORT.json',dict(kind=kind,world=str(world),world_written=False,ready=False,native_verified=False,
        applied_prior_civil_receipt='D:/eva/artifacts/map_complete_20261013/two_main_lifts_complete/APPLIED.json',
        original_native_groups=len(groups),group_subtrees_changed=len(ops),native_be_changes=sum(r['changed']for r in be_rows),
        complete_car_voxels=sum(len(c['cells'])for c in cars),additional_main_lifts=0,original_office_preserved=True,
        remaining=remaining,source_script_sha256=sha(Path(__file__).read_bytes())))
    print(json.dumps(dict(kind=kind,world_written=False,groups=len(ops),native_be_changes=sum(r['changed']for r in be_rows),car_voxels=sum(len(c['cells'])for c in cars)),ensure_ascii=False))


def prepare_capability_merge(world,candidate):
    """Pure Root merge: return exact before/after bytes, never save a world.

    Rechecks every changed subtree, preserves all actual other native groups,
    allows the independent depth/compact candidate to have been applied first.
    Geometry, block entities, doors and the new directory must be composed and
    read back by Root before the result is installed; this grants no readiness.
    """
    world,candidate=Path(world).resolve(),Path(candidate).resolve()
    doc=json.loads((candidate/'NATIVE_GROUP_PATCH.json').read_text('utf8'))
    need(Path(doc['world']).resolve()==world,'Candidate belongs to another world')
    raw=(world/CAP).read_bytes()
    result=merge_capability_bytes(raw,doc)
    return dict(path=world/CAP,before=raw,**result)


def merge_capability_bytes(raw,doc):
    """Pure typed-byte merge used by Root and isolated regression checks."""
    caps=nbtlib.File.parse(io.BytesIO(gzip.decompress(raw)))
    groups=caps['data']['movingelevators:elevator_groups'];original={k:v.snbt()for k,v in groups.items()}
    for row in doc['operations']:
        need(row['key']in groups and groups[row['key']].snbt()==row['before_snbt'],'Changed group differs or this patch was already installed: '+row['key'])
    for row in doc['operations']:groups[row['key']]=nbtlib.parse_nbt(row['after_snbt'])
    changed={r['key']for r in doc['operations']}
    need(set(groups)==set(original),'Native groups were created or removed')
    need(all(groups[k].snbt()==v for k,v in original.items()if k not in changed),'Unrelated live group modified')
    stream=io.BytesIO();caps.write(stream)
    return dict(after=gzip.compress(stream.getvalue(),mtime=0),
        changed_groups=sorted(changed),preserved_other_group_hashes={k:sha(v.encode())for k,v in original.items()if k not in changed})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--kind',choices=['depth','compact'],required=True)
    p.add_argument('--base-manifest',type=Path,default=ROOT/'.Codex/map_complete_20261013/coordinate_lift_audit/civil_candidate_v7/personnel_lifts_CANDIDATE_NOT_INSTALLED.json')
    args=p.parse_args();out=args.out.resolve()
    need(out.is_relative_to((ROOT/'.Codex').resolve())and not out.exists(),'Fresh output inside this checkout .Codex required')
    out.mkdir(parents=True);build(args.world.resolve(),out,args.kind,args.base_manifest.resolve())


if __name__=='__main__':main()
