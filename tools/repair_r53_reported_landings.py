"""Exact repairs for the 2026-10-17 reported entrances in the current save."""
from pathlib import Path
from collections import defaultdict, Counter
import argparse, copy, gzip, json, msvcrt
import nbtlib
from query_blocks import read_box, iter_block_entities, dimension_dir, AIR
from apply_s20_approved_semantic_repairs import Change, rewrite_region, atomic_replace

DIM='projectseele:geofront'
FLOOR='projectseele:nerv_floor_panel'
WALL='projectseele:nerv_structural_panel'

def plan(world, output):
    cells={}; tags={}; wanted={}; updated={}; reasons={}
    def read(lo,hi):
        cells.update(read_box(world,DIM,lo,hi));tags.update(dict(iter_block_entities(world,DIM,lo,hi)))
    def put(p,state,reason):
        assert p in cells,p
        assert p not in tags or p in updated,('Existing device',p)
        wanted[p]=state;reasons[p]=reason
    def sign(p,lines,facing='south'):
        assert cells[p] in AIR,(p,cells[p])
        put(p,f'minecraft:oak_wall_sign[facing={facing},waterlogged=false]','elevator_wayfinding')
        face=nbtlib.Compound({'messages':nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps({'text':s},ensure_ascii=False)) for s in (lines+['']*4)[:4]]),'color':nbtlib.String('black'),'has_glowing_text':nbtlib.Byte(0)})
        updated[p]=nbtlib.Compound({'id':nbtlib.String('minecraft:sign'),'x':nbtlib.Int(p[0]),'y':nbtlib.Int(p[1]),'z':nbtlib.Int(p[2]),'front_text':face,'back_text':copy.deepcopy(face),'is_waxed':nbtlib.Byte(1)})
    def entrance_sign(points,lines):
        for p in points:
            if cells[p] not in AIR:continue
            for facing,dx,dz in [('south',0,-1),('east',-1,0),('west',1,0),('north',0,1)]:
                q=p[0]+dx,p[1],p[2]+dz
                if wanted.get(q,cells.get(q)) in (WALL,'projectseele:nerv_wall_panel','projectseele:nerv_machine_edge'):
                    sign(p,lines,facing);return
        raise AssertionError('No measured wall at the reported entrance')
    read((45,-1016,348),(67,-1005,376))
    # Existing east approach: retain the escalator floor and native car; raise
    # only its low roof and complete the two measured side walls.
    for x in range(49,55):
        for z in range(359,371):
            for y in range(-1011,-1008):
                p=x,y,z
                put(p,WALL if y==-1009 or x in (49,54) else 'minecraft:air','east_hangar_approach_headroom')
    sign((50,-1012,360),['东侧主电梯 →','指挥区 / 科研区','机库整备层','沿廊道右转'],'east')
    entrance_sign([(x,-1012,z) for z in range(371,375) for x in range(54,63)],['东侧主电梯','↑ 指挥区 / 科研区','机库整备层','呼梯按钮在左侧'])
    read((59,-545,301),(74,-536,316))
    put((64,-542,307),FLOOR,'reported_east_doorway_gap')
    read((15,-514,249),(35,-488,281))
    for x in range(16,26):
        for y in range(-513,-502):
            put((x,y,257),'minecraft:black_concrete','original_tree_solid_backing')
    old=(28,-495,273);new=(28,-494,273)
    assert str(tags[old]['Artwork'])=='nerv'
    assert cells[new] in AIR
    artwork=copy.deepcopy(tags[old]);artwork['y']=nbtlib.Int(new[1])
    backing=(28<<38)|(272<<12)|(-494 & 4095)
    artwork['Backing']=nbtlib.Long(backing)
    updated[old]=None;updated[new]=artwork
    put(old,'minecraft:air','raise_original_command_logo')
    put(new,'projectseele:wall_artwork','raise_original_command_logo')
    for x in range(26,31):
        for y in range(-497,-491):put((x,y,272),'minecraft:black_concrete','raised_logo_backing_above_door')
    # Keep the existing three-wide doorway and its two original control sides.
    for x in range(27,30):
        put((x,-500,272),FLOOR,'command_door_threshold')
        for y in (-499,-498):put((x,y,272),'minecraft:air','command_door_aperture')
    read((100,-539,218),(139,-530,279))
    for p,tag in tags.items():
        if 112<=p[0]<=124 and -539<=p[1]<=-530 and 222<=p[2]<=239:
            assert str(tag['id'])=='projectseele:station_departure_board',('Retained functional device',p)
            updated[p]=None
    # Retire the northern blind branch from its junction at Z=240, including
    # all old floor/ceiling/lamps; the through hall starts at Z=241.
    for x in range(112,125):
        for z in range(222,240):
            for y in range(-539,-529):put((x,y,z),'minecraft:stone','retired_branch_from_junction')
        for y in range(-539,-529):put((x,y,240),WALL if y in (-537,-531) else 'projectseele:nerv_wall_panel','junction_continuous_wall')
    sign((125,-533,271),['地表交通电梯 →','通往地表与交通层','入口在东侧','沿现有走廊到达'],'west')
    junction=(118,-533,250)
    board=copy.deepcopy(tags[junction]);board['Row0']=nbtlib.String('↔ 总部主环廊');board['Row2']=nbtlib.String('电梯：沿南侧通道')
    updated[junction]=board;put(junction,cells[junction],'remove_retired_branch_direction')
    rows=[]
    for p,s in wanted.items():
        before_tag=tags.get(p);after_tag=updated.get(p,before_tag)
        a=None if before_tag is None else before_tag.snbt();b=None if after_tag is None else after_tag.snbt()
        if cells[p]!=s or a!=b:rows.append(dict(pos=p,before=cells[p],after=s,before_nbt=a,after_nbt=b,reason=reasons[p]))
    output.mkdir(parents=True,exist_ok=True)
    (output/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False).encode('utf8'),mtime=0))
    report=dict(world=str(world),changed_cells=len(rows),reasons=dict(Counter(r['reason'] for r in rows)),installed=False)
    (output/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False))

