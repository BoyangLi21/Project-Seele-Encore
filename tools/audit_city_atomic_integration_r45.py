"""Read frozen composer databases and complete City96 inputs; never read/write a world."""
from pathlib import Path
from collections import Counter
from functools import lru_cache
import argparse, gzip, hashlib, json, sqlite3, sys, time
import nbtlib
from query_blocks import palette_state
from regional_voxels import canonical_state
from measure_city_placements_r45 import unpack_pos
from install_city_rigid_metadata_r45 import same_tag

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/rebuild_r45'
DBS=[ART/'integration_sol_followup/offline_composer_v1/runs'/n/'cells.sqlite' for n in ('real_full_20261003_v3','real_bridge_20261003_v4')]
TOPO=ART/'city_motion/whole_topology_v2'
BUNDLE=ART/'city_motion_sol_followup/install_bundle_v6'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,default=ART/'city_atomic_integration_r45');a=ap.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    inputs=[*DBS,TOPO/'manifest.json',TOPO/'forward.jsonl.gz',TOPO/'inverse.jsonl.gz',BUNDLE/'manifest.json']
    freeze={str(p):sha(p) for p in inputs}
    dbs=[sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True) for p in DBS]
    for d in dbs:d.execute('PRAGMA query_only=ON')
    @lru_cache(maxsize=24)
    def chunk(cx,cz):
        cells={}
        for d in dbs:
            for sy,off,b,a,bn,an,owner,component in d.execute('SELECT sy,off,b,a,bn,an,owner,component FROM cells WHERE cx=? AND cz=?',(cx,cz)):
                assert (sy,off) not in cells,'Frozen bridge is not disjoint from v3'
                cells[sy,off]=(b,a,bn,an,owner,component)
        return cells
    def lookup(p):
        x,y,z=p;return chunk(x//16,z//16).get((y//16,((y&15)<<8)|((z&15)<<4)|(x&15)))
    counts=Counter();pairs=Counter();samples=[];n=0;start=time.monotonic()
    def record(kind,p,city,static):
        counts[kind]+=1;pairs[(kind,static[-1])]+=1
        if kind.startswith('CONFLICT') or len(samples)<30:
            samples.append(dict(kind=kind,pos=p,city=city,static=dict(zip(('before','after','before_nbt','after_nbt','owner','component'),static))))
    with (out/'conflicts.jsonl').open('x',encoding='utf8') as conflicts,gzip.open(TOPO/'forward.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            row=json.loads(line);n+=1;s=lookup(row['pos'])
            if s:
                b,a,bn,an,owner,component=s
                kind='CONFLICT_TOPOLOGY_PRECONDITION'
                if (a,an)==(row['before'],row['before_nbt']):kind='STATIC_AFTER_EQUALS_CITY_BEFORE'
                elif (a,an)==(row['after'],row['after_nbt']):kind='CONVERGENT_AFTER_OWNER_REVIEW_REQUIRED'
                record(kind,row['pos'],row,s)
                if kind.startswith('CONFLICT'):conflicts.write(json.dumps(samples[-1],ensure_ascii=False)+'\n')
            if n%500000==0:print('city rows',n,'seconds',round(time.monotonic()-start,1),flush=True)
        assert n==2859160
        cargo_count=be_count=0
        manifest=json.loads((TOPO/'manifest.json').read_text('utf8'))
        for r in manifest['records']:
            building=nbtlib.load(r['cargo'])['data']['Buildings'][0];cx,cy,cz=unpack_pos(int(building['Centre']));base=19-int(building['Height']) if r['index']<93 else -61
            assert sha(Path(r['cargo']))==r['sha256']
            for cell in building['Cargo']:
                x,y,z=unpack_pos(int(cell['Pos']));p=(cx+x,base+y,cz+z);cargo_count+=1;be_count+='NBT' in cell;s=lookup(p)
                if not s:continue
                tag=cell.get('NBT');expected=tag.copy() if tag is not None else None
                if expected is not None:
                    for k,v in zip(('x','y','z'),p):expected[k]=nbtlib.Int(v)
                state=canonical_state(palette_state(cell['State']));same=s[1]==state and same_tag(nbtlib.parse_nbt(s[3]) if s[3] is not None else None,expected)
                kind='STATIC_PRESERVES_CARGO_FULL_NBT' if same else 'CONFLICT_COMPLETE_CARGO'
                record(kind,p,dict(index=r['index'],state=state,full_nbt=expected.snbt() if expected is not None else None),s)
                if kind.startswith('CONFLICT'):conflicts.write(json.dumps(samples[-1],ensure_ascii=False)+'\n')
        assert cargo_count==749242 and be_count==1471
        # Static additions above the underground endpoint can obstruct the full motion prism.
        # Check the complete declared envelope, including roof/feet clearance, with the same frozen keyed reader.
        for r in manifest['records']:
            building=nbtlib.load(r['cargo'])['data']['Buildings'][0];cx,cy,cz=unpack_pos(int(building['Centre']));h=int(building['Height']);half=int(building['Half'])
            footprint=building.get('R45Footprint');xmin,xmax,zmin,zmax=[int(footprint[k]) for k in ('MinX','MaxX','MinZ','MaxZ')] if footprint is not None else (-half,half,-half,half)
            low=19-h if r['index']<93 else -61;high=cy+h+3
            for xchunk in range((cx+xmin)//16,(cx+xmax)//16+1):
                for zchunk in range((cz+zmin)//16,(cz+zmax)//16+1):
                    for (sy,off),s in chunk(xchunk,zchunk).items():
                        p=(xchunk*16+(off&15),sy*16+(off>>8),zchunk*16+((off>>4)&15))
                        if cx+xmin<=p[0]<=cx+xmax and cz+zmin<=p[2]<=cz+zmax and low<=p[1]<=high:
                            kind='STATIC_CLEARS_COMPLETE_SWEEP' if s[1] in ('minecraft:air','minecraft:cave_air','minecraft:void_air') and s[3] is None else 'CONFLICT_FULL_MOTION_ENVELOPE'
                            record(kind,p,dict(index=r['index'],envelope=[cx+xmin,low,cz+zmin,cx+xmax,high,cz+zmax]),s)
                            if kind.startswith('CONFLICT'):conflicts.write(json.dumps(samples[-1],ensure_ascii=False)+'\n')
    catalog=json.loads((ART/'integration_sol_followup/offline_composer_v4/catalog.json').read_text('utf8'));meta=json.loads((BUNDLE/'manifest.json').read_text('utf8'))
    city_targets={r['target'] for r in meta['operations']}|{meta['marker_target']}
    file_overlap=[dict(component=c['id'],target=f['target']) for c in catalog['components'] if c['id'] in catalog['default_components'] for f in c.get('files',[]) if f['target'] in city_targets]
    for p in inputs:assert sha(p)==freeze[str(p)],'Frozen input drift'
    result=dict(schema='projectseele.city-atomic-integration-readonly-r45.v1',world_read=False,world_written=False,current_writer_database_read=False,frozen_inputs=freeze,topology_rows=n,cargo_cells=cargo_count,complete_BE=be_count,counts=dict(counts),per_static_component=[dict(kind=k,component=c,count=v) for (k,c),v in sorted(pairs.items())],metadata_operation_count=len(meta['operations']),metadata_target_overlaps=file_overlap,samples=samples[:50],all_conflicts_file=str(out/'conflicts.jsonl'),elapsed_seconds=time.monotonic()-start,native_all96_pass=False)
    (out/'intersection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf8');print(json.dumps({k:result[k] for k in ('topology_rows','cargo_cells','complete_BE','counts','metadata_operation_count','metadata_target_overlaps','elapsed_seconds')},indent=2))
    for d in dbs:d.close()

if __name__=='__main__':main()
