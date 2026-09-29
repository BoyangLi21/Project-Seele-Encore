"""Reuse four isolated under-stair landings as accessible east-wing vestibules."""
from pathlib import Path
import argparse,json
import nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43';WORLD=ROOT/'run/saves/SEELE_FIELD_R43_REVIEW';OUT=ART/'pyramid_east_antechambers';LEVELS=(-434,-420,-406,-392)

def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    assert not list(OUT.glob('accessible_vestibules/applied_*/receipt.json')),'Already migrated'
    before=json.loads((OUT/'before_native_result.json').read_text());assert len(before)==4 and all(r['status']=='blocked_by_native_collision' for r in before)
    w=MeasuredWorld(WORLD);tags={}
    for y in LEVELS:
        w.box((66,y-1,350),(78,y+5,359));tags.update(iter_block_entities(WORLD,v.DIM,(66,y-1,350),(78,y+5,359)))
    w.load();v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();cases=[];portals=[]
    for y in LEVELS:
        # The existing paired moving walk already stops before this crossing.
        for x in range(69,78):
            for z in (355,356):
                assert w.get(x,y-1,z)=='projectseele:nerv_floor_panel',(x,y,z,'continuous existing sill required')
                if x!=72:
                    for yy in range(y,y+3):assert w.get(x,yy,z).partition('[')[0] in AIR|{'minecraft:light'},(x,yy,z,'preserve fixtures')
        for z in (355,356):
            for yy in range(y,y+3):
                q=(72,yy,z);s=w.block(q);assert q not in tags and s in {'projectseele:nerv_wall_panel','projectseele:nerv_wall_datum','projectseele:clear_glass'},(q,s)
                p.match((*q,*q),s,'minecraft:air','r43/east_antechamber/complete_two_metre_portal')
        # Keep a continuous lintel and use a flush trim on its existing jambs.
        for z in (354,357):
            for yy in range(y,y+4):
                q=(72,yy,z);s=w.block(q);assert q not in tags and s in {'projectseele:nerv_wall_panel','projectseele:nerv_wall_datum','projectseele:nerv_structural_panel','projectseele:clear_glass'},(q,s)
                p.match((*q,*q),s,'projectseele:nerv_machine_edge','r43/east_antechamber/flush_jamb')
        for z in (355,356):
            q=(72,y+3,z);s=w.block(q);assert q not in tags and s.partition('[')[0] in {'projectseele:nerv_wall_panel','projectseele:nerv_structural_panel'}
            p.match((*q,*q),s,'projectseele:nerv_machine_edge','r43/east_antechamber/retained_lintel')
        q=(71,y+3,355);s=w.block(q);assert q not in tags and s.partition('[')[0] in AIR
        state='projectseele:nerv_direction_panel[facing=west,wayfinding=true]';p.match((*q,*q),s,state,'r43/east_antechamber/visible_exit_header')
        p.block_entities[q]=nbtlib.Compound(dict(id=nbtlib.String('projectseele:station_departure_board'),x=nbtlib.Int(q[0]),y=nbtlib.Int(q[1]),z=nbtlib.Int(q[2]),Wayfinding=nbtlib.Byte(1),Station=nbtlib.String('东翼楼梯前室'),Route=nbtlib.String('通行指引'),Row0=nbtlib.String('↑ 东翼连廊'),Row1=nbtlib.String('电梯 · 主通道'),Row2=nbtlib.String('沿连廊前往直梯')))
        for z in (355.5,356.5):
            path=[[68.5,y,z],[76.5,y,z]]
            cases.extend([dict(id=f'r43/east_antechamber/{y}/{z}',path=path),dict(id=f'r43/east_antechamber/{y}/{z}/return',path=path[::-1])])
        portals.append(dict(floor_feet=y,aperture=[[72,y,355],[72,y+2,356]],stationary_landing=[[73,y-1,354],[77,y-1,358]],retained='Existing stair flights, glass/rail fall protection, complete floor and ceiling'))
    p.meta.update(portals=portals,walk_cases=cases,source='R04 complete stair-core slabs left isolated space north of each flight; the east corridor shell had no same-floor port here',
        design='Reuse existing under-stair floor as a service vestibule. Original circulation decision inspired by ordinary service lobbies; not presented as a specific TV set.',
        scope='Four lower east stair-core levels, excluding accepted command interior and all elevator/mechanical sweeps',validation='Before four native collision failures; after full-width traversal and visual checks pending')
    p.save_plan('accessible_vestibules');(OUT/'after_cases.json').write_text(json.dumps(cases,indent=2),'utf8')
    if apply:
        (OUT/'quality_walk_cases.before.json').write_bytes((WORLD/'quality_walk_cases.json').read_bytes());p.apply('accessible_vestibules')
        rows=json.loads((WORLD/'quality_walk_cases.json').read_text());rows.extend(cases);(WORLD/'quality_walk_cases.json').write_text(json.dumps(rows,ensure_ascii=False,separators=(',',':')),'utf8');(WORLD/'r43_walk_cases.json').write_text(json.dumps(cases),'utf8');(WORLD/'pyramid_east_antechambers_r43.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),'utf8')
    print('Four complete framed portals;',len(cases),'full-width native paths planned',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
