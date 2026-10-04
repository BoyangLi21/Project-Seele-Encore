"""Coherent rooms, galleries and stair connections in the existing NERV frame."""
import argparse,json
from dataclasses import replace
import regional_voxels as vox
from quality_structures import Builder,OUT,OLD,CASES,load,walk,flat
from regional_architecture import *
from query_blocks import iter_block_entities

def preserve_equipment(p):
    held=[]
    for pos,be in iter_block_entities(vox.WORLD,vox.DIM,(-430,-490,-65),(390,-430,820)):
        name=str(be['id'])
        if name not in ('minecraft:chest','minecraft:barrel') and name.startswith('minecraft:'):continue
        p.protect((*pos,*pos),'retained_equipment/'+name);held.append({'pos':pos,'snbt':be.snbt()})
    (OUT/'retained_underground_equipment.json').write_text(json.dumps(held,ensure_ascii=False,indent=2),encoding='utf-8')
    # Native lift bodies and controls are outside the new circulation footprint.
    p.protect((125,-449,265,137,-430,281),'public_native_lift')
    for rail in load(OLD/'transit2/track_samples.json'):
        if rail['mode']!='TRAIN':continue
        for x,y,z in {tuple(map(round,v)) for v in rail['points'][::2]}:
            if y<0:p.protect((x-1,y,z-1,x+1,y+5,z+1),'native_train_body')

class Network:
    def __init__(self,p):self.p=p;self.air=[];self.floors=[]
    def line(self,a,b,f,name,width=5,height=4,walls=True):
        before=len(self.p.ops);flat(self.p,a,b,f,width,height,name,walls)
        self.air.extend(o for o in self.p.ops[before:] if o.state==AIR)
        self.floors.extend(o for o in self.p.ops[before:] if o.box[1]==o.box[4]==f)
    def finish(self):
        # Junction openings are the union of deliberate corridors. No later
        # corridor end wall can seal a route that was already opened.
        for o in self.air:self.p.fill(*o.box,o.state,o.owner)
        for o in self.floors:self.p.fill(*o.box,o.state,o.owner)

def rooms(p):
    for f in (-462,-449):
        for side,x0,x1,programmes,exit_side in [
            ('west',-67,-34,[('医療室','MEDICAL'),('職員休憩室','QUARTERS'),('記録保管室','ARCHIVE'),('食堂','CAFETERIA')],'east'),
            ('east',94,127,[('作戦会議室','BRIEFING'),('解析作業室','ANALYSIS'),('通信審議室','SEELE LINK'),('補給準備室','SUPPLIES')],'west')]:
            for i,(label,purpose) in enumerate(programmes):
                z=263+i*32;end=117 if side=='east' and i==0 else x1;owner=f'hq/{side}/{f}/{i+1}'
                if side=='east' and i==0:p.fill(118,f+1,z,127,f+9,z+27,AIR,owner+'/retire_lift_overlap')
                q=Builder();furnished_room(q,(x0,end,z,z+27),f,owner,label,purpose,exit_side=exit_side)
                for o in q.ops:
                    if o.box[1]<f:continue
                    p.fill(*o.box,o.state,o.owner)
                p.block_entities.update(q.block_entities);p.meta['rooms'].extend(q.meta['rooms'])
                if side=='east' and i==0 and f==-449:
                    # Retained B-40 crosses above this room. A five-metre room
                    # and a separate deck preserve both usable volumes.
                    p.fill(x0,f+5,z,end,f+9,z+27,AIR,owner+'/ceiling_recession')
                    p.fill(x0,f+5,z,end,f+5,z+27,DARK,owner)
                    for xx in (99,111):p.fill(xx,f+5,z+5,xx+2,f+5,z+22,LIGHT,owner)
                # Recessed red datum and restrained ceiling panels.
                for zz in (z+1,z+26):p.fill(x0+1,f+4,zz,end-1,f+4,zz,RED,owner)

