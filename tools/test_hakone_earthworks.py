"""Regression examples for the reported road mesas and buried building plots."""
import unittest
import numpy as np
from hakone_earthworks import min_slope_envelope,grade_ground,grade_development,edge_defects,road_blocks


class EarthworksTests(unittest.TestCase):
    def test_road_half_steps_rise_monotonically_across_zero(self):
        floor,slab=road_blocks(np.arange(-5,8))
        top=floor+np.where(slab,.5,1)
        np.testing.assert_array_equal(np.diff(top),np.full(12,.5))

    def test_fixed_platforms_are_never_lowered_to_hide_a_conflict(self):
        target=np.zeros((9,9));fixed=np.zeros((9,9),bool)
        fixed[4,4]=fixed[4,5]=True;target[4,5]=20
        with self.assertRaises(ValueError):grade_development(target,np.ones((9,9),bool),[],fixed)

    def test_whole_plot_remains_on_full_blocks_beside_half_step_roads(self):
        target=np.full((40,40),17);developed=np.zeros((40,40),bool)
        area=np.s_[15:25,15:25];developed[area]=True;developed[:,10]=True
        fixed=np.zeros((40,40),bool);fixed[:,0]=True;target[:,0]=6
        result=grade_development(target,developed,[area],fixed,slope=2,plot_quantum=2)
        self.assertEqual(np.ptp(result[area]),0)
        self.assertFalse((result[area]%2).any())
        _,conflict=grade_ground(target//2,developed|fixed,result//2)
        self.assertFalse(conflict.any())

    def test_envelope_matches_all_seed_distances(self):
        values=np.full((7,9),np.inf,np.float32)
        seeds=[(0,1,18),(3,7,-2),(6,4,9)]
        for z,x,y in seeds:values[z,x]=y
        for slope in(.5,1,2):
            actual=min_slope_envelope(values,slope)
            expected=np.array([[min(y+slope*(abs(Z-z)+abs(X-x))for z,x,y in seeds)
                                for X in range(9)]for Z in range(7)])
            np.testing.assert_allclose(actual,expected)

    def test_high_road_gets_full_embankment(self):
        soil=np.full((101,101),80,np.int16);mask=np.zeros_like(soil,bool)
        mask[:,49:52]=True;heights=soil.copy();heights[mask]=110
        before=soil.copy();before[mask]=110
        self.assertTrue(edge_defects(before,mask))
        after,conflicts=grade_ground(soil,mask,heights)
        self.assertFalse(conflicts.any());self.assertFalse(edge_defects(after,mask))
        self.assertEqual(after[50,48],109)
        self.assertEqual(after[50,10],80)

    def test_entire_hillside_plot_is_clear(self):
        z,x=np.mgrid[:81,:81];soil=(80+x//2).astype(np.int16)
        mask=np.zeros_like(soil,bool);mask[30:51,30:51]=True
        height=soil.copy();height[mask]=87
        after,conflict=grade_ground(soil,mask,height)
        self.assertFalse(conflict.any())
        self.assertTrue(np.all(after[mask]==87))
        self.assertLessEqual(int(after[35,51]),88)
        self.assertFalse(edge_defects(after,mask))

    def test_flat_plot_and_adjacent_roads_are_solved_together(self):
        t=np.full((100,100),80,np.int16);developed=np.zeros_like(t,bool)
        developed[15:85,20:23]=True;developed[15:85,45:48]=True
        t[15:85,45:48]=120
        area=np.s_[40:60,25:44];developed[area]=True;t[area]=115
        fixed=np.zeros_like(t,bool);fixed[:,0]=True
        coupled=grade_development(t,developed,[area],fixed)
        self.assertEqual(np.ptp(coupled[area]),0)
        soil,conflicts=grade_ground(t,developed,coupled)
        self.assertFalse(conflicts.any());self.assertFalse(edge_defects(soil,developed))
        np.testing.assert_array_equal(coupled[fixed],t[fixed])

    def test_contradictory_existing_objects_are_reported(self):
        t=np.zeros((9,9),np.int16);mask=np.zeros_like(t,bool)
        mask[4,3]=mask[4,4]=True;t[4,4]=30
        _,conflicts=grade_ground(t,mask,t)
        self.assertTrue(conflicts[mask].all())


if __name__=='__main__':unittest.main()
