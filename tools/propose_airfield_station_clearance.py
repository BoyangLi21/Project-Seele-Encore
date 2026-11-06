"""Propose natural-infill removal inside surviving NERV station interiors.

Reads the already captured sections only. Emits exact preconditioned changes;
does not author recipes, install a candidate, or open any real world file.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

import nbtlib
import numpy as np

from audit_hakone_station_walks import Walker
from map_pipeline.station_sections import StationSections
from review_underground_station_evidence import Overlay, strict_walk
from render_hakone_voxel_3d import render_arrays


NATURAL={'minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]'}
FLOORS={'projectseele:nerv_floor_panel','projectseele:period_station_floor'}
STRUCT='projectseele:nerv_structural_panel'


def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')


def run(a):
    a.out.mkdir(exist_ok=False);reader=StationSections(a.source)
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    snapshot=json.loads(a.native.read_text('utf8'))
    devices=nbtlib.load(a.source/'devices.dat')['Devices']
    device_positions={tuple(int(d[k]) for k in ('x','y','z')) for d in devices if all(k in d for k in ('x','y','z'))}
    changes={};columns=[];unowned=[]
    def owned_column(x,z,floor,ceiling,kind,need_roof=True):
        floorstate=reader.state(x,floor,z);roof=reader.state(x,ceiling,z) if need_roof else None
        doorway_bearing=kind=='concourse_doorway' and floorstate==STRUCT
        tactile_bearing=kind.endswith('train_platform') and floorstate=='projectseele:station_tactile_warning'
        gallery_belt=kind=='boarding_gallery' and (floorstate or '').startswith('mtr:escalator_step[') and 'orientation=flat' in floorstate
        stair_bearing=kind.startswith('stair') and (floorstate==STRUCT or (floorstate or '').startswith(('minecraft:smooth_quartz_stairs[','mtr:escalator_step[')))
        if floorstate not in FLOORS and not doorway_bearing and not tactile_bearing and not gallery_belt and not stair_bearing:
            unowned.append(dict(pos=[x,floor,z],state=floorstate,kind=kind,reason='no_surviving_floor'));return
        if need_roof and roof!=STRUCT and not (roof or '').startswith('projectseele:nerv_strip_light'):
            unowned.append(dict(pos=[x,ceiling,z],state=roof,kind=kind,reason='no_surviving_roof'));return
        before_count=len(changes)
        for y in range(floor+1,ceiling):
            state=reader.state(x,y,z)
            if state is None:raise ValueError('Unknown interior cell')
            if state in NATURAL:
                if (x,y,z) in device_positions:raise ValueError('Natural infill shares an existing device')
                changes[x,y,z]=(state,'minecraft:air')
        columns.append(dict(x=x,z=z,floor=floor,ceiling=ceiling,floor_state=floorstate,roof_state=roof,
                            kind=kind,roof_required=need_roof,removed_natural=len(changes)-before_count))
    # Bounds come from retained R21/R28 architecture, and each column must
    # independently retain its floor and roof before infill removal is proposed.
    for x,z,X,Z,floor,roof,kind in [
        (365,39,477,81,72,83,'terminal'),
        (435,18,669,28,72,79,'boarding_gallery'),
        (437,28,445,38,72,79,'terminal_gallery_link'),
        (490,73,506,155,72,79,'station_ground_concourse'),
        (477,71,506,79,72,79,'terminal_concourse_link'),
        (490,80,506,80,72,79,'concourse_doorway'),
        (495,105,667,121,104,111,'north_train_platform'),
        (495,135,667,151,104,111,'south_train_platform'),
    ]:
        for xx in range(x,X+1):
            for zz in range(z,Z+1):owned_column(xx,zz,floor,roof,kind)
    for basez in (108,138):
        for n in range(38):
            x=498+n;floor=72+max(0,min(32,n-1))
            for z in range(basez,basez+8):owned_column(x,z,floor,floor+5,'stair_'+str(basez))
    # This existing short outside boarding approach has a surveyed dedicated
    # NERV floor; it ends before the live aircraft stair mechanism.
    for x in range(668,671):
        for z in range(-2,24):owned_column(x,z,72,78,'aircraft_approach',False)
    supports=[]
    for z in (107,116):
        if reader.state(517,95,z)!=STRUCT or reader.state(517,102,z)!=STRUCT:raise ValueError('Missing measured hanger anchor')
        for y in range(96,102):
            before_state=reader.state(517,y,z)
            if before_state!='minecraft:air':raise ValueError('Hanger would overwrite a retained object')
            changes[517,y,z]=(before_state,'projectseele:nerv_machine_edge')
        supports.append(dict(kind='roof beam hanger',bottom_anchor=[517,95,z],top_anchor=[517,102,z],
                             added_bounds=[517,96,z,517,101,z],material='projectseele:nerv_machine_edge'))
    lining=[]
    # Replace only already-solid natural faces in the surviving gallery wall
    # frame. No current air opening, sign, glass or equipment is closed.
    for x,z in [(x,29)for x in range(435,670)]+[(670,z)for z in range(18,29)]:
        if reader.state(x,72,z)!=STRUCT or reader.state(x,79,z)!=STRUCT:continue
        for y in range(73,79):
            old=reader.state(x,y,z)
            if old in NATURAL:
                if (x,y,z) in device_positions:raise ValueError('Existing device in lining')
                changes[x,y,z]=(old,'projectseele:nerv_wall_panel')
                lining.append(dict(pos=[x,y,z],before=old,after='projectseele:nerv_wall_panel',kind='gallery perimeter lining',floor=[x,72,z],roof=[x,79,z]))
    # Finite earth-retaining skin along the existing open boarding pavement.
    # Same occupied cells as the soil, so it does not narrow the public path.
    for x,z in [(671,z)for z in range(14,24)]+[(667,z)for z in range(14,17)]:
        if reader.state(x,72,z)!='projectseele:nerv_floor_panel':continue
        for y in range(73,78):
            old=reader.state(x,y,z)
            if old in NATURAL:
                changes[x,y,z]=(old,'projectseele:nerv_wall_panel')
                lining.append(dict(pos=[x,y,z],before=old,after='projectseele:nerv_wall_panel',kind='outside boarding retaining skin',floor=[x,72,z],roof=None))
    before=Walker(a.source,shapes);after=Walker(a.source,shapes);after.reader=Overlay(after.reader,{p:v[1] for p,v in changes.items()})
    cases=json.loads((a.metadata/'quality_walk_cases.json').read_text('utf8'));history=[]
    for c in cases:
        if c.get('id','').startswith(('r21/airport/nerv_terminal_boarding','r28/nerv_airport/')):
            route=c.get('path')or[c.get('start'),c.get('end')]
            history.append(dict(id=c['id'],path=route,before=strict_walk(before,route),after=strict_walk(after,route)))
    # Dense, measured stair vertices avoid interpreting an old straight height
    # interpolation as the physical profile of a two-half-step staircase.
    transfers=[]
    for basez,platformz in ((108,124),(138,132)):
        start=[441.5,73,42.5]
        route=[start,[441.5,73,75.5],[496.5,73,75.5],[496.5,73,basez+3.5],[499.5,73,basez+3.5]]
        route += [[498+n+.5,73+max(0,min(32,n-1)),basez+3.5] for n in range(2,34)]
        route += [[537.5,105,basez+3.5],[537.5,105,118.5 if platformz==124 else 138.5],[585.5,105,118.5 if platformz==124 else 138.5]]
        transfers.append(dict(id='terminal_to_train_'+str(platformz),path=route,before=strict_walk(before,route),after=strict_walk(after,route),reverse_after=strict_walk(after,list(reversed(route)))))
    boarding=next(t['path'] for t in history if t['id']=='r21/airport/nerv_terminal_boarding')
    deck_journeys=[]
    for t,basez,platformz,aisle in zip(transfers,(108,138),(124,132),(120.5,135.5)):
        prefix=t['path'][:-2]
        for xx in range(520,651,10):
            route=prefix+[[537.5,105,aisle],[xx+.5,105,aisle]]
            full=list(reversed(route))+boarding[1:]
            deck_journeys.append(dict(id=f'train_{platformz}_{xx}_to_aircraft',path=full,
                after=strict_walk(after,full),reverse_after=strict_walk(after,list(reversed(full)))))
    bay=next(s for s in snapshot['stations'] if s['name']=='湾岸联络口')
    assigned=[p for p in snapshot['resolved_platforms'] if p.get('station_id')==str(bay['id'])]
    box=[460,77,452,564,109,492];arr,pal=reader.box(box);counts=Counter(map(int,arr.ravel()))
    bay_devices=[dict(pos=[int(d[k]) for k in ('x','y','z')],id=str(d['id'])) for d in devices if all(k in d for k in ('x','y','z')) and all(box[i]<=int(d[k])<=box[i+3] for i,k in enumerate(('x','y','z')))]
    bay_report=dict(native_station=bay,assigned_platforms=assigned,active_routes_via_assigned_platforms=[],devices=bay_devices,
        mtr_blocks=[dict(state=pal[i],count=int(n)) for i,n in counts.items() if pal[i].startswith('mtr:')],
        classification='retained_station_region_without_current_native_boarding',
        current_passenger_service_proved=False,nonpassenger_function_not_invented=True,
        disposition='retain native identity; resolve final public wayfinding purpose in station programme; do not count as an active stop')
    edits=[dict(pos=list(p),before=v[0],after=v[1]) for p,v in sorted(changes.items())]
    chunks=[list(p) for p in sorted({(e['pos'][0]//16,e['pos'][2]//16)for e in edits})]
    write(a.out/'proposed-edits.json',edits)
    write(a.out/'required-full-height-chunks.json',dict(chunks=chunks,y_min=-128,y_max=319,
        reason='standard surface candidate source; current station capture contains only station sections',
        current_source=str(a.source),capture_before_install_required=True))
    write(a.out/'bay-contact-role.json',bay_report)
    views=[]
    for name,bounds in [('airport-stair-infill',[488,70,106,539,112,116]),('airport-terminal-infill',[434,70,39,477,84,77])]:
        ar,pal=reader.box(bounds)
        views.append(render_arrays(bounds,a.out/(name+'-before.png'),'航空基地现状：自然地层侵入已存站房内部',ar,pal,ar!=0))
        patched=ar.copy();air=pal.index('minecraft:air')
        x,y,z,X,Y,Z=bounds
        for (xx,yy,zz),v in changes.items():
            if x<=xx<=X and y<=yy<=Y and z<=zz<=Z:
                if v[1] not in pal:pal.append(v[1])
                patched[yy-y,zz-z,xx-x]=pal.index(v[1])
        views.append(render_arrays(bounds,a.out/(name+'-proposal.png'),'航空基地候选：仅清除既存建筑内部自然回填',patched,pal,ar!=0))
    report=dict(source=str(a.source),native_snapshot=str(a.native),edits=len(edits),by_before_state=dict(Counter(e['before']for e in edits)),
        guarded_columns=columns,unowned_columns=unowned,historical_paths=history,current_transfers=transfers,supports=supports,lining=lining,
        deck_to_aircraft_journeys=deck_journeys,views=views,exact_changed_chunks=chunks,
        preserves_all_artificial_blocks=True,preserves_all_device_positions=True,world_read=False,world_written=False,
        installation_authorized_by_this_tool=False,native_vehicle_envelopes_not_yet_verified=True,
        complete_station_repair=False,remaining='Review failed measured walks; validate actors, roof/wall enclosure and current-world preconditions before any installation')
    write(a.out/'review.json',report)
    print('Airport infill proposal',len(edits),'changed cells;',len(unowned),'columns conservatively excluded')
    for t in transfers:print(t['id'],t['after']['kind'],t['reverse_after']['kind'])
    print('Train-to-aircraft directions',Counter(t[d]['kind'] for t in deck_journeys for d in ('after','reverse_after')))


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('source','metadata','native','out'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