def build(p):
    preserve_equipment(p);rooms(p);net=Network(p)
    # Remove the former inline stairs; each gallery remains level end to end.
    for f in (-462,-449):
        for x in (-30,89):
            old_x=-29 if x==-30 else x
            p.fill(old_x-2,f+1,363,old_x+2,f+12,391,AIR,'hq/retire_inline_stairs')
            net.line((x,271),(x,399),f,f'hq/gallery/{x}/{f}',5,5)
        for i in range(4):
            z=276+i*32
            net.line((-37,z),(-30,z),f,f'hq/door/west/{i}/{f}',3,3,False)
            net.line((89,z),(97,z),f,f'hq/door/east/{i}/{f}',3,3,False)
    # Arrival hall is one uninterrupted floor, with both gallery mouths open.
    box_room(p,(-34,94,393,430),-462,11,'hq/arrival',WALL,'owned')
    for x in (-30,89):net.line((x,391),(x,425),-462,f'hq/lobby/{x}',5,5,False)
    net.line((-30,425),(89,425),-462,'hq/lobby/cross',7,5,False)
    net.line((30,475),(30,442),-467,'hq/station_approach',9,5)
    # Side alcoves leave the lower galleries independent of the stair flights.
    for side,b in [('west',(-27,-7,368,391)),('east',(65,85,368,391))]:
        box_room(p,b,-462,20,'hq/stair_alcove/'+side,WALL,'owned')
    net.line((-30,383),(-25,383),-462,'hq/west_stair_foot',5,5,False)
    net.line((89,383),(84,383),-462,'hq/east_stair_foot',5,5,False)
    net.line((-30,375),(-9,375),-449,'hq/west_upper_return',5,5,False)
    net.line((-9,375),(-9,383),-449,'hq/west_upper_landing',5,5,False)
    net.line((89,375),(68,375),-449,'hq/east_upper_return',5,5,False)
    net.line((68,375),(68,383),-449,'hq/east_upper_landing',5,5,False)
    net.line((-30,289),(-24,289),-449,'hq/retained_west_room',3,3,False)
    net.line((89,289),(80,289),-449,'hq/retained_east_room',3,3,False)
    # East transfer has a landing wholly north of the six-riser flight.
    net.line((89,271),(89,258),-449,'hq/east_transfer_approach',5,5)
    net.line((89,258),(112,258),-449,'hq/east_transfer_lower',5,5)
    net.line((112,258),(112,255),-449,'hq/east_transfer_turn',5,5)
    net.line((112,245),(123,245),-443,'hq/east_transfer_upper',5,4)
    net.line((123,247),(123,273),-443,'hq/public_lift_side_approach',3,4)
    # Retain the earlier B-40 transverse concourse above the reduced room roof.
    net.line((78,273),(123,273),-443,'hq/retained_B40_concourse',5,4)
    # Hangar connection enters the south platform door, away from its track.
    p.fill(113,-442,-24,143,-435,-20,AIR,'hangar/retire_old_T_junction')
    p.fill(113,-443,-24,143,-443,-20,AIR,'hangar/retire_disconnected_deck')
    net.line((118,245),(118,-14),-443,'hq/hangar_walkway',9,5)
    net.line((118,-14),(150,-14),-443,'hangar/turning_hall',9,5)
    net.line((150,-14),(150,-25),-443,'hangar/platform_approach',7,4)
    # Gateway access has a single continuous datum from the lift lobby.
    net.line((-360,726),(-309,726),-467,'nerv/arrival_spine',7,5,False)
    net.line((-309,726),(-309,774),-467,'nerv/arrival_platform_corridor',5,5)
    # Research access passes ABOVE the retained rail, then descends at the end.
    net.line((89,399),(196,399),-462,'science/hq_bridge',5,4)
    net.line((196,399),(196,404),-462,'science/hq_bridge_turn',5,4)
    net.line((196,407),(196,540),-461,'science/rail_overbridge',7,4)
    net.line((196,548),(196,552),-467,'science/stair_foot',5,4)
    net.line((196,552),(291,552),-467,'science/reception',5,4)
    net.line((291,552),(291,565),-467,'science/west_turn',5,4)
    net.line((291,565),(300,565),-467,'science/west_platform',5,4,False)
    net.line((320,565),(328,565),-467,'science/east_platform',5,4,False)
    net.line((328,447),(328,608),-467,'science/east_gallery',5,4)
    for z in (462,517,572):net.line((328,z),(337,z),-467,'science/lab_entry/'+str(z),3,3,False)
    net.line((275,552),(275,689),-467,'science/sigma_gallery',5,4)
    net.line((250,689),(275,689),-467,'science/sigma_return',5,4)
    net.line((250,681),(250,689),-467,'science/sigma_entrance',5,4,False)
    for z in (607,633,659):net.line((264,z),(275,z),-467,'science/cell_entry/'+str(z),3,3,False)
    net.line((259,100),(259,267),-467,'logistics/gallery',5,4)
    for z in (116,182,246):net.line((246,z),(259,z),-467,'logistics/door/'+str(z),3,3,False)
    net.line((259,180),(291,180),-467,'logistics/platform_corridor',5,4)
    net.finish()
    # Write flights after horizontal corridor clearing, then exact top caps.
    for x,head,end in [(-24,'east',-11),(83,'west',70)]:
        stairs(p,x,383,-462,13,head,'hq/side_flight',5,'owned')
        for i in range(13):
            xx=x+i*(1 if head=='east' else -1)
            for z in (380,386):p.fill(xx,-460+i,z,xx,-459+i,z,GLASS,'hq/stair_guard')
        walk('hq/side_flight/'+head,[x+(-.5 if head=='east' else 1.5),-461,383.5],[end+.5,-448,383.5])
    for a,b in [(-11,-7),(65,70)]:
        p.fill(a,-449,380,b,-449,386,FLOOR,'hq/side_stair_landing')
        p.fill(a,-448,381,b,-443,385,AIR,'hq/side_stair_landing')
    stairs(p,30,441,-467,5,'north','hq/arrival_stair',7,'owned')
    p.fill(26,-462,427,34,-462,436,FLOOR,'hq/arrival_top')
    p.fill(26,-461,427,34,-456,436,AIR,'hq/arrival_top')
    from regional_architecture import headquarters_arrival_stair_sides_r46
    headquarters_arrival_stair_sides_r46(p)
    walk('hq/arrival_stair',[30.5,-466,443.5],[30.5,-461,429.5])
    stairs(p,112,254,-449,6,'north','hq/public_transfer_stair',5,'owned')
    p.fill(109,-443,243,115,-443,248,FLOOR,'hq/public_transfer_top')
    p.fill(109,-442,243,115,-438,248,AIR,'hq/public_transfer_top')
    walk('hq/public_transfer_stair',[112.5,-448,255.5],[112.5,-442,247.5])
    stairs(p,196,405,-462,1,'south','science/bridge_riser',5,'owned')
    p.fill(193,-461,406,199,-461,408,FLOOR,'science/bridge_top')
    p.fill(193,-460,406,199,-457,408,AIR,'science/bridge_top')
    stairs(p,196,546,-467,6,'north','science/bridge_return_stair',5,'owned')
    p.fill(193,-461,538,199,-461,540,FLOOR,'science/return_top')
    p.fill(193,-460,538,199,-456,540,AIR,'science/return_top')
    walk('science/bridge_riser',[196.5,-461,403.5],[196.5,-460,408.5])
    walk('science/bridge_return_stair',[196.5,-466,548.5],[196.5,-460,539.5])
    # Moving steps occupy a side lane; the middle remains ordinary walking floor.
    for z in range(-10,242):
        for x,reverse in [(115,False),(120,True)]:
            for lane,side in [(0,'left'),(1,'right')]:p.put(x+lane,-443,z,'mtr:escalator_step[direction='+str(reverse).lower()+',facing=north,orientation=flat,side='+side+',status=true]','hq/moving_walk')
    for x in (-30,89):p.fill(x-2,-448,401,x+2,-447,401,GLASS,'hq/upper_end_guard')
    p.meta['route_authority']='Existing station datums, retained lift landings, named room doors; no inferred passages.'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    vox.OUT=OUT;p=Builder();build(p)
    (OUT/'walk_cases_circulation.json').write_text(json.dumps(CASES,ensure_ascii=False,indent=2),encoding='utf-8')
    p.apply('circulation_repair') if args.apply else p.save_plan('circulation_repair')

if __name__=='__main__':main()
