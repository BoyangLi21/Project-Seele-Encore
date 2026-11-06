import tempfile,unittest
from pathlib import Path
import numpy as np
from map_pipeline.retained_public import load_guard,verify


class RetainedPublicTest(unittest.TestCase):
    def test_half_slab_road_guards_bearing_and_tree_clearance_at_its_own_height(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'plan').mkdir()
            np.savez_compressed(p/'plan/retained-public.npz',bounds=[10,20,11,20],
                walk=np.array([[True,False]]),road=np.array([[True,False]]),grade2=np.array([[117,0]]))
            guard=load_guard(p)
            self.assertTrue(guard((10,57,20)))
            self.assertTrue(guard((10,63,20)))
            self.assertFalse(guard((10,64,20)))
            self.assertFalse(guard((11,59,20)))
            self.assertFalse(guard((9,59,20)))

    def test_verifier_finds_adjacent_floor_loss_and_low_tree_leaf(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'plan').mkdir()
            np.savez_compressed(p/'plan/retained-public.npz',bounds=[978,818,979,818],
                walk=np.array([[True,True]]),road=np.array([[True,True]]),grade2=np.array([[114,114]]))
            class Saved:
                def state(self,x,y,z,original=False):
                    state='minecraft:stone' if y<57 else 'minecraft:black_concrete' if y==57 else 'minecraft:air'
                    if not original and (x,y)==(978,57):return 'minecraft:air'
                    if not original and (x,y)==(979,61):return 'minecraft:oak_leaves'
                    return state
            report=verify(p,Saved())
            self.assertEqual(report['cells'],14)
            self.assertEqual([q[1:] for q in report['errors']],[[978,57,818],[979,61,818]])


if __name__=='__main__':unittest.main()
