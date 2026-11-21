"""Root's measured extension of the existing underground VTOL apron."""
import argparse,json
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    out=BASE/'underground_airport_expansion';plan=out/'three_original_style_stands'
    assert not list(plan.glob('applied_*')),'Never replay an installed airport stage'
    d=np.load(out/'SOURCE.npz');lo=tuple(map(int,d['origin']));before=d['states'];names=list(map(str,d['palette']));hi=(lo[0]+before.shape[2]-1,lo[1]+before.shape[0]-1,lo[2]+before.shape[1]-1)
    for s in ('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:gray_concrete','minecraft:white_concrete','minecraft:yellow_concrete','projectseele:nerv_structural_panel','minecraft:sea_lantern'):
        if s not in names:names.append(s)
    ids={s:i for i,s in enumerate(names)};after=before.copy()
    yy=np.arange(lo[1],hi[1]+1)[:,None,None];zz=np.arange(lo[2],hi[2]+1)[None,:,None];xx=np.arange(lo[0],hi[0]+1)[None,None,:]
    soil=np.isin(before,[i for i,s in enumerate(names)if s.split('[')[0]in('minecraft:grass_block','minecraft:stone','minecraft:dirt')])
    ground=np.max(np.where(soil,yy,-32768),axis=0);assert (ground>-32768).all()
    dist=np.maximum.reduce([np.broadcast_to(-930-xx,(1,before.shape[1],before.shape[2])),np.broadcast_to(xx+531,(1,before.shape[1],before.shape[2])),np.broadcast_to(-350-zz,(1,before.shape[1],before.shape[2])),np.broadcast_to(zz+190,(1,before.shape[1],before.shape[2])),np.zeros((1,before.shape[1],before.shape[2]))])
    approved=(dist<10)&(xx<=-531);hard=(dist==0)&(xx>=-930)&(xx<=-531)&(zz>=-350)&(zz<=-190)
    target=np.rint(ground+np.clip(1-dist/10,0,1)*(-476-ground)).astype(np.int16)
    top=target;low=np.minimum(ground,top)-3
    fill=approved&(yy>=low)&(yy<=top);after[fill]=ids['minecraft:stone']
    after[approved&(yy>top)&(yy<=np.maximum(ground,top)+2)]=ids['minecraft:air']
    shoulder=approved&~hard
    after[shoulder&(yy>=top-2)&(yy<top)]=ids['minecraft:dirt'];after[shoulder&(yy==top)]=ids['minecraft:grass_block[snowy=false]']
    after[hard&(yy>=-478)&(yy<=-477)]=ids['projectseele:nerv_structural_panel'];after[hard&(yy==-476)]=ids['minecraft:gray_concrete']
    after[hard&(yy>-476)]=ids['minecraft:air']
    # Flush paint/light fittings leave the entire measured wing and gear
    # envelope clear. Existing control post, plane, masts and apron unchanged.
    white=hard&((zz==-346)|(zz==-194)|(xx==-926));yellow=np.zeros_like(hard)
    for cx in(-640,-840):
        yellow|=hard&((xx==cx)&(zz>=-330)&(zz<=-215))
        yellow|=hard&((zz==-215)&(xx>=cx-10)&(xx<=cx+10))
        white|=hard&((xx==cx-72)|(xx==cx+72))&((zz>=-328)&(zz<=-312)|(zz>=-220)&(zz<=-204))
    after[white&(yy==-476)]=ids['minecraft:white_concrete'];after[yellow&(yy==-476)]=ids['minecraft:yellow_concrete']
    after[hard&(yy==-476)&((zz==-348)|(zz==-192))&((xx+930)%32==0)]=ids['minecraft:sea_lantern']
    changed=before!=after
    allowed={'minecraft:air','minecraft:void_air','minecraft:cave_air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:grass','minecraft:fern'}
    assert{names[int(v)]for v in np.unique(before[changed])}<=allowed
    assert np.array_equal(after[:,:,-530-lo[0]:],before[:,:,-530-lo[0]:]),'Original apron changed'
    tags=dict(iter_block_entities(BASE/'WORLD_R52','projectseele:geofront',lo,hi));assert not tags
    current,pal=measure(lo,hi);assert np.array_equal(np.asarray([ids[s]for s in pal],np.uint16)[current],before),'Survey changed'
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320))
    n=runs(p,lo,before,after,names,'R52_measured_northwest_airfield_extension')
    p.meta.update(root_author=True,original_airport_preserved=True,new_stands=[[-640,-464,-270],[-840,-464,-270]],apron_y=-476,gear_y=-475,aircraft_creation_pending=True)
    plan=p.save_plan('three_original_style_stands');report=dict(world_written=False,changed_cells=n,new_stands=p.meta['new_stands'],
        original_stand=[-440,-464,-270],original_apron_and_control_post_unchanged=True,airport_capacity_after=3,
        flat_body_space=[[-930,-475,-350],[-531,-330,-190]],terrain_shoulder_width=10,
        pending=['two explicit new aircraft identities','full native aircraft and cargo flight/receiver acceptance'])
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    if args.apply:
        receipt=p.apply('three_original_style_stands');actual,pal=measure(lo,hi)
        assert np.array_equal(np.asarray([ids[s]for s in pal],np.uint16)[actual],after)
        report.update(world_written=True,receipt=receipt,whole_apron_exact_readback=True);(plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')


if __name__=='__main__':main()
