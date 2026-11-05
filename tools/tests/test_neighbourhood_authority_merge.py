"""Regression: independently staged districts must not erase each other."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
from publish_hakone_neighbourhood_authority import merge_network


def network():
    d={k:np.zeros((16,16),bool)for k in('road','walk','marking','tunnel','plots')}
    d.update(bounds=np.array([0,-16,15,-1]),grade2=np.full((16,16),128,np.int16),
             ground=np.full((16,16),64,np.int16),old_ground=np.full((16,16),64,np.int16))
    return d


class IndependentDistrictMerge(unittest.TestCase):
    def test_unedited_and_roof_only_paths_survive_but_removed_floor_retires(self):
        with tempfile.TemporaryDirectory()as temp:
            p=Path(temp);(p/'source').mkdir();(p/'delta').mkdir()
            names=np.array(['minecraft:air','minecraft:smooth_stone','minecraft:grass_block[snowy=false]','minecraft:stone'])
            blocks=np.zeros((1,448,16,16),np.uint16)
            blocks[0,192,:,:]=2
            blocks[0,192,3,1]=1
            # Stale source has grass at paths added by another candidate.
            edits=[(75,2,1,0,3),(64,3,1,1,2),(64,4,1,2,1)]
            np.savez(p/'source/r.0.-1.npz',coordinates=[[0,-1]],blocks=blocks,palette=names)
            np.savez(p/'delta/r.0.-1.npz',coordinates=[[0,-1]],ranges=[0,len(edits)],
                indices=np.array([(y+128)*256+z*16+x for y,z,x,b,a in edits],np.uint32),
                before=[b for y,z,x,b,a in edits],after=[a for y,z,x,b,a in edits],palette=names)
            g=network();d=network()
            for j in(1,2,3):g['road'][j,1]=g['walk'][j,1]=True
            d['ground'][:]=d['old_ground'][:]=63  # older captured measurement
            d['old_ground'][3,1]=64
            d['road'][4,1]=d['walk'][4,1]=True
            d['grade2'][4,1]=130
            retired,ground=merge_network(g,d,p)
            self.assertEqual(retired,1)
            self.assertEqual(ground,2)
            self.assertTrue(g['walk'][1,1])
            self.assertTrue(g['walk'][2,1])
            self.assertFalse(g['walk'][3,1])
            self.assertTrue(g['walk'][4,1])
            self.assertEqual(g['ground'][1,1],64)
            self.assertEqual(g['ground'][2,1],64)
            self.assertEqual(g['ground'][3,1],63)
            self.assertEqual(g['grade2'][4,1],130)
            self.assertEqual(g['ground'][0,0],64)

    def test_out_of_frame_source_is_rejected(self):
        g=network();d=network();d['bounds'][0]=-16
        with self.assertRaisesRegex(ValueError,'exceeds current planning authority'):
            merge_network(g,d,Path('unused'))


if __name__=='__main__':unittest.main()
