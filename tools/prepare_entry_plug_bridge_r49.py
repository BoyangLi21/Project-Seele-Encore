"""Exact R49 retractable through-side bridge and real boarding stairs; no world writes."""
from pathlib import Path
import argparse,copy,gzip,json,math
from prepare_facilities_r48 import Author,DIM
from query_blocks import AIR
ROOT=Path(__file__).resolve().parents[1]
DECK='projectseele:entry_plug_bridge_deck';GUARD='projectseele:entry_plug_bridge_guard'
DIRS={'east':(1,0),'north':(0,-1),'south':(0,1),'west':(-1,0)}
LAYOUT='rear_crosswalk_19_21_through_sides_14_24_boarding_stairs_r49'
STAIR='minecraft:polished_andesite_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]'
HALF_STEP='minecraft:polished_andesite_slab[type=bottom,waterlogged=false]'
def panel(x,z):
    side=abs(x)
    return 19<=z<=21 and side<=16 or 14<=z<=24 and 3<=side<=6 or z in (14,15,23,24) and 3<=side<=16 or 16<=z<=18 and side==2
def flagstate(name,flags):return name+'['+','.join(k+'='+str(flags.get(k,False)).lower() for k in DIRS)+']'
def upper(x,z):return abs(x)==2 and 16<=z<=18
def room(v,q):
    x,y,z=q;d=5+42*v
    return d<=x<=d+2 and -395<=y<=-390 and -223<=z<=-217 or x==d-1 and y==-392 and z in(-219,-222)
