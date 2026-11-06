import tempfile
import unittest
from pathlib import Path
import numpy as np
from map_pipeline.launch_protection import LaunchProtection


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

    def test_vertical_extent_cannot_wrap(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)/'r.0.0.npz'
            np.savez(p, coordinates=[[0, 0]], ranges=[0, 1], indices=[-1], before=[0], after=[1])
            with self.assertRaisesRegex(ValueError, 'vertical extent'):
                LaunchProtection([]).assert_delta(p)


if __name__ == '__main__':
    unittest.main()
