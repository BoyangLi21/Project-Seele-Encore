"""Root separates horizontal hatch foundations from the actual rear-door lintel."""
import copy,json,math
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities

def main():
    out=BASE/'launch_hatch_bearings';stage='upper_seals_above_rear_lintels';assert not list((out/stage).glob('applied_*'))
    original=json.loads((out/'fifteen_source_matched_hatch_bearings/PLAN.json').read_text());gates=[];snapshots=[];count=0
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320))
    for bank,cz in((1,124),(2,-329),(3,-782)):
        lo=(-34,-570,cz-19);hi=(96,-559,cz+19);a,names=measure(lo,hi)
        for s in('minecraft:air','minecraft:barrier','projectseele:nerv_structural_panel'):
            if s not in names:names.append(s)
        ids={s:i for i,s in enumerate(names)};b=a.copy()
        def holes(x,z):return any(abs(x-cx)<=15 and abs(z-cz)<=15 for cx in(-12,30,72))
        for lane,cx in enumerate((-12,30,72)):
            for x in range(cx-21,cx+22):
                for z in range(cz-18,cz+19):
                    if holes(x,z):continue
                    b[:3,z-lo[2],x-lo[0]]=ids['projectseele:nerv_structural_panel']
                    b[3:5,z-lo[2],x-lo[0]]=ids['minecraft:air']
                    if abs(x-cx)>=16 and abs(z-cz)<=17:b[5:,z-lo[2],x-lo[0]]=ids['minecraft:air']
            lower=a[-568-lo[1],cz-15-lo[2]:cz+16-lo[2],cx-15-lo[0]:cx+16-lo[0]]
            upper=a[-565-lo[1],cz-15-lo[2]:cz+16-lo[2],cx-15-lo[0]:cx+16-lo[0]]
            assert np.all(lower==ids['minecraft:barrier']),('lower',bank,lane,{names[int(v)]:int((lower==v).sum())for v in np.unique(lower)})
            upper_states={names[int(v)]for v in np.unique(upper)}
            assert upper_states<=({'minecraft:air','projectseele:nerv_shaft_panel'}if bank==3 else{'minecraft:air'}),('upper',bank,lane,upper_states)
            b[-568-lo[1],cz-15-lo[2]:cz+16-lo[2],cx-15-lo[0]:cx+16-lo[0]]=ids['minecraft:air']
            b[-565-lo[1],cz-15-lo[2]:cz+16-lo[2],cx-15-lo[0]:cx+16-lo[0]]=ids['minecraft:barrier']
            g=copy.deepcopy(next(g for g in original['gates']if g['resource']==f'bank_{bank}_upper_lane_{lane}'))
            g['frame']['position'][1]+=3;g['closed_box'][1]+=3;g['closed_box'][4]+=3
            for s in g['supports']:
                s['position'][1]+=3;s['source_contact'][1]+=3;x,y,z=s['position'];assert names[int(b[y-lo[1],z-lo[2],x-lo[0]])]==s['state']
            gates.append(g)
        assert not list(iter_block_entities(vox.WORLD,vox.DIM,lo,hi))
        count+=runs(p,lo,a,b,names,'R52_separate_actual_horizontal_and_vertical_frames');snapshots.append((lo,hi,b,names))
    p.meta.update(root_author=True,rear_gate_maximum_y=-570.65,new_support_foundation_bottom=-570,new_horizontal_gate_floor=-565,route_nodes_unchanged=True)
    plan=p.save_plan(stage);receipt=p.apply(stage)
    for lo,hi,b,names in snapshots:
        a,pal=measure(lo,hi);ids={s:i for i,s in enumerate(names)};assert np.array_equal(np.asarray([ids[s]for s in pal])[a],b)
    report=dict(world_written=True,changed_cells=count,gates=gates,whole_exact_readback=True,actual_rear_frame_to_foundation_clearance=.65,all_route_nodes_unchanged=True,application=receipt,native_acceptance=False)
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print('UPPER_GATE_SEPARATION',count,'cells; 9 gates; .65m between real assemblies',flush=True)

if __name__=='__main__':main()
