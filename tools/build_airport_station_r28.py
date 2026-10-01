"""An S1 through stop, paired MTR access stairs and a graded airport road."""
from pathlib import Path
from collections import defaultdict
import json,math,nbtlib,numpy as np
from scipy.spatial import cKDTree
import regional_voxels as v
from build_station_boards_r19 import packed
from query_blocks import read_box,iter_block_entities
ROOT=v.ROOT;WORLD=ROOT/'run/saves/SEELE_FIELD_R28_REVIEW';OUT=ROOT/'artifacts/facility_r28/airport/civil'
FLOOR='projectseele:period_station_floor';WALL='projectseele:nerv_wall_panel';STRUCT='projectseele:nerv_structural_panel';GLASS='projectseele:clear_glass';LIGHT='projectseele:nerv_strip_light';AIR='minecraft:air'

def main():
    OUT.mkdir(parents=True,exist_ok=True);v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();owner='r28/nerv_airport';walks=[];boards=[]
    native=json.loads((OUT.parent/'native_final.json').read_text());receipt=json.loads((OUT.parent/'airport_native_receipt.json').read_text());assert receipt['passed']
    platforms=[q for q in native['platforms'] if q['id'] in receipt['new_platforms']]
    curves=[q for q in native['curves'] if q['id'] in receipt['new_rails']]
    def b(box,state):p.fill(*box,state,owner,'owned')
    def path(name,points):
        for suffix,q in (('',points),('/return',points[::-1])):walks.append(dict(id=owner+'/'+name+suffix,path=q))
    # Explicitly superseded native rail beds; airfield buildings end at Z=86.
    b((440,95,120,1030,113,136),AIR)
    for c in curves:
        for xx,yy,zz in c['points']:
            x,y,z=math.floor(xx),math.floor(yy),math.floor(zz)
            b((x-3,y-3,z-3,x+3,y-1,z+3),'minecraft:light_gray_concrete')
    # Raised platforms have complete decks, roof and outer walls. Access to
    # opposite directions goes below the tracks at ground concourse level.
    for z,Z in ((104,122),(134,152)):
        b((494,102,z,668,104,Z),STRUCT);b((495,104,z+1,667,104,Z-1),FLOOR)
        b((494,105,z,668,110,Z),AIR);b((494,111,z,668,111,Z),STRUCT)
        edge=z if z==104 else Z
        b((494,105,edge,668,109,edge),GLASS)
        for x in range(494,669,22):b((x,70,edge,x+1,110,edge),STRUCT)
        for x in (494,668):b((x,105,z,x,109,Z),GLASS)
        for x in range(502,661,14):b((x,110,z+6,x+5,110,z+6),LIGHT)
    # Covered ground concourse joins the terminal's east public entrance.
    for x,z,X,Z in ((489,72,507,156),(476,70,507,80)):
        b((x,70,z,X,72,Z),STRUCT);b((x,73,z,X,79,Z),WALL)
        b((x+1,73,z+1,X-1,78,Z-1),AIR);b((x+1,72,z+1,X-1,72,Z-1),FLOOR)
        b((x,79,z,X,79,Z),STRUCT)
    b((490,73,79,506,78,81),AIR)
    b((476,73,73,490,77,77),AIR);b((476,72,73,490,72,77),FLOOR)
    b((470,73,82,474,77,82),AIR)
    # Side-by-side ascending and descending escalators are two blocks wide;
    # the centre stair remains available and no belt ends on a platform lip.
    for basez in (108,138):
        for n in range(38):
            x=498+n;y=72+max(0,min(32,n-1))
            b((x,71,basez-1,x,y,basez+8),STRUCT)
            b((x,y+1,basez,x,y+4,basez+7),AIR)
            b((x,y+5,basez-1,x,y+5,basez+8),STRUCT)
            for z in (basez-1,basez+8):b((x,y+1,z,x,y+3,z),GLASS)
            if 2<=n<=33:
                b((x,y,basez+3,x,y,basez+4),'minecraft:smooth_quartz_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]')
            else:b((x,y,basez+3,x,y,basez+4),FLOOR)
            orient='landing_bottom' if n==0 else 'transition_bottom' if n==1 else 'slope' if n<=32 else 'transition_top' if n==33 else 'landing_top' if n==34 else 'flat'
            for z0,forward in ((basez,True),(basez+6,False)):
                for lane in (0,1):
                    side='left' if lane==0 else 'right';z=z0+lane
                    # End the complete native mechanism at landing_top.
                    # Its former3flat trailing rows carried the gate queue
                    # sideways; the commissioned upper hall needs a real
                    # stationary two-width landing before any gate or turn.
                    if n>34:
                        b((x,y,z,x,y,z),FLOOR)
                    else:
                        b((x,y,z,x,y,z),f'mtr:escalator_step[direction={str(forward).lower()},facing=east,orientation={orient},side={side},status=true]')
                    if orient not in ('flat','landing_bottom','landing_top'):
                        b((x,y+1,z,x,y+1,z),f'mtr:escalator_side[facing=east,orientation={orient},side={side}]')
        # Clear the station end wall across the whole upper landing width.
        b((534,105,basez,537,109,basez+7),AIR)
        path('stairs_'+str(basez),[[496.5,73,basez+3.5],[499.5,73,basez+3.5],[532.5,105,basez+3.5],[537.5,105,basez+3.5]])
    # Native platform doors align to the same 5-metre stopping grid.
    for platform in platforms:
        z=platform['position1']['z'];edge=z-2 if z==124 else z+2;face='south' if z==124 else 'north';door={}
        for x in range(523,650,5):door[x-1]=0;door[x]=1
        for x in range(495,668):
            isdoor=x in door;part=door.get(x,(x-520)%2);part=part if face=='north' else 1-part
            b((x,104,edge,x,104,edge),f'mtr:platform[door_type=apg,facing={face},side=0]')
            for half,y in (('lower',105),('upper',106)):
                props=f'facing={face},half={half},side={"left" if part==0 else "right"}'
                state=f'mtr:apg_door[end=false,{props},unlocked=true]' if isdoor else f'mtr:apg_glass[{props}]';b((x,y,edge,x,y,edge),state)
                if isdoor:p.block_entities[x,y,edge]=nbtlib.Compound({'id':nbtlib.String('mtr:apg_door'),'x':nbtlib.Int(x),'y':nbtlib.Int(y),'z':nbtlib.Int(edge)})
            tactile=edge-1 if z==124 else edge+1;b((x,104,tactile,x,104,tactile),'projectseele:station_tactile_warning')
        for x in (545,594,650):
            backingz=105 if z==124 else 151
            boardz=backingz+(1 if z==124 else -1)
            at=(x,107,boardz);boardface='south' if z==124 else 'north'
            # The full three-metre face stands in front of its backing.
            # An anchor cut into the backing hides its two outer text spans.
            b((x-1,105,backingz,x+1,109,backingz),STRUCT)
            p.put(*at,f'projectseele:station_departure_board[facing={boardface},wayfinding=false]',owner,'owned')
            p.block_entities[at]=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(x),'y':nbtlib.Int(107),'z':nbtlib.Int(boardz),'PlatformCentre':nbtlib.Long(packed((585,104,z))),'NativePlatformId':nbtlib.Long(platform['id']),'Station':nbtlib.String('NERV 航空基地'),'Route':nbtlib.String('S1'),'Wayfinding':nbtlib.Byte(0)})
            boards.append(dict(position=at,platform_id=platform['id']))
        for x in range(565,650,20):
            for dx in (0,2,4):p.put(x+dx,105,108 if z==124 else 148,f'projectseele:station_seat[facing={face}]',owner,'owned')
        path('platform_'+str(z),[[537.5,105,118.5 if z==124 else 138.5],[657.5,105,118.5 if z==124 else 138.5]])
    # Clear only the rolling-stock core after all civil pieces are laid.
    for c in curves:
        for xx,yy,zz in c['points']:
            x,y,z=math.floor(xx),math.floor(yy),math.floor(zz)
            b((x-1,y,z-1,x+1,y+6,z+1),AIR);b((x-1,y-1,z-1,x+1,y-1,z+1),'minecraft:gravel')
    # A continuous half-block graded road bypasses the old abrupt eight-metre
    # airport boundary. All columns are measured before the reversible patch.
    line=np.array([[280,80,80],[310,80,80],[345,78.5,105],[460,72,105],[473,72,92]],float)
    samples=[]
    for aa,bb in zip(line,line[1:]):samples.extend(np.linspace(aa,bb,max(2,math.ceil(np.linalg.norm((bb-aa)[[0,2]])*2))))
    samples=np.asarray(samples);tree=cKDTree(samples[:,[0,2]]);cells=read_box(WORLD,v.DIM,(272,64,70),(492,88,119));road=[]
    for x in range(272,493):
        for z in range(70,120):
            dist,i=tree.query([x+.5,z+.5])
            if dist>8:continue
            height=round(samples[i,1]*2)/2;floor=math.floor(height);half=height-floor>.1
            state='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]' if half else 'minecraft:gray_concrete'
            if dist<5.5:state='minecraft:blackstone_slab[type=bottom,waterlogged=false]' if half else 'minecraft:black_concrete'
            # Coordinates describe the top of a full-block road datum.
            top=floor+1 if half else floor
            b((x,64,z,x,floor-1,z),'minecraft:stone');b((x,floor,z,x,floor,z),'minecraft:stone' if half else state)
            if half:b((x,top,z,x,top,z),state)
            b((x,top+1,z,x,88,z),AIR);road.append([x,height+1,z])
    # The former straight cliff-end is green verge behind a continuous kerb.
    for x in range(318,350):
        for z in range(74,87):
            dist,_=tree.query([x+.5,z+.5])
            if dist<8:continue
            for y in range(77,82):
                old=cells.get((x,y,z),AIR)
                if old.split('[')[0] in ('minecraft:black_concrete','minecraft:white_concrete','minecraft:smooth_stone','minecraft:gray_concrete'):
                    p.match((x,y,z,x,y,z),old,'minecraft:grass_block[snowy=false]',owner+'/retired_cliff_spur')
    b((458,70,83,491,72,100),STRUCT);b((458,73,83,491,78,100),AIR);b((458,72,83,491,72,100),FLOOR)
    b((489,73,88,491,77,96),AIR)
    # Native stair entries connect through the ground underpass and terminal.
    path('terminal_to_concourse',[[473.5,73,75.5],[496.5,73,75.5],[496.5,73,149.5]])
    for z in (111.5,141.5):path('concourse_to_stair_'+str(z),[[496.5,73,90.5],[496.5,73,z],[499.5,73,z]])
    path('airport_road_walk',[[x+.5,y+1,z+.5] for x,y,z in samples[::12]])
    p.meta.update(walk_nodes=walks,boards=boards,platforms=platforms,road_profile=line.tolist(),station='NERV 航空基地',line='S1',stairs_clear_of_platform_edge=True)
    p.apply('nerv_airport_through_station_and_road')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'road_samples.json').write_text(json.dumps(road,separators=(',',':')))
    print('Airport stop, terminal paths and graded road installed in review',flush=True)

if __name__=='__main__':main()
