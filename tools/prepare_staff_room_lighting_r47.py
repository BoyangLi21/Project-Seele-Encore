"""Finite roof-backed work lighting at existing named facility duty posts."""
from pathlib import Path
import json
from query_blocks import read_box, iter_block_entities, AIR
from install_facility_lighting_r30 import static_ceiling
from lighting_envelopes_r47 import rail_swept
ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'artifacts/rebuild_r47/baseline/SEELE_R46_WORLD'
OUT=ROOT/'artifacts/rebuild_r47/audio_staff/world'; DIM='projectseele:geofront'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    roster=json.loads((WORLD/'nerv_staff_r15.json').read_text('utf8'))['stations']
    groups={}
    for row in roster:
        room=row.get('room','')
        if room.startswith(('hq/','science/','logistics/','base/','r04/pyramid/')):
            groups.setdefault(room,[]).append(row)
    rails=json.loads((WORLD/'native_transit_r26.json').read_text('utf8'))['curves']
    shafts=[(12,253,8),(130,273,5),(66,302,6),(-29,-278,6),(93,-52,7),(-360,750,10)]
    writes={}; surveys=[]
    for room,posts in groups.items():
        x,f,z=posts[0]['feet']; bounds=((x-5,f-1,z-5),(x+5,f+24,z+5))
        blocks=read_box(WORLD,DIM,*bounds); bes=dict(iter_block_entities(WORLD,DIM,*bounds))
        bright=[p for p,s in blocks.items() if any(k in s for k in ('ceiling_light','strip_light','froglight','glowstone','sea_lantern','shroomlight','minecraft:light[')) and 'lit=false' not in s]
        if any(abs(x-p[0])+abs(z-p[2])+abs(f+1-p[1])<=8 for p in bright):
            surveys.append(dict(room=room,result='existing local duty lighting retained'));continue
        if any(abs(x-X)<=r and abs(z-Z)<=r for X,Z,r in shafts):
            surveys.append(dict(room=room,result='HOLD moving lift envelope'));continue
        if rail_swept((x,f+4,z),rails):
            surveys.append(dict(room=room,result='HOLD native train envelope'));continue
        support=blocks.get((x,f-1,z),'UNKNOWN')
        if support in AIR or support=='UNKNOWN' or any(k in support for k in ('rail','water','lcl','stairs','slab','fence','bars')):
            surveys.append(dict(room=room,result='HOLD duty post bearing no longer full-height'));continue
        roof=next((y for y in range(f+5,f+25) if static_ceiling(blocks.get((x,y,z),'UNKNOWN'))),None)
        if roof is None:
            surveys.append(dict(room=room,result='HOLD no measured static roof'));continue
        positions=[(x,y,z) for y in range(f+4,roof)]
        if any(blocks.get(p) not in AIR or p in bes for p in positions):
            surveys.append(dict(room=room,result='HOLD occupied pendant attachment'));continue
        for p in positions:
            writes[p]=dict(pos=list(p),before=blocks[p],after='projectseele:nerv_ceiling_light[hanging=true,lit=true]' if p[1]==f+4 else 'minecraft:chain[axis=y,waterlogged=false]',before_nbt=None,after_nbt=None,reason=room+'/original-duty-post-roof-backed-task-light')
        surveys.append(dict(room=room,result='roof-backed human-scale task light',lamp=[x,f+4,z],roof=[x,roof,z]))
    forward=list(writes.values())
    patch=dict(schema='projectseele.r47.exact-block-patch.v1',world=str(WORLD),dimension=DIM,positive_edit_mask=[r['pos'] for r in forward],forward_patch=forward,
        inverse_patch=[dict(r,before=r['after'],after=r['before'],before_nbt=None,after_nbt=None) for r in forward],world_written=False)
    (OUT/'staff_room_lighting_patch.json').write_text(json.dumps(patch,ensure_ascii=False,indent=2)+'\n','utf8')
    (OUT/'staff_room_lighting_survey.json').write_text(json.dumps(dict(named_workrooms=len(groups),surveys=surveys,changes=len(forward),world_written=False,
        coverage='Existing named duty-post light gaps only; does not claim full floor/public-building light acceptance.'),ensure_ascii=False,indent=2)+'\n','utf8')
    print('Named workrooms',len(groups),'added fixtures',sum(s['result']=='roof-backed human-scale task light' for s in surveys),'changes',len(forward))

if __name__=='__main__':main()
