"""Undo the added side rooms, retaining the existing personnel gallery lights."""
from pathlib import Path
import argparse,numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
from prepare_continuous_upright_civil_r52 import cuboids

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',required=True,type=Path);p.add_argument('--world',type=Path);a=p.parse_args()
    world=a.world or a.base/'CANDIDATE'
    with np.load(a.base/'launch-inspection-proposal/PROPOSAL.npz') as d:
        lo=tuple(map(int,d['origin']));before=d['before'];installed=d['after'];names=d['palette'].tolist();mask=d['positive_edit_mask'].copy()
    mask[:,:,:max(0,-46-lo[0])]=False
    hi=(lo[0]+before.shape[2]-1,lo[1]+before.shape[0]-1,lo[2]+before.shape[1]-1)
    survey.WORLD=world;current,states=survey.measure(lo,hi)
    for state in states:
        if state not in names:names.append(state)
    lookup=np.asarray([names.index(s) for s in states],np.uint16);current=lookup[current]
    assert np.array_equal(current[mask],installed[mask]),'Side room source changed'
    after=current.copy();after[mask]=before[mask]
    vox.WORLD=world;vox.DIM=survey.DIM;vox.OUT=a.base/'retired-side-inspection-rooms'/world.name
    painter=vox.Painter(vertical_bounds=(-1440,320));cuboids(painter,lo,current,after,names,'retire_added_side_rooms')
    painter.meta.update(retained_existing_personnel_gallery=True,retained_gallery_lighting=True,changed_cells=int(mask.sum()))
    assert not list((vox.OUT/'retire_added_side_rooms').glob('applied_*'));painter.apply('retire_added_side_rooms')
    actual,states=survey.measure(lo,hi);assert np.array_equal(np.asarray(states)[actual],np.asarray(names)[after])
    print('Removed side rooms; retained original gallery and lighting; full readback passed',int(mask.sum()))

if __name__=='__main__':main()
