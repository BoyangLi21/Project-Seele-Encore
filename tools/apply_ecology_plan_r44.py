"""Parent-only strict replay of exact R44 native blocks and biome-section NBT.

No default write. --apply is intended for the root's single-writer queue after
the server stops. The shared voxel writer and existing region writer supply
backups, atomic replacement and native-state readback; no Anvil parser exists
in this tool. UUID, entity, player, NPC and transport files are never copied.
"""
from pathlib import Path
from collections import defaultdict
import argparse,copy,gzip,json,shutil,time,msvcrt
import nbtlib
import regional_voxels as vox
from validate_ecology_plans_r44 import verify_blocks,verify_biomes,nbt_equal
from query_blocks import iter_selected_biome_sections,dimension_dir
from transplant_s22_authority import read_region,parse_chunk,build_region,chunk_blob
from apply_s20_approved_semantic_repairs import atomic_replace

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';OUT=ROOT/'artifacts/rebuild_r44/ecology'

def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--blocks',type=Path);p.add_argument('--biomes',type=Path);p.add_argument('--apply',action='store_true');args=p.parse_args()
    assert args.name.replace('_','').replace('-','').isalnum();assert args.blocks or args.biomes
    if args.apply:
        from release_combat_r36 import guard
        guard()
    outcomes=[]
    if args.blocks:outcomes.append(verify_blocks(args.blocks))
    if args.biomes:outcomes.append(verify_biomes(args.biomes))
    assert all(r['passed'] for r in outcomes),'State/full-NBT precondition differs; do not force a stale plan'
    if args.blocks:
        with gzip.open(args.blocks,'rt',encoding='utf8') as stream:blocks=[json.loads(s) for s in stream]
    else:blocks=[]
    biomes=json.loads(args.biomes.read_text('utf8')) if args.biomes else []
    assert len({tuple(r['pos']) for r in blocks})==len(blocks),'Merge duplicate cell plans explicitly before replay'
    assert len({(*r['chunk'],r['section_y']) for r in biomes})==len(biomes),'Duplicate biome section'
    name=args.name;folder=OUT/('replay_'+name);folder.mkdir(parents=True,exist_ok=True)
    (folder/'preflight.json').write_text(json.dumps(outcomes,indent=2),'utf8')
    vox.WORLD=WORLD;vox.OUT=folder;painter=vox.Painter()
    for row in blocks:
        q=tuple(map(int,row['pos']));painter.match((*q,*q),row['before'],row['after'],row['owner'])
        before=nbtlib.parse_nbt(row['before_nbt']) if row.get('before_nbt') else None
        after=nbtlib.parse_nbt(row['after_nbt']) if row.get('after_nbt') else None
        if after is not None:
            if row['before']==row['after']:painter.update_block_entity(q,row['before'],before,after,row['owner'])
            else:painter.block_entities[q]=after
    painter.meta.update(native_plan=args.blocks.as_posix() if args.blocks else None,strict_preflight=True,full_nbt=True,biome_section_plan=args.biomes.as_posix() if args.biomes else None,
        progress_files_migrated=False,world_uuid_isolation='Exact SEELE_FIELD_R44_REVIEW path and existing session lock; per-region backups and each cell inverse')
    painter.save_plan(name)
    if not args.apply:
        print('Strict dry replay preflight',len(blocks),'block cells',len(biomes),'biome sections; world unchanged',flush=True);return
    lock=(WORLD/'session.lock').open('r+b');msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        # Recheck while the single-writer lock is held, before either phase.
        if args.blocks:assert verify_blocks(args.blocks)['passed']
        if args.biomes:assert verify_biomes(args.biomes)['passed']
        blocks_receipt=painter.apply(name,session_lock=lock) if blocks else None
        stamp=time.strftime('%Y%m%d_%H%M%S');journal=folder/('biome_applied_'+stamp);journal.mkdir();(journal/'before').mkdir()
        grouped=defaultdict(list)
        for row in biomes:grouped[row['chunk'][0]//32,row['chunk'][1]//32].append(row)
        for (rx,rz),rows in sorted(grouped.items()):
            selected=defaultdict(set)
            for row in rows:selected[tuple(row['chunk'])].add(row['section_y'])
            measured={(cx,cz,sy):tag for cx,cz,sy,tag in iter_selected_biome_sections(WORLD,'projectseele:geofront',selected)}
            for row in rows:assert nbt_equal(measured[(*row['chunk'],row['section_y'])],nbtlib.parse_nbt(row['before_snbt']))
            path=dimension_dir(WORLD,'projectseele:geofront')/f'region/r.{rx}.{rz}.mca';shutil.copy2(path,journal/'before'/path.name)
            stamps,blobs=read_region(path)
            by_chunk=defaultdict(list)
            for row in rows:by_chunk[tuple(row['chunk'])].append(row)
            for (cx,cz),changes in by_chunk.items():
                slot=(cx&31)+(cz&31)*32;root=parse_chunk(blobs[slot]);sections={int(s['Y']):s for s in root['sections']}
                for row in changes:sections[row['section_y']]['biomes']=nbtlib.parse_nbt(row['after_snbt'])
                blobs[slot]=chunk_blob(root)
            atomic_replace(path,build_region(stamps,blobs))
        selected=defaultdict(set)
        for row in biomes:selected[tuple(row['chunk'])].add(row['section_y'])
        actual={(cx,cz,sy):tag for cx,cz,sy,tag in iter_selected_biome_sections(WORLD,'projectseele:geofront',selected)}
        assert all(nbt_equal(actual[(*r['chunk'],r['section_y'])],nbtlib.parse_nbt(r['after_snbt'])) for r in biomes)
        receipt=dict(block_cells=len(blocks),biome_sections=len(biomes),biome_quarts=sum(len(r['quart_indices']) for r in biomes),verified=True,
            forward_blocks=str(args.blocks),forward_biomes=str(args.biomes),world=str(WORLD),entity_player_npc_transport_files_changed=False)
        (journal/'receipt.json').write_text(json.dumps(receipt,indent=2),'utf8');print(receipt,flush=True)
    finally:
        msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':main()
