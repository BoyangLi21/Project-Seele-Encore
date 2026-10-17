"""Keep the full inherited LCL lift-to-station landing in old-well cleanup."""
from pathlib import Path
import gzip,json,msvcrt
import nbtlib
from repair_r53_reported_landings import apply
from retire_r53_old_yashima_platform import packed
from apply_s20_approved_semantic_repairs import parse_state
B=Path('F:/eva/artifacts/r53_repair_20261015');W=B/'client/saves/SEELE_R53_WORLD';O=B/'station-port254'
rows=[]
for r in json.loads(gzip.decompress((B/'reported-exteriors250/EXACT_DELTA.json.gz').read_bytes())):
    x,y,z=r['pos']
    if 89<=x<=120 and -447<=y<=-437 and -64<=z<=12:
        rows.append(dict(pos=r['pos'],before=r['after'],after=r['before'],before_nbt=r.get('after_nbt'),after_nbt=r.get('before_nbt'),reason='retain_original_complete_station_lift_interface'))
O.mkdir(exist_ok=True);(O/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(),mtime=0));apply(W,O)
with (W/'session.lock').open('r+b') as lock:
    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    data=W/'dimensions/projectseele/geofront/data';top=nbtlib.load(next(data.glob('projectseele_city_rigid_topology_r45_*.dat')))['data'];folder=data/str(top['GenerationFolder'])/'chunks';groups={}
    for r in rows:groups.setdefault((r['pos'][0]//16,r['pos'][2]//16),[]).append(r)
    for (x,z),batch in groups.items():
        p=folder/f'{x}_{z}.dat'
        if not p.exists():continue
        d=nbtlib.load(p);entries={int(v['Pos']):v for v in d['Static']};pal=d['Palette'];ids={v.snbt():i for i,v in enumerate(pal)}
        for r in batch:
            old=entries.get(packed(r['pos']))
            if old is None:continue
            s=parse_state(r['after']);k=s.snbt()
            if k not in ids:ids[k]=len(pal);pal.append(s)
            old['StateId']=nbtlib.Int(ids[k])
        d.save(p,gzipped=True)
print('Retained station connection cells:',len(rows))
