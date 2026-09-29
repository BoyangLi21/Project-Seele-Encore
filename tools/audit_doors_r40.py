"""Whole-inventory door-pair, floor and approach audit; no edits or route-list limit."""
from pathlib import Path
from collections import Counter
import argparse,gzip,json
from measure_world_r40 import MeasuredWorld,properties,empty,ROOT,WORLD
from regional_voxels import canonical_state
from query_blocks import AIR

OUT=ROOT/'artifacts/world_combat_r40'
DIR={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}
def main(save=WORLD,out=OUT,features=None,dimension='projectseele:geofront'):
    out.mkdir(parents=True,exist_ok=True);doors=[];unhandled=Counter()
    with gzip.open(features or OUT/'inventory/doors.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            row=json.loads(line)
            if len(row)>4 and row[4]!='doors':continue
            x,y,z,s=row[:4];p=properties(s)
            if p.get('half')=='lower' and 'hinge' in p:doors.append((x,y,z,s))
            elif p.get('half')!='upper':unhandled[s]=unhandled.get(s,0)+1
    world=MeasuredWorld(save,dimension)
    for x,y,z,s in doors:world.around((x,y,z),4)
    world.load();rows=[];missing=set()
    shapes={canonical_state(s):b for s,b in json.loads((save/'native_collision_shapes.json').read_text('utf8')).items()}
    def shape(s):
        if s is None:return None
        if s.partition('[')[0] in AIR|{'minecraft:light'}:return []
        if s not in shapes:missing.add(s);return None
        return shapes[s]
    def clear(s,height):
        b=shape(s)
        return b is not None and not any(q[0]<.8 and q[3]>.2 and q[2]<.8 and q[5]>.2 and q[1]<height and q[4]>.01 for q in b)
    def bearing(s):
        b=shape(s)
        return b is not None and any(q[0]<=.5<=q[3] and q[2]<=.5<=q[5] and .90<=q[4]<=1.001 for q in b)
    for x,y,z,s in doors:
        p=properties(s);upper=world.get(x,y+1,z);issues=[]
        actual=world.get(x,y,z)
        if actual!=s:issues.append('inventory_changed')
        if upper is None:issues.append('unloaded_upper')
        elif upper.partition('[')[0]!=s.partition('[')[0] or properties(upper).get('half')!='upper':issues.append('broken_pair')
        floor=world.get(x,y-1,z)
        if floor is None:issues.append('unknown_floor')
        elif not bearing(floor):issues.append('unsupported_or_unmeasured_door')
        dx,dz=DIR[p['facing']];approaches=[]
        for direction in [1,-1]:
            xx,zz=x+dx*direction,z+dz*direction
            states=[world.get(xx,y-1,zz),world.get(xx,y,zz),world.get(xx,y+1,zz)]
            approaches.append(dict(pos=[xx,y,zz],states=states,clear=clear(states[1],1) and clear(states[2],.79),supported=bearing(states[0])))
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
    report=dict(scope='Every inventoried hinged two-block door, including modded namespaces, with native collision approaches. Sliding gates and trapdoors remain separate unclassified components, never passes.',world=str(save),dimension=dimension,doors=len(rows),counts=Counter(i for r in rows for i in r['issues']),unclassified_non_hinged_states=unhandled,missing_collision_states=sorted(missing),rows=rows)
    (out/'doors_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('Door audit:',report['doors'],dict(report['counts']),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,default=WORLD);p.add_argument('--out',type=Path,default=OUT);p.add_argument('--features',type=Path);p.add_argument('--dimension',default='projectseele:geofront');a=p.parse_args();main(a.world,a.out,a.features,a.dimension)
