"""Summarize actual gait timing/layer discontinuities without claiming art approval."""
from pathlib import Path
import argparse,json
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--media',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
assert not a.out.exists()
data=json.loads((a.media/'body_layers_r40.json').read_text('utf8'))['samples'];events=[];sources={}
for s in data:
    if 20<=s['review_tick']<135:
        v=s.get('actual_support_ownership',{}).get('actual_signal_samples_r45',{}).get('gait',{}).get('source','unrecorded')
        sources[v]=sources.get(v,0)+1
for first,last in zip(data,data[1:]):
    dt=last['tick']+last['partial']-first['tick']-first['partial']
    if not 0<dt<=3 or not 20<=first['review_tick']<135 or not 20<=last['review_tick']<135:continue
    for layer in ['source_clip','terrain','ground','feet','final']:
        for bone in ['leg_l','leg_r','shin_l','shin_r','foot_l','foot_r','arm_l','arm_r','forearm_l','forearm_r']:
            if bone not in first['layers'][layer]or bone not in last['layers'][layer]:continue
            qa=np.asarray(first['layers'][layer][bone]['quaternion_xyzw']);qb=np.asarray(last['layers'][layer][bone]['quaternion_xyzw'])
            dot=abs(qa@qb)/(np.linalg.norm(qa)*np.linalg.norm(qb));angle=float(2*np.degrees(np.arccos(np.clip(dot,0,1))))
            events.append(dict(layer=layer,bone=bone,angle=angle,source_dt_ticks=dt,
                from_review_tick=first['review_tick'],to_review_tick=last['review_tick'],
                gait=[first['gait'],last['gait']],move=[first['move_blend'],last['move_blend']],run=[first['run_blend'],last['run_blend']]))
report=dict(media=str(a.media.resolve()),scope='Actual recorded adjacent samples during continuous walk/run/turn segment20..134; no art pass or velocity limit inferred',
    signal_sources=sources,render_samples=len(data),layers={},largest_events=sorted(events,key=lambda x:-x['angle'])[:15],art_accepted=False)
for layer in ['source_clip','terrain','ground','feet','final']:
    values=[r['angle']for r in events if r['layer']==layer]
    report['layers'][layer]=dict(maximum_degrees=max(values),p95_degrees=float(np.percentile(values,95)),sample_count=len(values))
a.out.write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(dict(signal_sources=sources,layers=report['layers']),indent=2))
