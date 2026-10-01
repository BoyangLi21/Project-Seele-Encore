"""Upgrade complete existing checkpoint assemblies, retaining every lift and inside release."""
from pathlib import Path
import copy,json,zlib
import nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,AIR
from install_access_r44 import packed

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';OUT=ROOT/'artifacts/rebuild_r44/access/existing_checkpoints'
SITES=[dict(id='regional_surface',reader=(-354,82,732),facing='north',gate=(-363,81,733),exit=(-354,82,734),axis=True,width=7,height=5,label='NERV · 地下都市入口'),
       dict(id='emergency_inner',reader=(119,76,270),facing='west',gate=(120,75,271),exit=(121,76,270),axis=False,width=5,height=4,label='NERV · 地面联络直梯')]

def plan():
    OUT.mkdir(parents=True,exist_ok=True);w=MeasuredWorld(WORLD);tags={}
    for s in SITES:
        q=s['gate'];lo=(min(q[0],s['reader'][0])-2,q[1]-1,min(q[2],s['reader'][2])-2);hi=(max(q[0]+s['width'],s['reader'][0])+2,q[1]+s['height']+1,max(q[2]+s['width'],s['reader'][2])+2)
        w.box(lo,hi);tags.update((q,copy.deepcopy(t)) for q,t in iter_block_entities(WORLD,v.DIM,lo,hi))
    w.load();v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();preserved=[]
    for s in SITES:
        q=s['reader'];old=w.block(q);assert old is not None and q not in tags
        assert old.partition('[')[0].endswith('_button'),('Reader owner changed',q,old)
        p.match((*q,*q),old,'projectseele:nerv_access_reader[facing='+s['facing']+']','r44/'+s['id']+'/actual_reader')
        for span in range(s['width']):
            for dy in range(s['height']):
                a=(s['gate'][0]+(span if s['axis'] else 0),s['gate'][1]+dy,s['gate'][2]+(0 if s['axis'] else span));before=w.block(a)
                assert a not in tags and before is not None
                assert before.partition('[')[0] in AIR|{'minecraft:barrier','minecraft:gray_stained_glass'},('Checkpoint aperture changed',a,before)
                p.match((*a,*a),before,'minecraft:barrier','r44/'+s['id']+'/reader_owned_aperture')
        exit_state=w.block(s['exit']);assert exit_state.partition('[')[0].endswith('_button'),('Inside release missing',s['exit'],exit_state)
        p.block_entities[q]=nbtlib.Compound(dict(id=nbtlib.String('projectseele:nerv_access_reader'),x=nbtlib.Int(q[0]),y=nbtlib.Int(q[1]),z=nbtlib.Int(q[2]),
            Gate=nbtlib.Long(packed(s['gate'])),Exit=nbtlib.Long(packed(s['exit'])),Width=nbtlib.Int(s['width']),Height=nbtlib.Int(s['height']),Clearance=nbtlib.Int(1),Style=nbtlib.Int(1),
            DoorId=nbtlib.Int(zlib.crc32(s['id'].encode())&0x7fffffff),AlongX=nbtlib.Byte(int(s['axis'])),Linked=nbtlib.Byte(1),Label=nbtlib.String(s['label']),SwipeAt=nbtlib.Long(-1)))
        preserved.append(dict(id=s['id'],exit=s['exit'],state=exit_state,lift='All controller/car/group/floor NBT preserved; card gate is independent'))
    p.meta.update(sites=SITES,preserved=preserved,existing_nbt=[dict(pos=q,nbt=t.snbt()) for q,t in tags.items()],validation='Permission/open/traverse/exit/occupation/reload and actual lift cycles PENDING')
    p.save_plan('existing_checkpoint_readers');return p

if __name__=='__main__':plan()
