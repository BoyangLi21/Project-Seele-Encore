"""Move LCDs away from stair enclosures using their complete physical width."""
import argparse,gzip,json
import nbtlib
import regional_voxels as vox
from query_blocks import AIR,read_box,iter_block_entities
from build_station_boards_r19 import packed
from station_sign_readers_r44 import reader_visibility,NORMAL

OUT=vox.ROOT/'artifacts/world_repair_r19/stations'
EMPTY=AIR|{'minecraft:light'}

def main(apply=False):
    vox.OUT=OUT;p=vox.Painter();boards=json.loads((OUT/'live_departure_boards/places.json').read_text())['boards']
    with gzip.open(OUT/'live_departure_boards/ops.json.gz','rt',encoding='utf8') as f:original=json.load(f)
    stations=json.loads((vox.ROOT/'artifacts/world_expansion_20260907/transit_plan.json').read_text(encoding='utf8'))['platforms']
    stations+=json.loads((vox.ROOT/'artifacts/world_quality_r02/extension_plan.json').read_text(encoding='utf8'))['transit']['platforms']
    stations+=json.loads((vox.ROOT/'artifacts/world_expansion_r07/port_transit_plan.json').read_text(encoding='utf8'))['platforms']
    station_by_id={s['id']:s for s in stations};changes={};result=[]
    shapes=json.loads((vox.WORLD/'native_collision_shapes.json').read_text('utf8'))
    def change(pos,old,new,owner):
        if old!=new:changes[pos]=(old,new,owner)
    for b in boards:
        key,sign=b['id'].rsplit('/',1);sign=int(sign);s=station_by_id[key];cx,y,cz=map(int,s['center'])
        horizontal=s['heading'] in ('E','W');side=10 if s.get('compact') else 15;v=side*sign;half=s['length']//2-4
        def xyz(u,yy,vv):return (cx+u,yy,cz+vv) if horizontal else (cx+vv,yy,cz+u)
        ends=[xyz(-half,y,-side-1),xyz(half,y+11,side+1)];lo=tuple(map(min,zip(*ends)));hi=tuple(map(max,zip(*ends)))
        measured=read_box(vox.WORLD,vox.DIM,lo,hi)
        selected=None
        for u in (-8,8,-26,26,-34,34,0):
            if abs(u)+2>=half:continue
            clear=[xyz(uu,yy,v-sign*depth) for uu in range(u-2,u+3) for yy in (y+3,y+4) for depth in (1,2,3)]
            if not all(measured[q].split('[')[0] in EMPTY for q in clear):continue
            column=[xyz(u,yy,v) for yy in range(y+1,y+11)]
            allowed=EMPTY|{'minecraft:glass','minecraft:gray_stained_glass','minecraft:white_concrete','minecraft:light_gray_concrete','minecraft:gray_concrete','minecraft:polished_deepslate','minecraft:smooth_stone','minecraft:iron_block','projectseele:clear_glass','projectseele:nerv_wall_panel','projectseele:nerv_structural_panel'}
            if not all(measured[q].split('[')[0] in allowed or measured[q].startswith('projectseele:nerv_') and measured[q].split('[')[0].endswith(('_panel','_datum','_light')) for q in column):continue
            at=xyz(u,y+3,v-sign)
            face=('north' if sign>0 else 'south') if horizontal else ('west' if sign>0 else 'east')
            nx,nz=NORMAL[face];reader=(at[0]+nx*3,y+1,at[2]+nz*3)
            state_at=lambda q:measured.get(q,'UNKNOWN')
            optical=reader_visibility(state_at,lambda state: [] if state.split('[')[0] in AIR else shapes.get(state),at,face,reader,direction=False)
            if not optical['clear']:continue
            selected=u;break
        if selected is None:
            from collections import Counter
            print(key,sign,{u:dict(Counter(measured[xyz(u,yy,v)] for yy in range(y+1,y+11))) for u in (-8,8,-26,26) if abs(u)+2<half},flush=True)
            raise RuntimeError(('No unobstructed complete display site',key,sign))
        oldpos=tuple(b['pos']);old=measured[oldpos]
        if not old.startswith('projectseele:station_departure_board['):raise RuntimeError(('Missing old display',b,old))
        change(oldpos,old,'minecraft:air','r19/display_relocation')
        for op in original:
            if op['owner']!='r19/station_display_mount':continue
            pos=tuple(op['box'][:3])
            if pos[0]!=b['mount'][0] or pos[2]!=b['mount'][2] or not y<pos[1]<y+11:continue
            if measured[pos]==op['state']:change(pos,measured[pos],op['extra'][0],'r19/restore_old_display_mount')
        at=xyz(selected,y+3,v-sign);wall=xyz(selected,y+3,v)
        for yy in range(y+1,y+11):
            pos=xyz(selected,yy,v);change(pos,measured[pos],'projectseele:nerv_structural_panel','r19/unobstructed_display_mount')
        change(at,measured[at],old,'r19/unobstructed_live_display')
        tag=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(at[0]),'y':nbtlib.Int(at[1]),'z':nbtlib.Int(at[2]),
            'PlatformCentre':nbtlib.Long(packed((cx,y,cz))),'Station':nbtlib.String(s['name']),'Route':nbtlib.String(s['line']),
            'Row0':nbtlib.String('運行情報を確認中'),'Row1':nbtlib.String('')})
        p.block_entities[at]=tag;result.append(dict(b,pos=list(at),mount=list(wall),previous_pos=list(oldpos)))
    for pos,(before,after,owner) in changes.items():p.match((*pos,*pos),before,after,owner)
    p.meta.update(boards=result,clearance='Five-wide, two-high display/body and three-deep sight space measured as air; original stair glazing retained')
    p.apply('display_clearance') if apply else p.save_plan('display_clearance')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
