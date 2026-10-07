"""Extend a finished civil candidate's future AIR mask without writing its world."""
from pathlib import Path
from collections import defaultdict
import argparse,gzip,json
import nbtlib
from query_blocks import iter_box_cells,AIR,chunk_statuses
from inspect_map_assets import palette_state

def packed(p):
    x,y,z=p;n=((x&67108863)<<38)|((z&67108863)<<12)|(y&4095)
    return n-(1<<64) if n>=1<<63 else n
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--candidate',type=Path,required=True);args=ap.parse_args()
    candidate=args.candidate.resolve();source=candidate/'complete_generation_source.jsonl.gz'
    manifest_path=candidate/'generation_recipe/file_patch.json';manifest=json.loads(manifest_path.read_text('utf8'))
    if manifest.get('dorsal_airborne_envelope_explicit'):print('Already extended');return
    selected={(x,z)for x in range(1525//16,1735//16+1)for z in range(580//16,790//16+1)}
    assert set(chunk_statuses(args.world,'projectseele:geofront',selected).values())=={'full'}
    groups=defaultdict(list)
    for p,s in iter_box_cells(args.world,'projectseele:geofront',(1525,63,580),(1735,85,790)):
        if (p[0]-1630)**2+(p[2]-685)**2>105**2:continue
        assert s in AIR,('Original sea airborne volume is not clear',p,s)
        groups[p[0]//16,p[2]//16].append((p,s))
    operations={Path(op['after_file']).stem:op for op in manifest['operations']}
    temporary=source.with_name('complete_generation_source.extending.jsonl.gz');temporary.write_bytes(source.read_bytes())
    with gzip.open(temporary,'at',encoding='utf8')as stream:
        for (cx,cz),points in sorted(groups.items()):
            op=operations[f'{cx}_{cz}'];target=Path(op['after_file']);doc=nbtlib.load(target);palette=doc['Palette']
            air_id=next((i for i,r in enumerate(palette)if palette_state(r)=='minecraft:air'),None)
            if air_id is None:air_id=len(palette);palette.append(nbtlib.Compound({'Name':nbtlib.String('minecraft:air')}))
            cells={int(r['Pos']):r for r in doc['Static']}
            for p,s in points:
                cells[packed(p)]=nbtlib.Compound({'Pos':nbtlib.Long(packed(p)),'StateId':nbtlib.Int(air_id)})
                stream.write(json.dumps(dict(pos=list(p),before=s,after='minecraft:air',before_nbt=None,after_nbt=None,owner='r50_complete_generation',reason='Complete dorsal/attack airborne envelope above original water; future generation only'),ensure_ascii=False)+'\n')
            doc['Static']=nbtlib.List[nbtlib.Compound]([cells[k]for k in sorted(cells)]);doc.save(target,gzipped=True)
            op['changed_cells']+=len(points);op['complete_desired_cells']=op['changed_cells']
    temporary.replace(source);added=sum(map(len,groups.values()))
    manifest['changed_cells']+=added;manifest['complete_desired_cells']+=added
    manifest['dorsal_airborne_envelope_explicit']=True;manifest['unchanged_airborne_cells_added']=added
    manifest_path.write_text(json.dumps(manifest,indent=2),'utf8')
    print('Extended future generation by',added,'unchanged airborne AIR cells; no world patch or world writes')
if __name__=='__main__':main()
