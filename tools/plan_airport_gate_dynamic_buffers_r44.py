"""Complete airport escalator tails plus physical gate banks and real exit curves.

Exact forward/inverse only. Preserves the35 native rows of all four two-width
escalators, their inclines, transitions, landing caps, sides and ordinary stairs.
Retires all three obsolete motorised tail rows into the existing upper hall.
"""
from pathlib import Path
import copy,hashlib,json,math
import numpy as np
import regional_voxels as v
from query_blocks import AIR,iter_block_entities
from measure_world_r40 import MeasuredWorld,properties
from audit_facility_transit_r44 import Geometry
from finalize_public_station_gates_r44 import conflicts

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
ART=ROOT/'artifacts/rebuild_r44/facility_transit_r44'
OUT=ART/'airport_gate_dynamic_buffers_v1'
FLOOR='projectseele:period_station_floor'
MANIFEST=WORLD/'r44_public_station_gates.json'
SOURCE=ART/'public_station_gates_v2'


def dense(points):
    path=[]
    for a,b in zip(points,points[1:]):
        n=round(sum(abs(x-y) for x,y in zip(a,b)))
        assert sum(x!=y for x,y in zip(a,b))==1,('Only actual cardinal public hall segments',a,b)
        for p in np.linspace(a,b,max(1,n*2)+1):
            q=p.tolist()
            if not path or q!=path[-1]:path.append(q)
    return path


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    assert not list(OUT.glob('*/applied_*/receipt.json')),'Applied proposal is immutable'
    manifest=json.loads(MANIFEST.read_text('utf8'));cases=json.loads((SOURCE/'native_cases.json').read_text('utf8'))
    assert len(manifest['gates'])==80 and len(cases)==160
    w=MeasuredWorld(WORLD);w.box((489,69,103),(590,112,153));w.load();g=Geometry(w)
    native=json.loads((WORLD/'r44_public_station_gate_shapes.json').read_text('utf8'))
    g.shapes.update({v.canonical_state(s):b for s,b in native['collision_shapes'].items()})
    tags={q:copy.deepcopy(t) for q,t in iter_block_entities(WORLD,v.DIM,(489,69,103),(540,112,153))}
    changes={};dependencies={};mechanisms=[]
    for basez in (108,138):
        for z0,direction in ((basez,'true'),(basez+6,'false')):
            steps=[];sides=[]
            for n in range(38):
                x=498+n;y=72+max(0,min(32,n-1))
                orientation='landing_bottom' if n==0 else 'transition_bottom' if n==1 else 'slope' if n<=32 else 'transition_top' if n==33 else 'landing_top' if n==34 else 'flat'
                for lane in (0,1):
                    q=(x,y,z0+lane);expected=v.canonical_state(f'mtr:escalator_step[direction={direction},facing=east,orientation={orientation},side={"left" if lane==0 else "right"},status=true]')
                    actual=w.block(q);assert actual==expected,('Complete original native step precondition',q,actual,expected)
                    assert q not in tags,('Native step unexpectedly has BE',q)
                    dependencies[q]=actual;steps.append([*q,actual])
                    if n>34:changes[q]=(FLOOR,'whole_three_row_motorised_tail_retirement')
                    if orientation not in ('flat','landing_bottom','landing_top'):
                        s=(x,y+1,z0+lane);state=w.block(s)
                        assert state and state.startswith('mtr:escalator_side['),('Incomplete original side assembly',s,state)
                        dependencies[s]=state;sides.append([*s,state])
            mechanisms.append({'basez':z0,'direction':direction,'complete_native_before':steps,
                'complete_attached_sides_preserved':sides,'native_rows_before':38,'native_rows_after':35,
                'native_state_preserved':'All statuses=true; all slopes/transitions/landing caps and side meshes retain exact values',
                'static_upper_landing_rows':[533,534,535]})
    selected=[r for r in manifest['gates'] if r['station_id']=='-3509826829761857803' and r['position'][1]==105]
    assert {tuple(r['position']) for r in selected}=={(x,105,z) for x in (532,533) for z in (112,142)}
    relocated=[];new_manifest=copy.deepcopy(manifest)
    for row in selected:
        old=tuple(row['position']);new=(old[0]+2,old[1],old[2])
        actual=w.block(old);assert actual==row['closed_state'],('Current native closed gate required',old,actual)
        assert w.block(new) in AIR and old not in tags and new not in tags,('New physical bank consumes other object',new,w.block(new))
        changes[old]=('minecraft:air','complete_old_upper_bank_retirement')
        changes[new]=(row['closed_state'],'whole_upper_gate_bank_on_static_tail_landing')
        target=next(r for r in new_manifest['gates'] if tuple(r['position'])==old)
        target['position']=list(new);target['placement_revision']='airport_dynamic_waiting_r44_v1'
        relocated.append({'old':old,'new':new,'gate':target})
    assert len(changes)==32 and len(relocated)==4
    base_get=w.get
    opened={tuple(r['new']):r['gate']['open_state'] for r in relocated}
    after={q:s for q,(s,purpose) in changes.items()}
    w.get=lambda x,y,z:opened.get((x,y,z),after.get((x,y,z),base_get(x,y,z)))
    next_cases=copy.deepcopy(cases);changed_cases=[]
    by_old={tuple(r['old']):r for r in relocated}
    for i,case in enumerate(next_cases):
        old=tuple(case['actualAutomaticGate'])
        if old not in by_old:continue
        target=by_old[old];delta=np.asarray(target['new'])-np.asarray(old)
        case['actualAutomaticGate']=list(target['new']);case['path']=[(np.asarray(p)+delta).tolist() for p in case['path']]
        case['id']=f'r44/public_station_gate/-3509826829761857803/{target["new"][0]}_105_{target["new"][2]}' + ('/return' if cases[i]['id'].endswith('/return') else '')
        case['whole_physical_bank_revision']='airport_dynamic_waiting_r44_v1';changed_cases.append(i)
        for p in case['path']:
            q=tuple(map(math.floor,p));check=g.standing(q);assert check['status']=='STATIC_STANDING',('New full waiting footprint',i,p,check)
            assert not w.get(q[0],q[1]-1,q[2]).startswith('mtr:escalator_step['),('Waiting is still on a native consumer',i,p)
        # The same strict original3m buffers and actual leaf occupancy apply.
        for a,b in zip(dense(case['path']),dense(case['path'])[1:]):
            qa=tuple(map(math.floor,a));qb=tuple(map(math.floor,b))
            assert g.standing(qa)['status']=='STATIC_STANDING' and g.edge_clear(qa,qb),('Open native bank obstructs actual body',i,a,b)
    curves=[]
    for basez,platformz,gatez in ((138,135.5,142),(108,121.5,112)):
        if basez==138:
            points=[[583.5,105,platformz],[536.5,105,platformz],[536.5,105,145.5],[534.5,105,145.5],
                    [534.5,105,139.5],[532.5,105,139.5],[532.5,105,141.5]]
        else:
            points=[[583.5,105,platformz],[536.5,105,platformz],[536.5,105,109.5],[534.5,105,109.5],
                    [534.5,105,115.5],[532.5,105,115.5],[532.5,105,111.5]]
        path=dense(points)
        for a,b in zip(path,path[1:]):
            qa=tuple(map(math.floor,a));qb=tuple(map(math.floor,b))
            if g.standing(qa)['status']!='STATIC_STANDING' or not g.edge_clear(qa,qb):
                raise RuntimeError(('Real full platform-to-stair curve obstructed',basez,a,b,g.standing(qa)))
        for reverse in (False,True):curves.append({'id':f'r44/airport/static_upper_bank/{basez}'+('/return' if reverse else ''),
            'path':path[::-1] if reverse else path,'real_ports':'Retained APG platform staging to original ordinary-stair upper datum; no new station or endpoint',
            'nativeRequired':'Actual client keys, unchanged balances, working up/down escalators, disembark and stationary ordinary-floor gate buffers'})
    walks=json.loads((ART/'station_walk_cases_v2/station_walk_cases.json').read_text('utf8'))
    open_conflicts=conflicts([r['gate'] for r in relocated],g.shapes,walks)
    assert not open_conflicts,('New actual open bodies obstruct original whole501 walking routes',open_conflicts)
    # Both complete two-width two-row run-outs are existing ordinary floor.
    runout=[]
    for basez in (108,138):
        for z0 in (basez,basez+6):
            for x in (533,534,535):
                for z in (z0,z0+1):
                    q=(x,105,z);check=g.standing(q);assert check['status']=='STATIC_STANDING',('Whole native run-out not usable',q,check)
                    runout.append(check)
    w.get=base_get
    p,inv=v.Painter(),v.Painter();v.WORLD,v.OUT=WORLD,OUT
    for q,(target,purpose) in sorted(changes.items()):
        before=w.block(q);assert before is not None and q not in tags
        p.match((*q,*q),before,target,'r44/airport/'+purpose);inv.match((*q,*q),target,before,'inverse/r44/airport/'+purpose)
    report={'cells':32,'whole_native_components':mechanisms,'whole_physical_bank_relocation':relocated,
        'changed_case_indices':changed_cases,'original_scope_preserved':{'gate_cells':80,'paired_banks':40,'operating_stations':19},
        'whole_static_runout':runout,'original_full501_open_gate_body_conflicts':open_conflicts,
        'original_complete_be_snbt':[{'position':q,'snbt':t.snbt()} for q,t in sorted(tags.items())],
        'source_dependencies':[{'position':q,'state':s} for q,s in sorted(dependencies.items())],
        'original_manifest_sha256':hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        'producer_sha256':{'airport_complete_native_tail':hashlib.sha256((ROOT/'tools/build_airport_station_r28.py').read_bytes()).hexdigest(),
            'future_gate_allocator_rejects_enabled_motor_support':hashlib.sha256((ROOT/'tools/plan_public_station_gates_r44.py').read_bytes()).hexdigest()},
        'native_before_first_error':'public_gate_client_lifecycle/20261001_044009 case122 actual keys0 and native east drift; kept frozen',
        'pre_apply':['Root exclusive stopped-world current32states/dependencies/BE check','Install new finite80 manifest after exact hardware delta','Keep original160case artifact frozen; select relocated case revision explicitly'],
        'post_apply':['8 affected real client gate lifecycles with strict staging unchanged','All four paired native escalators up/down full trips and static disembark','Real curves/APG/ordinary stair/lower terminal access','Complete160 new-world/cold reload and finalcopy'],
        'apply_allowed':True,'world_write_performed':False,'native_passed':False,'visual_passed':False,
        'authority':'Full existing commissioned airport upper access assembly, complete original native mechanisms and original platform/stair ports; not a test-point-only change'}
    p.meta.update(report);p.save_plan('whole_airport_upper_gate_and_native_tails')
    inv.meta.update({'forward':'whole_airport_upper_gate_and_native_tails','original_manifest_sha256':report['original_manifest_sha256']})
    inv.save_plan('inverse_whole_airport_upper_gate_and_native_tails')
    (OUT/'contract.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'r44_public_station_gates_before.json').write_bytes(MANIFEST.read_bytes())
    for filename,data in (('r44_public_station_gates.json',new_manifest),('native_cases.json',next_cases),('whole_airport_curves_native_cases.json',curves)):
        (OUT/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'cells':len(changes),'whole_components':len(mechanisms),'gate_cells_relocated':len(relocated),
        'changed_case_indices':changed_cases,'full_curves':len(curves),'original_BE':len(tags),'open501conflicts':open_conflicts,'world_write_performed':False}))


if __name__=='__main__':main()
