"""Measured R50 GeoFront airfield/receiver civil candidates; never writes world.

Ground, old stair ownership, whole head envelopes and original typed NBT are
read from the sole construction source. Root installs the combined candidates.
"""
from pathlib import Path
import argparse,copy,json,math,uuid
import nbtlib
from prepare_facilities_r48 import Author,DIM,FLOOR,FRAME
from prepare_battle_civil_r50 import complete_recipe
from query_blocks import AIR

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r50/underground_airport'
NAT=AIR|{'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:azure_bluet'}
EDGE=lambda side:'projectseele:nerv_edge_rail['+','.join(k+'='+str(k==side).lower()for k in('east','north','south','west'))+']'

def legacy_stair_floor(z):return -411-(z-16)//2

def receiver(a):
    a.read((-35,-486,6),(101,-342,137));d={};plans=[];crew=[]
    def put(p,state,why):
        assert p not in a.t,('Original NBT protected',p)
        old=a.s[p];name=old.split('[')[0]
        assert name in NAT or name in {'projectseele:nerv_structural_panel','projectseele:nerv_floor_panel','projectseele:nerv_edge_rail','minecraft:polished_blackstone_stairs'}or old==state,(p,old,state)
        d[p]=(state,why,None)
    # Remove the full original surface/foundation/guard of the superseded top
    # stair segment. Its actual original edge piers are explicitly reused by
    # the new transverse head beam; no unowned buried rock is excavated.
    for v,cx in enumerate((-12,30,72)):
        for z in range(17,34):
            oldf=legacy_stair_floor(z)
            for x in range(cx-17,cx+18):
                for y in range(oldf-2,oldf+2):
                    p=x,y,z
                    if a.s[p].split('[')[0]in {'projectseele:nerv_structural_panel','projectseele:nerv_floor_panel','projectseele:nerv_edge_rail','minecraft:polished_blackstone_stairs'}:
                        put(p,'minecraft:air','Complete retirement of the original upper stair tread/foundation/guard; new side entrance replaces its whole function')
        for x in range(cx-15,cx+16):
            for z in range(6,119):
                for y in(-412,-411):
                    state='minecraft:iron_block'if y==-411 and x in(cx-13,cx+13)else FLOOR if y==-411 else FRAME
                    put((x,y,z),state,'Complete 31-wide supported same-axis mechanical rail bed; two flush real steel running strips')
                for y in range(-410,-344):put((x,y,z),'minecraft:air','Full 65-high original EVA and receiving-frame headroom on the real mechanical axis')
        for x in range(cx-17,cx+18):
            for z in range(83,119):
                for y in(-412,-411):put((x,y,z),FLOOR if y==-411 else FRAME,'Complete35-wide final unload/pose-binding stance deck, continuous with the original same-axis rail')
                for y in range(-410,-344):put((x,y,z),'minecraft:air','Complete35-wide unload stance and original frozen EVA envelope')
        # Two-thick edge trusses stay outside the old lower stair full width.
        # Their X locations deliberately avoid the new side stair at Z17..34.
        for xx in(cx-20,cx+18):
            for x in(xx,xx+1):
                for z in range(38,120):
                    for y in(-420,-419,-414,-413):put((x,y,z),FRAME,'Continuous deep side truss outside retained lower stairs and six-high personnel envelope')
                    if (z-38)%8<2:
                        for y in range(-418,-414):put((x,y,z),FRAME,'Face-connected truss web joins lower and upper chords')
        for z in(48,80,118):
            # Full upper transverse bearing links both real outside piers.
            for x in range(cx-20,cx+20):
                for zz in(z,z+1):
                    for y in(-414,-413):put((x,y,zz),FRAME,'Real transverse load beam to the individually founded outside piers')
            for xx in(cx-20,cx+18):
                for x in(xx,xx+1):
                    for zz in(z,z+1):
                        top=max(y for y in range(-486,-425)if a.s[x,y,zz].split('[')[0]in {'minecraft:stone','minecraft:dirt','minecraft:grass_block'})
                        assert all(a.s[x,y,zz].split('[')[0]in NAT for y in range(top-2,-412)),('Pier crosses an existing stair/device',x,zz)
                        for y in range(top-2,-412):put((x,y,zz),FRAME,'Whole two-wide pier/footer founded three layers into actual measured natural soil; original lower stairs remain outside it')
        # The old Z20 side piers connect to the new deck without blocking the
        # shared external crew lane. Actual R48 source defines these columns.
        for x in range(cx-17,cx+18):
            for z in(20,21):
                for y in(-414,-413):put((x,y,z),FRAME,'Explicit head load beam reuses the original R48 measured side piers, not a floating rail platform')
        side=9 if v<2 else 93
        edge=cx+17 if v in(0,2)else cx-17
        for x in range(min(edge,side)-2,max(edge,side)+3):
            for z in range(12,15):
                for y in(-413,-412,-411):put((x,y,z),FLOOR if y==-411 else FRAME,'Full side crew entrance opens the original pad guard and joins the five-wide replacement top stair')
                for y in range(-410,-404):put((x,y,z),'minecraft:air','Whole6-high named crew entrance; no blocked original centre stair entrance')
        # Side-lane stair is shared by00/01 and separately installed for02.
        for z in range(15,35):
            floor=-411 if z<17 else legacy_stair_floor(z)
            for x in range(side-2,side+3):
                for y in range(floor-2,floor+1):
                    state='minecraft:polished_blackstone_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]'if y==floor and z>=17 and z%2 else FLOOR if y==floor else FRAME
                    put((x,y,z),state,'Complete five-wide explicit crew replacement stair, matching original lower stair rise')
                for y in range(floor+1,floor+7):put((x,y,z),'minecraft:air','Full six-high personnel headroom separate from the31-wide mechanical rail')
            for x,face in((side-3,'west'),(side+3,'east')):
                put((x,floor+1,z),EDGE(face),'Actual side-stair edge guard; full five-wide surface remains free')
        target=cx+14 if v in(0,2)else cx-14
        for x in range(min(side,target)-2,max(side,target)+3):
            for z in range(34,37):
                for y in(-422,-421,-420):put((x,y,z),FLOOR if y==-420 else FRAME,'Full transverse crew landing joins actual retained lower stair at Z34')
                for y in range(-419,-413):put((x,y,z),'minecraft:air','Six-high lower stair join passes beneath the real mechanical deck')
        path=[[edge+.5,-410,13.5],[side+.5,-410,15.5]]+[[side+.5,legacy_stair_floor(z)+1,z+.5]for z in range(17,35)]+[[target+.5,-419,35.5]]
        crew.append(dict(variant=v,width=5,clear_height=6,path=path,retained_lower_stairs=[[cx-17,-469,34],[cx+17,-420,128]],retired_upper_stairs=[[cx-17,-421,17],[cx+17,-410,33]]))
        plans.append(dict(variant=v,feet=[cx+.5,-410,100.5],yaw=180,plane_root=[cx+.5,-298,100.5],
            pad_feet=[cx+.5,-410,6.5],bed_feet=[cx+.5,-410,-35.5],rail_width=31,
            rail_bounds=[[cx-15,-414,6],[cx+15,-411,118]],stand_bounds=[[cx-17,-412,83],[cx+17,-411,118]],
            route=[[cx+.5,-410,z+.5]for z in range(100,5,-1)],receiver_node=f'receiver_{v}'))
    a.full_desired=d
    a.emit('UG02_three_rail_receivers_and_crews',d,dict(receivers=plans,crew_redirects=crew,original_runtime_identity_progress_and_door_motion_retained=True,
        head_beam_reuses_original_R48_piers=True,all_other_piers_measured_to_natural_soil=True,new_airport_scope='Root-authorized underground air reception'))
    (a.out/'receiver_layout.json').write_text(json.dumps(dict(receivers=plans,crew_redirects=crew),ensure_ascii=False,indent=2),'utf8')
    before=json.loads((a.world/'r48_underground_sortie.json').read_text('utf8'));after=copy.deepcopy(before)
    for row,redirect in zip(after['plans'],crew):
        row['stairs_bounds']=redirect['retained_lower_stairs'];row['crew_top_redirect_r50']=redirect
        row['original_upper_stairs_replaced_r50']=True
    return [dict(relative_target='r48_underground_sortie.json',before=before,after=after)]

