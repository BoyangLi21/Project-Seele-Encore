"""Prepare current-world real factory lifecycle; never launches or copies a world."""
from pathlib import Path
import argparse,copy,json
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--template',type=Path,default=ROOT/'artifacts/rebuild_r44/space_photos/tv_upper_observation_after_v1/20261001_064916/launch.json');ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r44/combat/passenger_authority/current_factory_v1');args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
spec=json.loads(args.template.read_text('utf8'));required=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW/level.dat'
if not required.is_file():raise FileNotFoundError('Current guarded R44 review world missing; no clone or fallback allowed')
if Path(spec['workingDirectory']).resolve()!=(ROOT/'run').resolve():raise ValueError('Current run directory required')
witness=ROOT/'artifacts/rebuild_r44/space_photos/tv_cage_locked_lens_vanilla_v2/20261001_022427/r44_locked_cage_pose.jsonl';ids={}
with witness.open('r',encoding='utf8')as stream:
    for line in stream:
        row=json.loads(line);ids[row['variant']]=row['entity_uuid']
rows=[]
for variant in range(3):
    candidate=copy.deepcopy(spec);command=[x for x in candidate['command']if not x.startswith('-Dprojectseele.')]
    if '--quickPlaySingleplayer'not in command:raise ValueError('Singleplayer current-world template required')
    command[command.index('--quickPlaySingleplayer')+1]='SEELE_FIELD_R44_REVIEW'
    trace=out/f'variant_{variant}_callbacks.jsonl'
    props=dict(r44PassengerFactoryReview='true',r44PassengerFactoryVariant=str(variant),r44PassengerFactoryEvaUuid=ids[variant],
               r44PassengerWitnessPath=str(trace),r44TvCageReview='true',r44RigidMachineryGpu='true')
    command[1:1]=['-Dprojectseele.'+k+'='+v for k,v in props.items()];candidate['command']=command
    candidate['environment']['MOD_CLASSES']='projectseele%%'+str(ROOT/'build/resources/main')+';projectseele%%'+str(ROOT/'build/classes/java/main')
    file=out/f'variant_{variant}_launch_unfrozen.json';file.write_text(json.dumps(candidate,indent=2),'utf8')
    rows.append(dict(variant=variant,current_original_eva_uuid=ids[variant],launch=str(file),callback_trace=str(trace),
                     expected_plug='Runtime guard reads current saved FleetEntry.entryPlugId before any canonical lookup and requires that same original throughout'))
plan=dict(world='SEELE_FIELD_R44_REVIEW',source_guard='FactoryR20Review R44_PASSENGER uses existing R35 physical procedure with current R44 dynamic anchors and supplied original EVA UUID; old R20 fixed-frame checks are not used',
          runs=rows,workflow=['real tryBoardFromHatch','requestPrepare and actual insertion/transfer','SILO_READY→requestLaunch','DEPLOYED surface support','requestRecovery','same original PARKED capsule','real stopRiding/exit','real hatch reboard','second prepare/physical EVA→plug→pilot','cancel/return and final exit'],
          execution='Root only: compile/freeze each unfrozen launch after final source build, then launch_rendered_client_r17.py --prepared-file <frozen_launch>. Run variants separately; no parallel Minecraft or automatic world edit by this preparer.',
          report='run/saves/SEELE_FIELD_R44_REVIEW/Review/r44_passenger_factory_<variant>.json; callback stream in this directory; actual framebuffer media from existing FactoryR20Client',
          scope='Prepared only; not native or artistic PASS. UN original lifecycle remains its independent MechanicsR31Review/UNCommand route and is not implied by these three.')
(out/'current_world_lifecycle_plan.json').write_text(json.dumps(plan,indent=2),'utf8');print(json.dumps(rows,indent=2))
