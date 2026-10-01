"""Convert a regenerated original-baseline city to exact CURRENT-state repair only."""
from pathlib import Path
import argparse,gzip,json,hashlib,shutil,math
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def same_native_payload(first,second):
    if first is None or second is None:return first==second
    a,b=nbtlib.parse_nbt(first),nbtlib.parse_nbt(second)
    # Chunk serialization adds keepPacked=0 after native load. Compare that
    # one proven engine bookkeeping field semantically; the exact full actual
    # SNBT still remains in the delta BEFORE and inverse AFTER without loss.
    for tag in [a,b]:
        if tag.get('keepPacked')==nbtlib.Byte(0):tag.pop('keepPacked',None)
        if str(tag.get('id',''))=='minecraft:sign':
            for face in ['front_text','back_text']:
                if face in tag:
                    tag[face]['messages']=nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps(json.loads(str(message)),ensure_ascii=False,sort_keys=True,separators=(',',':'))) for message in tag[face]['messages']])
    return a==b


def main():
    p=argparse.ArgumentParser();p.add_argument('installed',type=Path);p.add_argument('regenerated',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists()
    old=[json.loads(s) for s in gzip.open(a.installed/'forward.jsonl.gz','rt',encoding='utf8')];new=[json.loads(s) for s in gzip.open(a.regenerated/'forward.jsonl.gz','rt',encoding='utf8')]
    original={tuple(r['pos']):r for r in old};desired={tuple(r['pos']):(r['after'],r.get('after_nbt'),r['owner'],r['reason']) for r in new}
    for q,r in original.items():desired.setdefault(q,(r['before'],r.get('before_nbt'),r['owner'],'Regenerated city explicitly retires this old geometry; original exact state is the desired replacement'))
    w=MeasuredWorld(WORLD)
    for q in desired:w.around(q,0)
    w.load();lo=tuple(min(q[i] for q in desired) for i in range(3));hi=tuple(max(q[i] for q in desired) for i in range(3));tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    held=[];rows=[]
    for q,(state,nbt,owner,reason) in sorted(desired.items()):
        current=w.block(q);tag=tags[q].snbt() if q in tags else None
        source=original.get(q)
        if source and (current!=source['after'] or not same_native_payload(tag,source.get('after_nbt'))):
            held.append(dict(pos=q,expected_installed=source['after'],current=current,expected_nbt=source.get('after_nbt'),current_nbt=tag));continue
        if current==state and same_native_payload(tag,nbt):continue
        rows.append(dict(pos=q,before=current,after=state,before_nbt=tag,after_nbt=nbt,owner=owner,reason=reason))
    assert not held,('Installed city changed independently; root must resolve before a repair',held[:8])
    a.output.mkdir(parents=True)
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as f:
            for row in rows:
                r=dict(row)
                if inverse:r['before'],r['after']=row['after'],row['before'];r['before_nbt'],r['after_nbt']=row['after_nbt'],row['before_nbt']
                f.write(json.dumps(r,ensure_ascii=False)+'\n')
    for name in ['new_district.json','native_cases.json','road_authority.json','ecology_reservations.json']:
        shutil.copy2(a.regenerated/name,a.output/name)
    source_audit=json.loads((a.regenerated/'audit.json').read_text('utf8'));source_audit.update(changed_cells=len(rows),exact_current_repair_only=True,world_written=False,ready=False)
    (a.output/'audit.json').write_text(json.dumps(source_audit,ensure_ascii=False,indent=2),'utf8')
    (a.output/'delta_provenance.json').write_text(json.dumps(dict(installed=str(a.installed.resolve()),installed_forward_sha256=sha(a.installed/'forward.jsonl.gz'),regenerated=str(a.regenerated.resolve()),regenerated_forward_sha256=sha(a.regenerated/'forward.jsonl.gz'),
        exact_current_cells=len(rows),full_nbt_inverse=True,world_written=False,full_original_city_reapply_allowed=False,
        interpretation='Only current installed blocks/NBT differing from the corrected deterministic target are included. Regeneration uses original BEFORE states as a virtual baseline; no world copy or write.'),indent=2),'utf8')
    print('Installed city exact repair delta',len(rows),'cells; no whole-city replay; world unchanged',flush=True)


if __name__=='__main__':main()
