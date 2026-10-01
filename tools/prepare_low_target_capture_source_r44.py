"""Retain actual full-body ACCAD body-punch takes as low-target task inputs.

This is a source-screening candidate, not a downed-opponent performance.
It never replaces standing punches or installs a runtime profile.
"""
from pathlib import Path
import argparse,json,sys
import prepare_combat_capture_sequence_r44 as sequence

ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--profile',type=Path,required=True);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
profile=json.loads(args.profile.read_text('utf8'))
for label in('jab','cross','hook','heavy'):
    profile['clips']['r32_'+label]=profile['clips']['r32_low_'+label]
temporary=args.out/'source_timing_profile.json';temporary.write_text(json.dumps(profile,separators=(',',':')),'utf8')
sequence.TAKES=[('guard','Male2_D1_StandToReady.bvh','l'),('jab','Male2_E16_BodyJabLeft.bvh','l'),('cross','Male2_E14_BodyCrossRight.bvh','r'),('hook','Male2_E9_BodyHookLeft.bvh','l'),('heavy','Male2_E10_BodyHookRight.bvh','r')]
# E10 is a body hook; preserve its measured horizontal target/arc instead of
# the standing vocabulary's special uppercut vertical peak rule.
original_argv=sys.argv;sys.argv=[str(Path(sequence.__file__)),'--out',str(args.out),'--profile',str(temporary),'--measured-strike-frame']
sequence.main();sys.argv=original_argv
card=json.loads((args.out/'source_card.json').read_text('utf8'));fixture=json.loads((args.out/'fixture.json').read_text('utf8'))
for segment in card['segments']:
    if segment['label']=='guard':continue
    old=segment['label'];new='low_'+old
    (args.out/'source'/(old+'.npz')).rename(args.out/'source'/(new+'.npz'));segment['label']=new
    segment['task_scope']='Actual standing body-punch full-body source. Requires independent task adaptation to actual downed receiver triangles, foot/knee/hand support, and target reaction before runtime review.'
    segment['source_semantics']='Whole actual body-punch take retained; this is not crouching or prone attack capture.'
card['quality']='UNAPPROVED low-target source screening only; no paired downed-target task solved'
fixture['source_motion_card']=card
(args.out/'source_card.json').write_text(json.dumps(card,indent=2),'utf8');(args.out/'fixture.json').write_text(json.dumps(fixture,separators=(',',':')),'utf8')
print('Actual body-punch task sources prepared',args.out,flush=True)
