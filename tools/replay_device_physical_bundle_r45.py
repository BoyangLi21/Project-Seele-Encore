"""Root-only25-cell stopped-QA replay using the existing writer; no default write.

Source is immutable. Capture a fresh target baseline; then explicit --apply.
Full original BE records and every file outside2 regions/1 marker are retained.
Byte rollback is allowed only before any subsequent world/progress mutation.
"""
from __future__ import annotations
import argparse,copy,gzip,hashlib,json,msvcrt,shutil,sys
from collections import defaultdict
from pathlib import Path
sys.dont_write_bytecode=True
import nbtlib,numpy as np
from audit_pyramid_components_r45 import ROOT,WORLD,read,write,sha
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,iter_selected_sections,dimension_dir
from transplant_s22_authority import read_region
from apply_s20_approved_semantic_repairs import atomic_replace
import regional_voxels as vox

SCHEMA='projectseele.device-physical-bundle-r45.v1'
IDENTITY='dimensions/projectseele/geofront/data/projectseele_tokyo3_building_world_id_r44.dat'
_ACTIVE_LOCK=None

def inventory(world):
    result={}
    for p in sorted(world.rglob('*')):
        if not p.is_file():continue
        key=p.relative_to(world).as_posix()
        if key=='session.lock' and _ACTIVE_LOCK is not None and Path(_ACTIVE_LOCK.name).resolve()==p.resolve():
            at=_ACTIVE_LOCK.tell();_ACTIVE_LOCK.seek(0);result[key]=hashlib.sha256(_ACTIVE_LOCK.read()).hexdigest();_ACTIVE_LOCK.seek(at)
        else:result[key]=sha(p)
    return result
def identity(world):
    uid=str(nbtlib.load(world/IDENTITY)['data']['WorldUUID']);data=nbtlib.load(world/'level.dat')['Data']
    return uid,int(data['WorldGenSettings']['seed'])
def target(path):
    p=path.resolve();assert p!=WORLD.resolve() and not p.is_relative_to(WORLD.resolve()),'The authoritative source is immutable'
    assert p.is_relative_to(ROOT/'artifacts/rebuild_r45') and p.name=='SEELE_FIELD_R45_REVIEW' and p.parent.name=='saves','Only an explicit isolated R45 QA save is writable'
    assert(p/'session.lock').is_file()and(p/'level.dat').is_file();return p
def external(path,world):
    p=path.resolve();assert not p.exists() and not p.is_relative_to(world) and not p.is_relative_to(WORLD) and 'saves'not in{q.lower()for q in p.parts};return p
def load_bundle(path,digest):
    assert sha(path)==digest,'Combined plan bytes changed';b=read(path);assert b['schema']==SCHEMA and b['cells']==25 and not b['navigation_or_model_install_included']
    assert sha(b['source_baseline']['path'])==b['source_baseline']['sha256']
    baseline=read(b['source_baseline']['path']);assert len(baseline['files'])==1736 and Path(baseline['source_world']).resolve()==WORLD.resolve()
    assert inventory(WORLD)=={r['relative']:r['sha256']for r in baseline['files']},'Immutable complete source epoch changed'
    assert sha(b['source_writer']['path'])==b['source_writer']['sha256'],'Writer audit no longer covers this source'
    for k in('forward','inverse','mask'):assert sha(b[k]['path'])==b[k]['sha256']
    f=[json.loads(s)for s in gzip.open(b['forward']['path'],'rt',encoding='utf8')];iv=[json.loads(s)for s in gzip.open(b['inverse']['path'],'rt',encoding='utf8')]
    assert len(f)==len(iv)==25 and len({tuple(r['pos'])for r in f})==25
    for a,c in zip(f,iv):assert a['pos']==c['pos'] and a['before_nbt']is None and a['after_nbt']is None and all(a[k]==c[v]for k,v in [('before','after'),('after','before'),('before_nbt','after_nbt'),('after_nbt','before_nbt')])
    marker=b['marker'];assert sha(marker['before_path'])==marker['before_sha256'] and sha(marker['after_path'])==marker['after_sha256']
    assert marker['relative']=='.projectseele_command_sliding_doors_r01.json';return b,f
def cells(world,rows,after=False):
    m=MeasuredWorld(world)
    for r in rows:m.around(r['pos'],0)
    m.load();assert all(v=='full'for v in m.status.values())
    chunks=set(m.selected);lo=(min(x for x,z in chunks)*16,-672,min(z for x,z in chunks)*16);hi=(max(x for x,z in chunks)*16+15,319,max(z for x,z in chunks)*16+15)
    records=[dict(pos=list(q),snbt=t.snbt())for q,t in iter_block_entities(world,'projectseele:geofront',lo,hi,selected_chunks=chunks)]
    tags={tuple(r['pos']):r['snbt']for r in records};assert len(tags)==len(records),'Duplicate native BE positions require separate investigation'
    for r in rows:
        q=tuple(r['pos']);assert m.block(q)==r['after'if after else'before'] and tags.get(q)is None,('Exact state/NBT precondition changed',q,m.block(q))
    return chunks,records
