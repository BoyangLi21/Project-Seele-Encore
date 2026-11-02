import unittest
import numpy as np
from prepare_hakone_south_shore import joint_street_grades


class ShoreGradingTest(unittest.TestCase):
    def test_flat_plot_and_cross_section_preserve_fixed_quay(self):
        heights=np.full((17,25),218,np.int16);developed=np.zeros_like(heights,bool)
        developed[6:11,:]=True;fixed=np.zeros_like(developed);fixed[6:11,:3]=True;heights[fixed]=200
        plots=[np.s_[5:12,17:22]];developed[plots[0]]=True
        sections=[{(z,x)for z in range(6,11)}for x in range(25)]
        grade,_=joint_street_grades(heights,developed,fixed,sections,plots)
        self.assertTrue(np.array_equal(grade[fixed],heights[fixed]))
        self.assertEqual(np.ptp(grade[plots[0]]),0)
        self.assertEqual(int(grade[plots[0]][0,0])%2,0)
        self.assertTrue(all(np.ptp([grade[z,x]for z,x in s])<=1 for s in sections))
        for axis in(0,1):
            both=np.take(developed,range(1,developed.shape[axis]),axis)&np.take(developed,range(developed.shape[axis]-1),axis)
            self.assertTrue(np.all(abs(np.diff(grade,axis=axis))[both]<=1))

    def test_infeasible_fixed_levels_are_rejected(self):
        heights=np.full((5,5),200,np.int16);fixed=np.zeros_like(heights,bool)
        fixed[2,1]=fixed[2,3]=True;heights[2,3]=208
        with self.assertRaisesRegex(ValueError,'Public plot levels'):
            joint_street_grades(heights,np.ones_like(fixed),fixed,[])

    def test_terrain_bounds_raise_flexible_plot(self):
        heights=np.full((9,15),200,np.int16);developed=np.ones_like(heights,bool)
        lower=np.full_like(heights,190);lower[3:6,10:13]=210
        grade,_=joint_street_grades(heights,developed,np.zeros_like(developed),[],[np.s_[3:6,10:13]],minimum=lower)
        self.assertTrue(np.all(grade>=lower));self.assertEqual(int(grade[4,11]),210)


if __name__=='__main__':unittest.main()
