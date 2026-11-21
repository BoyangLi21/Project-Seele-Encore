"""Architectural shell preview for the retained three bank-two well junctions.

Rectilinear shared proportions are chosen for the existing three active wells.
Measured route masks only exclude machinery; they do not choose room locations.
This tool deliberately has no world-writing entry point.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import survey_r52_original_complex as survey
from query_blocks import AIR,iter_block_entities
from plan_r53_old_well_enclosure import envelopes,escapes,LO,HI
from model_r53_facility import export,save_json


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,required=True)
    args=ap.parse_args();base=args.base;world=base/'CANDIDATE'
    out=base/'old-well-shell-preview';out.mkdir(exist_ok=True)
    core,_,sources=envelopes(base.parent/'map_complete_20261013')
    survey.WORLD=world;before,palette=survey.measure(LO,HI)
    after=before.copy();wanted=np.zeros_like(core);protected=np.zeros_like(core)
    yy,zz,xx=np.ogrid[LO[1]:HI[1]+1,LO[2]:HI[2]+1,LO[0]:HI[0]+1]
    for left,right in ((-29,5),(13,47),(55,89)):
        inside=(xx>=left)&(xx<=right)&(zz>=-54)&(zz<=5)&(yy>=-466)&(yy<=-380)
        walls=((xx==left)|(xx==right)|(zz==-54)|(zz==5))
        ringroof=(yy==-380)&~core
        wanted|=inside&(walls|ringroof)
    # Compact lift: the original cabin occupies x91..95, including its full
    # south landing/call/display area x90..98. x89 is its measured exterior.
    protected|=np.broadcast_to((xx>=90)&(zz>=-56)&(zz<=-44),core.shape)
    protected|=np.broadcast_to(zz<=-55,core.shape)
    tags=dict(iter_block_entities(world,survey.DIM,LO,HI))
    for p in tags:
        x,y,z=np.asarray(p)-LO;protected[y,z,x]=True
    declared=set()
    def retain(value):
        if isinstance(value,dict):
            if 'position' in value and isinstance(value['position'],list) and len(value['position'])==3:declared.add(tuple(value['position']))
            for child in value.values():retain(child)
        elif isinstance(value,list):
            for child in value:retain(child)
    for name in ('ROOT_MECHANICAL_OWNER.json','ROOT_RUNTIME_DIRECTORY.json'):
        retain(json.loads((world/name).read_text('utf8')))
    for p in declared:
        if all(LO[k]<=p[k]<=HI[k] for k in range(3)):
            x,y,z=np.asarray(p)-LO;protected[y,z,x]=True
    conflicts=np.argwhere(wanted&core)
    assert not len(conflicts),'Chosen outer wall intersects actual padded machinery'
    air=np.isin(before,[i for i,s in enumerate(palette) if s in AIR])
    mask=wanted&air&~protected
    for state in ('projectseele:nerv_shaft_panel','projectseele:nerv_structural_panel','projectseele:nerv_machine_edge'):
        if state not in palette:palette.append(state)
    after[mask]=palette.index('projectseele:nerv_shaft_panel')
    ribs=np.broadcast_to((yy%12==0)|np.isin(xx,[-29,5,13,47,55,89]),core.shape)
    after[mask&ribs]=palette.index('projectseele:nerv_structural_panel')
    after[mask&(yy==-380)]=palette.index('projectseele:nerv_machine_edge')
    before_cases=escapes(before,palette,core);after_cases=escapes(after,palette,core)
    # Ground-bearing readback is separate from horizontal sealing. Missing
    # bearing is a hold for further architecture, never permission to fill.
    bottom=wanted[-466-LO[1]];foundation=before[-467-LO[1]]
    foundation_air=np.isin(foundation,[i for i,s in enumerate(palette) if s in AIR])
    ungrounded=np.argwhere(bottom&foundation_air)
    expected_openings={(13,-9),(13,-8),(55,-9),(55,-8)}
    assert {(int(x+LO[0]),int(z+LO[2])) for z,x in ungrounded}==expected_openings
    spans=[]
    for x in (13,55):
        for z in (-10,-7):
            for y in (-467,-468,-469):
                assert palette[int(before[y-LO[1],z-LO[2],x-LO[0]])]=='projectseele:nerv_shaft_panel'
        for z in (-9,-8):
            for y in (-467,-468):assert palette[int(before[y-LO[1],z-LO[2],x-LO[0]])] in AIR
            assert palette[int(before[-469-LO[1],z-LO[2],x-LO[0]])]=='projectseele:nerv_shaft_panel'
            assert palette[int(after[-466-LO[1],z-LO[2],x-LO[0]])]=='projectseele:nerv_structural_panel'
        spans.append(dict(x=x,beam_y=-466,span_z=[-9,-8],bearing_z=[-10,-7],original_two_high_opening_preserved=True))
    survey.WORLD=base/'WORLD';frozen,frozen_names=survey.measure(LO,HI)
    frozen_cases=escapes(frozen,frozen_names,core)
    lookup=np.asarray([palette.index(s) if s in palette else 65535 for s in frozen_names],np.uint16)
    assert np.array_equal(lookup[frozen][mask],before[mask]),'Changed cells must still equal original delivered R53'
    report=dict(world_written=False,source_world=str(world),new_cells=int(mask.sum()),existing_cells_removed=0,
                before_leaking_slices=sum(r['horizontal_escape'] for r in before_cases),
                after_leaking_slices=sum(r['horizontal_escape'] for r in after_cases),
                remaining_open_slices=[r for r in after_cases if r['horizontal_escape']],
                foundation_air_cells=[[int(x+LO[0]),-467,int(z+LO[2])] for z,x in ungrounded],
                original_frozen_leaking_slices=sum(r['horizontal_escape'] for r in frozen_cases),
                all_changed_cells_equal_original_delivered_save=True,retained_base_opening_spans=spans,
                mechanical_core_conflicts=0,native_lift_and_declared_cells_protected=True,
                pending=['Complete outer shell/native fixture review','Native motion and actual visual review'])
    save_json(out/'REVIEW.json',report)
    np.savez_compressed(out/'PREVIEW.npz',origin=LO,palette=palette,before=before,after=after,positive_edit_mask=mask,core=core)
    export(after,palette,LO,HI,out,'three_retained_wells')
    print(json.dumps({k:report[k] for k in ('world_written','new_cells','before_leaking_slices','after_leaking_slices')}))
    print('Foundation air cells:',len(ungrounded))


if __name__=='__main__':main()
