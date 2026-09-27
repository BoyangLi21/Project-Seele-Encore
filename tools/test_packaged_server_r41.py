"""Boot the actual R41 reobfuscated server batch on a disposable world copy."""
from pathlib import Path
import json,queue,shutil,subprocess,threading,time
import build_server_ready_pack as base
from release_combat_r36 import guard
ROOT=base.ROOT;OUT=ROOT/'artifacts/server-ready-r41';STAGE=OUT/'stage';TEST=OUT/'production-run'
def main():
    guard();assert not TEST.exists()
    shutil.copytree(STAGE/'server',TEST);shutil.copytree(STAGE/'world',TEST/'SEELE_R41_WORLD')
    assert 'eula=true' in (ROOT/'run/eula.txt').read_text()
    shutil.copy2(ROOT/'run/eula.txt',TEST/'eula.txt')
    p=TEST/'server.properties';s=p.read_text(encoding='utf-8-sig').replace('server-port=25565','server-port=25574').replace('view-distance=24','view-distance=8')+'\nserver-ip=127.0.0.1\n'
    p.write_text(s,encoding='utf8');(TEST/'smoke_jvm_args.txt').write_text('-Xms1G\n-Xmx4G\n-XX:+UseG1GC\n-Dfile.encoding=UTF-8\n',encoding='utf8')
    java=Path.home()/'jdks/jdk-17.0.19+10/bin/java.exe'
    command=[str(java),'@smoke_jvm_args.txt','@libraries/net/minecraftforge/forge/1.20.1-47.4.10/win_args.txt','nogui']
    proc=subprocess.Popen(command,cwd=TEST,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',bufsize=1)
    events=queue.Queue()
    def consume():
        for line in proc.stdout:events.put(line)
        events.put(None)
    threading.Thread(target=consume,daemon=True).start()
    start=time.monotonic();ready=None;stop=False;lines=[]
    with (OUT/'production_server.log').open('w',encoding='utf8') as log:
        while True:
            try:line=events.get(timeout=1)
            except queue.Empty:line=''
            if line is None:break
            if line:
                log.write(line);log.flush();lines.append(line)
                if 'Done (' in line and ready is None:
                    ready=time.monotonic();print('R41 production Forge server ready',flush=True)
                    proc.stdin.write('nerv transport status\nexecute in projectseele:geofront run time query daytime\n');proc.stdin.flush()
            if ready and not stop and time.monotonic()-ready>30:
                proc.stdin.write('stop\n');proc.stdin.flush();stop=True
            if time.monotonic()-start>600:
                if proc.poll() is None:proc.stdin.write('stop\n');proc.stdin.flush()
                try:proc.wait(timeout=45)
                except subprocess.TimeoutExpired:proc.terminate()
                raise TimeoutError('R41 dedicated server deadline')
    code=proc.wait(timeout=60);text=''.join(lines)
    checks=dict(exit_zero=code==0,forge_ready=ready is not None,seele_initialized='Project SEELE initialized' in text,clean_save='Saving chunks' in text,
        no_fatal=not any(s in text for s in ('Failed to start the minecraft server','Missing mandatory dependencies','Mixin apply failed','Exception in server tick loop','Encountered an unexpected exception')))
    jar=next((TEST/'mods').glob('projectseele-*.jar'))
    proof=dict(passed=all(checks.values()),checks=checks,mod_sha256=base.sha256(jar),scope='Actual reobfuscated R41 private JAR, Forge 47.4.10, imported formal world copy; localhost only, clean shutdown. No remote login claim.')
    (OUT/'production_check.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(proof),flush=True)
    assert proof['passed']
if __name__=='__main__':main()
