"""Complete town/harbour junction with founded shoulders and whole lamp relocation."""
from pathlib import Path
from collections import Counter
import argparse,json,gzip,math,hashlib
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from regional_voxels import canonical_state
from plan_hakone_tokyo_link_r44 import SOIL,SMALL,PAVING,GUARD

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'

def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);args=p.parse_args();OUT=args.output
    assert not OUT.exists(),'Keep earlier complete attempts'
    w=MeasuredWorld(WORLD);lo,hi=(238,50,502),(292,97,539);w.box(lo,hi);w.load();assert set(w.status.values())=={'full'}
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    arrays=np.load(ROOT/'artifacts/rebuild_r44/surface_network/road_complete_authority_stage3.columns.npz');profiles={tuple(map(int,q)):(float(f),int(g)) for q,f,g in zip(arrays['coordinates'],arrays['actual_feet'],arrays['flags'])}
    assert profiles[250,520]==(81,31) and profiles[280,520]==(81,31)
    shape={canonical_state(s):b for s,b in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    changes={};held=[];protected_old_ports=[]
    lamp=[(273,y,522) for y in range(78,84)];states=[w.block(q) for q in lamp]
    rod='minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]'
    assert states==[rod]*5+['projectseele:street_light_head[facing=east]'] and not any(q in tags for q in lamp),'Complete existing functional lamp changed; preserve it'
    # Exact source support author, not an ownership guess from block type.
    source=ROOT/'artifacts/world_repair_r19/fixture_supports/grounded_lights_and_baffles/ops.json.gz'
    operations=json.load(gzip.open(source,'rt',encoding='utf8'))
    for q,s in zip(lamp,states):
        assert any(r['box']==list(q)+list(q) and r['state']==s and r['owner']=='r19/grounded_tokyo_style_street_light' for r in operations),(q,'Missing exact original complete lamp author receipt')
    def put(q,s,reason,allow=SOIL|SMALL|PAVING|AIR):
        old=w.block(q)
        if old is None or q in tags or old.split('[')[0] not in allow:
            held.append(dict(pos=q,state=old,nbt=tags[q].snbt() if q in tags else None,reason=reason));return
        if old!=s:changes[q]=(s,reason)
        elif q in changes:del changes[q]
    def after(q):return changes.get(q,(w.block(q),''))[0]
    for q in lamp:put(q,'minecraft:stone' if q[1]<80 else 'minecraft:air','Retire entire exact in-carriage lamp including its two below-floor mast cells before moving the complete six-cell assembly',{'minecraft:iron_bars','projectseele:street_light_head'})
    for q,s in zip(lamp,states):
        dest=(q[0],q[1]+3,529);assert w.block(dest) in AIR and dest not in tags
        put(dest,s,'Complete original street lamp moves beside the public sidewalk, preserving head direction and full six-cell support',AIR)
    # Both public roads already have Y81 feet; the short natural gap is a
    # continuous shallow formation, not a floating sheet or a raised hump.
    columns=[]
    for x in range(244,287):
        for dz in range(-6,7):
            z=520+dz
            for y in (78,79):
                if after((x,y,z)).split('[')[0] in SOIL:continue
                put((x,y,z),'minecraft:stone','Continuous shallow road formation joins the measured rock/dirt bearing')
            marking=abs(dz)==4 or (dz==0 and (x-244)%12<5)
            s='minecraft:smooth_stone' if abs(dz)>=5 else 'minecraft:white_concrete' if marking else 'minecraft:black_concrete'
            allowed=SOIL|SMALL|PAVING|AIR|({'minecraft:iron_bars','projectseele:street_light_head'} if (x,80,z) in lamp else set())
            put((x,80,z),s,'Full two-lane city/harbour junction with marked edges and two metre continuous sidewalks',allowed)
            for y in range(81,87):
                if after((x,y,z)) in AIR:continue
                allowed=SOIL|SMALL|PAVING|AIR|({'minecraft:iron_bars','projectseele:street_light_head'} if (x,y,z) in lamp else set())
                put((x,y,z),'minecraft:air','Full six metre road and sidewalk clearance, with whole owned lamp relocation',allowed)
            columns.append(dict(pos=[x,z],height2=162,carriage=abs(dz)<=4,source_id='r44/tokyo_harbour_complete_link'))
        for side in (-1,1):
            z=520+side*7;old=profiles.get((x,z))
            if old and old[1]&7==7 and abs(old[0]-81)<=.501:
                protected_old_ports.append(dict(pos=[x,z],native_original_feet=old[0],native_original_flags=old[1]));continue
            # The measured ground stays close; one-to-two banks make the edge
            # part of the street landscape instead of installing pit fencing.
            for d in range(0,5):
                zz=z+side*d;desired=79-math.ceil(d/2)
                soil=[y for y in range(50,81) if (w.get(x,y,zz) or '').split('[')[0] in SOIL]
                assert soil,(x,zz,'No real natural bearing')
                actual=max(soil)
                if actual>=desired:continue
                for y in range(actual+1,desired):put((x,y,zz),'minecraft:dirt','Local graded bank keeps the complete street edge grounded')
                put((x,desired,zz),'minecraft:grass_block[snowy=false]','A planted grass bank returns the connector shoulder to actual harbour terrain')
    fail=[];unknown=Counter()
    for c in columns:
        x,z=c['pos'];state=after((x,80,z));boxes=shape.get(state)
        if boxes is None or not any(b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and b[4]==1 for b in boxes):fail.append(dict(pos=[x,80,z],reason='Actual full-width native foot plane differs'))
        for y in range(81,87):
            state=after((x,y,z));boxes=[] if state in AIR or state.split('[')[0] in SMALL else shape.get(state)
            if boxes is None:unknown[state]+=1
            if boxes is None or boxes:fail.append(dict(pos=[x,y,z],reason='Whole-width six metre clearance blocked/unknown'))
    # New after-shapes are checked against the OLD exact public 3D foot rights,
    # including the transverse harbour street and all original sidewalk widths.
    for q,(s,reason) in changes.items():
        old=profiles.get((q[0],q[2]))
        if not old or old[1]&7!=7 or s in AIR:continue
        foot,flags=old;boxes=shape.get(s)
        if boxes is None:unknown[s]+=1;continue
        if any(q[1]+b[4]>foot+.001 and q[1]+b[1]<foot+(6 if flags&16 else 1.8) for b in boxes):fail.append(dict(pos=q,reason='New component intersects an existing effective public foot/vehicle envelope',old_feet=foot,old_flags=flags))
    rows=[dict(pos=q,before=w.block(q),after=s,before_nbt=None,after_nbt=None,owner='r44/tokyo_harbour_complete_link',reason=reason) for q,(s,reason) in sorted(changes.items())]
    OUT.mkdir(parents=True)
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(OUT/(name+'.jsonl.gz'),'wt',encoding='utf8') as f:
            for r in rows:
                v=dict(r)
                if inverse:v['before'],v['after']=r['after'],r['before']
                f.write(json.dumps(v)+'\n')
    (OUT/'road_authority.json').write_text(json.dumps(dict(columns=columns,world_written=False),indent=2),'utf8')
    cases=[]
    for z in range(514,527):
        path=[[x+.5,81,z+.5] for x in range(244,287)]
        for flow in ['east','west']:cases.append(dict(id=f'r44/tokyo_harbour_link/z{z}/{flow}',path=path if flow=='east' else path[::-1],vehicle_clearance=516<=z<=524,native_passed=False))
    for x in range(276,285):
        path=[[x+.5,81,z+.5] for z in range(500,539)]
        for flow in ['north','south']:cases.append(dict(id=f'r44/harbour_original_crossing/x{x}/{flow}',path=path if flow=='south' else path[::-1],vehicle_clearance=True,native_passed=False))
    (OUT/'native_all_direction_cases.json').write_text(json.dumps(cases),'utf8')
    audit=dict(world=str(WORLD),changed_cells=len(rows),full_width_columns=len(columns),lamp_source=lamp,lamp_destination=[[273,y,529] for y in range(81,87)],
        lamp_complete_state_and_full_nbt_preserved=True,lamp_source_author_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),protected_existing_ports=protected_old_ports,
        held=held,static_failures=fail,unknown_shapes=dict(unknown),ready=not held and not fail and not unknown,world_written=False,native_walk_vehicle_passed=False,visual_passed=False,
        interpretation='Complete gap, full road width, shallow natural banks, both town traffic directions and all existing public crossing directions remain separate actual/native/visual gates.')
    (OUT/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),'utf8');print('Harbour',len(rows),'columns',len(columns),'held',len(held),'fails',len(fail),'ready',audit['ready'],flush=True)

if __name__=='__main__':main()
