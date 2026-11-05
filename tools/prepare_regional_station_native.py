"""Create station-only MTR additions in an isolated copy of preserved native data."""
import argparse,json,shutil,subprocess
from pathlib import Path

def prepare(a):
    if a.collect_only:
        collect(a);return
    a.staging.mkdir(exist_ok=False);shutil.copytree(a.candidate/'preserved-native',a.staging/'native');(a.staging/'classes').mkdir()
    repo=Path(__file__).resolve().parents[1];libs=Path.home()/'.gradle/caches/modules-2/files-2.1/org.apache.logging.log4j'
    cp=';'.join(map(str,[a.staging/'classes',a.mtr]+sorted(libs.glob('*/2.19.0/*/*.jar'))))
    out=a.candidate/'native-station';out.mkdir()
    with(out/'compile.log').open('w',encoding='utf8')as log:
        subprocess.run([str(a.java/'bin/javac.exe'),'-encoding','UTF-8','-cp',cp,'-d',str(a.staging/'classes'),str(repo/'tools/java/RegionalStationOnlyAuthor.java')],stdout=log,stderr=subprocess.STDOUT,check=True)
    with(out/'engine.log').open('w',encoding='utf8')as log:
        subprocess.run([str(a.java/'bin/java.exe'),'-cp',cp,'RegionalStationOnlyAuthor',str(a.candidate/'native-station-plan.json'),str(a.staging/'native'),str(out)],stdout=log,stderr=subprocess.STDOUT,check=True)
    collect(a)

def collect(a):
    proof=json.loads((a.candidate/'native-station/native-station-proof.json').read_text('utf8'))
    assert proof['existing_loaded_objects_exact']and abs(proof['platform_length']-48)<1e-7
    for name in proof['members']:
        rel=Path(name);src=a.staging/'native'/rel.relative_to('mtr');target=a.candidate/'after'/rel
        assert not(a.candidate/'preserved-native'/rel.relative_to('mtr')).exists()
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
    manifest=json.loads((a.candidate/'manifest.json').read_text('utf8'));manifest['native_station_pending']=False;manifest['native_additions']=proof['members']
    (a.candidate/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    print('Native station prepared:',proof['station'],'3 new native members; 48-block platform;',proof['existing_routes'],'existing routes retained.')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in('candidate','staging','java','mtr'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--collect-only',action='store_true',help='Collect an already completed isolated engine run without rerunning it.')
    prepare(p.parse_args())