def section_hashes(world,chunks,rows=None):
    selected={q:set(range(-42,20))for q in chunks};patch=defaultdict(list)
    for r in rows or[]:patch[r['pos'][0]//16,r['pos'][1]//16,r['pos'][2]//16].append(r)
    result={}
    for cx,cz,sy,pal,idx in iter_selected_sections(world,'projectseele:geofront',selected):
        names=np.asarray(pal,dtype=object)[idx]
        for r in patch[cx,sy,cz]:
            x,y,z=r['pos'];offset=((y&15)<<8)|((z&15)<<4)|(x&15);assert names[offset]==r['before'];names[offset]=r['after']
        result[f'{cx}/{sy}/{cz}']=hashlib.sha256('\0'.join(names.tolist()).encode('utf8')).hexdigest()
    assert all(f'{x}/{y}/{z}'in result for x,y,z in patch);return result
def blob_hashes(world,regions):
    result={}
    for relative in regions:
        stamps,blobs=read_region(world/relative)
        result[relative]={str(slot):hashlib.sha256(blob).hexdigest()for slot,blob in enumerate(blobs)if blob is not None}
    return result
def preflight(world,b,rows,baseline):
    assert baseline['schema']=='projectseele.device-target-cold-baseline-r45.v1' and Path(baseline['world']).resolve()==world
    assert baseline['world_id']==b['source_world_id'] and int(baseline['world_seed'])==int(b['source_seed']) and identity(world)==(baseline['world_id'],int(baseline['world_seed']))
    assert inventory(world)==baseline['files'],'Target changed since the new stopped baseline; recapture, do not reuse a lease'
    marker=b['marker'];assert sha(world/marker['relative'])==marker['before_sha256'];return cells(world,rows)

def main(args):
    global _ACTIVE_LOCK
    world=target(args.world);out=external(args.out,world)
    # Existing lock only, no timestamp/byte replacement and no new lock file.
    with(world/'session.lock').open('r+b')as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        _ACTIVE_LOCK=lock
        try:
            if args.mode=='capture':
                uid,seed=identity(world);before=inventory(world);assert inventory(world)==before
                out.mkdir(parents=True);write(out/'target_cold_baseline.json',dict(schema='projectseele.device-target-cold-baseline-r45.v1',world=str(world),world_id=uid,world_seed=seed,files=before,world_written=False))
                print('Captured a new stopped target inventory outside the world; no world bytes written.',flush=True);return
            if args.mode=='rollback':
                receipt=read(args.receipt);assert receipt['schema']=='projectseele.device25-actual-root-apply-r45.v1' and receipt['installed'] and Path(receipt['world']).resolve()==world
                assert inventory(world)==receipt['after_files'],'World changed after replay. Do not restore region backups over gameplay/progress; recapture and audit a new inverse instead.'
                for r in receipt['backups']:assert sha(r['path'])==r['before_sha256'] and sha(world/r['relative'])==r['after_sha256']
                if not args.apply:
                    out.mkdir(parents=True);write(out/'rollback_preflight.json',dict(passed=True,world_written=False));print('Exact unchanged-epoch rollback preflight passed; --apply required.',flush=True);return
                out.mkdir(parents=True);undo=out/'after_backup';undo.mkdir()
                for i,r in enumerate(receipt['backups']):shutil.copy2(world/r['relative'],undo/f'{i:02d}.after')
                try:
                    for r in receipt['backups']:atomic_replace(world/r['relative'],Path(r['path']).read_bytes())
                    assert inventory(world)==receipt['before_files']
                except Exception:
                    for i,r in enumerate(receipt['backups']):atomic_replace(world/r['relative'],(undo/f'{i:02d}.after').read_bytes())
                    assert inventory(world)==receipt['after_files'];raise
                write(out/'rollback_receipt.json',dict(passed=True,world=str(world),exact_full_before_files_restored=True,installed=False));print('Exact no-subsequent-progress rollback verified.',flush=True);return
            b,rows=load_bundle(args.bundle,args.bundle_sha256)
            if args.mode=='readback':
                receipt=read(args.receipt);assert Path(receipt['world']).resolve()==world and receipt['bundle_sha256']==args.bundle_sha256
                assert inventory(world)==receipt['after_files'],'This is not the immediate stopped post-apply epoch'
                chunks,be=cells(world,rows,True);assert be==receipt['original_complete_BE_records']
                assert sha(world/b['marker']['relative'])==b['marker']['after_sha256']
                out.mkdir(parents=True);write(out/'readback.json',dict(passed=True,exact25_and_marker=True,complete_original_BE_records_retained=True,all_other_UUID_progress_transport_files_SHA_unchanged=True,world_written=False));print('Immediate exact25/marker/all-BE/full-file readback passed.',flush=True);return
            baseline=read(args.target_baseline);chunks,be=preflight(world,b,rows,baseline)
            expected_sections=section_hashes(world,chunks,rows)
            regions=sorted({f'dimensions/projectseele/geofront/region/r.{r["pos"][0]//512}.{r["pos"][2]//512}.mca'for r in rows})
            touched_slots={rel:{str((x&31)+(z&31)*32)for x,z in chunks if rel.endswith(f'r.{x//32}.{z//32}.mca')}for rel in regions}
            blobs=blob_hashes(world,regions);before=inventory(world)
            out.mkdir(parents=True);write(out/'strict_preflight.json',dict(passed=True,cells=25,complete_BE_records=len(be),target_baseline_sha256=sha(args.target_baseline),source_immutable=True,world_written=False))
            if not args.apply:print('Strict stopped target preflight passed; --apply required, no world bytes written.',flush=True);return
            backup=out/'before';backup.mkdir();allowed=regions+[b['marker']['relative']];saved=[]
            for i,rel in enumerate(allowed):
                p=backup/f'{i:02d}.before';shutil.copy2(world/rel,p);assert sha(p)==before[rel];saved.append(dict(relative=rel,path=str(p),before_sha256=before[rel]))
            try:
                vox.WORLD=world;vox.OUT=out/'writer';painter=vox.Painter()
                for r in rows:painter.match((*r['pos'],*r['pos']),r['before'],r['after'],r['owner'])
                painter.meta.update(exact25_bundle_sha256=args.bundle_sha256,all_before_after_NBT_null=True,no_navigation_or_model_install=True)
                raw=painter.apply('device25',session_lock=lock);assert raw['verified'] and raw['counts']['cells']==25
                # Atomic marker is part of this same stopped transaction.
                assert sha(world/b['marker']['relative'])==b['marker']['before_sha256']
                atomic_replace(world/b['marker']['relative'],Path(b['marker']['after_path']).read_bytes())
                after=inventory(world);assert set(after)==set(before)
                assert {k for k in before if before[k]!=after[k]}==set(allowed)
                assert all(after[k]==v for k,v in before.items()if k not in allowed)
                _,after_be=cells(world,rows,True);assert after_be==be,'Existing full native BE records were altered or retired'
                assert section_hashes(world,chunks)==expected_sections,'A voxel outside the exact25 mask changed'
                after_blobs=blob_hashes(world,regions)
                for rel,slots in blobs.items():
                    assert set(slots)==set(after_blobs[rel])
                    assert all(value==after_blobs[rel][slot]for slot,value in slots.items()if slot not in touched_slots[rel]),'An untouched chunk blob changed'
                assert sha(world/b['marker']['relative'])==b['marker']['after_sha256']
                for r in saved:r['after_sha256']=after[r['relative']]
                receipt=dict(schema='projectseele.device25-actual-root-apply-r45.v1',world=str(world),bundle=str(args.bundle.resolve()),bundle_sha256=args.bundle_sha256,
                    installed=True,cells=25,marker_installed=True,navigation_or_model_installed=False,before_files=before,after_files=after,backups=saved,
                    original_complete_BE_records=be,all_complete_BE_records_preserved=True,all_outside_mask_voxels_preserved=True,all_other_chunk_blobs_preserved=True,
                    all_other_UUID_seed_entities_players_NPC_transport_device_files_unchanged=True,native_verified=False,
                    rollback_requires_full_after_epoch_unchanged=True,derived_light_heightmaps_recomputed_by_existing_writer=True)
                write(out/'apply_receipt.json',receipt);print('Root exact25+marker transaction and full-NBT/identity/progress readback verified. Native gameplay still unverified.',flush=True)
            except Exception:
                for r in saved:atomic_replace(world/r['relative'],Path(r['path']).read_bytes())
                assert inventory(world)==before;raise
        finally:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);_ACTIVE_LOCK=None

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['capture','preflight','apply','readback','rollback']);p.add_argument('--world',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--bundle',type=Path);p.add_argument('--bundle-sha256');p.add_argument('--target-baseline',type=Path);p.add_argument('--receipt',type=Path);p.add_argument('--apply',action='store_true');args=p.parse_args()
    if args.mode in('preflight','apply','readback'):assert args.bundle and args.bundle_sha256
    if args.mode in('preflight','apply'):assert args.target_baseline
    if args.mode in('readback','rollback'):assert args.receipt
    if args.mode=='apply':assert args.apply,'Explicit --apply is mandatory'
    main(args)
