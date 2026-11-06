"""Read-only exact ownership comparison for the superseded near-city site."""
import gzip,json
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
from r52_spatial_plan import BASE
from query_blocks import iter_selected_sections

source=Path('D:/eva/artifacts/rebuild_r49/encounter_facilities/r50_yashima/complete_generation_source.jsonl.gz')
out=BASE/'old_yashima_retirement';out.mkdir(exist_ok=True);records=defaultdict(dict);count=Counter()
with gzip.open(source,'rt',encoding='utf8')as f:
    for line in f:
        r=json.loads(line);x,y,z=r['pos'];records[x//16,z//16,y//16][(y%16)*256+(z%16)*16+x%16]=r
selected={}
for x,z,y in records:selected.setdefault((x,z),set()).add(y)
mismatches=[];devices=[];exact=0;total=0
for x,z,y,pal,values in iter_selected_sections(BASE/'WORLD_R52','projectseele:geofront',selected):
    for index,row in records[x,z,y].items():
        actual=pal[int(values[index])];total+=1
        if actual==row['after']:exact+=1
        else:
            count[(row['after'],actual)]+=1
            if len(mismatches)<150:mismatches.append(dict(pos=row['pos'],authored=row['after'],current=actual,before=row['before']))
        if row['before_nbt']is not None or row['after_nbt']is not None:devices.append(row)
report=dict(world_written=False,source=str(source),owned_records=sum(map(len,records.values())),read_records=total,exact_current_matches=exact,mismatch_count=total-exact,mismatch_kinds=[dict(authored=a,current=b,count=n)for(a,b),n in count.most_common()],mismatch_examples=mismatches,device_records=devices,retirement_not_yet_authorized_by_this_measurement=True)
(out/'OWNERSHIP_PREFLIGHT.json').write_text(json.dumps(report,indent=2),'utf8');print({k:v for k,v in report.items()if k not in('device_records','mismatch_examples','mismatch_kinds')},flush=True)
