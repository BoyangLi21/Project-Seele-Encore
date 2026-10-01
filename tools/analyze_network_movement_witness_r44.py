"""Compare actual old/new native samples without inferring unsampled owner flags."""
from pathlib import Path
import json,re,math
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r44/network_runtime';rows=[]
for name in ('before','handnativev1'):
    server=json.loads((BASE/name/'server_samples.json').read_text('utf8'));client=json.loads((BASE/name/'client_samples.json').read_text('utf8'));log=(BASE/name/'server.log').read_text('utf8')
    rigs=[]
    for variant in range(5):
        ss=[r for r in server if r['variant']==variant];cc=[r for r in client if r['variant']==variant]
        velocities=[math.hypot(r['x']-p['x'],r['z']-p['z'])/(r['tick']-p['tick'])for p,r in zip(ss,ss[1:])if r['tick']>p['tick']]
        support=[r.get('foot_witness',{}).get('support_r44',{}).get('locomotion')for r in cc if 120<=r['age']<210]
        gaps=[r.get('foot_witness',{}).get('support_r44',{}).get('game_time',0)-p.get('foot_witness',{}).get('support_r44',{}).get('game_time',0)for p,r in zip(cc,cc[1:])if p['age']<210 and r['age']>=120]
        rigs.append(dict(variant=variant,server_rows=len(ss),client_rows=len(cc),max_actual_server_blocks_per_tick=max(velocities,default=0),
                         run_support_flags=sorted(set(str(v)for v in support)),maximum_run_client_observation_tick_gap=max(gaps,default=0)))
    warnings=[dict(time=m.group(1),actor=m.group(2),delta=[float(m.group(i))for i in (3,4,5)])for m in re.finditer(r'\[(\d\d:\d\d:\d\d)\].*?: (EVA-[^\n]+?) \(vehicle of R44Probe\) moved too quickly! ([\d.Ee+-]+),([\d.Ee+-]+),([\d.Ee+-]+)',log)]
    rows.append(dict(dataset=name,rigs=rigs,move_packet_warnings=warnings,warning_count=len(warnings)))
out=ROOT/'artifacts/rebuild_r44/combat/runtime_hands_basis/native_v1_stream_readback/network_move_comparison.json'
out.write_text(json.dumps(dict(rows=rows,scope='Actual server/client observations. v1 source did not sample serverMovement/power inputs. Before has a different earlier class epoch; no causal performance claim or threshold change.'),indent=2),'utf8')
print(json.dumps([{k:v for k,v in row.items()if k!='move_packet_warnings'}for row in rows],indent=2))
