import unittest
import numpy as np
from prepare_hakone_geographic_boundary import desired_band,measured,NO_WATER

class NaturalBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.names=['minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:gravel','minecraft:water[level=0]','minecraft:chest[facing=north,type=single,waterlogged=false]']
        self.codes=list(range(6));self.v=np.zeros((448,16,16),np.uint16)
        self.v[:38]=1;self.v[38:41]=2;self.v[41]=3
        self.g=np.full((16,16),-87,np.int16);self.w=np.full((16,16),NO_WATER,np.int16);self.guard=np.zeros_like(self.v,bool)

    def test_negative_datum_underwater_and_dry_join(self):
        target=self.g.copy();target[:,:8]=-91;target[:,8:]=-79
        level=np.where(target<-82,-82,NO_WATER)
        out,active=desired_band(self.v,self.names,self.g,self.w,target,level,self.guard,self.codes)
        g,w,_=measured(out,self.names)
        self.assertTrue(np.array_equal(g,target));self.assertTrue(np.array_equal(w,level))
        self.assertTrue(np.array_equal(out[:34],self.v[:34]));self.assertTrue(active.all())

    def test_buried_device_or_launch_volume_blocks_regrade(self):
        target=self.g+4
        self.v[43,4,5]=6
        with self.assertRaisesRegex(ValueError,'retained construction'):desired_band(self.v,self.names,self.g,self.w,target,self.w,self.guard,self.codes)
        self.v[43,4,5]=0;self.guard[43,4,5]=True
        with self.assertRaisesRegex(ValueError,'launch volume'):desired_band(self.v,self.names,self.g,self.w,target,self.w,self.guard,self.codes)

    def test_missing_or_changed_baseline_is_not_guessed(self):
        self.v[41,3,2]=0
        with self.assertRaisesRegex(ValueError,'previous runtime'):desired_band(self.v,self.names,self.g,self.w,self.g+3,self.w,self.guard,self.codes)

if __name__=='__main__':unittest.main()
