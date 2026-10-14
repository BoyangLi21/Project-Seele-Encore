"""Root-authored seven-lift binding measured against actual moved devices.

Produces an uninstalled candidate and a mismatch report. Never creates native
devices, activates a route claim, or substitutes a legacy coordinate fallback.
"""
import copy,json
from pathlib import Path
import nbtlib
import numpy as np
from query_blocks import iter_selected_sections,iter_block_entities
from r52_spatial_plan import BASE,PYRAMID,HANGAR

ROOT=Path(__file__).resolve().parents[1]
D={'north':(0,-1),'east':(1,0),'south':(0,1),'west':(-1,0)}
CW={'north':'east','east':'south','south':'west','west':'north'}
OP={'north':'south','east':'west','south':'north','west':'east'}
SPECS=[
 ('s20-command-rear-x12-z253-v4',(12,253),(9,253),'west','south',[-541,-516,-512,-502],[-2,1,0]),
 ('s20-compact-cage-x93-z204-v4',(93,-52),(96,-52),'east','south',[-468,-442],[2,1,0]),
 ('s20-surface-transit-v2',(130,273),(130,269),'north','west',[-535,75],[0,1,-3]),
 ('s23-commander-office-x28-z321-v1',(28,321),(31,321),'east','north',[-481,-457,-433],[2,1,0]),
 ('r25-east-command-gallery',(66,302),(63,302),'west','south',[-554,-541,-527,-513,-499,-485,-471,-457],[-2,1,0]),
 ('r25-west-observation',(89,366),(86,366),'west','south',[-704,-630,-603],[-2,1,0]),
 ('r52-hq-hangar-terminal-shared',(108,407),(108,410),'south','north',[-846,-704,-630,-603,-554],[0,1,2]),
]


