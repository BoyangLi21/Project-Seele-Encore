import unittest
import numpy as np
from plan_hakone_open_river_profile import fit_connected_water

class RiverProfileTests(unittest.TestCase):
    def check_drainage(self,wet,values,parents,outlets,grade):
        h,w=wet.shape
        for j,i in np.argwhere(wet):
            seen=set();p=int(j*w+i)
            while not outlets[divmod(p,w)]:
                self.assertNotIn(p,seen);seen.add(p);q=int(parents[divmod(p,w)]);self.assertGreaterEqual(q,0)
                self.assertLessEqual(values[divmod(q,w)],values[divmod(p,w)]+1e-8);p=q
            for J,I in((j-1,i),(j+1,i),(j,i-1),(j,i+1)):
                if 0<=J<h and 0<=I<w and wet[J,I]:self.assertLessEqual(abs(values[j,i]-values[J,I]),grade+1e-8)

    def test_sink_has_contained_downstream_spill_route(self):
        wet=np.ones((3,241),bool);g=np.tile(np.linspace(-81,-69,241),(3,1));g[:,110:150]-=3
        outlets=np.zeros_like(wet);outlets[:,0]=True
        values,parent=fit_connected_water(wet,g,outlets,-82,.05)
        self.assertTrue(np.all(values[outlets]==-82));self.check_drainage(wet,values,parent,outlets,.05)

    def test_tributaries_keep_different_measured_profiles(self):
        wet=np.zeros((161,241),bool);wet[80,:]=True;wet[:,80]=True
        g=np.full(wet.shape,-80.);g[80,:]=np.linspace(-81,-70,241);g[:80,80]=np.linspace(-68,-77,80);g[81:,80]=np.linspace(-77,-76,80)
        outlets=np.zeros_like(wet);outlets[80,0]=True
        values,parent=fit_connected_water(wet,g,outlets,-82,.1)
        self.assertGreater(values[0,80],values[-1,80]+1);self.check_drainage(wet,values,parent,outlets,.1)

    def test_disconnected_water_is_not_a_river(self):
        wet=np.zeros((4,4),bool);wet[0,:]=True;wet[3,3]=True;outlets=np.zeros_like(wet);outlets[0,0]=True
        with self.assertRaises(ValueError):fit_connected_water(wet,np.zeros((4,4)),outlets,-2,.05)

if __name__=='__main__':unittest.main()