def apply(world,output):
    rows=json.loads(gzip.decompress((output/'EXACT_DELTA.json.gz').read_bytes()))
    with (world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        chunks=defaultdict(list)
        for r in rows:chunks[r['pos'][0]>>4,r['pos'][2]>>4].append(r)
        regions=defaultdict(dict);removed=set();added={}
        for (cx,cz),batch in chunks.items():
            ys=[r['pos'][1] for r in batch];lo=(cx*16,min(ys),cz*16);hi=(cx*16+15,max(ys),cz*16+15)
            current=read_box(world,DIM,lo,hi);tags=dict(iter_block_entities(world,DIM,lo,hi));changes=[]
            for r in batch:
                p=tuple(r['pos']);tag=tags.get(p)
                assert current[p]==r['before'],('Changed block',p,current[p])
                assert (None if tag is None else tag.snbt())==r['before_nbt'],('Changed device',p)
                if r['before_nbt'] is not None:removed.add(p)
                if r['after_nbt'] is not None:added[p]=nbtlib.parse_nbt(r['after_nbt'])
                changes.append(Change('reported-landings',*p,r['before'],r['after'],'restore',r['reason']))
            regions[cx>>5,cz>>5][cx,cz]=changes
        for (rx,rz),batch in regions.items():
            path=dimension_dir(world,DIM)/f'region/r.{rx}.{rz}.mca'
            atomic_replace(path,rewrite_region(path,batch,removed,added))
        for (cx,cz),batch in chunks.items():
            ys=[r['pos'][1] for r in batch];lo=(cx*16,min(ys),cz*16);hi=(cx*16+15,max(ys),cz*16+15)
            actual=read_box(world,DIM,lo,hi);tags=dict(iter_block_entities(world,DIM,lo,hi))
            for r in batch:
                p=tuple(r['pos']);assert actual[p]==r['after'];tag=tags.get(p)
                assert (None if tag is None else tag.snbt())==r['after_nbt']
        (output/'INSTALLED.json').write_text(json.dumps(dict(world=str(world),changed_cells=len(rows),actual_readback=True,progress_unchanged=True),indent=2),'utf8')
        print('Installed and read back',len(rows),'exact cells')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    (apply if a.apply else plan)(a.world,a.output)
