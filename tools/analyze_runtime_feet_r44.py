"""Real final-FK/submitted-foot motion, tied to the frozen source support windows."""
from pathlib import Path
import argparse,collections,json,re
import numpy as np

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r44/network_runtime'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--label',default='stride_warp_orbit');args=ap.parse_args();folder=BASE/args.label
    samples=json.loads((folder/'client_samples.json').read_text());witness=json.loads((folder/'client/runtime_witness.json').read_text())
    bundle=Path(next(x['frozen'] for x in witness if 'bundle' in x));body=json.loads((bundle/'eva_body_r44.json').read_text())
    media=json.loads((folder/'media.json').read_text());frames=json.loads((Path(media['folder'])/'frames.json').read_text())
    cameras={}
    for frame in frames:
        values=[float(v) for v in re.findall(r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?',frame.get('camera',''))]
        if len(values)==3:cameras[(frame['variant'],frame['age'])]=np.asarray(values)
    groups=collections.defaultdict(list)
    for row in samples:groups[row['variant']].append(row)
    reports=[]
    for rig,rows in groups.items():
        cameras_dist=[];discrepancies=[];foot={} ;sole=[]
        for row in rows:
            w=row.get('foot_witness',{})
            fk=w.get('final_bone_fk_world',{});actual=w.get('submitted_mesh_vertex_world',{})
            camera=cameras.get((rig,row['age']))
            for side in ('l','r'):
                if side in fk and side in actual:discrepancies.append(float(np.linalg.norm(np.asarray(fk[side])-actual[side])))
                if side in actual and camera is not None:cameras_dist.append(float(np.linalg.norm(np.asarray(actual[side])-camera)))
                if side+'_sole_clearance' in w:sole.append(float(w[side+'_sole_clearance']))
        for mode in ('walk','run'):
            arrays={side:[] for side in ('l','r')};speeds={side:[] for side in ('l','r')};gait_speeds=[]
            contract=body['locomotion_contract_r43'][str(rig)][mode];mask=contract['support_mask_r44']
            for a,b in zip(rows,rows[1:]):
                if b['age']-a['age']<1 or b['age']-a['age']>3:continue
                if a['knife_type']>=0 or b['knife_type']>=0 or a['ordinary']>=0 or b['ordinary']>=0:continue
                if mode=='walk' and not (max(a['run'],b['run'])<.05 and 45<a['age']<96):continue
                if mode=='run' and not (min(a['run'],b['run'])>.95 and 140<a['age']<205):continue
                dp=(b['gait']-a['gait'])%1;dt=b['age']-a['age']
                if dp<1e-6 or dp>.3:continue
                gait_speeds.append(dp/dt)
                first=mask[min(len(mask)-1,round((a['gait']%1)*(len(mask)-1)))];last=mask[min(len(mask)-1,round((b['gait']%1)*(len(mask)-1)))]
                for side,index in [('l',0),('r',1)]:
                    if not first[index] or not last[index]:continue
                    p=a.get('foot_witness',{}).get('submitted_mesh_vertex_world',{}).get(side);q=b.get('foot_witness',{}).get('submitted_mesh_vertex_world',{}).get(side)
                    if p is None or q is None:continue
                    delta=np.asarray(q)-p;arrays[side].append(float(np.linalg.norm(delta[[0,2]])));speeds[side].append(float(np.linalg.norm(delta[[0,2]])/dt*20))
            foot[mode]=dict(cycle_seconds=1/np.median(gait_speeds)/20 if gait_speeds else None,
                sides={s:dict(support_pairs=len(arrays[s]),horizontal_delta_p50=float(np.median(arrays[s])) if arrays[s] else None,
                              speed_blocks_per_second_p50=float(np.median(speeds[s])) if speeds[s] else None,
                              speed_blocks_per_second_p95=float(np.percentile(speeds[s],95)) if speeds[s] else None) for s in ('l','r')})
        reports.append(dict(rig=rig,world_motion=foot,
                            camera_submitted_distance=[float(min(cameras_dist)),float(max(cameras_dist))] if cameras_dist else None,
                            beyond_96m=sum(d>96 for d in cameras_dist),camera_pairs=len(cameras_dist),
                            fk_to_submitted_vertex_distance_p50=float(np.median(discrepancies)) if discrepancies else None,
                            note='FK marker and submitted mesh point are different material points; compare motion/height, never treat their fixed offset as a pose error',
                            submitted_sole_clearance_range=[float(min(sole)),float(max(sole))] if sole else None))
    result=dict(label=args.label,bundle=str(bundle),scope='Actual encoded client final-bone and CPU-submitted mesh coordinates in real network gameplay; support masks are frozen source windows, not ground contact truth',
                rigs=reports,limitations=['Phase/position clocks may differ across network interpolation','Representative mesh vertex can roll; min-sole contact needed',
                                          'GPU postprocessing and actual pixels are separate','No artistic acceptance inferred'])
    (folder/'native_foot_analysis.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__':main()
