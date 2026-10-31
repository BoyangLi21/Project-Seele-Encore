"""Reconcile the complete commissioned canopies, preserving native platforms."""
import argparse,json
from pathlib import Path
from collections import defaultdict
import numpy as np
from query_blocks import iter_selected_sections,chunk_statuses,iter_block_entities
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import NATURAL

def repair(a):
    a.out.mkdir(exist_ok=False);(a.out/'source').mkdir();(a.out/'delta').mkdir()
    records=json.loads(a.contract.read_text('utf8'))['stations'];selected={}
    for r in records:
        x,y,z=r['center'];h=r['half'];dx,dz=(h+2,20)if r['horizontal']else(20,h+2)
        for cx in range((x-dx)//16,(x+dx)//16+1):
            for cz in range((z-dz)//16,(z+dz)//16+1):selected[cx,cz]=set(range(-8,20))
    statuses=chunk_statuses(a.frozen,'projectseele:geofront',selected)
    if any(s!='full'for s in statuses.values()):raise ValueError('An existing station is not completely saved')
    groups=defaultdict(dict)
    for p,sy in selected.items():groups[p[0]//32,p[1]//32][p]=sy
    for (rx,rz),chosen in groups.items():
        coords=sorted(chosen);lookup={p:i for i,p in enumerate(coords)};names=['minecraft:air'];ids={names[0]:0}
        blocks=np.zeros((len(coords),448,16,16),np.uint16)
        for cx,cz,sy,palette,values in iter_selected_sections(a.frozen,'projectseele:geofront',chosen):
            for s in palette:
                if s not in ids:ids[s]=len(names);names.append(s)
            remap=np.array([ids[s]for s in palette],np.uint16)
            blocks[lookup[cx,cz],sy*16+128:sy*16+144]=remap[values].reshape(16,16,16)
        np.savez_compressed(a.out/'source'/f'r.{rx}.{rz}.npz',coordinates=coords,blocks=blocks,palette=names)
    editor=Editor(a.out);results=[]
    shell=NATURAL|{'minecraft:light_gray_concrete','minecraft:smooth_stone','minecraft:light_gray_stained_glass',
        'minecraft:glass','minecraft:spruce_trapdoor','projectseele:clear_glass','projectseele:nerv_machine_edge',
        'projectseele:nerv_strip_light','projectseele:nerv_ceiling_light'}
    for r in records:
        x,y,z=r['center'];h=r['half'];horizontal=r['horizontal'];dx,dz=(h+2,20)if horizontal else(20,h+2)
        devices=dict(iter_block_entities(a.frozen,'projectseele:geofront',(x-dx,y+4,z-dz),(x+dx,y+13,z+dz)))
        def pos(u,Y,w):return(x+u,Y,z+w)if horizontal else(x+w,Y,z+u)
        count=0
        for u in range(-h,h+1):
            for w in range(-18,19):
                for Y in range(y+10,y+13):
                    q=pos(u,Y,w);old=editor.state(*q)
                    if q in devices:continue
                    if old.split('[')[0]not in shell:continue
                    new='minecraft:air'
                    if Y==y+11 and 4<=abs(w)<=17:new='minecraft:light_gray_concrete'
                    elif Y==y+12 and abs(w)<=3:new='projectseele:clear_glass'
                    elif Y==y+10 and ((u+h-2)%16==0 and abs(w)<=17):new='projectseele:nerv_machine_edge'
                    elif Y==y+10 and abs(w)==9 and(u+h)%12<5:new='projectseele:nerv_strip_light'
                    if old!=new:editor.put(*q,new);count+=1
        for u in range(-h+2,h,16):
            for w in(-17,17):
                for Y in range(y+4,y+10):
                    q=pos(u,Y,w)
                    if q not in devices and editor.state(*q).split('[')[0]in shell:
                        editor.put(*q,'minecraft:light_gray_concrete')
        for q in devices:
            if editor.state(*q)!=editor.state(*q,original=True):raise ValueError(('Station device changed',q))
        results.append(dict(station=r['station'],line=r['line'],center=r['center'],roof_cells=count,devices_preserved=len(devices)))
        print(r['station'],r['line'],count,flush=True)
        # Flush large regional buffers between stations without losing deltas.
        editor.save();editor.regions.clear()
    regions=editor.save()
    (a.out/'manifest.json').write_text(json.dumps(dict(world=str(a.world),regions=regions,cells=sum(r['cells']for r in regions),stations=results,world_written=False),ensure_ascii=False,indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=[],stations=len(results),native_platforms_changed=False,visual_verified=False),indent=2),'utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in('frozen','world','out','contract'):p.add_argument('--'+name,type=Path,required=True)
    repair(p.parse_args())
