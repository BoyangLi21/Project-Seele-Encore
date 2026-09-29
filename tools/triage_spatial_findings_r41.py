"""Stable spatial groups and exact floor context; priority is not disposition."""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,json,gzip,hashlib
from measure_world_r40 import MeasuredWorld

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41'


def main(world=None,findings=None,out=None):
    world=world or ART/'source_world_backup';findings=findings or ART/'envelopes/findings.json';out=out or ART/'triage'
    data=json.loads(findings.read_text('utf8'));rows=data['findings']
    with gzip.open(world/'nerv_routes_r24.json.gz','rt',encoding='utf8') as f:nav=json.load(f)
    public={tuple(n[:3]) for n in nav['nodes']}
    w=MeasuredWorld(world)
    for r in rows:
        x,y,z=r['pos'];w.box((x,y-1,z),(x,y-1,z))
    w.load();print('Measured actual underlying states for all findings',flush=True)
    buckets=defaultdict(lambda:defaultdict(list))
    for r in rows:
        key=(r['kind'],tuple(r.get('normal',[])),r.get('enclosed'))
        buckets[key][tuple(r['pos'])].append(r)
    groups=[]
    for key,points in buckets.items():
        while points:
            p,items=points.popitem();group=list(items);stack=[p]
            while stack:
                q=stack.pop()
                for delta in [(1,0,0),(-1,0,0),(0,0,1),(0,0,-1)]:
                    n=tuple(q[i]+delta[i] for i in range(3))
                    if n in points:group.extend(points.pop(n));stack.append(n)
            positions=sorted({tuple(r['pos']) for r in group});lo=[min(p[i] for p in positions) for i in range(3)];hi=[max(p[i] for p in positions) for i in range(3)]
            floors=Counter(w.get(x,y-1,z) for x,y,z in positions);hit=sum(p in public for p in positions)
            purpose_floor=any(s and (s.startswith(('projectseele:nerv_floor_panel','projectseele:nerv_machine_panel','projectseele:nerv_hazard_paving','mtr:platform')) or 'escalator_step' in s) for s in floors)
            priority=1 if key[0].startswith('moving_') or key[0]=='attached_sheet_candidate' or hit else 2 if purpose_floor or key[0]=='wall_intrusion' else 3 if key[2] else 4
            identity=hashlib.sha256(json.dumps([key,positions],sort_keys=True).encode()).hexdigest()[:14]
            groups.append(dict(id=key[0]+'-'+identity,kind=key[0],normal=key[1],enclosed=key[2],count=len(group),lo=lo,hi=hi,public_nodes=hit,priority=priority,
                               floors=dict(floors),states=sorted({r['state'] for r in group}),rows=group))
    assert len({g['id'] for g in groups})==len(groups)
    out.mkdir(parents=True,exist_ok=True)
    (out/'groups.json').write_text(json.dumps(groups,ensure_ascii=False,separators=(',',':')),'utf8')
    summary=Counter((r['kind'],r['priority']) for r in groups)
    (out/'counts.json').write_text(json.dumps([dict(kind=k[0],priority=k[1],groups=v,cells=sum(r['count'] for r in groups if (r['kind'],r['priority'])==k)) for k,v in summary.items()],indent=2),'utf8')
    for priority in (1,2,3):
        (out/f'priority_{priority}.json').write_text(json.dumps([{k:v for k,v in r.items() if k!='rows'} for r in groups if r['priority']==priority],ensure_ascii=False,indent=2),'utf8')
    print('Triage priorities',Counter(r['priority'] for r in groups),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path);p.add_argument('--findings',type=Path);p.add_argument('--out',type=Path);a=p.parse_args();main(a.world,a.findings,a.out)