def airport(a):
    a.read((-545,-488,-365),(-335,-429,-175))
    a.read((-356,-488,-196),(-144,-440,-184))
    a.read((-156,-488,-196),(-144,-440,141))
    a.read((-156,-488,121),(-22,-440,141))
    d={};roads={};trees=set()
    def put(p,state,why,tag=None):
        assert p not in a.t,('Existing device protected',p)
        old=a.s[p];name=old.split('[')[0]
        assert name in NAT or name.endswith(('_log','_leaves')) or old==state,(p,old,state)
        d[p]=state,why,tag
        if name.endswith(('_log','_leaves')):trees.add(p)
    def ground(x,z):
        return max(y for y in range(-488,-440)if a.s[x,y,z].startswith('minecraft:grass_block'))
    # A limited engineered apron with twelve-metre smooth soil shoulders.
    for x in range(-542,-337):
        for z in range(-362,-177):
            old=ground(x,z);dist=math.hypot(max(-530-x,x+350,0),max(-350-z,z+190,0))
            if dist>12:continue
            t=min(1.,dist/12);t=t*t*(3-2*t)
            top=round(-476*(1-t)+old*t);hard=-530<=x<=-350 and -350<=z<=-190
            for y in range(min(top,old)-4,max(top,old)+1):
                state='minecraft:gray_concrete'if hard and y==top else 'minecraft:grass_block[snowy=false]'if y==top else'minecraft:dirt'if y>=top-3 else'minecraft:stone'
                if y>top:state='minecraft:air'
                put((x,y,z),state,'Finite real apron/graded soil shoulder on measured bare natural ground; no whole-cavern reshape')
            if hard:
                for y in range(top+1,-428):put((x,y,z),'minecraft:air','Full empty heavy-aircraft fixed-yaw park/takeoff body envelope; office is a separate explicit component')
    # Existing R48 grass handoff is the road endpoint. Follow actual native
    # ground along the west detour; never cut through the wet bays/railway.
    points=[(-350,-190),(-150,-190),(-150,131),(-30,131)]
    route=[];floor_last=None
    for start,end in zip(points,points[1:]):
        n=max(abs(end[0]-start[0]),abs(end[1]-start[1]))
        for i in range(n+1):
            x=round(start[0]+(end[0]-start[0])*i/max(1,n));z=round(start[1]+(end[1]-start[1])*i/max(1,n))
            top=ground(x,z)
            if floor_last is not None:top=max(floor_last-1,min(floor_last+1,top))
            if x==-350 and z==-190:top=-476
            if x==-30 and z==131:top=-467
            floor_last=top;route.append([x+.5,top+1,z+.5])
            for X in range(x-2,x+3):
                for Z in range(z-2,z+3):roads[X,Z]=top
    for (x,z),top in roads.items():
        old=ground(x,z)
        for y in range(min(old,top)-3,max(old,top)+1):
            put((x,y,z),'minecraft:air'if y>top else 'minecraft:smooth_stone'if y==top else'minecraft:stone','Whole five-wide supported staff access follows actual ground and reaches the original handoff')
        for y in range(top+1,top+7):put((x,y,z),'minecraft:air','Six-high staff access, existing lower stairs and their protected route retained')
    # Explicit control post outside the plane's fixed-yaw139-wide body.
    for x in range(-365,-356):
        for z in range(-302,-291):
            for y in range(-478,-468):
                wall=x in(-365,-357)or z in(-302,-292)
                state=FRAME if y in(-478,-477,-469)else FLOOR if y==-476 else 'projectseele:nerv_wall_panel'if wall else'minecraft:air'
                if wall and y in(-473,-472)and z not in(-302,-292):state='projectseele:clear_glass'
                put((x,y,z),state,'Complete supported transport-duty room: walls, roof, windows and real personnel clearance')
    for y,half in((-475,'lower'),(-474,'upper')):
        put((-361,y,-292),f'projectseele:city_personnel_door[facing=south,half={half},hinge=right,open=false,powered=false]','Actual manual duty-room door, opens onto the separate apron service lane')
    for x in range(-363,-358):
        put((x,-475,-300),'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]','Actual duty desk; aviation dispatch uses the existing O radio interface')
    sign=(-360,-473,-291)
    text=['地下运输机组','待命／回收登记','驾驶通信 O','发射仓后门接应']
    tag=nbtlib.Compound({'id':nbtlib.String('minecraft:sign'),'x':nbtlib.Int(sign[0]),'y':nbtlib.Int(sign[1]),'z':nbtlib.Int(sign[2]),'is_waxed':nbtlib.Byte(1)})
    for face in('front_text','back_text'):
        tag[face]=nbtlib.Compound({'messages':nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps({'text':s},ensure_ascii=False))for s in text]),'color':nbtlib.String('black'),'has_glowing_text':nbtlib.Byte(0)})
    put(sign,'minecraft:oak_wall_sign[facing=south,waterlogged=false]','Full native sign BE with actual room-wall backing; no dead aircraft command button',tag)
    for x,z in [(-524,-344),(-524,-196),(-356,-344),(-356,-196)]:
        for y in range(-475,-466):put((x,y,z),FRAME,'Actual perimeter light mast outside parked wing/body geometry')
        put((x,-466,z),'minecraft:sea_lantern','Actual airfield perimeter light')
    # Whole botanical members touched by the new access road retire. Read halo
    # is explicit; crossing it fails rather than leaving a floating tree.
    done=set();tree_components=[]
    for seed in sorted(trees):
        if seed in done:continue
        todo=[seed];component=set()
        while todo:
            q=todo.pop()
            if q in done:continue
            assert q in a.s,('Whole tree exits measured halo',q)
            if not a.s[q].split('[')[0].endswith(('_log','_leaves')):continue
            done.add(q);component.add(q)
            for dx,dy,dz in((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):todo.append((q[0]+dx,q[1]+dy,q[2]+dz))
        for q in component:
            if q not in d:put(q,'minecraft:air','Complete natural tree member intersecting the authorized new personnel access; exact inverse retained')
        tree_components.append(dict(cells=len(component),bounds=[[min(q[k]for q in component)for k in range(3)],[max(q[k]for q in component)for k in range(3)]]))
    layout=dict(centre_xz=[-440,-270],floor_block_y=-476,apron_top_y=-475,airport_stand=[-440,-464,-270],airport_yaw=0,
        apron_bounds=[[-530,-478,-350],[-350,-476,-190]],capacity=1,heavy_VTOL=True,
        model_body_bounds=[[-69,-11,-56],[69,19,58]],park_gear_y=-475,crew_width=5,crew_route=route,
        control_post=[[-365,-476,-302],[-357,-469,-292]],dispatch_interface='Existing O aviation radio; no unbound physical dispatch button',
        fixed_yaw_park=True,all_yaw_turn_only_after_vertical_lift=True,trees=tree_components,
        reference='TV cavern/transport functional relationships; underground airport and exact footprint are original R50 engineering')
    a.full_desired=d;a.emit('UG01_northwest_heavy_VTOL_airfield',d,layout)
    (a.out/'airport_layout.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2),'utf8')
    return []

def guidance(a):
    a.read((10,-423,12),(14,-403,39));a.read((89,-423,12),(98,-403,39));d={}
    def put(p,state,why,tag=None):
        assert p not in a.t and (a.s[p]in AIR or a.s[p].startswith(('projectseele:nerv_edge_rail','projectseele:nerv_structural_panel'))),(p,a.s[p])
        d[p]=state,why,tag
    assert a.s[13,-411,15]==FLOOR,'Shared entry post uses the original actual apron floor'
    for x in(96,97):
        for y in(-413,-412,-411):put((x,y,15),FLOOR if y==-411 else FRAME,'Two-cell supported extension connects the02 sign post to the actual UG02 side landing at X95')
    for x in(13,97):
        for y in range(-410,-405):put((x,y,15),FRAME,'Actual side-entrance guide post founded on original apron edge outside full mechanical/crew widths')
    points=[((12,-407,15),'west',['人员阶梯 →','零号／初号接应','侧向通路下行','中央为机械轨道']),
        ((96,-407,15),'west',['人员阶梯 →','二号机接应','侧向通路下行','中央为机械轨道']),
        ((12,-416,38),'east',['接应台 ↑','零号／初号','侧阶梯至后门','机场沿地面西行']),
        ((92,-416,38),'east',['接应台 ↑','二号机','侧阶梯至后门','机场沿地面西行'])]
    for p,facing,lines in points:
        tag=nbtlib.Compound({'id':nbtlib.String('minecraft:sign'),'x':nbtlib.Int(p[0]),'y':nbtlib.Int(p[1]),'z':nbtlib.Int(p[2]),'is_waxed':nbtlib.Byte(1)})
        for face in('front_text','back_text'):
            tag[face]=nbtlib.Compound({'messages':nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps({'text':s},ensure_ascii=False))for s in lines]),'color':nbtlib.String('black'),'has_glowing_text':nbtlib.Byte(0)})
        put(p,f'minecraft:oak_wall_sign[facing={facing},waterlogged=false]','Actual complete native crew guidance sign, explicit supported side entrance/lower truss anchor',tag)
    a.full_desired=d;a.emit('UG03_actual_crew_side_guidance',d,dict(signs=[dict(pos=list(p),facing=f)for p,f,l in points],
        lower_sign_backing_depends_on_UG02=[[11,-416,38],[91,-416,38]],original_dead_end_guidance_not_recreated=True))
    return []

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True)
    ap.add_argument('--component',choices=['receiver','airport','guidance'],required=True);args=ap.parse_args()
    out=OUT/'candidates'/args.component;a=Author(args.world.resolve(),out);out.mkdir(parents=True,exist_ok=True)
    operations=receiver(a)if args.component=='receiver'else airport(a)if args.component=='airport'else guidance(a);complete_recipe(a)
    for p in out.glob('*/contract.json'):
        q=json.loads(p.read_text('utf8'));q.update(schema='projectseele.r50.underground-airport-candidate.v1',authorization='Root-relayed user GeoFront underground aircraft/receivers/complete crew reconnect')
        p.write_text(json.dumps(q,ensure_ascii=False,indent=2),'utf8')
    (out/'metadata_patch.json').write_text(json.dumps(dict(schema=50,operations=operations,world_written=False),ensure_ascii=False,indent=2),'utf8')
    (out/'manifest.json').write_text(json.dumps(dict(schema=50,source_world=str(a.world),components=a.components,changed_cells=len(a.all),world_written=False,native_verified=False,visual_verified=False),ensure_ascii=False,indent=2),'utf8')
    print('Receiver candidate',len(a.all),'cells; no world writes',flush=True)

if __name__=='__main__':main()
