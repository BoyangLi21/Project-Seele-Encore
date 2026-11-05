import unittest
import numpy as np
from prepare_hakone_network_recipes import dry_field_changes

class DryCoastalFieldTests(unittest.TestCase):
    def test_dry_potential_sea_datum_can_follow_a_raised_street(self):
        old=np.array([-80,-90,100],np.int16)*16;water=np.array([-82,-82,-32768],np.int16)
        result,changed=dry_field_changes(old,water,np.array([-80,-90,100]),np.array([-79,-89,101]),np.ones(3,bool))
        np.testing.assert_array_equal(result,np.array([-79,-90,101])*16)
        np.testing.assert_array_equal(changed,[True,False,True])
        np.testing.assert_array_equal(water,[-82,-82,-32768])

    def test_wet_saved_bed_and_new_below_datum_excavation_are_not_flooded(self):
        old=np.array([-80,-80,-80],np.int16)*16;water=np.full(3,-82,np.int16)
        result,changed=dry_field_changes(old,water,np.array([-80,-84,-80]),np.array([-84,-81,-79]),np.array([True,True,False]))
        np.testing.assert_array_equal(result,old);self.assertFalse(changed.any())

if __name__=='__main__':unittest.main()
