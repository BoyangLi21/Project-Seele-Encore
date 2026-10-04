"""Extract first/max native deviation and actual collision-stage transitions."""
from pathlib import Path
import argparse,json,hashlib
from collections import defaultdict


def main():
    parser=argparse.ArgumentParser();parser.add_argument('report',type=Path);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    report=json.loads(args.report.read_text('utf8'));trace=report.get('physics_trace',[])
    if not trace:raise ValueError('Original report has only aggregate max; cannot invent first/max tick or actor physics. Run a trace epoch.')
    grouped=defaultdict(dict)
    for row in trace:grouped[int(row['game_time'])][row['stage']]=row
    end=[v['server_end']for _,v in sorted(grouped.items())if'server_end'in v]
    first=next((r for r in end if r['absolute_feet_error']>.35),None)
    maximum=max(end,key=lambda r:r['absolute_feet_error'])
    times={r['game_time']for r in (first,maximum)if r}
    windows=[]
    for time in sorted(times):
        windows.append(dict(focus_game_time=time,ticks=[dict(game_time=t,stages=grouped[t])for t in sorted(grouped)if time-6<=t<=time+6]))
    out_ticks=[r for r in end if r['phase']=='OUT']
    phase_errors={phase:max(r['absolute_feet_error']for r in end if r['phase']==phase)for phase in sorted({r['phase']for r in end})}
    def transitions(row):
        rows=grouped.get(row['game_time'],{})
        before=rows.get('after_controller_before_stock_collision');after=rows.get('after_stock_collision')
        if not before or not after:return None
        return dict(actor_y_correction=after['actual_y']-before['actual_y'],before_velocity=before['actor_velocity'],after_velocity=after['actor_velocity'],
            before_on_ground=before['actor_on_ground'],after_on_ground=after['actor_on_ground'],entity_velocity=before['entity_velocity'])
    result=dict(schema='projectseele.city-native-physics-analysis-r45.v1',source=str(args.report.resolve()),source_sha256=hashlib.sha256(args.report.read_bytes()).hexdigest(),
        full_native_trace=True,threshold=.35,threshold_changed=False,first_over_threshold=first,maximum=maximum,
        first_transition=transitions(first)if first else None,maximum_transition=transitions(maximum),
        phase_max_errors=phase_errors,first_16_out_steps=out_ticks[:16],windows=windows,
        interpretation='Native stage positions/velocities are evidence. Gravity or event-order causation requires comparing constant and C1 epochs; no actor teleport or threshold relaxation.')
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2),'utf8')
    print(json.dumps({k:v for k,v in result.items()if k not in('windows','first_16_out_steps','interpretation')},indent=2))


if __name__=='__main__':main()
