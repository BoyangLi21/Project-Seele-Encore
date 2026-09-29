"""Space cleanup with explicit ownership, bounded paths and recoverable cold sources."""
from pathlib import Path
from collections import defaultdict
import argparse,datetime,hashlib,json,os,re,shutil,time,zipfile

ROOT=Path(__file__).resolve().parents[1].resolve();OUT=ROOT/'artifacts/repair_r43/cleanup'
CUTOFF=datetime.datetime(2026,9,28).timestamp()
KEEP_WORLDS={'SEELE_FIELD_R31_REVIEW','SEELE_FIELD_R43_REVIEW','SEELE_R43_TRAVEL_REVIEW'}

def safe(p):
    actual=p.resolve(strict=True)
    if actual==ROOT or not actual.is_relative_to(ROOT):raise ValueError(('Outside workspace',str(p),str(actual)))
    for parent in [p,*p.parents]:
        if parent==ROOT:break
        if parent.is_symlink() or parent.is_junction():raise ValueError(('Reparse point',str(parent)))
    return actual
def size(p):
    if p.is_file():return p.stat().st_size
    total=0
    for parent,dirs,files in os.walk(p,followlinks=False):
        for name in dirs:
            q=Path(parent)/name
            if q.is_junction() or q.is_symlink():raise ValueError(('Nested reparse point',str(q)))
        for name in files:total+=(Path(parent)/name).stat().st_size
    return total
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as stream:
        for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def plan():
    OUT.mkdir(parents=True,exist_ok=True);remove={};archive={}
    protected={str((ROOT/name).resolve()) for name in json.loads((ROOT/'artifacts/facility_r31/baseline.json').read_text('utf-8-sig'))['original_user_files']}
    def add(p,reason):
        if not p.exists() or str(p.resolve()) in protected:return
        safe(p);remove[str(p)]=dict(path=str(p),bytes=size(p),reason=reason,directory=p.is_dir())
    for p in (ROOT/'artifacts').glob('server-ready*'):
        if not p.is_dir() or p.is_junction():continue
        add(p/'production-run','Disposable packaged-server boot copy; parent logs and checks retained')
        m=re.fullmatch(r'server-ready-r(\d+)',p.name)
        if p.name=='server-ready' or m and int(m.group(1))<42:
            add(p/'stage','Superseded release expansion; R42 rollback and current R43 stage retained')
            for f in p.glob('*.zip'):add(f,'Superseded distribution archive; release record and original world backups retained')
    for p in ROOT.glob('start_eva_test*.bat'):
        if p.name not in {'start_eva_test_r42.bat','start_eva_test_r43.bat'}:add(p,'Obsolete revision launcher')
    for name in ('visual-run.err.log','visual-run.out.log','forge-1.20.1-47.4.10-installer.jar.log','MUJOCO_LOG.TXT'):add(ROOT/name,'Temporary root execution log')
    for p in (ROOT/'run/saves').iterdir():
        if p.is_dir() and re.search(r'(?:^|_)REVIEW(?:_|$)',p.name) and p.name not in KEEP_WORLDS and p.stat().st_mtime<CUTOFF:
            add(p,'Old disposable review world; actual played saves and current review fixtures retained')
    for base in (ROOT/'results',ROOT/'artifacts/motion_research/third_party/ProtoMotions/results'):
        if not base.exists():continue
        for folder in base.iterdir():
            if not folder.is_dir():continue
            scores=list(folder.glob('score_based.ckpt'));last=list(folder.glob('last.ckpt'))
            if not scores or not last:continue
            for p in folder.glob('epoch_*.ckpt'):add(p,'Intermediate training checkpoint; best score, last checkpoint, configs and logs retained')
    # Automatic historical image sequences are reproducible output, not source
    # models. Keep evenly spaced evidence and every named overview/summary.
    capture_roots=[ROOT/'run/screenshots'/name for name in ('projectseele_connected','projectseele_foundation','projectseele_visual')]
    for base in capture_roots:
        if not base.exists():continue
        for parent,dirs,files in os.walk(base):
            p=Path(parent);images=sorted(p/n for n in files if re.fullmatch(r'(?:frame|contact)_\d+\.(?:png|jpg)',n,re.I))
            if len(images)<40 or max(f.stat().st_mtime for f in images)>=CUTOFF:continue
            keep={images[round(i*(len(images)-1)/15)] for i in range(16)}
            for f in images:
                if f not in keep:add(f,'Superseded automatic frame sequence; 16 distributed frames and all audit/video files retained')
    motion=ROOT/'artifacts/motion_research';series=defaultdict(list)
    for p in motion.rglob('*.blend'):
        if p.stat().st_mtime<CUTOFF:series[p.relative_to(motion).parts[0]].append(p)
    newest={p for rows in series.values() for p in sorted(rows,key=lambda p:p.stat().st_mtime,reverse=True)[:2]}
    for rows in series.values():
        for p in rows:
            if p in newest or any(q.lower() in {'source','original','originals'} for q in p.relative_to(motion).parts):continue
            safe(p);archive[str(p)]=dict(path=str(p),bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns,reason='Cold generated Blender experiment; source bytes retained in verified archive')
    for p in motion.rglob('*.blend1'):
        if p.stat().st_mtime<CUTOFF:
            safe(p);archive[str(p)]=dict(path=str(p),bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns,reason='Old Blender autosave retained in cold source archive')
    # Full-region undo snapshots are highly repetitive. Keep the complete NBT
    # bytes compressed, plus the original per-cell inverse and receipt files.
    for top in (ROOT/'artifacts').iterdir():
        if not top.is_dir() or top.is_junction() or top.name in {'rebuild_r42','repair_r43'}:continue
        for receipt in top.rglob('receipt.json'):
            folder=receipt.parent;before=folder/'before'
            if not before.is_dir() or not (folder/'delta').is_dir() or not (folder/'block_entity_deltas.json').is_file():continue
            for p in before.rglob('*.mca'):
                if p.stat().st_mtime>=CUTOFF:continue
                safe(p);archive[str(p)]=dict(path=str(p),bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns,reason='Cold full-region undo snapshot; exact NBT archived, inverse cell tables kept in place')
    # Remove nested entries when their disposable parent is already selected.
    selected=[]
    for row in sorted(remove.values(),key=lambda r:len(Path(r['path']).parts)):
        if not any(Path(row['path']).is_relative_to(Path(p['path'])) for p in selected if p['directory']):selected.append(row)
    archive=[r for r in archive.values() if not any(Path(r['path']).is_relative_to(Path(p['path'])) for p in selected if p['directory'])]
    result=dict(created=datetime.datetime.now().isoformat(),remove=selected,archive=archive,protected='Actual played worlds, original assets, current R43 evidence, R42 rollback, current runtime and inverse patch tables')
    (OUT/'plan.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('Delete',len(selected),'items',round(sum(r['bytes'] for r in selected)/2**30,2),'GiB; archive',len(archive),'files',round(sum(r['bytes'] for r in archive)/2**30,2),'GiB',flush=True)

def apply_delete():
    from release_combat_r36 import guard
    guard();plan=json.loads((OUT/'plan.json').read_text());journal=OUT/'deleted.jsonl';freed=0
    with journal.open('a',encoding='utf8') as stream:
        for row in plan['remove']:
            p=Path(row['path'])
            if not p.exists():continue
            safe(p);assert size(p)==row['bytes'],('Candidate changed since plan',str(p))
            if p.is_dir():shutil.rmtree(p)
            else:p.unlink()
            freed+=row['bytes'];stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush()
    print('Deleted confirmed obsolete output',round(freed/2**30,3),'GiB',flush=True)

def archive_cold():
    plan=json.loads((OUT/'plan.json').read_text());target=ROOT/'backups/Retired_Experiment_Sources_20260929.zip';assert not target.exists()
    rows=plan['archive'];manifest=[]
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for i,row in enumerate(rows):
            p=Path(row['path']);safe(p);s=p.stat();assert s.st_size==row['bytes'] and s.st_mtime_ns==row['mtime_ns'],p
            name=p.relative_to(ROOT).as_posix();digest=hashlib.sha256()
            with p.open('rb') as source,z.open(name,'w',force_zip64=True) as destination:
                for block in iter(lambda:source.read(1024*1024),b''):destination.write(block);digest.update(block)
            manifest.append({**row,'member':name,'sha256':digest.hexdigest()})
            if i%30==0:print('Archived',i+1,'/',len(rows),'files',flush=True)
        z.writestr('SOURCE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(target) as z:assert z.testzip() is None,'Cold archive CRC validation failed'
    removed=0
    for row in manifest:
        p=Path(row['path']);safe(p);assert p.stat().st_size==row['bytes'] and p.stat().st_mtime_ns==row['mtime_ns'],p
        p.unlink();removed+=row['bytes']
    result=dict(archive=str(target),archive_bytes=target.stat().st_size,source_bytes=removed,net_freed_bytes=removed-target.stat().st_size,files=len(manifest),manifest=manifest)
    (OUT/'cold_archive.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');print('Verified cold archive; net freed',round(result['net_freed_bytes']/2**30,3),'GiB',flush=True)

def delete_historical_frames():
    rows=json.loads((OUT/'historical_frames.json').read_text());freed=0;count=0
    with (OUT/'deleted_historical_frames.jsonl').open('a',encoding='utf8') as journal:
        for row in rows:
            p=Path(row['path'])
            if not p.exists():continue
            safe(p);s=p.stat()
            assert s.st_size==row['bytes'] and s.st_mtime_ns==row['mtime_ns'] and s.st_mtime<CUTOFF,p
            assert p.is_relative_to(ROOT/'artifacts') and re.fullmatch(r'(?:frame|contact)_\d+\.(?:png|jpg)',p.name,re.I)
            p.unlink();journal.write(json.dumps(row)+'\n');freed+=row['bytes'];count+=1
            if count%10000==0:journal.flush();print('Removed historical frames',count,flush=True)
    print('Removed',count,'old intermediate frames; freed',round(freed/2**30,3),'GiB',flush=True)

def restore(member):
    archive=ROOT/'backups/Retired_Experiment_Sources_20260929.zip';target=ROOT/member
    assert target.resolve().is_relative_to(ROOT) and not target.exists()
    with zipfile.ZipFile(archive) as z:
        rows=json.loads(z.read('SOURCE_MANIFEST.json'));row=next(r for r in rows if r['member']==member)
        target.parent.mkdir(parents=True,exist_ok=True)
        with z.open(member) as source,target.open('xb') as destination:shutil.copyfileobj(source,destination,1024*1024)
    assert sha(target)==row['sha256'];print('Restored exact source bytes:',target)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['plan','delete','archive','restore','frames-delete']);p.add_argument('--member');a=p.parse_args()
    if a.action=='restore':restore(a.member)
    else:{'plan':plan,'delete':apply_delete,'archive':archive_cold,'frames-delete':delete_historical_frames}[a.action]()
