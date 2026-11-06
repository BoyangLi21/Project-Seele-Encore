"""Root final physical seats and recesses for the fifteen remaining shaft seals."""
import argparse,json,math,uuid
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--retained-surface-bulkheads',action='store_true');args=ap.parse_args()
    stage='retained_surface_column_nine_bulkheads'if args.retained_surface_bulkheads else'fifteen_source_matched_hatch_bearings';out=BASE/'launch_hatch_bearings'
    assert not list((out/stage).glob('applied_*'))
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront'
    painter=vox.Painter(vertical_bounds=(-960,320));gates=[];snapshots=[];count=0
    cases=[(1,f'retained_{i+1}',y,-36)for i,y in enumerate((-332,-192,-52))]if args.retained_surface_bulkheads else[(1,'surface',80,-36),(2,'surface',-476,-329),(1,'upper',-568,124),(2,'upper',-568,-329),(3,'upper',-568,-782)]
    for bank,kind,y,cz in cases:
        lo=(-34,y-5,cz-19);hi=(96,y+6,cz+19);before,names=measure(lo,hi)
        for s in ('minecraft:air','projectseele:nerv_structural_panel'):
            if s not in names:names.append(s)
        ids={s:i for i,s in enumerate(names)};after=before.copy()
        holes=lambda x,z:any(abs(x-cx)<=15 and abs(z-cz)<=15 for cx in(-12,30,72))
        for lane,cx in enumerate((-12,30,72)):
            seal=before[y-lo[1],cz-15-lo[2]:cz+16-lo[2],cx-15-lo[0]:cx+16-lo[0]]
            assert seal.shape==(31,31)and all(names[int(v)]=='minecraft:barrier'for v in np.unique(seal)),(bank,kind,lane,'not a complete seal')
            for x in range(cx-21,cx+22):
                for z in range(cz-18,cz+19):
                    if holes(x,z):continue
                    after[y-5-lo[1]:y-2-lo[1],z-lo[2],x-lo[0]]=ids['projectseele:nerv_structural_panel']
                    after[y-2-lo[1]:y-lo[1],z-lo[2],x-lo[0]]=ids['minecraft:air']
                    # Clear only the model's side cassette space, not the
                    # neighbouring pedestrian decks at the closed datum.
                    if abs(x-cx)>=16 and abs(z-cz)<=17:
                        after[y-lo[1]:,z-lo[2],x-lo[0]]=ids['minecraft:air']
            supports=[]
            for sx in(-1,1):
                for sz in(-1,1):
                    for off in(16.1,20.4):
                        point=[cx+.5+sx*off,y-2,cz+.5+sz*16.1];x,z=math.floor(point[0]),math.floor(point[2])
                        assert names[int(after[y-3-lo[1],z-lo[2],x-lo[0]])]=='projectseele:nerv_structural_panel'
                        supports.append(dict(position=[x,y-3,z],state='projectseele:nerv_structural_panel',source_contact=point))
            gates.append(dict(resource=f'bank_{bank}_{kind}_lane_{lane}',visual=str(uuid.uuid5(uuid.NAMESPACE_URL,f'projectseele:r52:bank{bank}:{kind}:{lane}')),variant=2-lane,kind='SILO',stage=1 if kind=='upper'else 3,frame=dict(position=[cx+.5,y+.02,cz+.5],quaternion=[0,0,0,1]),width=31,height=31,silo_hatch=dict(opening_x=31,opening_z=31,open_ticks=80,close_ticks=20,separation_sign=1,beam_bottom=-2.02,service_column_ports=False),supports=supports,closed_box=[cx-15,y,cz-15,cx+15,y,cz+15]))
        # The rear serial door reaches this component's lower corner. Its
        # independent sealed cells remain owned by that door, never by this
        # horizontal hatch's foundation fill.
        pressure=before==ids['minecraft:barrier'];after[pressure]=before[pressure]
        touched={names[int(v)]for v in np.unique(before[before!=after])}
        # The retained surface outlet includes its coloured lane rim and top
        # shaft-ladder segment. This exact machinery envelope replaces that
        # rim; it does not grant edits to rooms, devices or surrounding roads.
        rim={'minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]',
             'minecraft:black_concrete','minecraft:iron_block','minecraft:light_gray_concrete',
             'minecraft:polished_basalt[axis=y]','minecraft:sea_lantern','minecraft:smooth_stone',
             'minecraft:chiseled_quartz_block','minecraft:orange_concrete','minecraft:purple_concrete',
             'minecraft:red_concrete','minecraft:ladder[facing=north,waterlogged=false]',
             'minecraft:ladder[facing=south,waterlogged=false]'}
        assert all(s.startswith('projectseele:nerv_')or s in rim for s in touched),(bank,kind,touched)
        for pos,tag in iter_block_entities(vox.WORLD,vox.DIM,lo,hi):
            x,yy,z=pos;assert before[yy-lo[1],z-lo[2],x-lo[0]]==after[yy-lo[1],z-lo[2],x-lo[0]],(pos,str(tag['id']))
        count+=runs(painter,lo,before,after,names,'R52_real_hatch_seats_and_cassettes');snapshots.append((lo,hi,after,names))
    painter.meta.update(root_author=True,gate_count=len(gates));plan=painter.save_plan(stage)
    report=dict(world_written=False,cells=count,gates=gates,native_acceptance=False)
    if args.apply:
        report['application']=painter.apply(stage)
        for lo,hi,after,names in snapshots:
            a,p=measure(lo,hi);ids={s:i for i,s in enumerate(names)};assert np.array_equal(np.asarray([ids[s]for s in p])[a],after)
        report.update(world_written=True,whole_exact_readback=True)
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print('FINAL_HATCH_BEARINGS',count,'cells',len(gates),'gates',report['world_written'],flush=True)

if __name__=='__main__':main()
