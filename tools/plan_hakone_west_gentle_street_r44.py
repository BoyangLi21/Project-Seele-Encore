"""Road-first feasible flat west-town pocket, grounded in full-width current soil."""
from pathlib import Path
import argparse,json,gzip,math
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from plan_new_city_blocks_r44 import SOIL,SMALL,PAVING
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists()
    w=MeasuredWorld(WORLD);w.box((-1960,65,490),(-1870,150,534));w.load();tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(-1960,65,490),(-1870,150,534),selected_chunks=set(w.selected)))
    changes={};held=[];columns={};lines=[(-1944,504,-1880,504),(-1944,520,-1880,520),(-1944,504,-1944,520)]
    owner='r44/hakone_west/new_gentle_street_loop'
    def put(q,s,reason):
        old=w.block(q)
        if old is None or q in tags or old.split('[')[0] not in SOIL|SMALL|PAVING|AIR:held.append(dict(pos=q,state=old,reason=reason));return
        s=canonical_state(s)
        if s!=old:changes[q]=(s,reason)
    for x,z,X,Z in lines:
        length=max(abs(X-x),abs(Z-z))
        for i in range(length+1):
            xx=round(x+(X-x)*i/max(1,length));zz=round(z+(Z-z)*i/max(1,length))
            for d in range(-6,7):
                q=(xx,zz+d) if z==Z else (xx+d,zz);columns[q]=dict(pos=q,height2=210,native_feet=105,carriage=abs(d)<=4,source_id=owner)
    profiles=[]
    for (x,z),col in columns.items():
        grass=[y for y in range(65,145) if (w.get(x,y,z) or '').split('[')[0]=='minecraft:grass_block']
        natural=max(grass) if grass else None
        # Old X1880 street is retained as a whole real side of the new loop.
        if x>=-1886:continue
        if natural is None:held.append(dict(pos=[x,104,z],reason='No current natural grass bearing'));continue
        profiles.append(dict(pos=[x,z],native_natural_soil=natural,proposed_road_feet=105,cut_or_fill=104-natural))
        if abs(natural-104)>6:held.append(dict(pos=[x,104,z],reason='Required earthworks exceed six metre road-first bound',actual_soil=natural));continue
        for y in range(min(natural+1,102),104):put((x,y,z),'minecraft:stone','Continuous shallow earth formation reaches real natural soil')
        put((x,104,z),'minecraft:black_concrete' if col['carriage'] else 'minecraft:smooth_stone','Whole13-column flat road/sidewalk loop, two actual existing street ports')
        for y in range(105,max(112,natural+2)):put((x,y,z),'minecraft:air','Complete road/sidewalk clearance and restrained measured earth cut')
    rows=[dict(pos=q,before=w.block(q),after=s,before_nbt=None,after_nbt=None,owner=owner,reason=r) for q,(s,r) in sorted(changes.items())]
    a.output.mkdir(parents=True)
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as f:
            for row in rows:
                r=dict(row)
                if inverse:r['before'],r['after']=row['after'],row['before']
                f.write(json.dumps(r)+'\n')
    (a.output/'road_authority.json').write_text(json.dumps(dict(columns=list(columns.values()),world_written=False),indent=2),'utf8')
    (a.output/'audit.json').write_text(json.dumps(dict(actual_ports=[[-1880,105,504],[-1880,105,520]],whole_width_columns=len(columns),
        proposed_road_grade=0,maximum_cut_or_fill_metres=max(abs(r['cut_or_fill']) for r in profiles),profiles=profiles,changed_cells=len(rows),held=held,
        world_written=False,ready=not held,native_car_turning_passed=False,landscape_passed=False,
        instruction='First verify real whole-width old ports and the complete full-size vehicle loop. Place the replacement western mixed block only beside this measured gentle corridor; preserve the south-cliff failure as rejected geometry.'),ensure_ascii=False,indent=2),'utf8')
    print('Gentle west street',len(rows),'cells',len(columns),'columns','maxcut/fill',max(abs(r['cut_or_fill']) for r in profiles),'held',len(held))


if __name__=='__main__':main()
