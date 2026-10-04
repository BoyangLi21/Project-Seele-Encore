"""Prepare real R45 cage cycles from the current original saved fleet."""
from pathlib import Path
import argparse,copy,hashlib,json,uuid
import nbtlib

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW'

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    spec=json.loads((ROOT/'.Codex/client-launch-r17.json').read_text('utf8'))
    saved=WORLD/'data/projectseele_eva_fleet.dat';before=hashlib.sha256(saved.read_bytes()).hexdigest()
    fleet=nbtlib.load(saved)['data']['Fleet'];entries={int(r['Variant']):r for r in fleet}
    assert set(entries)=={0,1,2},'Original three-unit fleet required'
    def identity(tag):return str(uuid.UUID(hex=''.join(f'{int(x)&0xffffffff:08x}'for x in tag)))
    rows=[]
    for variant in range(3):
        row=entries[variant];assert str(row['Phase'])=='PARKED','Preserve active progress; do not reset it to pass QA'
        candidate=copy.deepcopy(spec);command=[x for x in candidate['command']if not x.startswith('-Dprojectseele.')]
        assert '--quickPlaySingleplayer'in command
        command[command.index('--quickPlaySingleplayer')+1]=WORLD.name
        trace=out/f'variant_{variant}_callbacks.jsonl';eva=identity(row['Canonical']);plug=identity(row['EntryPlug'])
        props=dict(nativeReviewWorld=WORLD.name,r44PassengerFactoryReview='true',r44PassengerFactoryVariant=str(variant),
                   r44PassengerFactoryEvaUuid=eva,r44PassengerWitnessPath=trace.as_posix(),r44TvCageReview='true',
                   r44TvPersonnelPlatformsReview='true',r44RigidMachineryGpu='true')
        command[1:1]=[f'-Dprojectseele.{k}={v}'for k,v in props.items()];candidate['command']=command
        candidate['environment']['MOD_CLASSES']='projectseele%%'+(ROOT/'build/resources/main').as_posix()+';projectseele%%'+(ROOT/'build/classes/java/main').as_posix()
        path=out/f'variant_{variant}_launch_unfrozen.json';path.write_text(json.dumps(candidate,indent=2),'utf8')
        rows.append(dict(variant=variant,eva_uuid=eva,plug_uuid=plug,launch=str(path),callback_trace=str(trace)))
    assert hashlib.sha256(saved.read_bytes()).hexdigest()==before
    (out/'plan.json').write_text(json.dumps(dict(world=str(WORLD),fleet_sha256=before,runs=rows,world_written=False,
        native_passed=False,scope='Real existing hatch boarding, insertion/transfer, launch, recovery, exit/reboard, prepare/cancel; no surrogate fleet'),indent=2),'utf8')
    print('Prepared three original-fleet R45 factory cycles; no world write')

if __name__=='__main__':main()
