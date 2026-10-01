"""Cross-read native R44 plan preconditions through the shared frozen-save reader."""
from pathlib import Path
from collections import defaultdict
import argparse,gzip,json
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_selected_biome_sections,iter_block_entities
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'

def nbt_equal(a,b):
    if a is None or b is None:return a is None and b is None
    def ordered(t):
        if isinstance(t,dict):return nbtlib.Compound({k:ordered(v) for k,v in sorted(t.items())})
        if isinstance(t,nbtlib.List):return type(t)([ordered(v) for v in t])
        return t
    return ordered(a).snbt()==ordered(b).snbt()

def verify_blocks(path):
    with gzip.open(path,'rt',encoding='utf8') as stream:rows=[json.loads(line) for line in stream]
    w=MeasuredWorld(WORLD)
    for row in rows:w.around(row['pos'],0)
    w.load();points=[tuple(map(int,r['pos'])) for r in rows];tags={}
    if points:
        lo=tuple(min(q[i] for q in points) for i in range(3));hi=tuple(max(q[i] for q in points) for i in range(3))
        tags={q:t for q,t in iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected))}
    failures=[]
    for row,q in zip(rows,points):
        before=canonical_state(row['before']);actual=w.block(q)
        expected=nbtlib.parse_nbt(row['before_nbt']) if row.get('before_nbt') else None
        if before!=actual or not nbt_equal(expected,tags.get(q)):failures.append(dict(pos=q,expected=before,actual=actual,nbt_equal=nbt_equal(expected,tags.get(q))))
    return dict(plan=str(path),cells=len(rows),precondition_failures=failures,passed=not failures)

def verify_biomes(path):
    stem=path.name.split('.biomes',1)[0]
    native=path.with_name(stem+'.result.json')
    if native.exists() and json.loads(native.read_text('utf8')).get('per_batch_biomes_applyable') is False:
        raise RuntimeError('This is a raw batch biome plan. Apply only the unique merged_biome_plans from the final native complete manifest.')
    rows=json.loads(path.read_text('utf8'));selected=defaultdict(set)
    for row in rows:selected[tuple(row['chunk'])].add(row['section_y'])
    measured={(cx,cz,sy):tag for cx,cz,sy,tag in iter_selected_biome_sections(WORLD,'projectseele:geofront',selected)}
    failures=[]
    for row in rows:
        key=(*row['chunk'],row['section_y']);expected=nbtlib.parse_nbt(row['before_snbt']);after=nbtlib.parse_nbt(row['after_snbt'])
        assert len(row['before_names'])==len(row['after_names'])==64
        allowed=set(row['before_names'])|{'projectseele:geofront_surface','projectseele:geofront_meadow','projectseele:geofront_woodland','projectseele:geofront_highland'}
        assert all(str(p) in allowed for p in after['palette'])
        if not nbt_equal(measured.get(key),expected):failures.append(dict(section=key,reason='Exact native old biome NBT differs from frozen-save NBT'))
    return dict(plan=str(path),sections=len(rows),quart_cells=sum(len(r['quart_indices']) for r in rows),precondition_failures=failures,passed=not failures)

def main():
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);args=p.parse_args()
    native=args.plan.name.split('.forward',1)[0].split('.biomes',1)[0]
    outcome=args.plan.with_name(native+'.result.json')
    if outcome.exists():assert json.loads(outcome.read_text('utf8'))['native_preview_complete'],'Native preview failed; preserve its plan as failure evidence only'
    report=verify_biomes(args.plan) if 'biome' in args.plan.name and args.plan.suffix=='.json' else verify_blocks(args.plan)
    target=args.plan.with_name(args.plan.name+'.preflight.json');target.write_text(json.dumps(report,indent=2),'utf8')
    print({k:v if k!='precondition_failures' else len(v) for k,v in report.items()},flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
