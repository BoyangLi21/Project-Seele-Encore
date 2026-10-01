"""Whole current information fixtures, after nine-ray full-face diagnosis.

Plans only. Preserve each original board NBT and explicitly relocate its whole
mount. No ceiling, stair, railway or user-progress record is reconstructed.
"""
from pathlib import Path
import copy, gzip, json, math
import nbtlib
from measure_world_r40 import MeasuredWorld, properties
from query_blocks import AIR, iter_block_entities
from audit_facility_transit_r44 import Geometry, NORMAL
from station_sign_readers_r44 import reader_visibility

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/facility_transit_r44/full_board_faces_v2'
STRUCT='projectseele:nerv_structural_panel'
BARS='minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]'


def main():
    assert not OUT.exists()
    mounts=[(117,-440,-55)]+[(x,107,z) for x in (545,594,650) for z in (105,151)]
    stand=(-398,82,698); air_labels=[(-1666,85,-327),(744,85,1123)]
    w=MeasuredWorld(WORLD)
    for q in mounts+[stand]+air_labels:w.around(q,24)
    w.load();g=Geometry(w);changes={};tags={};cards=[];cases=[];cameras=[]
    def be(q):return dict(iter_block_entities(WORLD,'projectseele:geofront',q,q))[q]
    def put(q,s,tag=None):
        assert q not in changes,('Overlapping fixture component',q)
        changes[q]=s
        if tag is not None:tags[q]=tag
    for old in mounts+[stand]:
        state=w.block(old);original=be(old);face=properties(state)['facing'];nx,nz=NORMAL[face]
        q=(old[0]+nx,old[1],old[2]+nz) if old!=stand else (old[0]+2,old[1],old[2])
        new=copy.deepcopy(original)
        for k,v in zip(('x','y','z'),q):new[k]=nbtlib.Int(v)
        if old!=stand:
            backing='projectseele:clear_glass' if old==(117,-440,-55) else STRUCT
            put(old,backing);put(q,state,new)
            # The old anchor is explicitly restored to the same fixed backing
            # material as its five neighbors; the entire face moves outward.
            for across in (-1,0,1):
                for h in (0,1):
                    p=(old[0]+across*nz,old[1]+h,old[2]-across*nx)
                    assert p==old or w.block(p)==backing,('Different backing owner',p,w.block(p))
                    front=(p[0]+nx,p[1],p[2]+nz)
                    assert w.block(front) in AIR,('Whole face not clear',front,w.block(front))
        else:
            put(old,'minecraft:air');put(q,state,new)
            for y in (81,82):
                a=(-399,y,698);b=(-395,y,698)
                assert w.block(a)==BARS and w.block((-397,y,698))==BARS and w.block(b)in AIR
                put(a,'minecraft:air');put(b,BARS)
            for x in (-397,-395):assert g.standing((x,81,698))['status'] in ('STATIC_STANDING','OBSERVED_OBSTRUCTION')
        feet=q[1]-2 if old!=stand else 81
        reader=(q[0]+nx*3,feet,q[2]+nz*3)
        assert g.standing(reader)['status']=='STATIC_STANDING'
        state_at=lambda p:changes.get(p,w.block(p))
        proof=reader_visibility(state_at,g.boxes,q,face,reader,direction=bool(new.get('Wayfinding',False)),route_map='MapRows'in new)
        assert proof['clear'],(q,proof)
        # A three-metre clear, supported approach connects to the retained
        # station aisle. This supplements, not replaces, whole station paths.
        start=(reader[0]+nx*3,feet,reader[2]+nz*3)
        original_get=w.get;w.get=lambda x,y,z:changes.get((x,y,z),original_get(x,y,z))
        path=g.flat_path(start,reader,radius=10);w.get=original_get
        assert path,('No retained aisle approach',q)
        for reverse in (False,True):cases.append(dict(id='r44/full_board_face/'+str(len(cards))+('/return'if reverse else''),path=[[x+.5,y,z+.5]for x,y,z in (path[::-1]if reverse else path)]))
        eye=[reader[0]+.5,reader[1]+1.62,reader[2]+.5];aim=[q[0]+.5+nx*.205,q[1]+(1.1 if bool(new.get('Wayfinding',False))else.8),q[2]+.5+nz*.205];delta=[aim[i]-eye[i]for i in range(3)]
        cameras.append(dict(file=f'r44_whole_board_face_{len(cards)}.png',position=[reader[0]+.5,reader[1],reader[2]+.5],yaw=math.degrees(math.atan2(-delta[0],delta[2])),pitch=-math.degrees(math.atan2(delta[1],math.hypot(delta[0],delta[2]))),fovDegrees=70,warmupTicks=240,requiredSections=[q,list(old)]))
        cards.append(dict(old=old,new=q,face=face,reader=reader,nine_ray_proof=proof,kind='complete_floor_stand'if old==stand else'whole_fixed_wall_panel',original_full_nbt=original.snbt(),new_full_nbt=new.snbt()))
    for q in air_labels:
        original=be(q);assert str(original['Route'])=='F1'and int(original['AirService'])==0
        new=copy.deepcopy(original);new['AirService']=nbtlib.Byte(1);put(q,w.block(q),new)
    rows=[]
    for q,state in sorted(changes.items()):
        current_tags=dict(iter_block_entities(WORLD,'projectseele:geofront',q,q));old=current_tags.get(q)
        rows.append(dict(pos=q,before=w.block(q),after=state,before_nbt=old.snbt()if old is not None else None,after_nbt=tags[q].snbt()if q in tags else None,owner='r44/complete_station_information_fixture'))
    OUT.mkdir(parents=True)
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(OUT/(name+'.jsonl.gz'),'wt',encoding='utf8')as stream:
            for row in rows:
                r=dict(row)
                if inverse:r['before'],r['after']=row['after'],row['before'];r['before_nbt'],r['after_nbt']=row['after_nbt'],row['before_nbt']
                stream.write(json.dumps(r,ensure_ascii=False)+'\n')
    report=dict(fixtures=cards,air_labels=air_labels,cells=len(rows),world_written=False,native_pass=False,art_pass=False,root_cause='Anchor-only backing cut exposed centre while the wider rendered face overlapped surrounding full blocks; a stand was also placed immediately behind a stair sidewall.',generator_fixes=['build_airport_station_r28.py offsets board in front of complete backing','build_station_route_maps_r25.py and relocate_station_boards_r19.py now require nine lettering rays','revise_airport_transit_r20.py marks actual F1 displays as aircraft service'])
    for name,data in [('contract',report),('native_cases',cases),('cameras',cameras)]: (OUT/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    print('Complete eight fixture candidates plus two F1 titles:',len(rows),'cells; world unchanged')


if __name__=='__main__':main()
