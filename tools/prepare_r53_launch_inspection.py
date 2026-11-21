"""Measured architectural proposal for the three launch-bank inspection rooms.

This extends the two-lift personnel gallery with a sealed viewing interface at
each bank. It does not create a pedestrian crossing through active EVA lanes.
Only query_blocks-backed measurements supply existing block states.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import survey_r52_original_complex as survey
from query_blocks import AIR, iter_block_entities
from model_r53_facility import export, save_json

LO=(-53,-1031,10)
HI=(-29,-1024,378)
BANKS=((1,124),(2,76),(3,28))
WALL='projectseele:nerv_wall_panel'
FLOOR='projectseele:nerv_floor_panel'
EDGE='projectseele:nerv_machine_edge'
STRUCT='projectseele:nerv_structural_panel'
GLASS='minecraft:gray_stained_glass'
LIGHT='projectseele:nerv_strip_light[lit=true]'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',required=True,type=Path)
    args=ap.parse_args();base=args.base;world=base/'CANDIDATE'
    out=base/'launch-inspection-proposal';out.mkdir(exist_ok=True)
    survey.WORLD=world;before,palette=survey.measure(LO,HI)
    after=before.copy();owners={};walks=set()
    def put(x,y,z,state,owner):
        if state not in palette:palette.append(state)
        after[y-LO[1],z-LO[2],x-LO[0]]=palette.index(state)
        owners[x,y,z]=owner
    def box(a,b,state,owner):
        for x in range(a[0],b[0]+1):
            for y in range(a[1],b[1]+1):
                for z in range(a[2],b[2]+1):put(x,y,z,state,owner)
    for bank,z in BANKS:
        name=f'launch_bank_{bank}/sealed_inspection_room'
        box((-46,-1031,z-6),(-29,-1024,z+6),WALL,name)
        box((-45,-1030,z-5),(-30,-1025,z+5),'minecraft:air',name)
        box((-46,-1031,z-6),(-29,-1031,z+6),FLOOR,name)
        box((-46,-1030,z-2),(-46,-1027,z+2),'minecraft:air',name+'/gallery_port')
        box((-29,-1029,z-4),(-29,-1026,z+4),GLASS,name+'/sealed_window')
        for yy in (-1030,-1025):box((-29,yy,z-5),(-29,yy,z+5),EDGE,name+'/window_frame')
        for zz in (z-5,z+5):box((-29,-1029,zz),(-29,-1026,zz),STRUCT,name+'/window_jamb')
        for x in (-43,-36):
            for zz in (z-6,z+6):box((x,-1030,zz),(x,-1025,zz),STRUCT,name+'/wall_pilaster')
        for x in range(-43,-31):
            for zz in (z-3,z+3):put(x,-1024,zz,LIGHT,name+'/recessed_ceiling_light')
        for x in range(-45,-29):
            for zz in (z-5,z+5):put(x,-1031,zz,EDGE,name+'/floor_border')
        for x in range(-45,-29):
            for zz in range(z-5,z+6):walks.add((x,-1030,zz))
        for zz in range(z-2,z+3):walks.add((-46,-1030,zz))
    # Ceiling lighting stays above the existing four-block-high gallery.
    for z in range(14,371,8):
        for x in (-51,-48):put(x,-1026,z,LIGHT,'launch_gallery/recessed_ceiling_light')
    mask=before!=after
    tags=dict(iter_block_entities(world,survey.DIM,LO,HI))
    for x,y,z in tags:assert not mask[y-LO[1],z-LO[2],x-LO[0]],('Native device protected',(x,y,z))
    declared=set()
    def protect(value):
        if isinstance(value,dict):
            if 'position' in value and isinstance(value['position'],list) and len(value['position'])==3:
                declared.add(tuple(value['position']))
            for child in value.values():protect(child)
        elif isinstance(value,list):
            for child in value:protect(child)
    for name in ('ROOT_MECHANICAL_OWNER.json','ROOT_RUNTIME_DIRECTORY.json'):
        protect(json.loads((world/name).read_text('utf8')))
    for x,y,z in declared:
        if all(LO[k]<=q<=HI[k] for k,q in enumerate((x,y,z))):
            assert not mask[y-LO[1],z-LO[2],x-LO[0]],('Declared device/foundation protected',(x,y,z))
    # Below -960 the installed bank curves equal the measured original paths.
    core=np.zeros_like(mask)
    for rel in ('phased_routes/final68_measurement/combined/MEASURED_SOURCE.npz',
                'phased_routes/reverse_head_edges_measurement/MEASURED_SOURCE.npz'):
        with np.load(base.parent/'map_complete_20261013'/rel) as data:
            for i,key in enumerate(data['section_keys']):
                org=np.asarray(key)[[0,2,1]]*16
                a=np.maximum(LO,org);b=np.minimum(HI,org+15)
                if np.any(a>b):continue
                dst=tuple(slice(int(a[k]-LO[k]),int(b[k]-LO[k]+1)) for k in (1,2,0))
                src=tuple(slice(int(a[k]-org[k]),int(b[k]-org[k]+1)) for k in (1,2,0))
                core[dst]|=data['core'][i].reshape(16,16,16)[src]
    solid=~np.isin(after,[i for i,s in enumerate(palette) if s in AIR])
    overlap=np.argwhere(mask&solid&core)
    failed=[]
    for x,y,z in walks:
        if str(palette[after[y-1-LO[1],z-LO[2],x-LO[0]]]) not in (FLOOR,EDGE):failed.append((x,y,z,'floor'))
        if any(str(palette[after[yy-LO[1],z-LO[2],x-LO[0]]]) not in AIR for yy in (y,y+1,y+2)):failed.append((x,y,z,'headroom'))
    changes=[]
    for y,z,x in np.argwhere(mask):
        p=int(x+LO[0]),int(y+LO[1]),int(z+LO[2])
        changes.append(dict(pos=p,before=palette[int(before[y,z,x])],after=palette[int(after[y,z,x])],owner=owners[p]))
    report=dict(world_written=False,source_world=str(world),purpose='Three sealed launch-bank inspection rooms connected to both original main lifts',
                authority='User requested both main lifts reach the launch area and overall hangar/launch reconstruction',
                bank_interfaces=[dict(bank=b,centre_z=z,window_x=-29,personnel_feet_y=-1030,view='westmost EVA lane; no claim of a crossing through all three lanes') for b,z in BANKS],
                changed_cells=len(changes),walk_cells=len(walks),walk_failures=failed,
                new_solid_motion_core_overlap=overlap.tolist(),native_device_changes=0,
                runtime_native_geometry_and_visual_review_pending=True)
    save_json(out/'REVIEW.json',report);save_json(out/'EXACT_PROPOSAL.json',changes)
    np.savez_compressed(out/'PROPOSAL.npz',origin=LO,palette=palette,before=before,after=after,positive_edit_mask=mask,core=core)
    export(after,palette,LO,HI,out,'inspection_rooms',max_y=-1025)
    export(after[:,108:121,:],palette,(-53,-1031,118),(-29,-1024,130),out,'bank_one_room_detail',max_y=-1025)
    print(json.dumps({k:report[k] for k in ('world_written','changed_cells','walk_cells','walk_failures','new_solid_motion_core_overlap')}))


if __name__=='__main__':main()
