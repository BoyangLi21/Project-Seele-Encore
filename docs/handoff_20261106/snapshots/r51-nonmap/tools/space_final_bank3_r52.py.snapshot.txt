"""Give the third bank the same 453m spacing as banks one and two.

Only Root's never-delivered third lower well is moved. The intact original
R50 bank cross-section and personnel/rail hall are reused byte-for-byte.
"""
import argparse,json,math
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE,HANGAR
from facility_frame_nbt_r52 import state_in_frame
from plan_factory_r20 import guide_y
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    out=BASE/'bank3_spacing';stage='final_three_equal_spaced_banks';assert not list((out/stage).glob('applied_*'))
    lo=(-54,-680,-800);hi=(108,-546,-348);before,pal=measure(lo,hi)
    source=np.load(BASE/'survey/original_hangar_transfer_launch.npz');a=source['states'];o=source['origin'];sp=list(map(str,source['palette']))
    names=list(dict.fromkeys(pal+[state_in_frame(s,HANGAR)for s in sp]+['minecraft:stone','minecraft:deepslate[axis=y]','projectseele:nerv_machine_edge']))
    ids={s:i for i,s in enumerate(names)};before=np.asarray([ids[s]for s in pal],np.uint16)[before];after=before.copy();owned=np.zeros_like(before,bool)
    def sl(b):
        x,y,z,X,Y,Z=b;assert lo[0]<=x<=X<=hi[0]and lo[1]<=y<=Y<=hi[1]and lo[2]<=z<=Z<=hi[2]
        return np.s_[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]
    def put(b,v):after[sl(b)]=v;owned[sl(b)]=True
    remap=np.asarray([ids[state_in_frame(s,HANGAR)]for s in sp],np.uint16)
    bank=remap[a[-444-o[1]:-310-o[1]+1,-54-o[2]:-18-o[2]+1,-29-o[0]:89-o[0]+1]][:,::-1,::-1]
    old_box=(-29,-680,-467,89,-546,-431);assert np.array_equal(before[sl(old_box)],bank),'Old Root-only bank was externally changed'
    # Retire the entire old third well, including its floor/top, then install
    # one continuous existing-style level hall through that former footprint.
    geology=np.array([ids['minecraft:deepslate[axis=y]'if y< -672 else'minecraft:stone']for y in range(-680,-545)],np.uint16)[:,None,None]
    put(old_box,np.broadcast_to(geology,bank.shape))
    put((-29,-680,-800,89,-546,-764),bank)
    z=-100;g=int(math.floor(guide_y(z)));section=remap[a[g-6-o[1]:g+86-o[1]+1,z-o[2],:]][:,::-1]
    put((-54,-653,-763,108,-561,-348),np.repeat(section[:,None,:],416,axis=1))
    for zz in range(-763,-347,20):
        for xx in(-53,107):put((xx,-652,zz,xx,-562,min(-348,zz+1)),ids['projectseele:nerv_machine_edge'])
    original=np.zeros_like(owned);original[sl(old_box)]=True;original[sl((-54,-653,-430,108,-561,-348))]=True
    observed={names[int(v)]for v in np.unique(before[owned&~original])}
    assert observed<={'minecraft:stone','minecraft:deepslate[axis=y]','minecraft:deepslate','minecraft:bedrock'},observed
    tags=dict(iter_block_entities(BASE/'WORLD_R52','projectseele:geofront',lo,hi));assert not tags,'No original device may be moved in this new empty bank'
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320))
    n=runs(p,lo,before,after,names,'R52_only_new_third_bank_equal_spacing')
    p.meta.update(root_author=True,original_hangar_and_ramp_unchanged=True,first_two_banks_unchanged=True,third_bank_z=-781.5,
                  three_bank_centres_z=[124.5,-328.5,-781.5],two_identical_level_corridors=True)
    plan=p.save_plan(stage);report=dict(world_written=False,changed_cells=n,old_third_bank_z=-448.5,new_third_bank_z=-781.5,
                 bank_spacing=453,third_source_section_exact=True,new_track_hall_bounds=[[-54,-653,-763],[108,-561,-348]],
                 original_actors_or_devices_written=False,first_two_banks_unchanged=True,original_hangar_ramp_unchanged=True,
                 retired_old_third_well_complete=True,pending=['final parallel third outlet','updated fixed guide instances and runtime directory'])
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    if args.apply:
        receipt=p.apply(stage);actual,pa=measure(lo,hi);assert np.array_equal(np.asarray([ids[s]for s in pa],np.uint16)[actual],after)
        report.update(world_written=True,receipt=receipt,whole_section_exact_readback=True);(plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')


if __name__=='__main__':main()
