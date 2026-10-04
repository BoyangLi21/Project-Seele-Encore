"""Full-save vertical elevator and NERV door inventory, never an escalator audit.

Read-only source/instance catalogue. No live launch, no world apply, no geometry
permission from air; complete original native hardware SNBT is retained.
"""
from pathlib import Path
import argparse,hashlib,json
from collections import Counter
import numpy as np
from query_blocks import iter_matching_sections,iter_block_entities
from measure_world_r40 import MeasuredWorld,properties
from inspect_map_assets import region_chunks

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW'
OUT=ROOT/'artifacts/rebuild_r45/tv_lifts_doors_sol_followup'
DIM='projectseele:geofront'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,default=WORLD)
    ap.add_argument('--out',type=Path,default=OUT/'inventory_v3');a=ap.parse_args();assert not a.out.exists()
    stats={};cells={};chunks=set()
    # Palette prefilter receives registry Names without property brackets.
    traits=json.loads((a.world/'native_state_traits_r44.json').read_text('utf8'))
    door_names={r['block']for r in traits.values()if 'door'in r.get('runtime_class','').lower()}
    woods=('oak','spruce','birch','jungle','acacia','dark_oak','mangrove','cherry','bamboo','crimson','warped','iron')
    door_names.update('minecraft:'+wood+suffix for wood in woods for suffix in ('_door','_trapdoor'))
    door_names.add('projectseele:city_personnel_door')
    prefixes=('movingelevators:','projectseele:nerv_access_reader',*sorted(door_names))
    for cx,cz,sy,pal,indices in iter_matching_sections(a.world,DIM,prefixes,stats):
        selected=np.array([s.startswith(prefixes)for s in pal])[indices].reshape(16,16,16)
        for iy,iz,ix in np.argwhere(selected):
            q=(cx*16+int(ix),sy*16+int(iy),cz*16+int(iz));state=pal[int(indices[(iy*16+iz)*16+ix])]
            cells[q]=state;chunks.add((cx,cz))
    assert stats['complete']
    lo=tuple(min(q[i]for q in cells)for i in range(3));hi=tuple(max(q[i]for q in cells)for i in range(3))
    tags=dict(iter_block_entities(a.world,DIM,lo,hi,selected_chunks=chunks));hardware=[];doors=[];readers=[];hatches=[]
    for q,state in sorted(cells.items()):
        tag=tags.get(q);row=dict(pos=q,state=state,full_nbt=None if tag is None else tag.snbt())
        if state.startswith('movingelevators:'):hardware.append(row)
        elif state.startswith('projectseele:nerv_access_reader['):readers.append(row)
        elif 'trapdoor'in state:
            hatches.append(dict(**row,role='SERVICE_HATCH_OR_DECORATIVE_FIXTURE_REQUIRES_AUTHORED_USE',not_automatically_public_entrance=True))
        elif properties(state).get('half')=='lower':
            scope='NERV_HQ_UNDERGROUND'if -590<=q[1]<=-310 and -110<=q[0]<=345 and -310<=q[2]<=630 else 'OUTSIDE_NERV_HQ_OR_UNRESOLVED_OWNER'
            doors.append(dict(**row,scope=scope,upper_state=cells.get((q[0],q[1]+1,q[2])),native_verified=False))
    interfaces=json.loads((ROOT/'artifacts/rebuild_r45/transport_facilities_sol_high/facility_landings/lifts.json').read_text('utf8'))
    known={tuple(s['controller'])for l in interfaces for s in l['landings']}
    controllers=[r for r in hardware if r['state'].partition('[')[0]=='movingelevators:elevator_block']
    # Registry paths are pinned instance facts; BE ID is the second identity.
    controllers=[r for r in hardware if tags.get(tuple(r['pos'])) is not None
                 and str(tags[tuple(r['pos'])].get('id'))=='movingelevators:elevator_tile']
    unregistered=[r for r in controllers if tuple(r['pos'])not in known]
    managed=[]
    w=MeasuredWorld(a.world)
    for lift in interfaces:
        for stop in lift['landings']:w.around(stop['cabin_centre'],12)
    marker=json.loads((a.world/'.projectseele_command_sliding_doors_r01.json').read_text('utf8'))
    for door in marker['doors']:
        for q in door['aperture']+door['buttons']:w.around(q,2)
    w.load()
    for lift in interfaces:
        stops=[]
        for s in lift['landings']:
            q=tuple(s['controller']);tag=tags.get(q)
            label=None if tag is None else str(tag.get('data',{}).get('name',''))
            stops.append(dict(**s,actual_controller_state=w.block(q),actual_controller_nbt=None if tag is None else tag.snbt(),
                actual_native_label=label,actual_has_name=bool(tag and tag.get('data',{}).get('hasName',0)),
                fixed_call_state=w.block(s['outside_call']),native_interlock_and_rider_stability_verified=False))
        managed.append(dict(id=lift['id'],transport_kind='VERTICAL_NATIVE_CABIN_ELEVATOR',landings=stops))
    command=[]
    for d in marker['doors']:
        command.append(dict(**d,kind='NERV_COMMAND_PAIRED_SLIDING_DOOR',
            actual_aperture=[dict(pos=q,state=w.block(q))for q in d['aperture']],
            actual_fixed_inputs=[dict(pos=q,state=w.block(q))for q in d['buttons']],
            approved_core_layout_preserved=True,native_verified=False))
    entity_doors=[];entity_regions=0
    # Entity decoding stays in the existing shared Anvil reader; UUID/full NBT
    # are evidence only and never converted into replacement world objects.
    for region in sorted((a.world/'dimensions/projectseele/geofront/entities').glob('r.*.*.mca')):
        entity_regions+=1;_,rx,rz=region.stem.split('.');rx,rz=int(rx),int(rz)
        for cx,cz,chunk in region_chunks(region,(rx*32,rx*32+31,rz*32,rz*32+31)):
            for e in chunk.get('Entities',chunk.get('entities',[])):
                name=str(e.get('id',''))
                if name.startswith('projectseele:')and any(token in name for token in ('door','gate','hatch','lift')):
                    entity_doors.append(dict(id=name,uuid=[int(v)for v in e.get('UUID',[])],pos=[float(v)for v in e.get('Pos',[])],full_nbt=e.snbt()))
    a.out.mkdir(parents=True)
    for name,data in [('all_native_hardware',hardware),('all_ordinary_lower_doors',doors),('all_access_readers',readers),
                      ('all_vertical_elevators',managed),('all_command_sliding_doors',command),('unregistered_native_controllers',unregistered),
                      ('all_trapdoor_hatches',hatches),('all_persistent_door_gate_lift_entities',entity_doors)]:
        (a.out/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    report=dict(world=str(a.world.resolve()),dimension=DIM,full_save_palette_scan=stats,
        vertical_groups=len(managed),registered_landings=len(known),actual_native_controllers=len(controllers),
        unregistered_controllers=len(unregistered),native_hardware_cells=len(hardware),ordinary_door_leaves=len(doors),
        ordinary_scope_counts=dict(Counter(r['scope']for r in doors)),access_readers=len(readers),command_sliding_pairs=len(command),
        registry_door_name_denominator=sorted(door_names),trapdoor_hatch_cells=len(hatches),entity_regions_read=entity_regions,
        persistent_door_gate_lift_entities=len(entity_doors),
        escalators_and_moving_walks_used_as_vertical_references=False,world_written=False,native_verified=False,visual_reviewed=False,
        instance_ids_and_full_native_hardware_nbt_preserved=True)
    (a.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report))


if __name__=='__main__':main()
