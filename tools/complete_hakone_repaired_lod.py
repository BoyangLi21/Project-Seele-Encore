"""Wait for a native LOD import, stop its isolated server, install the cache."""
import argparse,json,sqlite3,time,subprocess,sys
from pathlib import Path

def complete(a):
    expected=len(json.loads((a.export/'export.json').read_text('utf8'))['exported']);deadline=time.monotonic()+1200;previous=None
    while True:
        if time.monotonic()>deadline:raise TimeoutError('Native saved-column import incomplete')
        try:r=json.loads((a.export/'columns/native-import.json').read_text('utf8'))
        except(FileNotFoundError,json.JSONDecodeError):time.sleep(2);continue
        if r['completed']!=previous:print('Imported',r['completed'],'/',expected,flush=True);previous=r['completed']
        if r['done']:
            if r['completed']!=expected or r['total']!=expected:raise ValueError('Imported tile set mismatch')
            break
        time.sleep(2)
    previous=None;quiet_since=None
    while True:
        if time.monotonic()>deadline:raise TimeoutError('Distant hierarchy incomplete')
        with sqlite3.connect((a.cache/'dimensions/projectseele/geofront/data/DistantHorizons.sqlite').resolve().as_uri()+'?mode=ro',uri=True)as db:pending=db.execute('select count(*) from FullData where ApplyToParent=1 or ApplyToChildren=1').fetchone()[0]
        if pending==0:
            if quiet_since is None:quiet_since=time.monotonic()
            if time.monotonic()-quiet_since>=20:break
        else:quiet_since=None
        if pending!=previous:print('Hierarchy pending',pending,flush=True);previous=pending
        time.sleep(2)
    subprocess.run([str(a.java),'-cp',str(a.repo/'.Codex/native1023'),'R53ReadOnlyAttach1023',str(a.pid),str(a.repo/'.Codex/cache-stop-r55.jar'),str(a.cache)+'|'+str(a.export/'cache-stop-final.json')],check=True)
    subprocess.run(['powershell','-NoProfile','-Command',f'Wait-Process -Id {a.pid} -ErrorAction SilentlyContinue'],creationflags=subprocess.CREATE_NO_WINDOW,check=False)
    (a.export/'cache-stop.json').write_bytes((a.export/'cache-stop-final.json').read_bytes())
    subprocess.run([sys.executable,str(a.repo/'tools/install_hakone_lod_cache.py'),'--world',str(a.world),'--cache',str(a.cache),'--export',str(a.export),'--out',str(a.out)],check=True)
    print('Distant cache installed after ordinary stop and zero parent/child queues',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('world','cache','export','out','repo','java'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--pid',type=int,required=True);complete(p.parse_args())
