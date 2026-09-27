"""Read every generated GeoFront chunk, including structures outside old route lists."""
from pathlib import Path
from collections import Counter
import gzip,json,time
import numpy as np
from query_blocks import iter_matching_sections

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R40_REVIEW'
OUT=ROOT/'artifacts/world_combat_r40/inventory'

def feature(state):
    name=state.partition('[')[0]
    if 'escalator' in name or 'travellator' in name:return 'moving_walks'
    if 'elevator' in name or 'lift_' in name:return 'lifts'
    if name.startswith('mtr:') and any(s in name for s in ['platform','apg','psd']):return 'platforms'
    if name.endswith('_stairs'):return 'stairs'
    if 'departure_board' in name or 'sign' in name or 'route_map' in name:return 'signs'
    if 'button' in name or name.endswith(':lever'):return 'controls'
    if name.endswith('_door') or name.endswith('_trapdoor') or 'sliding_door' in name:return 'doors'
    if any(s in name for s in ['ceiling_light','wall_light','lantern','glowstone','light_fixture']):return 'lights'
    return None

def authored(state):
    name=state.partition('[')[0]
    return name.startswith(('projectseele:','mtr:','movingelevators:','another_furniture:')) or any(s in name for s in ['concrete','terracotta','stone_brick','quartz','polished','glass','iron_block','stairs','slab','bricks','sign','door','button','lantern','barrier'])

def main():
    OUT.mkdir(parents=True,exist_ok=True);stats={};counts=Counter();features=Counter();sections=[];started=time.monotonic()
    writers={name:gzip.open(OUT/(name+'.jsonl.gz'),'wt',encoding='utf8') for name in ['moving_walks','lifts','platforms','stairs','signs','controls','doors','lights']}
    try:
        for cx,cz,sy,palette,index in iter_matching_sections(WORLD,'projectseele:geofront',[''],stats):
            hist=np.bincount(index,minlength=len(palette));built=0
            for n,state in enumerate(palette):
                count=int(hist[n]);counts[state]+=count
                if authored(state):built+=count
                kind=feature(state)
                if kind is None or not count:continue
                ids=np.flatnonzero(index==n);features[kind]+=len(ids)
                for i in ids:
                    row=[cx*16+int(i&15),sy*16+int(i>>8),cz*16+int((i>>4)&15),state]
                    writers[kind].write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
            if built:sections.append([cx,cz,sy,built])
            if stats['matching_sections']%12000==0:print(stats['chunks_read'],'chunks;',stats['matching_sections'],'sections;',round(time.monotonic()-started,1),'seconds',flush=True)
    finally:
        for writer in writers.values():writer.close()
    record=dict(world=str(WORLD),scope='All stored FULL chunks in projectseele:geofront, no route/catalogue restriction',scan=stats,feature_counts=features,authored_sections=sections,state_counts=counts,seconds=time.monotonic()-started)
    (OUT/'world.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
    print('Full palette inventory complete',stats,dict(features),flush=True)

if __name__=='__main__':main()
