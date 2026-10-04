"""Measured TV-inspired vertical cabin/fixed-jamb candidates; no apply entry.

TV22 passenger walls and TV12 utility walls are separate observations. Original
dimensions, floors, roofs, moving door apertures, full hardware NBT, names and
permissions stay intact. R07 pressure doors are a different design class.
"""
from pathlib import Path
import argparse,gzip,json,hashlib
from collections import Counter
import nbtlib
from query_blocks import iter_block_entities
from measure_world_r40 import MeasuredWorld,properties

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW'
ART=ROOT/'artifacts/rebuild_r45/tv_lifts_doors_sol_followup'
DIM='projectseele:geofront'
NORMAL={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}
STYLES={(-368,750):('regional_gateway','tv12_large_utility'),
    (-26,-278):('r25-west-observation','tv22_staff'),
    (9,253):('s20-command-rear-x12-z253-v4','tv12_secure_service'),
    (31,321):('s23-commander-office-x28-z321-v1','tv22_command_suite'),
    (63,302):('r25-east-command-gallery','tv22_staff'),
    (96,-52):('s20-compact-cage-x93-z204-v4','tv12_hangar_utility'),
    (130,269):('s20-surface-transit-v2','tv12_surface_utility')}


def wall(style,height):
    if style=='tv22_command_suite':return 'minecraft:purple_terracotta'if height==1 else 'projectseele:nerv_wall_panel'
    if style=='tv22_staff':return 'minecraft:purple_terracotta'if height==1 else 'projectseele:nerv_wall_panel'
    return 'projectseele:nerv_structural_panel'if height==2 else 'projectseele:nerv_machine_panel'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,default=WORLD)
    ap.add_argument('--out',type=Path,default=ART/'shells_v1');a=ap.parse_args();assert not a.out.exists()
    lifts=json.loads((ART/'inventory_v2/all_vertical_elevators.json').read_text('utf8'))
    present=json.loads((ART/'all7_current_car_presence.json').read_text('utf8'));cars={r['lift']:r for r in present}
    w=MeasuredWorld(a.world)
    for lift in lifts:
        for stop in lift['landings']:w.around(stop['cabin_centre'],12)
    w.load();lo=tuple(min(q[i]*16 for q in w.selected)if i in(0,2)else -590 for i in range(3))if False else (-390,-590,-300)
    tags=dict(iter_block_entities(a.world,DIM,(-390,-590,-300),(160,100,780),selected_chunks=set(w.selected)))
    all_before={};changes={};protected=set();schemas=[];frames=[];cases=[]
    paintable={'minecraft:iron_block','projectseele:clear_glass','minecraft:light_gray_stained_glass',
        'projectseele:nerv_structural_panel','projectseele:nerv_machine_panel','projectseele:nerv_wall_panel',
        'minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:polished_deepslate'}
    def put(q,after,owner,reason):
        before=w.block(q)
        if q in protected or q in tags or before not in paintable or before==after:return
        if before is None:raise RuntimeError(('Unknown',q))
        changes[q]=dict(pos=list(q),before=before,after=after,before_nbt=None,after_nbt=None,owner=owner,reason=reason)
    for lift in lifts:
        car=cars[lift['id']];assert len(car['candidate_cars'])==1
        c=car['candidate_cars'][0];x,y,z=c['centre'];r,h=car['radius'],car['height'];key=tuple(lift['landings'][0]['controller'][i]for i in(0,2));runtime_id,style=STYLES[key]
        exits={s['exit']for s in lift['landings']};car_doors=set()
        if r==7:
            car_doors={(X,Y,743)for X in range(-363,-356)for Y in range(y,y+5)}
        else:
            for facing in exits:
                dx,dz=NORMAL[facing];lx,lz=-dz,dx
                car_doors.update((x+r*dx+k*lx,y+dy,z+r*dz+k*lz)for k in(-1,0,1)for dy in(0,1,2))
        protected.update(car_doors)
        for X in range(x-r,x+r+1):
            for Z in range(z-r,z+r+1):
                for Y in range(y-1,y+h-1):
                    q=(X,Y,Z);all_before[q]=dict(pos=list(q),state=w.block(q),full_nbt=None if q not in tags else tags[q].snbt())
                protected.update(((X,y-1,Z),(X,y+h-2,Z)))
        wall_holes=[]
        for X in range(x-r,x+r+1):
            for Z in range(z-r,z+r+1):
                if abs(X-x)!=r and abs(Z-z)!=r:continue
                for Y in range(y,y+h-2):
                    q=(X,Y,Z)
                    if q not in car_doors and w.block(q)in('minecraft:air','minecraft:void_air'):wall_holes.append(q)
                    if q not in car_doors:put(q,wall(style,Y-y),lift['id']+'/tv_cabin_non_door_wall','Original TV wall palette adapted to existing fixed-size native car; excludes moving doors, floor/roof and all devices')
        assert not wall_holes,('Do not paint an unclosed cabin as complete',lift['id'],wall_holes)
        for s in lift['landings']:
            cx,cy,cz=s['cabin_centre'];dx,dz=NORMAL[s['exit']];lx,lz=-dz,dx
            plane=tuple(s['door_plane']);radius=3 if key==(-368,750)else 2;height=5 if radius==3 else 3
            throat={(plane[0]+k*lx,cy+dy,plane[2]+k*lz)for k in range(-radius,radius+1)for dy in range(height)}
            protected.update(throat);protected.add(tuple(s['outside_call']))
            # Finite existing outer frame cells only; never extend into air.
            rim={(plane[0]+k*lx,cy+dy,plane[2]+k*lz)for k in(-(radius+1),radius+1)for dy in range(height+1)}
            rim.update((plane[0]+k*lx,cy+height,plane[2]+k*lz)for k in range(-radius-1,radius+2))
            for q in sorted(rim):put(q,'projectseele:nerv_structural_panel',lift['id']+'/fixed_landing_jamb','Existing solid fixed jamb remains outside car/door sweep; reusable industrial TV-inspired frame')
            frames.append(dict(lift=lift['id'],controller=s['controller'],label=s['actual_native_label'],plane=plane,
                fixed_call=s['outside_call'],fixed_call_state=w.block(s['outside_call']),input_on_moving_leaf=tuple(s['outside_call'])in throat,
                original_hardware_nbt=s['actual_controller_nbt'],frame_mask=[list(q)for q in sorted(rim)],
                protected_door_sweep=[list(q)for q in sorted(throat)],call_and_name_verified_live=False))
            cases.append(dict(lift=lift['id'],source_controller=s['controller'],outside_call=s['outside_call'],handoff=s['handoff'],
                destinations=[stop['controller']for stop in lift['landings']if stop['controller']!=s['controller']],
                stages=['closed complete cabin and all opposite unused door leaves','fixed outside call while cabin is absent','wait at actual supported lobby','real layer-door open only on actual car arrival',
                    'card authority and denied destination','enter car and native menu with human floor names','ride centre/corners/first tick/packet stall with two clients',
                    'arrive and naturally leave without falling','same-floor recall and return','occupied threshold hold and close','same JVM reload and cold reload','actual current-shader still photographs'],
                native_verified=False,visual_reviewed=False))
        schemas.append(dict(id=lift['id'],runtime_id=runtime_id,style=style,actual_car=c['centre'],size=[r*2+1,h,r*2+1],
            purpose='Large vertical utility access'if r==7 else 'Commander/reception suite'if key==(31,321)else 'Secure Dogma/service connection'if key==(9,253)else 'Vertical staff or hangar transfer',
            real_picture_source='TV22 passenger cabin'if style.startswith('tv22')else 'TV12 utility cabin',
            not_canonical_TV=['existing game dimensions','shaft/pit/drive design','game floor schedule','fixed controls and safety implementation'],
            original_car_door_cells=[list(q)for q in sorted(car_doors)],complete_closed_volume_condition='All non-door walls+complete floor+roof; native declared door leaves must physically close before capture',
            retained_full_hardware_nbt=True,leaf_and_ceiling_grille_high_detail_mesh_owner='root'))
    assert len(schemas)==7 and len(frames)==24 and not any(r['input_on_moving_leaf']for r in frames)
    assert not(set(changes)&protected)and not(set(changes)&set(tags))
    a.out.mkdir(parents=True)
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(a.out/(name+'.jsonl.gz'),'wt',encoding='utf8')as f:
            for q,row in sorted(changes.items()):
                item=dict(row)
                if inverse:item['before'],item['after']=row['after'],row['before']
                f.write(json.dumps(item,ensure_ascii=False,separators=(',',':'))+'\n')
    with gzip.open(a.out/'positive_edit_mask.jsonl.gz','wt',encoding='utf8')as f:
        for q in sorted(changes):f.write(json.dumps(list(q))+'\n')
    with gzip.open(a.out/'all7_complete_cabin_before.jsonl.gz','wt',encoding='utf8')as f:
        for row in all_before.values():f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
    metadata=dict(schema=45,dimension=DIM,styles={r['runtime_id']:r['style']for r in schemas},
        basis='Actually viewed TV22 passenger andTV12 utility cabin features; unseen drive mechanics are game adaptation',floor_repair_max_cells=1)
    for name,data in [('all7_cabin_types',schemas),('all24_fixed_layer_frames',frames),('all24_native_lifecycle_cases',cases),
        ('preserved_all_block_entities',[dict(pos=list(q),state=w.block(q),snbt=t.snbt())for q,t in tags.items()]),('.projectseele_tv_lifts_r45',metadata)]:
        (a.out/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    report=dict(world=str(a.world.resolve()),vertical_groups=7,layer_frames=24,changed_cells=len(changes),
        changed_by_owner=dict(Counter(r['owner']for r in changes.values())),all_car_floors_and_roofs_untouched=True,
        all_moving_door_cells_untouched=True,all_hardware_nbt_untouched=True,all_floors_names_and_permissions_retained=True,
        static_candidate_only=True,native_function_verified=False,visual_reviewed=False,world_written=False,
        root_model_specs='Door leaves retain current apertures; add TV22 thin wall-band and TV12 roof-grid/redlamp overlay within existing collision bounds. Unseen motor/cable/winch is engineering adaptation, not asserted TV evidence.')
    (a.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report))


if __name__=='__main__':main()
