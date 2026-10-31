"""Join commissioned city streets to their measured surrounding carriageways."""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import NATURAL
from hakone_earthworks import road_blocks


def author(a):
    a.out.mkdir(exist_ok=False);(a.out/'source').mkdir();(a.out/'delta').mkdir()
    for f in (a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    for f in (a.base/'delta').glob('*.npz'):shutil.copy2(f,a.out/'delta'/f.name)
    e=Editor(a.out)
    # Actual existing road nodes on both sides. The short ramps reuse the
    # unfinished handoff spaces; station halls and launch mouths stay intact.
    routes=[('west',[(-310,280),(-321,280)],80,83),
            ('south',[(-70,680),(-70,696),(-90,696)],80,80),
            ('east',[(290,200),(294,200),(294,192)],80,79),
            ('north',[(-110,40),(-124,40),(-124,22)],80,82)]
    paving={'minecraft:black_concrete','minecraft:white_concrete','minecraft:gray_concrete','minecraft:smooth_stone',
            'projectseele:road_asphalt_slab','projectseele:road_marking_slab','minecraft:polished_blackstone_slab','minecraft:stone_brick_stairs',
            'projectseele:station_tactile_warning','projectseele:station_tactile_path'}
    report=[]
    for name,anchors,first,last in routes:
        for (x,z),y in [(anchors[0],first),(anchors[-1],last)]:
            if e.state(x,y,z).split('[')[0]not in paving:raise ValueError(('Unmeasured carriageway endpoint',name,x,y,z,e.state(x,y,z)))
        path=[]
        for (x,z),(X,Z)in zip(anchors,anchors[1:]):
            n=max(abs(X-x),abs(Z-z));path.extend((round(x+(X-x)*t/n),round(z+(Z-z)*t/n))for t in range(n))
        path.append(anchors[-1]);grades=np.rint(np.linspace(first*2,last*2,len(path))).astype(int)
        cells={};dist={};centre={q:i for i,q in enumerate(path)}
        for i,(x,z)in enumerate(path):
            for dx in range(-4,5):
                for dz in range(-4,5):
                    q=x+dx,z+dz;d=max(abs(dx),abs(dz))
                    if d<dist.get(q,99):cells[q]=int(grades[centre.get(q,i)]);dist[q]=d
        counts=0
        for (x,z),grade in cells.items():
            y,slab=map(int,road_blocks(np.array(grade)))
            # All current non-natural objects in the full road envelope are
            # retained as explicit obstacles, never silently carved away.
            for Y in range(y-1,y+5):
                s=e.state(x,Y,z).split('[')[0]
                if Y<=y and s=='minecraft:light_gray_concrete':continue
                if s not in NATURAL|paving|{'minecraft:yellow_terracotta','minecraft:yellow_concrete'}:
                    raise ValueError(('Street handoff reaches actual structure',name,x,Y,z,s))
            floor='minecraft:smooth_stone'if dist[x,z]>2 else'minecraft:gray_concrete'
            if slab:floor='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'if dist[x,z]>2 else'projectseele:road_asphalt_slab[type=bottom,waterlogged=false]'
            e.put(x,y-1,z,'minecraft:stone');e.put(x,y,z,floor)
            for Y in range(y+1,y+5):e.put(x,Y,z,'minecraft:air')
            counts+=1
        for i,(x,z)in enumerate(path):
            y,slab=map(int,road_blocks(np.array(grades[i])))
            if i%12<5:e.put(x,y,z,'projectseele:road_marking_slab[type=bottom,waterlogged=false]'if slab else'minecraft:white_concrete')
        report.append(dict(id=name,path=[[x,float(g)/2,z]for (x,z),g in zip(path,grades)],width=9,cells=counts))
    regions=e.save();manifest=json.loads((a.base/'manifest.json').read_text('utf8'))
    manifest.update(regions=regions,cells=sum(r['cells']for r in regions),road_interfaces=report)
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=['Final terrain and recipes pending'],interfaces=report),indent=2),'utf8')
    print('Four complete nine-block street interfaces prepared',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in('source','base','out'):p.add_argument('--'+name,type=Path,required=True)
    author(p.parse_args())
