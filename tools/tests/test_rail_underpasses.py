import unittest
from map_pipeline.rail_underpasses import editable_underpass_column,allowed_roof_infill_column,physical_deck_ceilings


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

    def test_soffit_infill_preserves_existing_bridge_and_track_clearance(self):
        class Source:
            def state(self,x,y,z,original=False):
                if original:return {5:'minecraft:stone_bricks',6:'minecraft:stone'}.get(y,'minecraft:air')
                return 'minecraft:light_gray_concrete'
        # Lowest rail floor is 8 (guard starts at -22), upper guard 15.
        mask=allowed_roof_infill_column(Source(),0,0,-22,15,[[-1,4,-1,1,9,1]])
        self.assertTrue(mask[4+22])
        self.assertFalse(mask[5+22])
        self.assertFalse(mask[6+22])
        self.assertFalse(mask[8+22])

    def test_soffit_exception_cannot_remove_soil(self):
        class Source:
            def state(self,x,y,z,original=False):return 'minecraft:stone'if original else'minecraft:air'
        self.assertFalse(allowed_roof_infill_column(Source(),0,0,-22,15,[[-1,4,-1,1,5,1]]).any())

    def test_lower_rail_limits_multilevel_infill(self):
        class Source:
            def state(self,x,y,z,original=False):return 'minecraft:air'if original else'minecraft:light_gray_concrete'
        mask=allowed_roof_infill_column(Source(),0,0,-23,30,[[-1,5,-1,1,12,1]])
        self.assertTrue(mask[5+23])
        self.assertFalse(mask[6+23])

    def test_actual_track_footprint_distinguishes_lateral_portal(self):
        limits=physical_deck_ceilings([dict(points=[[-10.5,8.5,.5],[10.5,8.5,.5]])],[-1,-1,1,8])
        self.assertEqual(limits[0,0],5)
        self.assertEqual(limits[0,4],5)
        self.assertEqual(limits[0,8],319)

    def test_crossing_lower_track_controls_soffit(self):
        limits=physical_deck_ceilings([dict(points=[[-10.5,20.5,.5],[10.5,20.5,.5]]),
                                      dict(points=[[.5,8.5,-10.5],[.5,8.5,10.5]])],[0,0,0,0])
        self.assertEqual(limits[0,0],5)


if __name__ == '__main__':
    unittest.main()
