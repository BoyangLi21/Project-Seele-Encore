import unittest
from map_pipeline.entrance_infill import validated_apron_infill


class Source:
    def __init__(self,state='minecraft:air'):self.material=state
    def state(self,*p,original=False):
        assert original
        return self.material


class InfillTests(unittest.TestCase):
    def check(self,pos=(2,1,0),state='minecraft:air',trains=(),shift=(0,0,0)):
        row=dict(id='station',door=[0,2,0],approach=[3,2,0],site=dict(floor=1),
                 occupied_bounds=[-2,0,-2,0,5,2],translation=list(shift))
        return validated_apron_infill(Source(state),dict(protected_apron_infill=[dict(parcel='station',positions=[pos])]),
                                      [row],dict(trains=list(trains)))

    def test_single_missing_exterior_floor_is_admitted(self):
        self.assertEqual(self.check(),{(2,1,0):'minecraft:smooth_stone'})

    def test_interior_and_wrong_floor_are_rejected(self):
        for p in [(0,1,0),(2,2,0)]:
            with self.assertRaises(ValueError):self.check(pos=p)

    def test_existing_structural_block_is_never_replaced(self):
        with self.assertRaises(ValueError):self.check(state='minecraft:stone_bricks')

    def test_running_track_footprint_is_rejected(self):
        with self.assertRaises(ValueError):self.check(trains=[dict(points=[[2.5,3,.5],[2.5,3,10.5]])])

    def test_moved_parcel_does_not_inherit_infill_exception(self):
        with self.assertRaises(ValueError):self.check(shift=(1,0,0))


if __name__=='__main__':unittest.main()