SOLID={'projectseele:nerv_machine_panel','projectseele:nerv_machine_edge','minecraft:smooth_stone','projectseele:nerv_structural_panel','projectseele:nerv_shaft_panel','minecraft:iron_block','minecraft:sea_lantern','projectseele:nerv_strip_light','minecraft:polished_deepslate','projectseele:nerv_floor_panel',DECK}
def wanted(actual,cx,v,amount):
    cells={}
    def get(q):return cells.get(q,actual[q])
    def sturdy(q):
        s=get(q);name=s.split('[')[0]
        if name in AIR:return False
        assert name in SOLID or s in(STAIR,HALF_STEP),('Unknown source sturdy shape',q,s)
        return name in SOLID
    def known_guard(s):return s.split('[')[0] in AIR|{'minecraft:light','projectseele:nerv_edge_rail',GUARD}
    for x in range(-16,17):
        for z in range(14,25):
            q=cx+x,-395,-240+z
            cells[q]=flagstate(DECK,{}) if panel(x,z) and amount>=min(9,25-z) else 'minecraft:air'
    for x in(-2,2):
        for z in range(16,19):cells[cx+x,-394,-240+z]=(HALF_STEP if z==18 else STAIR if z==17 else flagstate(DECK,{})) if amount==9 else 'minecraft:air'
    for x in range(-19,20):
        for z in range(14,25):
            q=cx+x,-395,-240+z;at=q[0],-394,q[2]
            if room(v,at) or upper(x,z) and amount==9:continue
            old=actual[at]
            if not known_guard(old) and not upper(x,z):continue
            if not sturdy(q):cells[at]=old if old.startswith('minecraft:light[') else 'minecraft:air';continue
            flags={side:not sturdy((q[0]+dx,q[1],q[2]+dz)) for side,(dx,dz) in DIRS.items()}
            if q in cells:cells[q]=flagstate(DECK,flags)
            cells[at]=flagstate(GUARD,flags) if any(flags.values()) else old if old.startswith('minecraft:light[') else 'minecraft:air'
    for x in(-2,2):
        for z in range(16,19):
            q=cx+x,-394,-240+z;at=q[0],-393,q[2]
            flags=dict(west=True,east=True,north=z==16)
            cells[at]=flagstate(GUARD,flags) if amount==9 else 'minecraft:air'
            if amount==9 and z==16:cells[q]=flagstate(DECK,flags)
    return cells

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r49/bridge_topology');args=ap.parse_args()
    a=Author(args.world.resolve(),args.out.resolve());a.out.mkdir(parents=True,exist_ok=True)
    rooms=json.loads((a.world/'r47_pilot_restrooms.json').read_text('utf8'))['slots'];desired={};objects=[];all_states=[]
    for v,cx in enumerate((-12,30,72)):
        a.read((cx-21,-397,-229),(cx+21,-389,-214))
        for q,s in a.s.items():
            if cx-16<=q[0]<=cx+16 and q[1]==-395 and -226<=q[2]<=-216:
                assert q not in a.t and (s in AIR or s.startswith(DECK+'[')),('Original bridge floor source changed',q,s)
        next_=wanted(a.s,cx,v,9)
        for q,s in next_.items():
            assert q not in a.t,('Complete device NBT forbids bridge overwrite',q)
            desired[q]=(s,'R49 complete next through-side gallery, retractable boarding stair and full multi-height edge guard; original seat/goal/plug/crane retained',None)
        for amount in range(10):
            state=wanted(a.s,cx,v,amount)
            assert all(state[cx+x,-395,-240+z] in AIR for x in range(-16,17) for z in range(14,25)) if amount==0 else True
            if amount<9:
                assert all(state[cx+x,y,-240+z] in AIR or state[cx+x,y,-240+z].startswith(GUARD+'[') for x in(-2,2) for y in(-394,-393) for z in range(16,19))
            all_states.append(dict(variant=v,extension=amount,cells=[[list(q),s] for q,s in state.items()]))
        slot=next(s for s in rooms if s['variant']==v)
        objects.append(dict(variant=v,bed=[cx,-443,-240],original_pilot_uuid=slot['pilot_uuid'],original_goal=slot['goal'],original_stand=slot['stand'],
                            through_routes=[[[cx+sign*4+.5,-394,-225.5],[cx+sign*4+.5,-394,-215.5]] for sign in(-1,1)],
                            boarding_stairs=[dict(half_step=[cx+sign*2,-394,-222],stair=[cx+sign*2,-394,-223],landing=[cx+sign*2,-394,-224],half_step_feet_y=-393.5,upper_feet_y=-393) for sign in(-1,1)],
                            hatch_centre=[cx+.5,-392.8,-223.5],first_error=[cx+3,-395,-226],before_first_error='minecraft:air',
                            retraction_steps=10,all_new_civil_work_retracted_at_zero=True))
    a.emit('R49_through_side_bridge_and_stairs',desired,dict(bays=objects,user_reference='artifacts/rebuild_r48/references/user_entry_plug_bridge.jpg',old_short_branch_north_end_and_missing_floor_measured=True,old_goal_and_seat_and_restroom_NBT_retained=True,main_19_21_unbroken=True,central_well_abs_X_0_1_retained=True,original_crane_and_capsule_motion_identity_untouched=True,source_and_native_game_verified=False))
    contract=a.out/'R49_through_side_bridge_and_stairs/contract.json';data=json.loads(contract.read_text('utf8'));data['schema']='projectseele.r49.bridge-topology-candidate.v1';data['authorization']='User R49 both through galleries and real boarding stairs';contract.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    marker=json.loads((a.world/'r48_entry_plug_bridge.json').read_text('utf8'));new=copy.deepcopy(marker)
    new.update(layout=LAYOUT,topology_revision=49,through_side_x=[[-6,-3],[3,6]],through_side_z=[14,24],fixed_side_connections_z=[[14,15],[23,24]],
               stair_x=[-2,2],stair_z=17,half_step_z=18,stair_floor_y=-394,landing_z=[16],landing_feet_y=-393,all_stairs_retract_before_plug_motion=True,
               original_boarding_feet_y=-394,original_boarding_relative_xz=[2,19],native_game_verified=False)
    (a.out/'r48_entry_plug_bridge.json').write_text(json.dumps(new,ensure_ascii=False,indent=2),'utf8')
    (a.out/'metadata_patch.json').write_text(json.dumps(dict(schema=49,operations=[dict(relative_target='r48_entry_plug_bridge.json',before=marker,after=new)],world_written=False),ensure_ascii=False,indent=2),'utf8')
    with gzip.open(a.out/'full_extension_states.json.gz','wt',encoding='utf8') as f:json.dump(all_states,f)
    a.recipe();(a.out/'manifest.json').write_text(json.dumps(dict(schema=49,changed_cells=len(a.all),world=str(a.world),layout=LAYOUT,bays=objects,world_written=False,native_game_verified=False,source_recipe_migrated=True),ensure_ascii=False,indent=2),'utf8')
    print('R49 measured bridge candidate',len(a.all),'changed cells; 3 bays x10 full next geometry states; no world writes')
if __name__=='__main__':main()
