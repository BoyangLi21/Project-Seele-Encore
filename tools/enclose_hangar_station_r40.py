"""Close the measured upper facade gaps without sealing connected passenger halls or rail portals."""
import argparse,json
from pathlib import Path
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,WORLD,ROOT
from query_blocks import AIR,iter_block_entities
OUT=ROOT/'artifacts/world_combat_r40/hangar_station'

def main(apply=False):
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();w=MeasuredWorld();w.box((108,-446,-60),(194,-429,-20));w.load();protected=dict(iter_block_entities(WORLD,v.DIM,(108,-446,-60),(194,-429,-20)))
    frame='projectseele:nerv_structural_panel';glass='projectseele:clear_glass';walls={};ports=[]
    edges=[((x,z),(0,side)) for x in range(112,190) for z,side in [(-55,-1),(-25,1)]]
    edges += [((x,z),(side,0)) for z in range(-54,-25) for x,side in [(112,-1),(189,1)]]
    floor_names={frame,'projectseele:nerv_floor_panel','minecraft:smooth_stone','minecraft:polished_deepslate','minecraft:light_gray_concrete'}
    for (x,z),(dx,dz) in edges:
        ox,oz=x+dx,z+dz
        outside_floor=(w.get(ox,-443,oz) or '').partition('[')[0] in floor_names
        clear=all((w.get(ox,Y,oz) or '').partition('[')[0] in AIR|{'minecraft:light'} for Y in [-442,-441])
        ceiling=next((Y for Y in range(-440,-431) if (w.get(ox,Y,oz) or '').partition('[')[0] in floor_names),None)
        connected=outside_floor and clear and ceiling is not None
        # This is the registered south entrance used by the complete pyramid
        # -> train route. Its outer concourse has a higher ceiling than this
        # facade probe, so ceiling-range inference alone must not seal it.
        if z==-25 and 148<=x<=153:
            connected=True;ceiling=-438
        rail=x in (112,189) and -43<=z<=-37
        if connected:ports.append(dict(x=x,z=z,ceiling=ceiling))
        for y in range(-443,-432):
            if rail and -443<=y<=-437:continue
            if connected and -442<=y<ceiling:continue
            q=x,y,z;old=w.block(q)
            if q in protected or old.startswith(('mtr:','movingelevators:')):continue
            if any(t in old for t in ('stairs','button','lever','door','one_way','escalator')):continue
            after=frame if y in (-443,-442,-436,-433) or (x+z)%14 in (0,1) else glass
            if old!=after:walls[q]=after
    for q,after in sorted(walls.items()):p.match((*q,*q),w.block(q),after,'r40/hangar_station/continuous_glazed_envelope')
    p.meta.update(bounds=[112,-443,-55,189,-433,-25],connected_hall_apertures=ports,rail_portal_width=7,rail_portal_height=7,station_platform_ids=[-4991105154196472855],render_evidence='r40_hangar_station.png confirmed open upper facade, rather than a cutaway artefact')
    p.save_plan('station_envelope')
    if apply:p.apply('station_envelope')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Facade repairs',len(walls),'connected hall columns',len(ports))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
