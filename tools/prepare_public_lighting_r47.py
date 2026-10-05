"""Measured pendant lights in named station/arrival interiors; no save writer."""
from pathlib import Path
import json, math
from query_blocks import read_box, iter_block_entities, AIR
from install_facility_lighting_r30 import static_ceiling
from lighting_envelopes_r47 import rail_swept

ROOT=Path(__file__).resolve().parents[1]; WORLD=ROOT/'artifacts/rebuild_r47/baseline/SEELE_R46_WORLD'
OUT=ROOT/'artifacts/rebuild_r47/audio_staff/world'; DIM='projectseele:geofront'
AREAS=[
 ('large_lift_arrival_foyer',(-398,-466,730),(-373,-466,742)),
 ('geofront_arrival_station',(-357,-466,768),(-303,-466,803)),
 ('hq_station_concourse',(9,-466,471),(51,-466,480)),
 ('hangar_station_concourse',(130,-442,-60),(177,-442,-49)),
]

def main():
    OUT.mkdir(parents=True,exist_ok=True); writes={}; reports=[]
    rails=json.loads((WORLD/'native_transit_r26.json').read_text('utf8'))['curves']
    for name,lo,hi in AREAS:
        x,f,z=lo;X,_,Z=hi;top=f+18
        bounds=((x,f-1,z),(X,top,Z)); blocks=read_box(WORLD,DIM,*bounds)
        bes={tuple(pos) for pos,be in iter_block_entities(WORLD,DIM,*bounds)}
        existing=[p for p,s in blocks.items() if any(k in s for k in ('ceiling_light','strip_light','glowstone','froglight','sea_lantern','shroomlight','minecraft:light['))]
        selected=[];held=[]
        for xx in range(x+2,X,7):
            for zz in range(z+2,Z,7):
                foot=(xx,f,zz);floor=blocks.get((xx,f-1,zz),'UNKNOWN')
                if floor in AIR or floor=='UNKNOWN' or any(k in floor for k in ('rail','water','lcl','glass','stairs','slab','bars','fence')):continue
                if any(blocks.get((xx,f+i,zz)) not in AIR for i in range(4)):continue
                if any(abs(xx+360)<10 and abs(zz-750)<10 for _ in [0]):continue
                if rail_swept((xx,f+4,zz),rails):continue
                if any(abs(xx-p[0])+abs(zz-p[2])+abs((f+1)-p[1])<=8 for p in existing):continue
                roof=next((y for y in range(f+5,top+1) if static_ceiling(blocks.get((xx,y,zz),'UNKNOWN'))),None)
                if roof is None:held.append(dict(feet=foot,reason='No surveyed static roof in named room'));continue
                positions=[(xx,y,zz) for y in range(f+4,roof)]
                if any(blocks.get(p) not in AIR or p in bes for p in positions):continue
                for p in positions:
                    after='projectseele:nerv_ceiling_light[hanging=true,lit=true]' if p[1]==f+4 else 'minecraft:chain[axis=y,waterlogged=false]'
                    writes[p]=dict(pos=list(p),before=blocks[p],after=after,before_nbt=None,after_nbt=None,reason=name+'/roof-backed-pendant-outside-native-train-and-lift-envelopes')
                selected.append(dict(feet=list(foot),lamp=[xx,f+4,zz],roof=[xx,roof,zz]))
                existing.append((xx,f+4,zz))
        reports.append(dict(id=name,bounds=bounds,fixtures=selected,held=held))
    forward=list(writes.values())
    inverse=[dict(r,before=r['after'],after=r['before'],before_nbt=r['after_nbt'],after_nbt=r['before_nbt']) for r in forward]
    patch=dict(schema='projectseele.r47.exact-block-patch.v1',world=str(WORLD),dimension=DIM,positive_edit_mask=[r['pos'] for r in forward],forward_patch=forward,inverse_patch=inverse,world_written=False)
    (OUT/'public_lighting_patch.json').write_text(json.dumps(patch,ensure_ascii=False,indent=2)+'\n','utf8')
    (OUT/'public_lighting_survey.json').write_text(json.dumps(dict(areas=reports,total_block_changes=len(forward),root_cause='Very high roof fixtures cannot illuminate low concourse floors; suspended human-scale fixtures bring real block light down while preserving the roof.',native_light_rebuild_required=True,world_written=False),ensure_ascii=False,indent=2)+'\n','utf8')
    print('Public pendant fixtures:',sum(len(r['fixtures']) for r in reports),'block changes:',len(forward),'held:',sum(len(r['held']) for r in reports))

if __name__=='__main__':main()
