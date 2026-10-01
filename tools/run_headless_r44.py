"""Run one named native author or guarded quality job in the single construction save."""
from pathlib import Path
import argparse,json,subprocess,threading,time
from release_combat_r36 import guard
from launch_rendered_client_r17 import java_environment
from freeze_native_r44 import freeze

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44';WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('job',choices=('ecology','interiors','future','towers','buildings'));parser.add_argument('input',type=Path);parser.add_argument('--timeout',type=int,default=600);parser.add_argument('--profile',action='store_true');parser.add_argument('--drain-ticks',type=int,default=200);parser.add_argument('--expiring-bootstrap',action='store_true');args=parser.parse_args();guard();assert 0<=args.drain_ticks<=2400
    target=args.input.resolve()
    if args.job=='interiors':target.mkdir(parents=True,exist_ok=True)
    assert target.exists()
    marker=target/'audit.json' if args.job=='interiors' else target.with_name(target.name+'.complete.json')
    if args.job=='towers' and json.loads(target.read_text('utf8'))['mode']=='interrupt':
        marker=target.with_name(target.name+'.checkpoint.json')
    error_marker=target/'failed.json' if args.job=='interiors' else target.with_name(target.name+'.failed.json')
    assert not marker.exists() and not error_marker.exists(), 'Preserve the earlier result; create a named new input attempt'
    output=ART/'native_authors'/args.job/time.strftime('%Y%m%d_%H%M%S');output.mkdir(parents=True)
    spec=json.loads((ART.parent/'repair_r43/moving_devices/native_dry_route/launch.json').read_text('utf8'))
    command=[s for s in spec['command'] if not s.startswith('-Dprojectseele.') and not s.startswith(('-Xmx','-Xms'))]
    property_name={'ecology':'r44EcologyJob','interiors':'r44TokyoInteriorPlan','future':'r44EcologyFutureJob','towers':'r44TokyoQualityJob','buildings':'r44RegionalBuildingQualityJob'}[args.job]
    command[1:1]=['-Xms512M','-Xmx4G','-Dprojectseele.'+property_name+'='+target.as_posix()]
    if args.expiring_bootstrap:command[1:1]=['-Dprojectseele.r44ExpiringVehicleBootstrap=true']
    if args.profile:
        command[1:1]=['-XX:StartFlightRecording=filename='+str((output/'native_author.jfr').resolve())+',settings=profile,dumponexit=true,maxsize=128m',
            '-Dprojectseele.r44ChunkTicketTrace='+(output/'chunk_tickets.json').resolve().as_posix()]
    command[command.index('--world')+1]=WORLD.name;spec['command']=command
    spec=freeze(spec,output);(output/'launch.json').write_text(json.dumps(spec),'utf8')
    if target.is_file():(output/'input_snapshot.json').write_bytes(target.read_bytes())
    def quote(s):return '"'+s.replace('\\','\\\\').replace('"','\\"')+'"'
    argfile=output/'launch.args';argfile.write_text('\n'.join(quote(s) for s in command[1:]),'utf8')
    env=java_environment()[1];env.update(spec['environment'])
    completed=threading.Event();failure=threading.Event();operation_error=''
    with (output/'server.log').open('w',encoding='utf8') as log:
        process=subprocess.Popen([command[0],'@'+str(argfile.resolve())],cwd=spec['workingDirectory'],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
        def read():
            for line in process.stdout:
                log.write(line);log.flush()
                if ('R44 ecology dry-run complete' in line or 'R44 central tower interior plans complete' in line):completed.set()
                if ('Ecology dry run failed' in line or 'R44 interior planning failed' in line):failure.set();completed.set()
        worker=threading.Thread(target=read,daemon=True);worker.start()
        try:
            began=time.time()
            while not completed.wait(1):
                if marker.exists() and marker.stat().st_mtime>=began:completed.set();break
                if error_marker and error_marker.exists() and error_marker.stat().st_mtime>=began:failure.set();completed.set();break
                if process.poll() is not None:raise RuntimeError('Native author exited before completion: '+str(output))
                if time.time()-began>args.timeout:raise TimeoutError('Native author exceeded its budget: '+str(output))
            assert not failure.is_set(),'Native author failed; preserve its first error'
            if args.profile:
                trace=output/'chunk_tickets.json'
                initial=json.loads(trace.read_text('utf8'))['samples'][-1]['trace_age']
                drain_began=time.time()
                while True:
                    current=json.loads(trace.read_text('utf8'))['samples'][-1]['trace_age']
                    if current-initial>=args.drain_ticks:break
                    if process.poll() is not None or time.time()-drain_began>max(90,args.drain_ticks*.15):
                        raise RuntimeError('Post-author live ticket drain did not complete')
                    time.sleep(1)
                (output/'drain_scope.json').write_text(json.dumps(dict(start_trace_age=initial,end_trace_age=current,
                    seconds=time.time()-drain_began,forced_gc=False,scope='Ordinary server ticks after dry-run export; no ticket removal or extra chunk loading'),indent=2),'utf8')
        except Exception as error:
            operation_error=repr(error);failure.set()
        finally:
            if process.poll() is None:
                process.stdin.write('stop\n');process.stdin.flush()
                try:process.wait(timeout=60)
                except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=15)
            worker.join(timeout=5)
    (output/'result.json').write_text(json.dumps(dict(completed=completed.is_set(),failure=failure.is_set(),error=operation_error,exit_code=process.returncode,job=args.job,input=str(target)),indent=2),'utf8')
    assert completed.is_set() and not failure.is_set() and process.returncode==0, operation_error or str(error_marker)
    if args.job in ('towers','buildings'):
        proof=json.loads(marker.read_text('utf8'));(output/'native_result.json').write_bytes(marker.read_bytes())
        assert proof.get('passed',False),proof
    print('Completed native job:',output,flush=True)

if __name__=='__main__':main()
