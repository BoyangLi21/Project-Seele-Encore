"""Fit source sole support to actual native displacement; cadence gains are candidates."""
from pathlib import Path
import argparse,collections,json
import numpy as np
from validate_combat_bundle_r44 import Pose

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44/combat'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--samples',type=Path,default=ROOT/'artifacts/rebuild_r44/network_runtime/before/server_samples.json');args=ap.parse_args()
    baseline=json.loads((ROOT/'artifacts/rebuild_r44/baseline.json').read_text('utf8'))
    local=Path(baseline['instance'])/'projectseele-local-maps';body=json.loads((local/'eva_body_r43.json').read_text('utf8'))
    records=json.loads(args.samples.read_text('utf8'));groups=collections.defaultdict(list)
    for value in records:groups[value['variant']].append(value)
    report=[]
    for key in range(5):
        raw=groups[key];segments={'walk':[],'run':[]}
        for first,last in zip(raw,raw[1:]):
            if first['entity']!=last['entity'] or first['ordinary']>=0 or last['ordinary']>=0 or not first['ground'] or not last['ground']:continue
            dt=last['tick']-first['tick'];distance=np.hypot(last['x']-first['x'],last['z']-first['z']);phase=(last['gait']-first['gait'])%1
            if dt<=0 or distance<.05 or phase<1e-5 or phase>.5:continue
            name='walk' if max(first['run'],last['run'])<.05 else 'run' if min(first['run'],last['run'])>.95 else None
            if name:segments[name].append(dict(speed=distance/dt,measured_stride=distance/phase,phase_per_tick=phase/dt))
        rig=body['rigs'][str(key)];profile=json.loads((local/f'eva_gameplay_r42_{key}.json').read_text('utf8'))
        motion=body['stance_clips_by_rig'][str(key)];support=body.get('rig_support',{}).get(str(key),body['support']);clips=[]
        for label,gain in [('walk',1.75),('run',3.5)]:
            clip=motion['clips'][label];count=len(clip['frames']);points=[];contacts=[]
            for frame in clip['frames']:
                pose=Pose(rig,motion['bones'],frame);feet=[]
                for side in ('l','r'):
                    matrix=pose.matrix('foot_'+side);vertices=np.asarray(support['foot_'+side]);world=vertices@matrix[:3,:3].T+matrix[:3,3]
                    low=world[:,1].min();patch=world[world[:,1]<=low+.3]
                    feet.append(patch.mean(0)*5/16)
                points.append(feet);contacts.append(frame.get('foot_contact',[True,True]))
            points=np.asarray(points);contacts=np.asarray(contacts,bool);phase=np.linspace(0,1,count)
            dx=np.diff(points[:,:,2],axis=0);dp=np.diff(phase)
            valid=contacts[:-1]&contacts[1:]
            # Native yaw=0 advances +Z, while the Bedrock body faces local -Z.
            ratios=dx[valid]/np.broadcast_to(dp[:,None],dx.shape)[valid]
            positive=ratios[ratios>1]
            fitted=float(np.median(positive)) if len(positive) else None
            contract=body['locomotion_contract_r43'][str(key)][label];source=float(contract['stride_blocks'])
            def slip(stride):
                world=np.diff(phase)[:,None]*stride-dx
                selected=world[valid]
                return dict(rms_blocks_per_cycle=float(np.sqrt(np.mean((selected/np.broadcast_to(dp[:,None],dx.shape)[valid])**2))),
                            median_step_drift_blocks=float(np.median(abs(selected))))
            samples=segments[label]
            speed=float(np.median([s['speed'] for s in samples])) if samples else None
            clips.append(dict(clip=label,source_stride_blocks=source,source_support_fit_stride_blocks=fitted,
                  gain=gain,gain_candidate_stride_blocks=source/gain,source_support_slip=slip(source),gain_candidate_support_slip=slip(source/gain),
                  support_fit_slip=slip(fitted) if fitted else None,native_pairs=len(samples),
                  native_median_speed_blocks_per_tick=speed,native_measured_stride_blocks=float(np.median([s['measured_stride'] for s in samples])) if samples else None,
                  native_source_cycle_seconds=source/speed/20 if speed else None,native_gain_cycle_seconds=source/gain/speed/20 if speed else None))
        report.append(dict(rig=key,clips=clips))
    result=dict(scope='Existing real server movement and source rigid-sole FK. Neither restored gain nor a sole-fit scalar is a visual acceptance decision.',
                samples=str(args.samples),rigs=report,
                limitations=['Source sole patch can roll between vertices', 'Raw stride has no guaranteed zero-sliding FK after normalized limb retarget',
                             'Guard gait uses a separate support profile', 'Actual client final-foot telemetry and visible playback remain required'])
    file=ART/'cadence_audit.json';file.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(report=str(file),rigs=report),ensure_ascii=False))


if __name__=='__main__':main()
