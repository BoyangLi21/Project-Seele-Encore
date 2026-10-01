"""Three whole wall-mounted MTR route signs on existing information fixtures.

Uses the pinned mod's exported collision shapes and configured platform IDs.
The native block's facing points into its backing, opposite its reading face.
No world writes: a comparison candidate, not global sign acceptance.
"""
from pathlib import Path
import copy, hashlib, json, math
import nbtlib
import regional_voxels as v
from query_blocks import AIR, iter_block_entities
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry, NORMAL
from station_route_contract_r44 import RouteDiagrams

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/facility_transit_r44/native_route_sign_trial_v1'


def main():
    assert not OUT.exists()
    choices=json.loads((OUT.parent/'native_sign_integration/fixed_wall_candidates.json').read_text('utf8'))
    selected=[next(r for r in choices if r['board']==q) for q in ([123,-441,-26],[135,-441,-54],[-124,97,-184])]
    w=MeasuredWorld(WORLD)
    for r in selected:w.around(r['board'],10)
    w.load();g=Geometry(w);diagrams=RouteDiagrams();v.WORLD,v.OUT=WORLD,OUT
    p,inv=v.Painter(),v.Painter();cards=[];cases=[];views=[]
    for i,r in enumerate(selected):
        upper=tuple(r['board']);lower=(upper[0],upper[1]-1,upper[2]);nx,nz=NORMAL[r['face']]
        backing_face=next(f for f,n in NORMAL.items() if n==(-nx,-nz))
        diagram=diagrams.diagram(r['platform'],r['face']);dx,dz=diagram['native_departure_vector']
        right=dx*nz-dz*nx;away=-dx*nx-dz*nz
        assert abs(right)>abs(away), 'Native left/right arrows require a side-on information fixture'
        arrow=2 if right>0 else 1
        state=w.block(upper);tag=dict(iter_block_entities(WORLD,v.DIM,upper,upper))[upper]
        assert state.startswith('projectseele:station_departure_board') and int(tag['NativePlatformId'])==r['platform']
        assert w.block(lower) in AIR
        deps=[]
        for q in (lower,upper):
            b=(q[0]-nx,q[1],q[2]-nz);bs=w.block(b)
            assert g.boxes(bs)==[[0.,0.,0.,1.,1.,1.]] and bs in {'projectseele:nerv_structural_panel','projectseele:nerv_wall_panel','projectseele:clear_glass'}
            deps.append({'position':b,'state':bs})
        # These existing fixtures have fixed wall support, without suspended
        # rods left over after their old three-metre panel is removed.
        for x in range(upper[0]-1,upper[0]+2):
            for z in range(upper[2]-1,upper[2]+2):
                for y in range(upper[1]+1,upper[1]+9):
                    q=(x,y,z);s=w.block(q)
                    assert s is not None and not any(a in s for a in ('chain','iron_bars'))
                    deps.append({'position':q,'state':s})
        new={}
        for q,half in ((lower,'lower'),(upper,'upper')):
            target=f'mtr:route_sign_wall_light[facing={backing_face},half={half},propagate_property={arrow}]'
            shape=g.boxes(target);assert shape is not None and shape
            new[q]=target
            p.match((*q,*q),w.block(q),target,'r44/native_route_sign/complete_wall_fixture')
            inv.match((*q,*q),target,w.block(q),'inverse/r44/native_route_sign')
            p.block_entities[q]=nbtlib.Compound(id=nbtlib.String('mtr:route_sign_wall_light'),x=nbtlib.Int(q[0]),y=nbtlib.Int(q[1]),z=nbtlib.Int(q[2]),platform_id=nbtlib.Long(r['platform']))
        inv.block_entities[upper]=copy.deepcopy(tag)
        original_get=w.get;w.get=lambda x,y,z:new.get((x,y,z),original_get(x,y,z))
        reader=tuple(r['reader']);assert g.standing(reader)['status']=='STATIC_STANDING'
        # Both two-metre passenger bypass lanes remain usable on the actual
        # station slab; each fixture uses no track, gate or escalator block.
        tx,tz=nz,-nx
        for distance in (2,3):
            path=[(upper[0]+nx*distance+tx*a,reader[1],upper[2]+nz*distance+tz*a) for a in range(-3,4)]
            assert all(g.standing(q)['status']=='STATIC_STANDING' for q in path)
            assert all(g.edge_clear(a,b) for a,b in zip(path,path[1:]))
            cases.append({'id':f'r44/native_route_sign/{i}/bypass_{distance}','path':[[x+.5,y,z+.5] for x,y,z in path]})
        w.get=original_get
        pos=[reader[0]+.5,reader[1],reader[2]+.5]
        target=[upper[0]+.5+nx*.43125,upper[1]+.15,upper[2]+.5+nz*.43125]
        delta=[target[0]-pos[0],target[1]-(pos[1]+1.62),target[2]-pos[2]]
        views.append({'file':f'r44_native_route_sign_{i}.png','position':pos,
            'yaw':math.degrees(math.atan2(-delta[0],delta[2])),'pitch':math.degrees(math.atan2(-delta[1],math.hypot(delta[0],delta[2]))),
            'fovDegrees':70,'warmupTicks':360,'action':'daytime:6000','requiredSections':[list(lower),list(upper)]})
        cards.append({'lower':lower,'upper':upper,'physical_front':r['face'],'native_back_facing':backing_face,
            'arrow_property':arrow,'platform':r['platform'],'diagram':diagram,'reader':reader,'old_full_nbt':tag.snbt(),'dependencies':deps})
    report={'fixtures':cards,'cells':6,'full_new_native_be':6,'actual_collision_source_sha256':hashlib.sha256((WORLD/'native_collision_shapes.json').read_bytes()).hexdigest(),
        'source_reference':'Pinned MTR4.0.5 actual BlockRouteSignBase/RenderRouteSign and official wiki route_sign',
        'world_written':False,'native_direction_and_readability':'PENDING','whole_station_acceptance':False}
    p.meta.update(report);inv.meta.update({'complete_inverse':True})
    p.save_plan('three_native_wall_route_signs');inv.save_plan('inverse_three_native_wall_route_signs')
    (OUT/'contract.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    (OUT/'native_cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),'utf8')
    (OUT/'cameras.json').write_text(json.dumps(views,ensure_ascii=False,indent=2),'utf8')
    print('Native signs trial: three complete backed fixtures, six actual-shape bypass paths; world unchanged')


if __name__=='__main__':main()
