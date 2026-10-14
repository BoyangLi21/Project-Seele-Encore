"""Read-only bounded measurements of the original R51-delivered complex."""
from pathlib import Path
import json
import numpy as np
from query_blocks import chunk_statuses,iter_selected_sections,iter_block_entities

BASE=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009')
WORLD=BASE/'WORLD_R52';OUT=BASE/'survey';DIM='projectseele:geofront'
BOXES={
    'headquarters_and_original_station':((-112,-490,184),(184,-276,512)),
    'terminal_complete':((-56,-647,232),(116,-516,420)),
    'original_hangar_transfer_launch':((-48,-513,-302),(114,-310,32)),
    'west_lake_context':((-240,-566,192),(32,-454,464)),
}

def measure(lo,hi):
    names=['minecraft:air'];ids={names[0]:0}
    data=np.zeros((hi[1]-lo[1]+1,hi[2]-lo[2]+1,hi[0]-lo[0]+1),np.uint16)
    selected={(x,z):set(range(lo[1]//16,hi[1]//16+1))
              for x in range(lo[0]//16,hi[0]//16+1) for z in range(lo[2]//16,hi[2]//16+1)}
    assert set(chunk_statuses(WORLD,DIM,selected).values())=={'full'}
    for cx,cz,sy,palette,indices in iter_selected_sections(WORLD,DIM,selected):
        mapping=[]
        for state in palette:
            if state not in ids:ids[state]=len(names);names.append(state)
            mapping.append(ids[state])
        values=np.asarray(mapping,np.uint16)[indices].reshape(16,16,16)
        x,y,z=cx*16,sy*16,cz*16
        a=(max(lo[0],x),max(lo[1],y),max(lo[2],z));b=(min(hi[0],x+15),min(hi[1],y+15),min(hi[2],z+15))
        data[a[1]-lo[1]:b[1]-lo[1]+1,a[2]-lo[2]:b[2]-lo[2]+1,a[0]-lo[0]:b[0]-lo[0]+1]=values[a[1]-y:b[1]-y+1,a[2]-z:b[2]-z+1,a[0]-x:b[0]-x+1]
    return data,names

def main():
    assert not OUT.exists(), 'Use the existing measurements; do not overwrite their baseline'
    OUT.mkdir();report={}
    for name,(lo,hi) in BOXES.items():
        cells,palette=measure(lo,hi)
        np.savez_compressed(OUT/(name+'.npz'),origin=lo,states=cells,palette=palette)
        devices=[dict(pos=list(p),id=str(tag['id']),nbt=tag.snbt()) for p,tag in iter_block_entities(WORLD,DIM,lo,hi)]
        (OUT/(name+'_devices.json')).write_text(json.dumps(devices,ensure_ascii=False,indent=2),'utf8')
        unique,counts=np.unique(cells,return_counts=True)
        report[name]=dict(bounds=[lo,hi],cells=int(cells.size),devices=len(devices),
            palette_counts={palette[int(i)]:int(n) for i,n in zip(unique,counts)},world_written=False)
        print(name,cells.shape,len(devices),'devices',flush=True)
    (OUT/'ORIGINAL_MEASUREMENTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')

if __name__=='__main__':main()
