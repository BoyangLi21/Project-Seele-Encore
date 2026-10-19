"""Read the composed morning repair from the actual current singleplayer save."""
import argparse,gzip,hashlib,json
from collections import defaultdict
from pathlib import Path
import nbtlib
from query_blocks import read_box,iter_block_entities

def same(a,b):
    return a is b if a is None or b is None else nbtlib.parse_nbt(a)==nbtlib.parse_nbt(b)

def verify(world,base,out):
    order=('signs700','signs701','lobby704','signs707','signs708','signs709','pockets713','signs714','stair718','stair719','signs721')
    composed={};stair={}
    for folder in order:
        rows=json.loads(gzip.decompress((base/folder/'EXACT_DELTA.json.gz').read_bytes()))
        for r in rows:
            p=tuple(r['pos'])
            if p in composed:
                old=composed[p];assert old['after']==r['before'] and same(old['after_nbt'],r['before_nbt']),(folder,p,'patch chain')
                composed[p]=dict(r,before=old['before'],before_nbt=old['before_nbt'])
            else:composed[p]=r
            if folder in ('pockets713','stair718','stair719'):
                old=stair.get(p,r);stair[p]=dict(r,before=old['before'],before_nbt=old['before_nbt'])
    groups=defaultdict(list)
    for p,r in composed.items():groups[p[0]//16,p[2]//16].append(r)
    for (cx,cz),rows in groups.items():
        lo=(cx*16,min(r['pos'][1] for r in rows),cz*16);hi=(cx*16+15,max(r['pos'][1] for r in rows),cz*16+15)
        actual=read_box(world,'projectseele:geofront',lo,hi);tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi))
        for r in rows:
            p=tuple(r['pos']);assert actual[p]==r['after'],(p,'block mismatch',actual[p],r['after'])
            assert same(None if p not in tags else tags[p].snbt(),r['after_nbt']),(p,'NBT mismatch')
    effective=lambda rows:[r for r in rows if r['before']!=r['after'] or not same(r['before_nbt'],r['after_nbt'])]
    net=effective(composed.values());pocket=effective(stair.values())
    nav={}
    for name in ('nerv_routes_r24.json.gz','nearest_lift_paths_r44.json.gz','r53_personnel_walking_graph.json.gz'):
        raw=(world/name).read_bytes();nav[name]=hashlib.sha256(raw).hexdigest()
        # Installed navigation is the final pocket-retirement result.
        assert raw==(base/'pockets713/navigation'/name).read_bytes(),('navigation delivery mismatch',name)
    nearest=json.loads(gzip.decompress((world/'nearest_lift_paths_r44.json.gz').read_bytes()))
    raw=(world/'nerv_routes_r24.json.gz').read_bytes()
    assert nearest['graph_sha256']==hashlib.sha256(raw).hexdigest(),'nearest table does not match graph'
    report=dict(world=str(world),actual_readback=True,checked_cells=len(composed),net_changed_cells=len(net),final_pocket_and_seele_cells=len(pocket),navigation_file_sha256=nav,nearest_graph_sha256=nearest['graph_sha256'],world_written=False,scope='Only this morning exact block/NBT changes and matching derived navigation; does not certify all-round gameplay or all-map art.')
    out.mkdir(parents=True,exist_ok=True)
    (out/'NET_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(net,ensure_ascii=False).encode(),mtime=0))
    (out/'FINAL_POCKET_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(pocket,ensure_ascii=False).encode(),mtime=0))
    (out/'READBACK.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=Path,required=True);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();verify(a.world,a.base,a.output)
