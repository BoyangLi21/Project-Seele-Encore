"""Submit ordinary native client commands or capture the actual framebuffer."""
from pathlib import Path
import argparse,hashlib,json,os,time

def read(p):return json.loads(p.read_text('utf-8-sig'))
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--host',type=Path,required=True)
    ap.add_argument('--command',action='append',default=[])
    ap.add_argument('--screenshot',type=Path)
    ap.add_argument('--quit',action='store_true')
    a=ap.parse_args();host=a.host.resolve();spec=read(host/'launch.json')
    world=Path(spec['world']).resolve()
    assert world==Path('D:/eva/artifacts/map_complete_20261013/WORLD').resolve()
    assert not host.is_relative_to(world) and (host/'RUNNING.json').is_file()
    assert not (host/'RESULT.json').exists(),'The actual client has exited'
    assert read(host/'RUNNING.json')['jar_sha256']==spec['jar_sha256']
    assert len(a.command)<=8 and all(c and len(c)<256 and not any(v in c for v in '\r\n\0') for c in a.command)
    inbox=host/'commands.json';old=read(inbox);seq=int(old['seq'])+1
    document=dict(seq=seq,commands=a.command)
    if a.screenshot:
        target=a.screenshot.resolve();assert target.suffix.lower()=='.png' and not target.exists() and not target.is_relative_to(world)
        document['screenshot']=str(target)
    if a.quit:document['quit']=True
    with (host/'ROOT_SUBMISSIONS.jsonl').open('a',encoding='utf8') as f:
        f.write(json.dumps(dict(document,utc_ms=int(time.time()*1000),ordinary_network_permissions=True,function_pass_claimed=False),ensure_ascii=False)+'\n')
    temporary=inbox.with_suffix('.root.tmp');temporary.write_text(json.dumps(document,ensure_ascii=False)+'\n','utf8');os.replace(temporary,inbox)
    print(json.dumps(dict(seq=seq,submitted=True,function_pass_claimed=False),ensure_ascii=False))
if __name__=='__main__':main()
