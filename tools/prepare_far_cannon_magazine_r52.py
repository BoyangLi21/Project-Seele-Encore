"""Root founded fixed-cannon lift pit and its source-sized 39 by 53m hatch."""
import argparse,hashlib,json,math,uuid
from pathlib import Path
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    root=Path(__file__).resolve().parents[1];out=BASE/'far_cannon_magazine';stage='founded_original_cannon_lift_chamber';assert not list((out/stage).glob('applied_*'))
    measurefile=root/'artifacts/r52_original_owner_candidate_20261010/ACTUAL_FINAL_DOOR_CIVIL_MEASUREMENTS_OCT11.json';source=json.loads(measurefile.read_text('utf8'))['cannon_hatch']
    lo=(-1279,157,-1429);hi=(-1224,180,-1366);a,names=measure(lo,hi)
    for s in ('minecraft:air','minecraft:barrier','projectseele:nerv_structural_panel','projectseele:nerv_floor_panel','minecraft:sea_lantern'):
        if s not in names:names.append(s)
    ids={s:i for i,s in enumerate(names)};b=a.copy()
    def fill(box,state):
        x,y,z,X,Y,Z=box;assert lo[0]<=x<=X<=hi[0]and lo[1]<=y<=Y<=hi[1]and lo[2]<=z<=Z<=hi[2]
        b[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]=ids[state]
    fill((-1273,157,-1426,-1231,173,-1369),'projectseele:nerv_structural_panel')
    fill((-1271,159,-1424,-1233,159,-1372),'projectseele:nerv_floor_panel')
    fill((-1271,160,-1424,-1233,173,-1372),'minecraft:air')
    for x in(-1272,-1232):
        for z in(-1420,-1405,-1390,-1375):fill((x,164,z,x,164,z),'minecraft:sea_lantern')
    # Finite bearing and cassette room derived from the actual same-source
    # complete curve. The sealed opening remains one exact collision table.
    bounds=source['full_curve_bounds'];x,z=math.floor(bounds[0]),math.floor(bounds[2]);X,Z=math.ceil(bounds[3])-1,math.ceil(bounds[5])-1
    for xx in range(x,X+1):
        for zz in range(z,Z+1):
            if -1271<=xx<=-1233 and -1424<=zz<=-1372:continue
            fill((xx,169,zz,xx,171,zz),'projectseele:nerv_structural_panel')
            fill((xx,172,zz,xx,180,zz),'minecraft:air')
    fill((-1271,174,-1424,-1233,174,-1372),'minecraft:barrier')
    bearings=source.get('bearing_points',[]);assert len(bearings)==8,source.keys()
    supports=[]
    for r in bearings:
        q=r.get('world',r.get('point'));assert q is not None,r
        xx,yy,zz=math.floor(q[0]),round(q[1])-1,math.floor(q[2]);assert yy==171
        assert names[int(b[yy-lo[1],zz-lo[2],xx-lo[0]])]=='projectseele:nerv_structural_panel'
        supports.append(dict(position=[xx,yy,zz],state='projectseele:nerv_structural_panel',source_contact=q))
    assert not list(iter_block_entities(BASE/'WORLD_R52','projectseele:geofront',lo,hi))
    assert{names[int(v)]for v in np.unique(a[a!=b])}<=set(('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]'))
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320));n=runs(p,lo,a,b,names,'R52_actual_original_cannon_lift_room')
    # Both top entries are real redstone inputs with existing solid support.
    small=[]
    for point,state in [((-1315,175,-1373),'minecraft:lever[face=floor,facing=east,powered=false]'),((-1302,175,-1374),'minecraft:stone_button[face=floor,facing=north,powered=false]')]:
        arr,pal=measure(point,point);old=pal[int(arr[0,0,0])];assert old=='minecraft:air',(point,old)
        base=(point[0],point[1]-1,point[2]);v,pal2=measure(base,base);assert pal2[int(v[0,0,0])]not in('minecraft:air','minecraft:water')
        p.exact((*point,*point),old,state,'R52_service_hatch_and_cannon_inputs');small.append((point,state))
    gate=dict(resource='yashima_cannon_hatch',visual=str(uuid.uuid5(uuid.NAMESPACE_URL,'projectseele:r52:yashima:cannon:hatch')),kind='SILO',variant=1,stage=3,frame=dict(position=source['position'],quaternion=source['quaternion']),width=39,height=53,silo_hatch=dict(opening_x=39,opening_z=53,open_ticks=80,close_ticks=80,separation_sign=1,beam_bottom=-2.02,service_column_ports=False),supports=supports,closed_box=[-1271,174,-1424,-1233,174,-1372])
    p.meta.update(root_author=True,gate=gate,source_measurement_sha256=hashlib.sha256(measurefile.read_bytes()).hexdigest());plan=p.save_plan(stage)
    report=dict(world_written=False,changed_cells=n+2,gate=gate,cannon_uuid=str(uuid.uuid5(uuid.NAMESPACE_URL,'projectseele:r52:yashima:fixed_cannon')),raised_position=[-1242.5,174,-1400.5],closed_position=[-1242.5,157.5,-1400.5],stroke=16.5,solid_pit_floor=159,cradle_contact_y=160,interaction_control=[-1302,175,-1374],native_acceptance=False)
    if args.apply:
        report['application']=p.apply(stage);actual,pal=measure(lo,hi);assert np.array_equal(np.asarray([ids[s]for s in pal])[actual],b)
        for point,state in small:
            arr,pal=measure(point,point);assert pal[int(arr[0,0,0])]==state
        report.update(world_written=True,whole_exact_readback=True)
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items()if k!='gate'}),flush=True)

if __name__=='__main__':main()
