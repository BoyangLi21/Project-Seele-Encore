"""Read whole proposed expansion terrain, existing ownership and natural bearings."""
from pathlib import Path
from collections import Counter
import argparse,hashlib,json
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
SITES=[('tokyo_north_extension',[-240,160,-760,-544]),('hakone_south_extension',[-1872,-1616,1056,1248]),('kirisato_north_extension',[-2896,-2624,-1328,-1168])]


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--site',action='append');a=p.parse_args();assert not a.output.exists();a.output.mkdir(parents=True)
    owners=json.loads((ROOT/'artifacts/rebuild_r44/city_buildings/actual_authored_ownership.json').read_text('utf8'))
    summaries=[]
    sites=[(s.split(':')[0],list(map(int,s.split(':')[1].split(',')))) for s in a.site] if a.site else SITES
    for name,b in sites:
        x0,x1,z0,z1=b;w=MeasuredWorld(WORLD);w.box((x0,40,z0),(x1,310,z1));w.load()
        tops=np.full((z1-z0+1,x1-x0+1),-32768,np.int16);water=np.full_like(tops,-32768);foreign=np.full_like(tops,-32768)
        for (cx,sy,cz),(palette,ids) in w.tiles.items():
            names=[s.split('[')[0] for s in palette];data=ids.reshape(16,16,16)
            xx0,xx1=max(x0,cx*16),min(x1,cx*16+15);zz0,zz1=max(z0,cz*16),min(z1,cz*16+15)
            if xx0>xx1 or zz0>zz1:continue
            box=(slice(zz0-z0,zz1-z0+1),slice(xx0-x0,xx1-x0+1));local=(slice(None),slice(zz0-cz*16,zz1-cz*16+1),slice(xx0-cx*16,xx1-cx*16+1))
            for target,allow in [(tops,np.array([s=='minecraft:grass_block' for s in names])),(water,np.array([s=='minecraft:water' for s in names])),(foreign,np.array([not s.startswith('minecraft:') for s in names]))]:
                active=allow[data[local]];ys=np.arange(16,dtype=np.int16)[:,None,None]+sy*16
                candidate=np.where(active,ys,-32768).max(axis=0);target[box]=np.maximum(target[box],candidate)
        measured=np.array([w.status.get((x//16,z//16))=='full' for z in range(z0,z1+1) for x in range(x0,x1+1)]).reshape(tops.shape)
        valid=(tops!=-32768)&measured;tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(x0,40,z0),(x1,310,z1),selected_chunks=set(w.selected)))
        overlap=[]
        for building in owners['buildings']:
            lo,hi=building['planned_bounds']
            if lo[0]<=x1 and hi[0]>=x0 and lo[2]<=z1 and hi[2]>=z0:overlap.append(dict(id=building['id'],bounds=building['planned_bounds']))
        profile=a.output/(name+'.columns.npz');np.savez_compressed(profile,origin=[x0,z0],grass_top=tops,water_top=water,foreign_top=foreign,complete_columns=measured)
        summary=dict(id=name,bounds=b,total_columns=tops.size,full_columns=int(measured.sum()),grass_columns=int(valid.sum()),
            grass_top_quantiles=np.quantile(tops[valid],[0,.1,.25,.5,.75,.9,1]).tolist() if valid.any() else [],
            submerged_grass_columns=int((valid&(water>tops)).sum()),foreign_block_columns=int((foreign!=-32768).sum()),
            chunk_status_counts=dict(Counter(w.status.values())),existing_building_intersections=overlap,
            full_nbt=[dict(pos=q,snbt=t.snbt()) for q,t in tags.items()],profiles=str(profile.resolve()),
            role='Explicit user R44 new-city expansion candidate, not permission inferred from empty space; preserve existing blocks/identity and root-only exact diff construction',world_written=False)
        summaries.append(summary);print(name,'full',summary['full_columns'],'grass quantiles',summary['grass_top_quantiles'],'foreign',summary['foreign_block_columns'],'NBT',len(tags),flush=True)
    (a.output/'survey.json').write_text(json.dumps(dict(sites=summaries,source_regional_plan=str(WORLD/'regional_plan.json'),
        source_regional_plan_sha256=hashlib.sha256((WORLD/'regional_plan.json').read_bytes()).hexdigest(),
        battle_core_preserved=dict(centre=[32,80,217],no_new_construction_within_horizontal_radius=250),world_written=False),ensure_ascii=False,indent=2),'utf8')


if __name__=='__main__':main()
