"""Read every actual R45 school/station door, fixture and boarding endpoint.

Complete object enumeration is not a native operation or artistic pass.
Only dedicated agent artifacts are written.
"""
from pathlib import Path
import argparse
import json
from collections import Counter

from measure_world_r40 import MeasuredWorld,properties
from query_blocks import iter_block_entities
from school_hakone_patch_r45 import ROOT,ART,sha


def main():
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,default=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW');p.add_argument('--lifecycle',type=Path,default=ART/'lifecycle_v2');a=p.parse_args()
    output=a.lifecycle/'object_inventory';assert not output.exists();output.mkdir()
    scoped=[]
    for label,bounds in [('school',[216,48,-790,314,102,-668]),('hakone',[-1560,90,610,-1396,151,770])]:
        w=MeasuredWorld(a.world);lo,hi=tuple(bounds[:3]),tuple(bounds[3:]);w.box(lo,hi);w.load()
        be={q:tag.snbt() for q,tag in iter_block_entities(a.world,'projectseele:geofront',lo,hi)}
        doors=[];devices=[]
        for (cx,sy,cz),(palette,ids) in w.tiles.items():
            wanted={i for i,s in enumerate(palette) if '_door[' in s and 'half=lower' in s or any(t in s for t in ['ticket_barrier','fence_gate','residential_chair','station_seat','water_cauldron','minecraft:ladder','period_fixture[','minecraft:barrel['])}
            for index,pid in enumerate(ids):
                if int(pid) not in wanted:continue
                q=(cx*16+(index&15),sy*16+(index>>8),cz*16+((index>>4)&15))
                if not all(lo[k]<=q[k]<=hi[k] for k in range(3)):continue
                st=palette[int(pid)];row=dict(id='r45/'+label+'/'+str(q[0])+'_'+str(q[1])+'_'+str(q[2]),position=list(q),actual_state=st,actual_full_NBT=be.get(q),native_operated=False)
                if '_door[' in st and 'half=lower' in st:
                    face=properties(st).get('facing');dx,dz={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}[face]
                    row.update(kind='actual_paired_door',upper_position=[q[0],q[1]+1,q[2]],actual_upper_state=w.get(q[0],q[1]+1,q[2]),front=[q[0]+.5+dx*1.5,q[1],q[2]+.5+dz*1.5],rear=[q[0]+.5-dx*1.5,q[1],q[2]+.5-dz*1.5],required=['native_use_open','whole_aperture_walk_both_directions','native_use_close','restore_exact_current_pair_state_NBT'])
                    doors.append(row)
                else:
                    props=properties(st);kind=props.get('kind',st.partition('[')[0].split(':')[1]);row.update(kind=kind,required=['actual_backing_and_full_model_collision','real_front_operation_or_reading_point','use_if_functional','save_reload_preservation']);devices.append(row)
        (output/(label+'_all_actual_doors.json')).write_text(json.dumps(doors,ensure_ascii=False,indent=2),'utf8')
        (output/(label+'_all_actual_devices.json')).write_text(json.dumps(devices,ensure_ascii=False,indent=2),'utf8')
        scoped.append(dict(facility=label,bounds=bounds,doors=len(doors),devices=len(devices),kinds=dict(Counter(d['kind'] for d in devices)),full_BE=len(be),native_verified=False))
    source=ART/'hakone_v5/boarding_interfaces.json';items=json.loads(source.read_text('utf8'));ports=[]
    for item in items:
        for i,q in enumerate(item['source']['all_actual_door_approaches']):
            ports.append(dict(id='r45/hakone/boarding/'+item['source_platform']+'/'+str(i),platform_id=item['source_platform'],station_id='6131386888082811228',ordinal=i,approach=q,source_complete_native_interface_sha256=sha(source),native_verified=False,required=['closed_APG_enclosure','matching_actual_train_door_arrival','APG_and_train_open_synchronization','actual_supported_boarding','train_departure_load_sync','destination_arrival_supported_exit','same_platform_return','save_cold_reload_preserved_identity']))
    assert len(ports)==368 and Counter(p['platform_id'] for p in ports)==Counter({'-3388587481325067738':104,'2113004979025593751':104,'3559976582378878399':80,'1700974792440530138':80})
    (output/'hakone_all_368_boarding_ports.json').write_text(json.dumps(ports,indent=2),'utf8')
    report=dict(world=str(a.world.resolve()),dimension='projectseele:geofront',actual_saved_world_scopes=scoped,boarding_platforms=4,boarding_ports=len(ports),new_tail_planned_not_assumed_installed=str((a.lifecycle/'school_tail/contract.json').resolve()),full_door_state_and_NBT_read_only=True,world_written=False,native_operations_verified=False,visual_passed=False)
    (output/'inventory.json').write_text(json.dumps(report,indent=2),'utf8')
    print('Whole actual inventories',[(s['facility'],s['doors'],s['devices'],s['full_BE']) for s in scoped],'boarding',len(ports),flush=True)


if __name__=='__main__':main()
