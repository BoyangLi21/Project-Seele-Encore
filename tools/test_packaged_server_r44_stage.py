"""Bounded protocol49 reobfuscated-server smoke on one disposable stage copy.

Root must invoke explicitly. Never copies tested runtime/world state back to stage.
Optional console commands and freshly generated proof JSON can add native gates.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, os, queue, re, shutil, subprocess, threading, time
import package_r44_stage as pack
from package_release_r39 import data, read, jar
from release_combat_r36 import guard

ROOT, OUT, STAGE, WORLD = pack.ROOT, pack.OUT, pack.STAGE, pack.WORLD

def progress_snapshot(world):
    """Player/entity/SavedData/runtime progress, excluding static terrain/cache."""
    result={}
    for p in sorted(world.rglob('*')):
        if not p.is_file() or p.name.endswith('.lock'):
            continue
        rel=p.relative_to(world)
        parts=rel.parts
        if 'region' in parts or 'poi' in parts or any(s in ('logs','Review','review','screenshots') for s in parts):
            continue
        if p.name in ('level.dat','level.dat_old') or any(s in ('data','playerdata','entities','advancements','stats','mtr') for s in parts):
            result[rel.as_posix()]=pack.base.sha256(p)
    return result

def set_properties(path, updates):
    original=path.read_text(encoding='utf-8-sig').splitlines()
    keys=set(updates)
    lines=[line for line in original if line.partition('=')[0] not in keys]
    path.write_text('\n'.join(lines+['%s=%s'%(k,v) for k,v in updates.items()])+'\n',encoding='utf8')

def find_java(explicit):
    if explicit:
        path=Path(explicit)
    else:
        path=Path.home()/'jdks/jdk-17.0.19+10/bin/java.exe'
        if not path.is_file() and os.environ.get('JAVA_HOME'):
            path=Path(os.environ['JAVA_HOME'])/'bin/java.exe'
    assert path.is_file(), 'Specify an installed Java17 executable with --java'
    version=subprocess.run([str(path),'-version'],capture_output=True,text=True,encoding='utf8',errors='replace',check=True)
    assert re.search(r'version "17(?:[.\-+"]|$)',version.stdout+version.stderr), 'Minecraft Forge batch requires Java17'
    return path

def load_commands(args):
    commands=['nerv transport status','execute in projectseele:geofront run time query daytime']
    if args.commands_json:
        extra=read(args.commands_json)
        assert isinstance(extra,list) and all(isinstance(s,str) for s in extra), 'commands JSON must be a string list'
        commands.extend(extra)
    commands.extend(args.command)
    assert all(s.strip() and '\n' not in s and '\r' not in s for s in commands), 'One console command per entry'
    assert all(s.strip().lower()!='stop' for s in commands), 'The harness owns bounded shutdown'
    return commands

def proof_specs(args, test):
    specs=[dict(path=s,required_values={'passed':True}) for s in args.extra_proof]
    if args.proof_specs_json:
        supplied=read(args.proof_specs_json)
        assert isinstance(supplied,list)
        specs.extend(supplied)
    for spec in specs:
        path=Path(spec['path'].replace('{TEST}',str(test)))
        path=(path if path.is_absolute() else test/path).resolve()
        assert path.is_relative_to(test.resolve()), 'Extra proofs must be freshly generated inside this disposable run'
        assert not path.exists(), ('Stale extra proof in runtime input',path)
        spec['resolved']=str(path)
        spec.setdefault('required_values',{'passed':True})
    return specs

def collect_extra(specs, mod_sha256):
    results=[]
    for spec in specs:
        path=Path(spec['resolved'])
        row=dict(path=str(path),required_values=spec['required_values'],passed=False)
        try:
            value=read(path)
            checks={key:value.get(key)==expected for key,expected in spec['required_values'].items()}
            if 'mod_sha256' in value:
                checks['matching_mod_sha256']=value['mod_sha256']==mod_sha256
            row.update(sha256=pack.base.sha256(path),checks=checks,passed=all(checks.values()),value=value)
        except Exception as failure:
            row['error']=str(failure)
        results.append(row)
    return results

def main(args):
    guard()
    batch=pack.verify_stage()
    assert not (OUT/'production_check.json').exists(), 'Existing production evidence preserved; review/archive before another run'
    # All input paths remain read-only. The staged server already owns WORLD;
    # copy once, never copytree(stage/world, test/WORLD) a second time.
    test=OUT/('production-run-'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    assert not test.exists() and test.resolve().is_relative_to(OUT.resolve())
    assert (STAGE/'server'/WORLD/'level.dat').is_file()
    stage_before=pack.files_hash(STAGE/'server')
    protected_roots={
        'SOURCE':ROOT/'artifacts/rebuild_r44/source_world_backup',
        'COMPOSED':pack.COMPOSED,
        'STAGED_WORLD':STAGE/'world',
    }
    protected_before={name:progress_snapshot(path) for name,path in protected_roots.items()}
    shutil.copytree(STAGE/'server',test)
    actual=jar(test)
    assert pack.base.sha256(actual)==batch['mod_sha256']==pack.base.sha256(jar(STAGE/'server'))
    pack.verify_embedded_model(actual)
    assert pack.files_hash(test)==stage_before, 'Copied runtime/world differs from actual stage server'
    eula=ROOT/'run/eula.txt'
    assert re.search(r'^eula\s*=\s*true\s*$',eula.read_text(encoding='utf-8-sig'),re.M), 'Use the owner-existing EULA acceptance, never silently accept'
    shutil.copy2(eula,test/'eula.txt')
    set_properties(test/'server.properties',dict(**{'server-port':str(args.port),'server-ip':'127.0.0.1',
        'view-distance':'8','simulation-distance':'8','level-name':WORLD,'enable-rcon':'false','enable-query':'false'}))
    flags=batch['false_system_flags']
    # Copy explicit release flag values while limiting disposable-test heap.
    original_args=(test/'user_jvm_args.txt').read_text(encoding='utf8')
    assert all('-D'+flag+'=false' in original_args for flag in flags)
    enabled_review={'projectseele.r44VehicleDamageReview'} if args.vehicle_damage_review else set()
    smoke='-Xms1G\n-Xmx4G\n-XX:+UseG1GC\n-Dfile.encoding=UTF-8\n'+''.join('-D'+flag+'='+('true' if flag in enabled_review else 'false')+'\n' for flag in flags)
    assert enabled_review.issubset(flags), 'Review switch must exist in this exact built batch'
    (test/'smoke_jvm_args.txt').write_text(smoke,encoding='utf8')
    commands=[s.replace('{TEST}',str(test)) for s in load_commands(args)]
    specs=proof_specs(args,test)
    java=find_java(args.java)
    command=[str(java),'@smoke_jvm_args.txt','@libraries/net/minecraftforge/forge/1.20.1-47.4.10/win_args.txt','nogui']
    events=queue.Queue()
    proc=None;ready=None;stop_at=None;start=time.monotonic();lines=[];failure=None;timed_out=False;exit_code=None;forced=False
    log_path=test/'production_server.log'
    try:
        proc=subprocess.Popen(command,cwd=test,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
            text=True,encoding='utf8',errors='replace',bufsize=1,creationflags=subprocess.CREATE_NO_WINDOW)
        def consume():
            for line in proc.stdout:
                events.put(line)
            events.put(None)
        threading.Thread(target=consume,daemon=True).start()
        with log_path.open('w',encoding='utf8') as log:
            while True:
                try:
                    line=events.get(timeout=1)
                except queue.Empty:
                    line=''
                if line is None:
                    break
                if line:
                    log.write(line);log.flush();lines.append(line)
                    if 'Exception in server tick loop' in line and stop_at is None:
                        failure='Native server reported a fatal tick failure'
                        stop_at=time.monotonic()
                    if 'Done (' in line and ready is None:
                        ready=time.monotonic()
                        print('R44 actual packaged Forge server ready; bounded 30s run',flush=True)
                        for entry in commands:
                            proc.stdin.write(entry+'\n')
                        proc.stdin.flush()
                now=time.monotonic()
                if ready is not None and stop_at is None and now-ready>=30 and all(Path(s['resolved']).is_file() for s in specs):
                    proc.stdin.write('save-all flush\nstop\n');proc.stdin.flush();stop_at=now
                if stop_at is None and now-start>args.boot_deadline:
                    timed_out=True
                    proc.stdin.write('save-all flush\nstop\n');proc.stdin.flush();stop_at=now
                if stop_at is not None and now-stop_at>args.shutdown_deadline:
                    timed_out=True;forced=True;proc.terminate()
                    raise TimeoutError('Bounded clean shutdown deadline expired')
            exit_code=proc.wait(timeout=args.shutdown_deadline)
    except BaseException as caught:
        failure=repr(caught)
    finally:
        if proc is not None and proc.poll() is None:
            try:
                proc.stdin.write('save-all flush\nstop\n');proc.stdin.flush()
                exit_code=proc.wait(timeout=args.shutdown_deadline)
            except Exception:
                forced=True;proc.terminate()
                try: exit_code=proc.wait(timeout=15)
                except subprocess.TimeoutExpired: proc.kill();exit_code=proc.wait(timeout=15)
        elif proc is not None:
            exit_code=proc.returncode
        stage_unchanged=pack.files_hash(STAGE/'server')==stage_before
        protection={name:progress_snapshot(path)==protected_before[name] for name,path in protected_roots.items()}
        text=''.join(lines)
        extra=collect_extra(specs,batch['mod_sha256'])
        checks=dict(exit_zero=exit_code==0,forge_ready=ready is not None,seele_initialized='Project SEELE initialized' in text,
            at_least_30_seconds=ready is not None and stop_at is not None and stop_at-ready>=30,
            clean_save='Saving chunks' in text and ('Stopping server' in text or 'Saving worlds' in text),
            no_timeout_or_forced_stop=not timed_out and not forced and failure is None,
            no_fatal=not any(s in text for s in ('Failed to start the minecraft server','Missing mandatory dependencies','Mixin apply failed',
                'Exception in server tick loop','Encountered an unexpected exception','NoClassDefFoundError','NoSuchMethodError')),
            source_progress_unchanged=all(protection.values()),stage_server_bytes_unchanged=stage_unchanged,
            matching_runtime_sha256=pack.base.sha256(actual)==batch['mod_sha256'],extra_proofs_passed=all(row['passed'] for row in extra))
        proof=dict(passed=all(checks.values()),checks=checks,protocol=49,mod_sha256=batch['mod_sha256'],test=str(test),log=str(log_path),
            stage_complete_sha256=pack.base.sha256(OUT/'stage_complete.json'),world=WORLD,listen_ip='127.0.0.1',port=args.port,
            commands=commands,extra_proofs=extra,progress_protection=protection,default_review_flags_false=[f for f in flags if f not in enabled_review],test_only_enabled_flags=sorted(enabled_review),
            exception=failure,exit_code=exit_code,elapsed_seconds=round(time.monotonic()-start,2),global_complete=False,manual_acceptance='PENDING',
            scope='Actual protocol49 private reobfuscated JAR and existing stage world on one disposable full-server copy; localhost-only 30s, clean save/shutdown; no state copied back; no remote login or artistic acceptance claim.')
        pack.atomic_new_json(OUT/'production_check.json',proof)
        print(json.dumps(proof,ensure_ascii=False,indent=2),flush=True)
    assert proof['passed'], 'Actual packaged production smoke failed; inspect preserved log/proof'

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--java')
    parser.add_argument('--port',type=int,default=25574)
    parser.add_argument('--boot-deadline',type=int,default=600)
    parser.add_argument('--shutdown-deadline',type=int,default=60)
    parser.add_argument('--command',action='append',default=[])
    parser.add_argument('--commands-json',type=Path)
    parser.add_argument('--extra-proof',action='append',default=[])
    parser.add_argument('--vehicle-damage-review',action='store_true',help='Enable only the native vehicle-health fixture in the disposable copy')
    parser.add_argument('--proof-specs-json',type=Path)
    args=parser.parse_args()
    assert 1024<=args.port<=65535 and 30<=args.boot_deadline<=1200 and 15<=args.shutdown_deadline<=120
    main(args)
