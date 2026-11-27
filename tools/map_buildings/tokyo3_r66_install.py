"""Publish a checked overlay into a stopped copy. Dry-run by default; resumable with a distinct backup folder."""
import argparse,contextlib,hashlib,json,os,shutil,sys
from pathlib import Path
from private_cleanup import DATA,control
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from install_r53_carrier_trays import stopped_world

def sha(f):
    if not f.is_file():return None
    with f.open('rb')as s:return hashlib.file_digest(s,'sha256').hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('world',type=Path);p.add_argument('overlay',type=Path);p.add_argument('backup',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args()
    w,o,b=map(Path.resolve,[a.world,a.overlay,a.backup])
    if w==b or w in b.parents or b in w.parents or o==b or o in b.parents or b in o.parents:raise SystemExit('choose separate overlay/backup/world paths')
    m=json.loads((o/'manifest.json').read_text('utf8'));rows=dict(m['data'])
    for n,hashes in m['regions'].items():rows[(DATA.parent/'region'/n).as_posix()]=hashes
    # Cold staging snapshots frequently omit vanilla's advisory lock file.
    # Create the normal lock marker exclusively so a concurrently opened save
    # still has to win the same OS byte-range lock.
    if not (w/'session.lock').exists():
        try:
            with (w/'session.lock').open('xb') as lock:lock.write('☃'.encode('utf8'))
        except FileExistsError:pass
    with stopped_world(w):
        state=control(w)
        if state['phase']!='IDLE' or (state['uuid'],state['depth'],state['current'][0],state['previous'][0])!=(m['world_uuid'],m['depth'],m['current_trip'],m['previous_trip']):raise SystemExit('city endpoint or journal changed; regenerate the overlay on this stopped world')
        pending=[];done=0
        for name,h in rows.items():
            rel=Path(name)
            if rel.is_absolute() or '..' in rel.parts or not (w/rel).resolve().is_relative_to(w):raise ValueError('invalid path '+name)
            if sha(o/rel)!=h['output']:raise ValueError('changed overlay '+name)
            current=sha(w/rel)
            if current==h['output']:done+=1;continue
            if current!=h['input']:raise ValueError('world changed since stage; regenerate overlay: '+name)
            if (b/rel).exists() and sha(b/rel)!=h['input']:raise ValueError('backup already belongs to another source: '+name)
            pending.append((rel,h))
        print('Checked',len(rows),'files;',len(pending),'pending;',done,'already current.')
        if not a.apply:return
        b.mkdir(parents=True,exist_ok=True);marker=b/'overlay-manifest.json'
        if marker.exists() and marker.read_bytes()!=(o/'manifest.json').read_bytes():raise ValueError('backup belongs to another overlay')
        if not marker.exists():shutil.copyfile(o/'manifest.json',marker)
        for rel,h in pending:
            dst=w/rel;back=b/rel
            if dst.is_file() and not back.exists():
                back.parent.mkdir(parents=True,exist_ok=True);scratch=back.with_name(back.name+'.r66-partial');shutil.copyfile(dst,scratch);os.replace(scratch,back)
            dst.parent.mkdir(parents=True,exist_ok=True);tmp=dst.with_name(dst.name+'.r66-partial');shutil.copyfile(o/rel,tmp)
            if sha(tmp)!=h['output']:raise IOError(str(tmp))
            os.replace(tmp,dst)
        assert all(sha(w/name)==h['output'] for name,h in rows.items())
        print('Installed and verified',len(rows),'files.')
if __name__=='__main__':main()
