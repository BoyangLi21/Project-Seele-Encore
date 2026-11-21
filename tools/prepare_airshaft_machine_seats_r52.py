"""Root civil bearings/recesses for the measured actual 164m door sources."""
import argparse,json,hashlib,math,msvcrt
from pathlib import Path
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities
import survey_r52_original_complex as survey
import extend_world_depth_r52 as extension


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    base=args.base.resolve();world=base/'WORLD';survey.WORLD=extension.WORLD=world
    root=Path(__file__).resolve().parents[1];out=base/'air_transport_shaft';stage='actual_machine_bearings_and_cassettes'
    assert not list((out/stage).glob('applied_*'))
    sp=root/'.Codex/r52_airlift_draft/ACTUAL_LARGE_SILO_HATCH_MEASUREMENT_ROOT_DATUM68_01.json'
    vp=root/'.Codex/r52_airlift_draft/ACTUAL_VERTICAL_SIDE_STACK_MEASUREMENT.json'
    sd=json.loads(sp.read_text());vd=next(c for c in json.loads(vp.read_text())['cases']if c['net_width_height']==[164.,181.])
    assert sd['source_sha']==json.loads(vp.read_text())['source_sha']==hashlib.sha256((root/'src/main/resources/assets/projectseele/mesh/tv_facilities_r16.json').read_bytes()).hexdigest()
    assert sd['opening_xz']==[164.,164.] and sd['all_static_and_moving_extents'][1]==-2.01
    specs=[('horizontal',(-1226,62,-807),(-1015,69,-634),sd,[-1120,68.01,-720]),
           ('vertical',(-1226,-480,-642),(-1015,-290,-627),vd,[-1120,-475,-635])]
    vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-1344,320))
    cases=[];expected=[];changed=0
    for kind,lo,hi,geometry,frame in specs:
        before,names=measure(lo,hi)
        for s in ('minecraft:air','projectseele:nerv_structural_panel'):
            if s not in names:names.append(s)
        ids={s:i for i,s in enumerate(names)};after=before.copy()
        def fill(box,state):
            x,y,z,X,Y,Z=box;after[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]=ids[state]
        if kind=='horizontal':
            for x in range(lo[0],hi[0]+1):
                for z in range(lo[2],hi[2]+1):
                    if -1202<=x<=-1039 and -802<=z<=-639:continue
                    fill((x,62,z,x,65,z),'projectseele:nerv_structural_panel')
                    fill((x,66,z,x,67,z),'minecraft:air')
        else:
            # Eight real panels nest in four tiers per side. A continuous
            # footer and header carry the wide cassettes through native rock.
            fill((-1226,-480,-642,-1015,-476,-627),'projectseele:nerv_structural_panel')
            fill((-1226,-293,-642,-1015,-290,-627),'projectseele:nerv_structural_panel')
            fill((-1225,-475,-641,-1016,-294,-628),'minecraft:air')
            # Preserve the already installed closed pressure collision plane.
            barrier=names.index('minecraft:barrier');after[before==barrier]=barrier
        supports=[]
        for local in geometry['mandatory_bearing_points_local']:
            world=np.array(local)+frame;assert abs(world[1]-round(world[1]))<1e-6
            x,y,z=math.floor(world[0]),round(world[1])-1,math.floor(world[2]);state=names[int(after[y-lo[1],z-lo[2],x-lo[0]])]
            assert state=='projectseele:nerv_structural_panel',(kind,world.tolist(),state)
            supports.append(dict(position=[x,y,z],state=state,actual_source_contact=world.tolist()))
        assert not list(iter_block_entities(vox.WORLD,vox.DIM,lo,hi))
        changed+=runs(p,lo,before,after,names,'R52_actual_'+kind+'_door_bearing')
        expected.append((lo,hi,after,names));cases.append(dict(kind=kind,frame=frame,support_cells=supports))
    p.meta.update(root_author=True,measured_machine_sources=[str(sp),str(vp)],cases=cases,playable=False)
    plan=p.save_plan(stage);report=dict(world_written=False,changed_cells=changed,cases=cases,geometry_measurement_sha256={sp.name:hashlib.sha256(sp.read_bytes()).hexdigest(),vp.name:hashlib.sha256(vp.read_bytes()).hexdigest()},pending=['door controller installation','native opening/closing and flight clearance'])
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    if args.apply:
        lock=extension.acquire_world_lock()
        try:
            receipt=p.apply(stage,session_lock=lock)
            for lo,hi,after,names in expected:
                actual,pal=measure(lo,hi);mapping={s:i for i,s in enumerate(names)}
                assert np.array_equal(np.array([mapping[s]for s in pal],np.uint16)[actual],after)
            report.update(world_written=True,receipt=receipt,whole_recess_and_bearing_exact_readback=True);(plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
