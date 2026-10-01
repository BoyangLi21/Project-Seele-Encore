"""Relocate two existing blocked information fixtures as complete components.

Uses original board NBT and real platform boarding mouths; no corridor or
ceiling is cut to make a label visible. This produces exact plans only.
"""
from pathlib import Path
import copy, json, math
import nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld, properties
from query_blocks import AIR, iter_block_entities
from audit_facility_transit_r44 import Geometry, NORMAL
from plan_tv_cage_cameras_r44 import optical_ray
from station_route_contract_r44 import RouteDiagrams

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/facility_transit_r44/existing_sign_readers_v1'


def main():
    assert not OUT.exists()
    sites=[((-1484,121,664),(-1486,121,664),'west',(-1489,119,664),1700974792440530138),
        ((-296,-463,771),(-296,-466,771),'south',(-296,-466,774),7409068398910781353)]
    w=MeasuredWorld(WORLD)
    for old,q,face,reader,pid in sites:w.around(q,28)
    w.load();g=Geometry(w);diagrams=RouteDiagrams()
    platforms=json.loads((OUT.parent/'platform_interfaces/interfaces.json').read_text('utf8'))['platforms']
    p,inv=v.Painter(),v.Painter();v.WORLD,v.OUT=WORLD,OUT;cards=[];cases=[];cameras=[]
    for old,q,face,reader,pid in sites:
        state=w.block(old);tag=dict(iter_block_entities(WORLD,v.DIM,old,old))[old]
        assert state.startswith('projectseele:station_departure_board')
        nx,nz=NORMAL[face];wayfinding=properties(state)['wayfinding']=='true'
        target=state.replace('facing='+properties(state)['facing'],'facing='+face)
        volume=[(q[0]+a*nz,q[1]+h,q[2]+a*nx) for a in (-1,0,1) for h in (0,1)]
        assert all(w.block(t) in AIR for t in volume)
        backing=[(q[0]-nx+a*nz,q[1]+h,q[2]-nz+a*nx) for a in (-1,0,1) for h in (0,1)]
        assert all(g.boxes(w.block(t))==[[0.,0.,0.,1.,1.,1.]] for t in backing)
        assert g.standing(reader)['status']=='STATIC_STANDING'
        eye=[reader[0]+.5,reader[1]+1.62,reader[2]+.5]
        glyph=[q[0]+.5+nx*.205,q[1]+(1 if wayfinding else .8),q[2]+.5+nz*.205]
        assert optical_ray(w,g,eye,glyph) is None
        original_get=w.get
        replacements={old:'minecraft:air',q:target}
        w.get=lambda x,y,z:replacements.get((x,y,z),original_get(x,y,z))
        platform=next(t for t in platforms if int(t['id'])==pid);paths=[]
        for gate in platform['gates']:
            start=tuple(gate['approach'])
            if abs(start[1]-reader[1])>.01 or math.dist(start,reader)>22:continue
            path=g.flat_path(start,reader,radius=28)
            if path:paths.append(path)
        assert paths,('No real boarding-mouth path to the relocated fixture',q)
        path=min(paths,key=len)
        w.get=original_get
        new=copy.deepcopy(tag)
        for name,value in zip(('x','y','z'),q):new[name]=nbtlib.Int(value)
        if 'MapRows' in new:
            d=diagrams.diagram(pid,face)
            new['MapRows']=nbtlib.List[nbtlib.String]([nbtlib.String(s) for s in d['rows']])
            for i in range(3):new['Row'+str(i)]=nbtlib.String(d['rows'][i])
        p.match((*old,*old),state,'minecraft:air','r44/retire_blocked_whole_information_fixture')
        p.match((*q,*q),w.block(q),target,'r44/relocate_fixture_to_actual_public_reader')
        p.block_entities[q]=new
        inv.match((*old,*old),'minecraft:air',state,'inverse/r44/old_information_fixture')
        inv.match((*q,*q),target,w.block(q),'inverse/r44/new_information_fixture')
        inv.block_entities[old]=copy.deepcopy(tag)
        for reverse in (False,True):
            points=path[::-1] if reverse else path
            cases.append({'id':f'r44/relocated_reader/{len(cards)}'+('/return' if reverse else ''),'path':[[x+.5,y,z+.5] for x,y,z in points]})
        delta=[glyph[i]-eye[i] for i in range(3)]
        cameras.append({'file':f'r44_relocated_information_{len(cards)}.png','position':[reader[0]+.5,reader[1],reader[2]+.5],
            'yaw':math.degrees(math.atan2(-delta[0],delta[2])),'pitch':math.degrees(math.atan2(-delta[1],math.hypot(delta[0],delta[2]))),
            'fovDegrees':70,'warmupTicks':360,'requiredSections':[q,list(old)]})
        cards.append({'old_position':old,'new_position':q,'old_state':state,'new_state':target,'old_full_nbt':tag.snbt(),'new_full_nbt':new.snbt(),
            'reader':reader,'actual_boarding_path':path,'fixed_backing':[{'position':t,'state':w.block(t)} for t in backing],
            'authority':'Retained actual fixture and native platform interface; existing station fabric is preserved',
            'full_fixture_render_volume':volume,'stair_ceiling_or_moving_device_carved':False})
    p.meta.update(fixtures=cards);p.save_plan('whole_existing_information_fixtures')
    inv.save_plan('inverse_whole_existing_information_fixtures')
    (OUT/'contract.json').write_text(json.dumps({'fixtures':cards,'cells':4,'world_written':False,'native_passed':False,'visual_passed':False},ensure_ascii=False,indent=2),'utf8')
    (OUT/'native_cases.json').write_text(json.dumps(cases,indent=2),'utf8')
    (OUT/'cameras.json').write_text(json.dumps(cameras,indent=2),'utf8')
    print('Two complete fixture candidates, four cells, four real boarding-reader paths; world unchanged')


if __name__=='__main__':main()
