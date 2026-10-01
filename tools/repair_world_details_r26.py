"""Measured R26 exterior, machinery, seating and walkway corrections."""
from pathlib import Path
import copy,json,math
import numpy as np
import regional_voxels as v,scan_regional_completion as scan,plan_factory_r20 as f,repair_facility_r21 as h
from query_blocks import read_box,iter_block_entities,AIR
from tv_crane_girder_design_r44 import running_state as crane_running_state_r44
ROOT=v.ROOT;WORLD=ROOT/'run/saves/SEELE_R26_REVIEW';OUT=ROOT/'artifacts/facility_r26/details'

def main():
    OUT.mkdir(parents=True,exist_ok=True);v.WORLD=scan.WORLD=WORLD;v.OUT=OUT;reports=[]
    def scene(lo,hi):f.LO=h.LO=lo;f.HI=h.HI=hi;return h.Facility()
    def apply(s,name):
        p=v.Painter();changed=s.before!=s.after
        if not changed.any():reports.append(dict(name=name,walk_nodes=s.walks));return
        for q,t in iter_block_entities(WORLD,v.DIM,h.LO,h.HI):
            if changed[q[1]-h.LO[1],q[2]-h.LO[2],q[0]-h.LO[0]]:
                assert str(t.get('id')) in ('minecraft:sign','minecraft:banner'),('Protected mechanism',name,q,str(t.get('id')))
        s.delta(p,'r26/'+name);p.meta.update(walk_nodes=s.walks,description=s.descriptions);p.apply(name);reports.append(dict(name=name,walk_nodes=s.walks))
    # One opaque perimeter around the launch plant. The only north-face
    # openings are the enclosed mechanical approach and enclosed upper gallery.
    s=scene((-32,-374,-86),(115,80,-16));panel='minecraft:black_concrete'
    for y in range(-370,80):
        for x in range(-31,115):
            s.fill((x,y,-17,x,y,-17),panel)
            mechanical=y<=-349 and any(abs(x-c)<=17 for c in (-12,30,72))
            observer=89<=x<=112 and -369<=y<=-364
            if not mechanical and not observer:s.fill((x,y,-55,x,y,-55),panel)
        for z in range(-54,-17):
            s.fill((-31,y,z,-31,y,z),panel);s.fill((114,y,z,114,y,z),panel)
    for x in range(-31,115):
        for z in range(-55,-16):
            if not any(abs(x-c)<=17 and -53<=z<=-19 for c in (-12,30,72)):
                s.fill((x,79,z,x,79,z),panel)
    # Close the named ceiling joint without lowering the observer's headroom.
    s.fill((89,-363,-57,99,-362,-48),f.STRUCT)
    s.path('shaft_observer_retained',[[103.5,-369,-70.5],[103.5,-369,-52.5],[93.5,-369,-52.5]])
    apply(s,'continuous_launch_plant_envelope')
    # Lower the exact old overhead runways by nine metres with the hoist.
    s=scene((-35,-378,-273),(96,-356,-212));moves=[]
    for cx in (-12,30,72):
        candidates={(x,y,z) for x in (cx-4,cx+4) for y in range(-363,-360) for z in range(-271,-213)}
        candidates|={(x,y,z) for z in (-271,-214) for x in range(cx-19,cx+20) for y in range(-363,-360)}
        for q in candidates:
            x,y,z=q;old=s.palette[s.before[y-h.LO[1],z-h.LO[2],x-h.LO[0]]]
            if old!=f.EDGE:continue
            # Transverse frames carry the observer floor and keep the9m
            # shift. Running beams must end atY-373 below the trolley,
            # not form another3m-high solid channel through its top chord.
            frame=z in (-271,-214)
            running=(x in (cx-4,cx+4) and -266<=z<=-216)
            target=(x,y-(9 if frame else 13),z)
            state=s.palette[s.before[target[1]-h.LO[1],z-h.LO[2],x-h.LO[0]]]
            assert state in AIR|{f.EDGE,f.STRUCT,'projectseele:clear_glass'},('Lower runway is obstructed',target,state)
            # Retain roof material when this old rail shared a ceiling seam.
            roof=y==-361 and any(s.palette[s.before[y-h.LO[1],Z-h.LO[2],X-h.LO[0]]]==f.STRUCT for X,Z in ((x-1,z),(x+1,z)) if h.LO[0]<=X<=h.HI[0])
            s.fill((*q,*q),f.STRUCT if roof else 'minecraft:air')
            if frame or running:s.fill((*target,*target),f.EDGE if frame else crane_running_state_r44(target[1],z))
            moves.append(q)
    apply(s,'lowered_crane_runways');reports[-1]['moved_cells']=len(moves)
    # Explicitly retire only the protruding ledge in front of the unchanged skin.
    s=scene((-72,-450,207),(-40,-435,234));removed=0
    for iy,iz,ix in np.argwhere(s.before!=s.state('minecraft:air')):
        x,y,z=int(ix+h.LO[0]),int(iy+h.LO[1]),int(iz+h.LO[2]);old=s.palette[s.before[iy,iz,ix]]
        radius=math.floor(120*(1-(y+466)/172)+.5)
        if z>=327-radius or old.startswith('projectseele:nerv_pyramid_'):continue
        if old.split('[')[0] not in {'minecraft:air','minecraft:black_concrete','minecraft:polished_blackstone','minecraft:polished_deepslate','minecraft:light_gray_concrete','projectseele:nerv_structural_panel','minecraft:light'}:continue
        s.fill((x,y,z,x,y,z),'minecraft:air');removed+=1
    apply(s,'retired_northwest_exterior_ledge');reports[-1]['removed_cells']=removed
    # The moving walk must stop before the intersecting lift lobby. Remove
    # the old cut-off stubs and leave a complete, level pedestrian junction.
    s=scene((-37,-397,-278),(-10,-387,-259));count=0
    for iy,iz,ix in np.argwhere(np.array([q.startswith('mtr:escalator_') for q in s.palette])[s.before]):
        x,y,z=int(ix+h.LO[0]),int(iy+h.LO[1]),int(iz+h.LO[2])
        if x<=-18:s.fill((x,y,z,x,y,z),f.FLOOR if y==-395 else 'minecraft:air');count+=1
    # Reopen a three-wide passage through both sides of the new lobby sleeve.
    for x in (-25,-21):s.fill((x,-394,-267,x,-392,-263),'minecraft:air')
    s.path('observation_lift_belt_junction',[[-30.5,-394,-265.5],[-14.5,-394,-265.5]])
    s.path('observation_lift_lobby_exit',[[-23.5,-394,-273.5],[-23.5,-394,-265.5],[-14.5,-394,-265.5]])
    apply(s,'clear_two_block_walkway_lift_crossing');reports[-1]['retired_belt_cells']=count
    # Complete chairs replace the old stool/banner/sign/backrest assemblies.
    s=scene((6,-445,262),(52,-388,365));source=s.before.copy();seats=[]
    for iy,iz,ix in np.argwhere(np.array(['stool[' in q for q in s.palette])[source]):
        x,y,z=int(ix+h.LO[0]),int(iy+h.LO[1]),int(iz+h.LO[2]);face='south'
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            q=(x+dx,y,z+dz);old=s.palette[source[y-h.LO[1],q[2]-h.LO[2],q[0]-h.LO[0]]]
            if 'command_seat_back' in old:
                face=old.split('facing=')[1].split(',')[0].split(']')[0]
                s.fill((*q,q[0],y+1,q[2]),'minecraft:air')
            elif old.startswith(('minecraft:bamboo_wall_sign','minecraft:jungle_wall_sign','minecraft:dark_oak_wall_sign')):s.fill((*q,*q),'minecraft:air')
        q=(x,y+1,z);old=s.palette[source[y+1-h.LO[1],z-h.LO[2],x-h.LO[0]]]
        if 'banner' in old:s.fill((*q,*q),'minecraft:air')
        s.fill((x,y,z,x,y,z),'projectseele:nerv_office_chair[facing='+face+']');seats.append([x,y,z])
    apply(s,'complete_command_room_seating');reports[-1]['seats']=seats
    (WORLD/'facility_chairs_r26.json').write_text(json.dumps(dict(installed=True,seats=seats)),encoding='utf8')
    (OUT/'contract.json').write_text(json.dumps(dict(changes=reports,walk_nodes=[q for r in reports for q in r['walk_nodes']]),ensure_ascii=False,indent=2),encoding='utf8')
    print('R26 details complete',[(r['name'],r.get('moved_cells',r.get('removed_cells',r.get('retired_belt_cells',len(r.get('seats',[])))))) for r in reports])
if __name__=='__main__':main()
