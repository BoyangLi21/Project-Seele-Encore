import unittest
from map_pipeline.rail_underpasses import editable_underpass_column


class CapturedColumn:
    def __init__(self, states):
        self.states = states

    def state(self, x, y, z, original=False):
        assert original
        return self.states.get(y, 'minecraft:air')


class UnderpassTests(unittest.TestCase):
    def test_foundations_survive_below_clearance(self):
        source = CapturedColumn({63: 'minecraft:gray_concrete', 64: 'minecraft:stone',
                                 65: 'minecraft:iron_bars', 66: 'minecraft:light_gray_concrete'})
        mask = editable_underpass_column(source, 1084, 422, 61, 101, [[1064, 32, 410, 1110, 84, 444]], False, 0)
        self.assertTrue(mask[64-61])
        for y in (63, 65, 66):
            self.assertFalse(mask[y-61])
        self.assertFalse(mask[85-61])

    def test_only_declared_surface_can_be_rebuilt(self):
        source = CapturedColumn({64: 'minecraft:white_concrete', 65: 'minecraft:white_concrete', 66: 'minecraft:white_concrete'})
        mask = editable_underpass_column(source, 1084, 422, 61, 101, [[1064, 32, 410, 1110, 84, 444]], True, 130)
        self.assertTrue(mask[65-61])
        self.assertFalse(mask[64-61])
        self.assertFalse(mask[66-61])

    def test_road_shape_mismatch_is_retained(self):
        source = CapturedColumn({66: 'minecraft:smooth_stone'})
        mask = editable_underpass_column(source, 1084, 422, 61, 101, [[1064, 32, 410, 1110, 84, 444]], True, 131)
        self.assertFalse(mask[66-61])

    def test_track_envelope_cannot_be_exempted(self):
        with self.assertRaises(ValueError):
            editable_underpass_column(CapturedColumn({}), 1084, 422, 61, 101, [[1064, 32, 410, 1110, 95, 444]], False, 0)


if __name__ == '__main__':
    unittest.main()
