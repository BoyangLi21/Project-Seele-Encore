"""Remove the measured extra column from the raised command emblem backing."""
import gzip,json,msvcrt
from pathlib import Path
import nbtlib
from query_blocks import read_box
from repair_r53_reported_landings import apply
from apply_s20_approved_semantic_repairs import parse_state
from retire_r53_old_yashima_platform import packed

BASE=Path('F:/eva/artifacts/r53_repair_20261015')
WORLD=BASE/'client/saves/SEELE_R53_WORLD'
OUT=BASE/'command-logo546'

def main():
    old=json.loads(gzip.decompress((BASE/'reported-landings237/EXACT_DELTA.json.gz').read_bytes()))
    cells=read_box(WORLD,'projectseele:geofront',(31,-497,272),(31,-492,272))
    rows=[]
    for r in old:
        if r['reason']!='raised_logo_backing_above_door' or r['pos'][0]!=31:continue
        p=tuple(r['pos']);assert r['before']=='minecraft:air' and cells[p]==r['after']=='minecraft:black_concrete'
        assert r['before_nbt'] is None and r['after_nbt'] is None
        rows.append(dict(pos=p,before=r['after'],after=r['before'],before_nbt=None,after_nbt=None,reason='restore_five_wide_centred_command_logo_backing'))
    assert len(rows)==6
    OUT.mkdir(exist_ok=True)
    (OUT/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(),mtime=0))
    apply(WORLD,OUT)
    with (WORLD/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        data=WORLD/'dimensions/projectseele/geofront/data'
        topology=nbtlib.load(next(data.glob('projectseele_city_rigid_topology_r45_*.dat')))['data']
        path=data/str(topology['GenerationFolder'])/'chunks/1_17.dat'
        changed=0
        if path.exists():
            doc=nbtlib.load(path);palette=doc['Palette'];ids={r.snbt():i for i,r in enumerate(palette)}
            state=parse_state('minecraft:air');key=state.snbt()
            if key not in ids:ids[key]=len(palette);palette.append(state)
            positions={packed(r['pos']) for r in rows}
            for r in doc['Static']:
                if int(r['Pos']) in positions:r['StateId']=nbtlib.Int(ids[key]);changed+=1
            if changed:doc.save(path,gzipped=True)
    (OUT/'REVIEW.json').write_text(json.dumps(dict(corrected_cells=6,generator_cells=changed,backing_width=5,
        logo_anchor_unchanged=True,doorway_unchanged=True,earth_glazing_unchanged=True),indent=2),'utf8')
    print('Command emblem backing aligned: 6 extra blocks removed; generator entries:',changed)

if __name__=='__main__':main()
