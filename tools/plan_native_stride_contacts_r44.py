"""Explicit five-rig speed/cycle/stride targets; no playback-speed-only install."""
from pathlib import Path
import argparse,json,hashlib

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/combat'
baseline=OUT/'cadence_audit.json';old=json.loads(baseline.read_text('utf8'))
ap=argparse.ArgumentParser();ap.add_argument('--source-card',type=Path);ap.add_argument('--output',type=Path,default=OUT/'five_native_stride_contact_plan.json');args=ap.parse_args()
source=json.loads(args.source_card.read_text('utf8')) if args.source_card else None
periods={r['label']:r['original_window_seconds'] for r in source['segments']if r['label']in('walk','run')}if source else dict(walk=1.25,run=1.15)
rows=[]
for rig in old['rigs']:
    for clip in rig['clips']:
        seconds=periods[clip['clip']]
        velocity=clip['native_median_speed_blocks_per_tick']
        stride=velocity*20*seconds if velocity is not None else None
        rows.append(dict(variant=rig['rig'],clip=clip['clip'],actual_old_native_speed_blocks_per_tick=velocity,
                         actual_old_source_stride_blocks=clip['source_stride_blocks'],actual_old_cycle_seconds=clip['native_source_cycle_seconds'],
                         target_source_cycle_seconds=seconds,geometry_target_cycle_travel_blocks=stride,
                         old_native_pairs=clip['native_pairs'],status='Measured old denominator; new exact compiled epoch and actual sole vertices must be recaptured before runtime promotion'))
latest=dict(variant=1,run_observed_blocks_per_tick=2.102,older_run_blocks_per_tick=3.146,
            candidate_cycle_travel_at_new_observed_velocity=2.102*20*periods['run'],
            issue='1.5x speed difference between original and stride_world_anchors persists; do not overwrite balance or infer the other four new velocities from it')
plan=dict(old_native_source=old['samples'],old_report_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),rigs=rows,latest_discrepancy=latest,source_timing_card=str(args.source_card)if args.source_card else None,source_cadence_preserved=source is not None,
    required_authoring='One phase owns actual entity travel, pelvis COM, source foot stance/swing, toe/heel rollover and step sounds. Retarget source root horizontal travel and explicit touchdown-to-touchdown sole goals to the per-rig stride, then solve actual full-mesh anatomical IK. Do not multiply phase gain while retaining the old 58/104-block stance path.',
    native_denominator=['Each of five rigs straight walk/run at stable actual velocity and synchronization, with stand→start→walk/run→brake',
        'Actual client final foot vertices + world-static planted contact patch and entity displacement at same tick/partial; heel/toe roll classified separately',
        'Walk-run blended transition, turning, slopes/steps, air/land; world support slip and named pelvis/knee/ankle matrices',
        'Server-authoritative versus local-pilot movement speed 1.5x contrast with identical input/material/synchronization; attribute values recorded'],
    runtime_installed=False,numerical_target_is_visual_acceptance=False)
args.output.write_text(json.dumps(plan,indent=2),'utf8')
print(json.dumps(rows,indent=2))
