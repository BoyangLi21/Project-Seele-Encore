"""Prepare the existing guarded R31 close-contact runner with native skin evidence.

This does not launch Java or modify a world. Root owns compilation, freeze and
the actual client queue. A/B keeps resources identical unless binding is named.
"""
from pathlib import Path
import argparse,json,hashlib,shutil

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('first_slot','dominant','running'),default='first_slot')
ap.add_argument('--label',required=True);ap.add_argument('--template',type=Path,default=ROOT/'.Codex/client-r42-motion-1.json')
args=ap.parse_args();out=ROOT/'artifacts/rebuild_r44/combat/native_skin_witness'/args.label
if not args.label.replace('_','').isalnum():raise ValueError('Invalid private review label')
out.mkdir(parents=True,exist_ok=False)
spec=json.loads(args.template.read_text('utf8'));command=[s for s in spec['command'] if not s.startswith('-Dprojectseele.')]
properties=['-Dprojectseele.regionalBuild=r31-combat','-Dprojectseele.combatVariant=1',
            '-Dprojectseele.r38Close=true','-Dprojectseele.combatVideo=true','-Dprojectseele.combatSideView=true',
            '-Dprojectseele.combatFieldEnergy=0','-Dprojectseele.nativeCapture=true',
            '-Dprojectseele.reviewArtifactRoot='+str(out/'native_media'),
            '-Dprojectseele.r44RiggedSkinWitnessPath='+str(out/'actual_rigged_skin.jsonl'),
            '-Dprojectseele.r44RiggedSkinWitnessFrames=480','-Dprojectseele.r44RiggedSkinWitnessTickGap=3',
            '-Dprojectseele.r44DominantSkinReview='+str(args.mode=='dominant').lower(),
            '-Dprojectseele.r44RunningSkinReview='+str(args.mode=='running').lower()]
command[1:1]=properties
world='SEELE_FIELD_R31_REVIEW'
if '--quickPlaySingleplayer' in command:command[command.index('--quickPlaySingleplayer')+1]=world
else:command.extend(['--quickPlaySingleplayer',world])
spec['command']=command
(out/'launch_unfrozen.json').write_text(json.dumps(spec,indent=2),'utf8')
plan=dict(existing_runner='tools/run_combat_review_r31.py --close-contacts --video --side-view --variant 1',
    existing_scenario='CombatR31Review CLOSE: Sachiel SHOVE/HOOK/JAB/OVERHEAD, normal non-first-battle skin; avoids authored wrap-cache bypass',
    world=world,properties=properties,source_template=str(args.template),source_template_sha256=hashlib.sha256(args.template.read_bytes()).hexdigest(),
    launch=str(out/'launch_unfrozen.json'),root_next_step='Compile current source, freeze_native_r44.freeze(spec,out/epoch) and save launch_frozen.json; then launch_rendered_client_r17.py --prepared-file that frozen file. Root alone runs this.',
    actual_output=str(out/'actual_rigged_skin.jsonl'),replay_command='python tools/replay_rigged_angel_witness_r44.py --witness '+str(out/'actual_rigged_skin.jsonl')+' --out '+str(out/'actual_skin_readback.json'),
    prototype='Separate candidate: counter_v13/bind_region/elbow_forearm_candidate/sachiel_elbow_forearm_r44.mesh.json includes inherited sole candidate; do not add it to renderer-only A/B',
    runtime_started=False,native_validated=False,artistic_acceptance=False)
(out/'native_skin_plan.json').write_text(json.dumps(plan,indent=2),'utf8')
print(json.dumps(plan,indent=2))
