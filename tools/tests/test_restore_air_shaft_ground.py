import unittest
import numpy as np
from restore_air_shaft_ground import BOX, PAD, plan


def columns(x0, x1, z0, z1):
    return slice(z0 - BOX[2], z1 - BOX[2] + 1), slice(x0 - BOX[0], x1 - BOX[0] + 1)


class RestoreAirShaftGroundTest(unittest.TestCase):
    def setUp(self):
        shape = BOX[3] - BOX[2] + 1, BOX[1] - BOX[0] + 1
        self.before = np.full(shape, 30.0)
        self.before[:, :200] = 44.0                        # a rise in the west
        self.now = self.before.copy()
        self.now[columns(-1300, -1000, -850, -600)] = -100.0     # the pit, wider than the pad
        self.now[columns(-900, -880, -500, -480)] = 0.0          # another hollow, not joined to it

    def test_only_the_ground_joined_to_the_shaft_returns(self):
        wanted, dug = plan(self.before, self.now, 26)
        self.assertTrue(dug[columns(-1300, -1000, -850, -600)].all())
        self.assertFalse(dug[columns(-900, -880, -500, -480)].any())
        self.assertFalse(dug[columns(-1400, -1310, -1000, -900)].any())

    def test_the_pad_is_level_and_passes_into_the_earlier_ground(self):
        wanted, dug = plan(self.before, self.now, 26)
        self.assertTrue((wanted[columns(PAD[0], PAD[1], PAD[2], PAD[3])] == 26).all())
        row = wanted[-720 - BOX[2]]
        east = row[PAD[1] - BOX[0]:PAD[1] - BOX[0] + 80]
        self.assertTrue((np.diff(east) >= 0).all())
        self.assertEqual(east[0], 26)
        self.assertEqual(east[64], 30)
        self.assertEqual(wanted[-720 - BOX[2], 100], 44)

    def test_ground_standing_above_the_pad_is_cut_to_it(self):
        self.now[columns(PAD[0], PAD[0] + 20, PAD[2], PAD[3])] = 60.0
        wanted, dug = plan(self.before, self.now, 26)
        self.assertTrue(dug[columns(PAD[0], PAD[0] + 20, PAD[2], PAD[3])].all())
        self.assertTrue((wanted[columns(PAD[0], PAD[0] + 20, PAD[2], PAD[3])] == 26).all())

    def test_a_pit_running_out_of_the_box_stops_the_tool(self):
        self.now[columns(-1300, BOX[1], -730, -710)] = -100.0
        with self.assertRaises(SystemExit):
            plan(self.before, self.now, 26)

    def test_restored_ground_is_found_again_as_the_pad_alone(self):
        wanted, dug = plan(self.before, self.now, 26)
        again = np.where(dug, wanted, self.now)
        wanted2, dug2 = plan(self.before, again, 26)
        self.assertTrue(np.allclose(np.where(dug2, wanted2, again), again))


if __name__ == '__main__':
    unittest.main()
