import tempfile
import unittest
from pathlib import Path
import numpy as np
from map_pipeline.launch_protection import LaunchProtection, airshaft_volume


class LaunchProtectionTest(unittest.TestCase):
    def test_inclined_route_cell_blocks_air_fill(self):
        guard = LaunchProtection([('incline', [-1152, 32, -1536, -1121, 63, -1505])])
        with self.assertRaisesRegex(ValueError, 'EVA launch protection'):
            guard.assert_positions([(-1137, 54, -1510)])
        # This is a finite volume: ground below/above and outside remains
        # editable, unlike the old entire-column terrain mask.
        guard.assert_positions([(-1137, 31, -1510), (-1137, 64, -1510), (-1120, 54, -1510)])

    def test_negative_chunk_delta_hits_native_support(self):
        guard = LaunchProtection([('support', [-17, 80, -1, -17, 80, -1])])
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)/'r.-1.-1.npz'
            offset = (80+128)*256+15*16+15
            np.savez(p, coordinates=[[-2, -1]], ranges=[0, 1], indices=[offset], before=[0], after=[1])
            with self.assertRaisesRegex(ValueError, 'support'):
                guard.assert_delta(p)

    def test_air_shaft_is_guarded_over_its_whole_flight_height(self):
        hatch = dict(opening_x=164, opening_z=164)
        gates = [dict(frame=dict(position=[-1120, 68.01, -720]), silo_hatch=hatch),
                 dict(frame=dict(position=[-1120, -89.99, -720]), silo_hatch=hatch)]
        # Between the gates only: the volume that let terrain close the shaft under its lower gate.
        self.assertEqual(airshaft_volume(gates, []), [-1204, -93, -804, -1036, 72, -636])
        shafts = [dict(motion='AIRCRAFT', occupancy=['space/c-33_-11_-21', 'space/c-38_9_-25']),
                  dict(motion='GROUND_MECHANICAL', occupancy=['space/c0_-16_0', 'space/c0_12_0'])]
        box = airshaft_volume(gates, shafts)
        self.assertEqual(box, [-1204, -352, -804, -1036, 319, -636])
        guard = LaunchProtection([('retained-airshaft', box)])
        for y in (-300, -110, 0, 200):
            with self.assertRaisesRegex(ValueError, 'retained-airshaft'):
                guard.assert_positions([(-1120, y, -720)])
        # Ground beside the shaft wall stays editable.
        guard.assert_positions([(-1206, 20, -720), (-1120, 20, -634)])
        self.assertIsNone(airshaft_volume([], shafts))

    def test_vertical_extent_cannot_wrap(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)/'r.0.0.npz'
            np.savez(p, coordinates=[[0, 0]], ranges=[0, 1], indices=[-1], before=[0], after=[1])
            with self.assertRaisesRegex(ValueError, 'vertical extent'):
                LaunchProtection([]).assert_delta(p)


if __name__ == '__main__':
    unittest.main()
