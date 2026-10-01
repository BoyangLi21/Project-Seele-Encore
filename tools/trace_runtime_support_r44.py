"""Classify real submitted-foot discontinuities, without claiming visual pass."""
from pathlib import Path
import argparse,collections,json
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r44/network_runtime'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--label',default='stride_world_anchors');args=ap.parse_args();folder=BASE/args.label
    rows=json.loads((folder/'client_samples.json').read_text('utf8'));w=json.loads((folder/'client/runtime_witness.json').read_text('utf8'))
    bundle=Path(next(x['frozen'] for x in w if 'bundle' in x));body=json.loads((bundle/'eva_body_r44.json').read_text('utf8'));groups=collections.defaultdict(list)
    for row in rows:groups[row['variant']].append(row)
    summaries=[];events=[];floors=[]
    for rig,items in groups.items():
        contracts=body['locomotion_contract_r43'][str(rig)];source={};stats=collections.defaultdict(list)
        for mode in ('walk','run'):
            mask=contracts[mode]['support_mask_r44'];episodes={}
            for side,index in [('l',0),('r',1)]:
                on=np.asarray(mask,bool)[:,index];starts=np.flatnonzero(on&~np.roll(on,1));spans=[]
                for start in starts:
                    span=1
                    while span<len(on) and on[(start+span)%len(on)]:span+=1
                    spans.append(dict(begin=round(start/(len(on)-1),5),end=round((start+span)/(len(on)-1),5),width=round(span/(len(on)-1),5)))
                episodes[side]=dict(fraction=float(on.mean()),episodes=spans)
            source[mode]=episodes
        for row in items:
            mode='knife' if row['knife_type']>=0 else 'ordinary' if row['ordinary']>=0 else 'run' if row['run']>.95 else 'walk' if row['age']<96 and row['run']<.05 else 'transition_or_idle'
            foot=row.get('foot_witness',{});phase=row['gait']%1
            for side,index in [('l',0),('r',1)]:
                value=foot.get(side+'_sole_clearance')
                if value is None:continue
                stats[(mode,side)].append(value)
                if value<-.25:
                    source_mode='run' if row['run']>.5 else 'walk';mask=contracts[source_mode]['support_mask_r44'];plant=mask[min(len(mask)-1,round(phase*(len(mask)-1)))][index]
                    floors.append(dict(rig=rig,age=row['age'],mode=mode,side=side,clearance=value,source_plant=plant,phase=phase,run=row['run'],knife_phase=row['knife_phase']))
        for a,b in zip(items,items[1:]):
            dt=b['age']-a['age']
            if not 1<=dt<=3:continue
            if a['knife_type']>=0 or b['knife_type']>=0 or a['ordinary']>=0 or b['ordinary']>=0:continue
            for side,index in [('l',0),('r',1)]:
                p=a['foot_witness'].get('submitted_mesh_vertex_world',{}).get(side);q=b['foot_witness'].get('submitted_mesh_vertex_world',{}).get(side)
                if p is None or q is None:continue
                delta=np.asarray(q)-p;length=float(np.linalg.norm(delta[[0,2]]))
                if length<.5:continue
                mode='run' if min(a['run'],b['run'])>.95 else 'walk' if max(a['run'],b['run'])<.05 else 'blend'
                masks=contracts['run' if mode=='run' else 'walk']['support_mask_r44'];plant=[masks[min(len(masks)-1,round((x['gait']%1)*(len(masks)-1)))][index] for x in (a,b)]
                events.append(dict(rig=rig,ages=[a['age'],b['age']],side=side,mode=mode,phase=[a['gait']%1,b['gait']%1],plant=plant,
                    delta=delta.tolist(),horizontal_delta=length,entity_delta=[b['x']-a['x'],b['y']-a['y'],b['z']-a['z']],run=[a['run'],b['run']]))
        summaries.append(dict(rig=rig,source_support=source,sole_by_state={mode+'_'+side:dict(count=len(v),minimum=min(v),p50=float(np.median(v)),p95=float(np.percentile(v,95)))for (mode,side),v in stats.items()}))
    result=dict(label=args.label,bundle=str(bundle),rigs=summaries,large_events=events,below_ground=floors,
        limits='Actual synchronized CONTACTS active/plant data not present in this epoch; source masks alone cannot identify server anchor ownership.')
    (folder/'support_trace.json').write_text(json.dumps(result,indent=2),'utf8')
    print(json.dumps(dict(rigs=summaries,largest_events=sorted(events,key=lambda r:r['horizontal_delta'],reverse=True)[:24],worst_floor=sorted(floors,key=lambda r:r['clearance'])[:20]),indent=2))


if __name__=='__main__':main()
