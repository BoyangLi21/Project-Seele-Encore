"""Export complete declarative static masks/cargo for future chunks, never apply.

Full masks include unchanged owned AIR/support; a sparse patch is not a future
generator. Root reviews and installs relative recipe folders with its receipt.
"""
from pathlib import Path
from collections import defaultdict
import argparse,gzip,hashlib,json,shutil
import nbtlib
from plan_city_rigid_topology_r45 import packed,IRON,LINER,FLOOR,ground_hatch_state
from plan_city_private_rigid_topology_r45 import state_tag

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r45/city_motion/generation_v1')
    parser.add_argument('--topology',type=Path,default=ROOT/'artifacts/rebuild_r45/city_motion/whole_topology_v2');args=parser.parse_args()
    out=args.out.resolve();assert not out.exists();whole=args.topology.resolve();manifest=json.loads((whole/'manifest.json').read_text('utf8'))
    assert manifest['objects']==96 and manifest['full_be']==1471
    assert sorted(record['index'] for record in manifest['records'])==list(range(96))
    palette=[];ids={};shards=defaultdict(dict);grounds=defaultdict(list)
    def code(state):
        if state not in ids:ids[state]=len(palette);palette.append(state_tag(state))
        return ids[state]
    def put(q,state):shards[q[0]//16,q[2]//16][packed(q)]=code(state)
    for record in manifest['records']:
        index=record['index'];row=record['source'];generated=index<93
        cx,cy,cz=row['source_center']if generated else row['center'];half=row['half'];h=row['height'];base=19-h if generated else -61
        a,b,c,d=(-half,half,-half,half)if generated else tuple(row['footprint'][k]for k in ('MinX','MaxX','MinZ','MaxZ'))
        # Entire declared sweep, not only the currently non-air patch cells.
        for x in range(a,b+1):
            for z in range(c,d+1):
                for y in range(base,cy+h+4):put((cx+x,y,cz+z),'minecraft:air')
                put((cx+x,base-1,cz+z),LINER)
                edge=max(abs(x),abs(z))
                if generated:
                    name=ground_hatch_state(x,z,half,index>=64).partition(':')[2]
                else:name='polished_deepslate'if x in(a,b)or z in(c,d)else'iron_block'if(x-a)%5==0 or(z-c)%5==0 else'gray_concrete'
                grounds[(cx+x)//16,(cz+z)//16].append(nbtlib.Compound({'Pos':nbtlib.Long(packed((cx+x,80,cz+z))),'StateId':nbtlib.Int(code('minecraft:'+name)),'Object':nbtlib.Int(index)}))
        for y in range(base-1,80):
            for x in range(a-1,b+2):
                for z in range(c-1,d+2):
                    if x in(a-1,b+1)or z in(c-1,d+1):
                        if generated and z==d+1 and abs(x)<=1 and base+1<=y<=base+3:continue
                        put((cx+x,y,cz+z),LINER)
        for y in(20,24):
            for x in range(a-4,b+5):
                for z in range(c-4,d+5):
                    if x<a-2 or x>b+2 or z<c-2 or z>d+2:put((cx+x,y,cz+z),IRON)
            for x in range(a-3,a):put((cx+x,y,cz),IRON)
            for x in range(b+1,b+4):put((cx+x,y,cz),IRON)
            for z in range(c-3,c):put((cx,y,cz+z),IRON)
            for z in range(d+1,d+4):put((cx,y,cz+z),IRON)
        for bearing in row['overhead_bearings']:
            px,py,pz=bearing['pad_center']if generated else bearing['pad'];sx=-1 if px<cx else 1;sz=-1 if pz<cz else 1
            for x in(px,px+sx):
                for z in(pz,pz+sz):
                    for y in range(20,py+1):put((x,y,z),IRON)
            for dx in(-1,0,1):
                for dz in(-1,0,1):put((px+dx,py,pz+dz),IRON)
        # Exact final proposed non-AIR rows override generic material recipes,
        # preserving measured sidewalk choice and the original private marker.
        print(f'future mask {index+1}/96',flush=True)
    for line in gzip.open(whole/'forward.jsonl.gz','rt',encoding='utf8'):
        row=json.loads(line)
        if row['after']=='minecraft:air' or row['reason']=='complete_moving_floor_after_core_relocation' or row['reason']=='old_controller_position_becomes_operable_hatch_cover':continue
        put(tuple(row['pos']),row['after'])
    for marker in ((-110,-62,150),(151,-62,128),(144,-62,302)):put(marker,'minecraft:netherite_block')
    out.mkdir(parents=True);(out/'chunks').mkdir();(out/'cargo').mkdir();files=[]
    for record in manifest['records']:
        assert hashlib.sha256(Path(record['cargo']).read_bytes()).hexdigest()==record['sha256'],'Cargo source epoch changed; do not regenerate from stale labels'
        shutil.copyfile(record['cargo'],out/'cargo'/f"{record['index']}.dat")
    for (x,z),states in sorted(shards.items()):
        rows=nbtlib.List[nbtlib.Compound]([nbtlib.Compound({'Pos':nbtlib.Long(p),'StateId':nbtlib.Int(v)})for p,v in sorted(states.items())])
        tag=nbtlib.File({'Version':nbtlib.Int(1),'WorldUUID':nbtlib.String(manifest['world_id']),'InitialDepth':nbtlib.Int(312),
            'Palette':nbtlib.List[nbtlib.Compound](palette),'Static':rows,'Ground':nbtlib.List[nbtlib.Compound](grounds.get((x,z),[]))})
        path=out/'chunks'/f'{x}_{z}.dat';tag.save(path,gzipped=True);files.append(dict(file=path.name,cells=len(rows),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    summary=dict(schema='projectseele.city-future-generation-r45.v1',world_id=manifest['world_id'],objects=96,world_written=False,
        default_enabled=False,full_sparse_patch_not_used_as_sole_generator=True,full_static_cells=sum(f['cells']for f in files),
        topology_source=str(whole),topology_manifest_sha256=hashlib.sha256((whole/'manifest.json').read_bytes()).hexdigest(),
        topology_forward_sha256=manifest['forward_sha256'],full_cargo_sha256={str(r['index']):r['sha256'] for r in manifest['records']},
        relative_install_folder='city_rigid_generation_r45',native_future_chunk_passed=False,files=files)
    (out/'manifest.json').write_text(json.dumps(summary,indent=2),'utf8');print({k:v for k,v in summary.items()if k!='files'})


if __name__=='__main__':main()
