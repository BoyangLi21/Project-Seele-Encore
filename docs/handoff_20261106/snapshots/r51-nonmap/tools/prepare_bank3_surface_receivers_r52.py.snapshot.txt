"""Root founded Hakone receivers, real closed holes and measured eight-seat frames."""
import argparse,json,math,uuid
from pathlib import Path
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    out=BASE/'bank3_surface_receivers';stage='three_founded_low_receivers';assert not list((out/stage).glob('applied_*'))
    lo=(-1244,40,1114);hi=(-1095,142,1186);before,names=measure(lo,hi)
    src=np.load(BASE/'bank3_outlet_parallel/SURFACE_SOURCE.npz');so=src['origin'];sp=list(map(str,src['palette']));a=src['states']
    soil=np.array([s.split('[')[0]in('minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel','minecraft:sand')for s in sp]);ys=np.arange(a.shape[0])+so[1]
    old=np.full(a.shape[1:],-32768,np.int16)
    for i,y in enumerate(ys):old=np.where(soil[a[i]],y,old)
    for s in ('minecraft:air','minecraft:barrier','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','projectseele:nerv_structural_panel','projectseele:nerv_floor_panel','projectseele:nerv_machine_edge'):
        if s not in names:names.append(s)
    ids={s:i for i,s in enumerate(names)};after=before.copy();cxes=(-1212,-1170,-1128);cz=1150
    def fill(x,y,z,X,Y,Z,state):
        assert lo[0]<=x<=X<=hi[0]and lo[1]<=y<=Y<=hi[1]and lo[2]<=z<=Z<=hi[2]
        after[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]=ids[state]
    holes=lambda x,z:any(abs(x-cx)<=15 and abs(z-cz)<=15 for cx in cxes)
    for x in range(lo[0],hi[0]+1):
        for z in range(lo[2],hi[2]+1):
            distance=math.hypot(max(-1234-x,0,x+1105),max(1126-z,0,z-1174))
            if distance>=10 or holes(x,z):continue
            ground=int(old[z-so[2],x-so[0]]);assert ground>=44
            t=min(1,distance/10);t=t*t*(3-2*t);height=round(68*(1-t)+ground*t)
            fill(x,min(ground-2,65),z,x,height,z,'minecraft:stone')
            if distance==0:
                fill(x,height-2,z,x,height-1,z,'projectseele:nerv_structural_panel');fill(x,height,z,x,height,z,'projectseele:nerv_floor_panel')
            else:
                fill(x,height-2,z,x,height-1,z,'minecraft:dirt');fill(x,height,z,x,height,z,'minecraft:grass_block[snowy=false]')
            fill(x,height+1,z,x,142,z,'minecraft:air')
    gates=[]
    for lane,cx in enumerate(cxes):
        fill(cx-15,68,cz-15,cx+15,68,cz+15,'minecraft:barrier')
        # Real source frame/cassette recess. Only the fixed four support beams
        # touch the below-grade seats; a solid apron must not cut their feet.
        for x in range(cx-21,cx+22):
            for z in range(cz-18,cz+19):
                if holes(x,z):continue
                fill(x,63,z,x,65,z,'projectseele:nerv_structural_panel');fill(x,66,z,x,67,z,'minecraft:air')
        support=[]
        for side in(-1,1):
            for end in(-1,1):
                for offset in(16.1,20.4):
                    point=[cx+.5+side*offset,66,cz+.5+end*16.1];x,z=math.floor(point[0]),math.floor(point[2])
                    assert names[int(after[65-lo[1],z-lo[2],x-lo[0]])]=='projectseele:nerv_structural_panel'
                    support.append(dict(position=[x,65,z],state='projectseele:nerv_structural_panel',source_contact=point))
        gates.append(dict(resource=f'bank_3_surface_lane_{lane}',visual=str(uuid.uuid5(uuid.NAMESPACE_URL,f'projectseele:r52:bank3:surface:{lane}')),variant=2-lane,kind='SILO',frame=dict(position=[cx+.5,68.02,cz+.5],quaternion=[0,0,0,1]),width=31,height=31,
                          silo_hatch=dict(opening_x=31,opening_z=31,open_ticks=80,close_ticks=20,separation_sign=1,beam_bottom=-2.02,service_column_ports=False),supports=support,closed_box=[cx-15,68,cz-15,cx+15,68,cz+15]))
    assert not list(iter_block_entities(BASE/'WORLD_R52','projectseele:geofront',lo,hi))
    touched={names[int(v)]for v in np.unique(before[before!=after])}
    assert not any('_log'in s or'_leaves'in s or'mtr:'in s for s in touched),touched
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320));n=runs(p,lo,before,after,names,'R52_founded_Hakone_receivers')
    p.meta.update(root_author=True,gates=gates,apron_floor=68,playable=False);plan=p.save_plan(stage)
    report=dict(world_written=False,changed_cells=n,gates=gates,apron_floor=68,native_soil_before_range=[int(old.min()),int(old.max())],founded_graded_transition_metres=10,pending=['actual controller and route commissioning','native launch and recovery'])
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print('BANK3_RECEIVERS',n,'cells',flush=True)
    if args.apply:
        receipt=p.apply(stage);actual,pal=measure(lo,hi);assert np.array_equal(np.array([ids[s]for s in pal],np.uint16)[actual],after)
        report.update(world_written=True,receipt=receipt,whole_apron_exact_readback=True);(plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')


if __name__=='__main__':main()
