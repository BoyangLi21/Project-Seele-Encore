"""Whole-inventory door-pair, floor and approach audit; no edits or route-list limit."""
from pathlib import Path
from collections import Counter
import gzip,json
from measure_world_r40 import MeasuredWorld,properties,empty,ROOT

OUT=ROOT/'artifacts/world_combat_r40'
DIR={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}
def main():
    doors=[]
    with gzip.open(OUT/'inventory/doors.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            x,y,z,s=json.loads(line);name=s.partition('[')[0]
            if name.startswith('minecraft:') and name.endswith('_door') and properties(s).get('half')=='lower':doors.append((x,y,z,s))
    world=MeasuredWorld()
    for x,y,z,s in doors:world.around((x,y,z),4)
    world.load();rows=[]
    for x,y,z,s in doors:
        p=properties(s);upper=world.get(x,y+1,z);issues=[]
        if upper is None:issues.append('unloaded_upper')
        elif upper.partition('[')[0]!=s.partition('[')[0] or properties(upper).get('half')!='upper':issues.append('broken_pair')
        floor=world.get(x,y-1,z)
        if floor is None:issues.append('unknown_floor')
        elif empty(floor):issues.append('unsupported_door')
        dx,dz=DIR[p['facing']];approaches=[]
        for direction in [1,-1]:
            xx,zz=x+dx*direction,z+dz*direction
            states=[world.get(xx,y-1,zz),world.get(xx,y,zz),world.get(xx,y+1,zz)]
            approaches.append(dict(pos=[xx,y,zz],states=states,clear=empty(states[1]) and empty(states[2]),supported=states[0] is not None and not empty(states[0])))
        if not any(a['clear'] and a['supported'] for a in approaches):issues.append('no_supported_approach')
        elif not all(a['clear'] for a in approaches):issues.append('blocked_side')
        if 'iron_door' in s:
            controls=[]
            for xx in range(x-3,x+4):
                for yy in range(y-1,y+3):
                    for zz in range(z-3,z+4):
                        v=world.get(xx,yy,zz)
                        if v and any(t in v for t in ['button','lever','pressure_plate','redstone_block','tripwire_hook','card_reader']):controls.append([xx,yy,zz,v])
            if not controls:issues.append('no_local_control')
        else:controls=[]
        rows.append(dict(pos=[x,y,z],state=s,upper=upper,floor=floor,approaches=approaches,controls=controls,issues=issues))
    report=dict(scope='Every vanilla door lower half found in all FULL GeoFront chunks; trapdoors and native MTR gates audited separately',doors=len(rows),counts=Counter(i for r in rows for i in r['issues']),rows=rows)
    (OUT/'doors_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('Door audit:',report['doors'],dict(report['counts']),flush=True)
if __name__=='__main__':main()
