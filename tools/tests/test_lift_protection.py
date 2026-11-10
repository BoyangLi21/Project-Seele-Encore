import unittest
from map_pipeline.lift_protection import cage_anchor


class LiftProtectionTest(unittest.TestCase):
    def test_main_lift_cage_sits_in_front_of_its_controller(self):
        # Controller (-368, 750) faces east; the 15 x 15 cage measured in the world is x -367..-353, z 743..757.
        self.assertEqual(cage_anchor(-368, 750, 'east', 15, 15, 0, 0), (-367, 743))

    def test_other_facings_follow_moving_elevators(self):
        self.assertEqual(cage_anchor(0, 0, 'south', 5, 5, 0, 0), (-2, 1))
        self.assertEqual(cage_anchor(0, 0, 'north', 5, 5, 0, 0), (-2, -5))
        self.assertEqual(cage_anchor(0, 0, 'west', 5, 5, 0, 0), (-5, -2))


if __name__ == '__main__':
    unittest.main()
