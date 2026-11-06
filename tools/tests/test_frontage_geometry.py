import unittest
from map_pipeline.frontage_geometry import entrance_frame


class EntranceGeometryTests(unittest.TestCase):
    def test_offset_door_leaf_does_not_create_diagonal_porches(self):
        cases=[([9,1,20],[10,1,23],(10,20,0,1)),
               ([20,1,9],[17,1,10],(20,10,-1,0)),
               ([11,1,20],[10,1,17],(10,20,0,-1)),
               ([20,1,11],[23,1,10],(20,10,1,0))]
        for door,approach,want in cases:
            with self.subTest(door=door):
                self.assertEqual(entrance_frame(dict(door=door,approach=approach)),want)

    def test_unknown_diagonal_doorway_requires_geometry_review(self):
        with self.assertRaises(ValueError):
            entrance_frame(dict(id='unknown',door=[0,1,0],approach=[2,1,2]))