def main():
    world=BASE/'WORLD_R52';out=BASE/'personnel_lift_binding';out.mkdir(exist_ok=True)
    original=json.loads((ROOT/'artifacts/r52_personnel_lift_runtime/ORIGINAL_OFFICE_AND_DOORS.json').read_text('utf8'))
    office=copy.deepcopy(original['office_access']);office['middle_y']-=93
    for key in ('readers','middle_reader'):
        office[key]=[list(PYRAMID.block(v)) for v in office[key]] if key=='readers' else list(PYRAMID.block(office[key]))
    for key in ('meeting_boxes','lift_room_boxes','landing_lease_box'):
        boxes=office[key] if key!='landing_lease_box' else [office[key]]
        for box in boxes:box[1]-=93;box[4]-=93
    controls=office['room_controls']
    for row in controls['gate']:row['lower']=list(PYRAMID.block(row['lower']))
    for row in controls['gate_readers']:
        for key in ('position','backing'):row[key]=list(PYRAMID.block(row[key]))
    for row in controls['pilot_guard_doors']:
        row['lower']=list(HANGAR.block(row['lower']));row['facing']=OP[row['facing']]
        row['approach_feet']=[list(HANGAR.point(p)) for p in row['approach_feet']]
    points=set();floors=[];lifts=[]
    def point(q):points.add(tuple(q));return list(q)
    for name,(x,z),(cx,cz),side,exit,ys,inside in SPECS:
        lift=dict(id=name,controller_side=side,controller_facing=OP[side],inside_button_offset=inside,
                  inside_display_offset=[inside[0],inside[1]+1,inside[2]],floors=[]);lifts.append(lift)
        dx,dz=D[exit];sx,sz=D[CW[exit]]
        for y in ys:
            f=dict(label='',cabin=[x,y,z],exit=exit,approach_y=y,controller=point((cx,y,cz)),calls=[],
                   restricted=(name==office['lift_id'] and y in (-457,-433))or(name.endswith('terminal-shared')and y==-846))
            for key,distance,half in [('landing_doors',4,2),('cabin_doors',3 if name=='s20-surface-transit-v2' else 2,1)]:
                f[key]=[dict(pos=point((x+dx*distance+sx*i,y+j,z+dz*distance+sz*i)),
                    closed_state='minecraft:gray_stained_glass' if key=='landing_doors' else 'minecraft:light_gray_stained_glass') for i in range(-half,half+1) for j in range(3)]
            if name.endswith('terminal-shared'):calls=[(111,y+1,403)]
            elif name=='r25-east-command-gallery':calls=[(x-1,y+1,z+6)]
            else:calls=[(x+dx*5+sx*3,y+1,z+dz*5+sz*3)]
            if name==office['lift_id']:
                calls += [tuple(p) for p in office['readers'] if p[1]==y+1]
            for q in dict.fromkeys(calls):point(q);f['calls'].append(dict(position=list(q),target_controller=f['controller']))
            for offset in (inside,lift['inside_display_offset']):point((x+offset[0],y+offset[1],z+offset[2]))
            if name.endswith('terminal-shared'):point((111,y+2,403))
            lift['floors'].append(f);floors.append((lift,f))
    for p in office['readers']:point(p)
    for r in controls['gate_readers']:point(r['position']);point(r['backing'])
    for r in controls['gate']+controls['pilot_guard_doors']:
        point(r['lower']);point((r['lower'][0],r['lower'][1]+1,r['lower'][2]))
    selected={}
    for x,y,z in points:selected.setdefault((x//16,z//16),set()).add(y//16)
    actual={p:'minecraft:air' for p in points}
    for cx,cz,sy,palette,indices in iter_selected_sections(world,'projectseele:geofront',selected):
        wanted=[p for p in points if (p[0]//16,p[2]//16,p[1]//16)==(cx,cz,sy)]
        for x,y,z in wanted:actual[x,y,z]=palette[int(indices[(y%16)*256+(z%16)*16+x%16])]
    tags={}
    for _,(x,z),_,_,_,ys,_ in SPECS:
        tags.update(iter_block_entities(world,'projectseele:geofront',(x-8,min(ys)-1,z-8),(x+8,max(ys)+5,z+8)))
    caps=nbtlib.load(world/'dimensions/projectseele/geofront/data/capabilities.dat')['data']['movingelevators:elevator_groups']
    issues=[];facts=[]
    for lift,f in floors:
        q=tuple(f['controller']);t=tags.get(q)
        if t is None or str(t['id'])!='movingelevators:elevator_tile':issues.append(dict(lift=lift['id'],at=q,issue='missing actual floor controller'));continue
        f['label']=str(t['data']['name']);f['controller_state']=actual[q]
        facing=lift['controller_facing'];expected='movingelevators:elevator_block[facing='+facing+']'
        if actual[q]!=expected:issues.append(dict(at=q,issue='controller state/facing mismatch',actual=actual[q],expected=expected))
        group=caps[str(q[0])+';'+str(q[2])]['group'];expected_ys=[v['cabin'][1] for v in lift['floors']]
        if list(map(int,group['floors']))!=expected_ys:issues.append(dict(at=q,issue='native group floors differ'))
        remaining=[]
        for c in f['calls']:
            p=tuple(c['position']);state=actual[p];tag=tags.get(p)
            if state.startswith('minecraft:polished_blackstone_button['):kind='vanilla_button';facing=state.split('facing=')[1].split(',')[0].split(']')[0]
            elif tag is not None and str(tag['id'])=='projectseele:nerv_access_reader':kind='seele_reader';facing=state.split('facing=')[1].split(',')[0].split(']')[0]
            elif tag is not None and str(tag['id'])=='movingelevators:button_tile':
                kind='native_linked';facing={2:'north',3:'south',4:'west',5:'east'}[int(tag['data']['facing'])]
                target=[int(tag['data']['controller'+a]) for a in ('X','Y','Z')]
                if target!=f['controller']:issues.append(dict(at=p,issue='native external call controller link mismatch',target=target))
                d=(p[0],p[1]+1,p[2]);c['display']=dict(position=list(d),state=actual[d])
            elif lift['id']==office['lift_id'] and p not in map(tuple,office['readers']):
                # Original SEELE reader replaced this optional legacy call.
                facts.append(dict(at=p,actual=state,unused_legacy_office_call=True));continue
            else:issues.append(dict(at=p,issue='no measured supported call device',actual=state,id=str(tag['id']) if tag is not None else None));continue
            c.update(kind=kind,state=state,facing=facing);remaining.append(c)
        f['calls']=remaining
        if not remaining:issues.append(dict(lift=lift['id'],floor=f['cabin'][1],issue='no actual calls'))
        for key in ('landing_doors','cabin_doors'):
            states={actual[tuple(d['pos'])] for d in f[key]}-{'minecraft:air'}
            glass={s for s in states if 'stained_glass' in s}
            if len(glass)==1:
                for d in f[key]:d['closed_state']=next(iter(glass))
            for d in f[key]:
                state=actual[tuple(d['pos'])]
                if state not in ('minecraft:air',d['closed_state']):issues.append(dict(lift=lift['id'],at=d['pos'],issue='door plane has non-door material',actual=state,key=key))
        facts.append(dict(lift=lift['id'],floor=f['cabin'],controller_nbt=t.snbt(),native_car_at_this_floor=bool(group['floorData'][expected_ys.index(q[1])]['isCageAvailable'])))
    candidate=dict(schema='projectseele.r52.s20-lifts.v1',scope='s20_personnel_only',complete_replacement=True,
                   epoch=52,directory_fingerprint='0'*64,ready=False,lifts=lifts,office_access=office)
    (out/'CANDIDATE_NOT_INSTALLED.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2),'utf8')
    (out/'MEASURED_BINDINGS.json').write_text(json.dumps(dict(world_written=False,measured_points=len(actual),issues=issues,
        facts=facts,actual=[dict(pos=p,state=s)for p,s in sorted(actual.items())]),ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(world_written=False,lifts=len(lifts),floors=len(floors),measured_points=len(actual),issues=len(issues)),ensure_ascii=False))
    for issue in issues:print(json.dumps(issue,ensure_ascii=False))


if __name__=='__main__':main()
